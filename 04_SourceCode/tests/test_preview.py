import os
import socket
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit
from unittest.mock import patch

from app import create_app
from app.preview import DETAILS, MENUS
from app.preview_data import DATA


class PreviewMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.buttons = []
        self.forms = []
        self.ids = set()
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a":
            self.links.append(attrs["href"])
        elif tag == "form":
            self.forms.append(attrs)
        elif tag == "button":
            self.buttons.append(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])


class PreviewTests(unittest.TestCase):
    def setUp(self):
        connection = patch.object(socket.socket, "connect", side_effect=AssertionError("Preview opened a connection"))
        connection.start()
        self.addCleanup(connection.stop)
        self.client = create_app({"TESTING": True, "PREVIEW_ENABLED": True}).test_client()

    def preview_paths(self):
        yield "/preview/"
        for role in MENUS:
            yield f"/preview/{role}"
            for group in (role, "staff") if role == "management" else (role,):
                for page, _, _ in MENUS[group]:
                    yield f"/preview/{role}/{page}"
                for page, (_, _, collection) in DETAILS.get(group, {}).items():
                    if collection:
                        for key in DATA[collection]:
                            yield f"/preview/{role}/{page}/{key}"
                    else:
                        yield f"/preview/{role}/{page}"

    def test_every_screen_and_fixture_renders_read_only(self):
        for path in self.preview_paths():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn("Set-Cookie", response.headers)
                html = response.get_data(as_text=True)
                self.assertIn("BẢN XEM TRƯỚC — DỮ LIỆU MINH HỌA", html)
                markup = PreviewMarkup(html)
                self.assertEqual(markup.forms, [])
                for button in markup.buttons:
                    self.assertIn("disabled", button)
                    self.assertEqual(button.get("type"), "button")
                self.assertEqual(self.client.post(path).status_code, 405)

    def test_all_menu_actions_filters_and_anchors_have_valid_targets(self):
        targets = set()
        for path in self.preview_paths():
            markup = PreviewMarkup(self.client.get(path).get_data(as_text=True))
            for url in markup.links:
                if url.startswith("#"):
                    self.assertIn(url[1:], markup.ids)
                else:
                    targets.add(url)
        for target in targets:
            with self.subTest(target=target):
                url = urlsplit(target)
                self.assertFalse(url.netloc)
                response = self.client.get(url.path + ("?" + url.query if url.query else ""))
                self.assertEqual(response.status_code, 200)
                if url.fragment:
                    self.assertIn(url.fragment, PreviewMarkup(response.get_data(as_text=True)).ids)

    def test_preview_config_loopback_and_no_forwarding(self):
        with patch.dict(os.environ, {"IRONPULSE_PREVIEW": "0"}):
            disabled = create_app({"TESTING": True}).test_client()
        self.assertEqual(disabled.get("/preview/member").status_code, 404)
        self.assertNotIn(b"/preview/member", disabled.get("/login").data)
        with patch.dict(os.environ, {"IRONPULSE_PREVIEW": "1"}):
            enabled = create_app({"TESTING": True}).test_client()
        self.assertEqual(enabled.get("/preview/member", base_url="http://127.0.0.1:5055").status_code, 200)
        for options in (
            {"base_url": "https://example.invalid"},
            {"environ_overrides": {"REMOTE_ADDR": "192.0.2.2"}},
            {"headers": {"X-Forwarded-For": "192.0.2.2"}},
        ):
            with self.subTest(options=options):
                self.assertEqual(enabled.get("/preview/member", **options).status_code, 404)

    def test_invalid_roles_records_and_real_private_routes(self):
        for path in ("/preview/admin", "/preview/member/unknown", "/preview/member/membership/invalid",
                     "/preview/member/memberships/IP-104", "/preview/trainer/pt-detail"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        for role in MENUS:
            for method in ("GET", "POST"):
                response = self.client.open(f"/{role}/restricted?preview=1", method=method)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("Set-Cookie", response.headers)

    def test_fixture_quota_filters_and_sensitive_fields(self):
        active = self.client.get("/preview/member/membership/IP-104").get_data(as_text=True)
        self.assertIn("<td>Lớp nhóm</td><td>12 lượt</td><td>2</td>", active)
        self.assertIn("Không giới hạn", active)
        self.assertIn("1.290.000 ₫", active)
        pending = self.client.get("/preview/member/membership/IP-108").get_data(as_text=True)
        self.assertIn("Gói này chưa có biên lai.", pending)
        contracts = self.client.get("/preview/staff/contracts?status=ACTIVE").get_data(as_text=True)
        self.assertIn("IP-104", contracts)
        self.assertNotIn("IP-108", contracts)
        schedule = self.client.get("/preview/trainer/schedule?type=GROUP").get_data(as_text=True)
        self.assertIn("Morning Flow", schedule)
        self.assertNotIn("PT sức mạnh", schedule)
        details = self.client.get("/preview/trainer/class-detail/yoga").get_data(as_text=True)
        self.assertIn("<td>Ẩn</td><td>Ẩn</td>", details)
        self.assertNotIn("@example.invalid", details)
