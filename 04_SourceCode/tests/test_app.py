import os
import socket
import unittest
from unittest.mock import patch

from app import create_app
from app.navigation import ROLE_MENUS


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.connection = patch.object(socket.socket, "connect", side_effect=AssertionError("UI-01 opened a connection"))
        self.connection.start()
        self.addCleanup(self.connection.stop)
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_factory_and_environment(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-only-value"}):
            app = create_app()
        self.assertEqual(app.secret_key, "test-only-value")
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_login_view_has_disabled_form_and_navigation(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for text in ('name="email"', 'type="password"', '<fieldset disabled', 'Chưa tích hợp', 'href="/register"'):
            self.assertIn(text, page)
        self.assertNotIn("Set-Cookie", response.headers)

    def test_register_view_uses_phase_fields(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        fields = ("full_name", "ssn", "date_of_birth", "gender", "address", "email",
                  "password", "phone", "emergency_contact_phone", "health_notes")
        for field in fields:
            self.assertIn(f'name="{field}"', page)
        for field in ("person_id", "created_at", "join_date", "password_hash"):
            self.assertNotIn(f'name="{field}"', page)
        self.assertIn('<fieldset disabled', page)
        self.assertIn('pattern="[0-9]{12}"', page)
        self.assertIn('Chưa tích hợp', page)

    def test_stylesheets_load(self):
        page = self.client.get("/login").get_data(as_text=True)
        for url in ("/static/site.css", "/static/bootstrap.min.css"):
            with self.subTest(url=url):
                self.assertIn(url, page)
                with self.client.get(url) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.mimetype, "text/css")

    def test_unknown_path_returns_404(self):
        response = self.client.get("/khong-ton-tai")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Không tìm thấy trang", response.get_data(as_text=True))

    def test_disabled_posts_do_not_read_payload_or_create_session(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "test-only-value"})
        client = app.test_client()
        for url in ("/login", "/register"):
            with self.subTest(url=url), patch.object(app.request_class, "form", side_effect=AssertionError("Payload read")):
                response = client.post(url, data={"password": "test-input"})
                self.assertEqual(response.status_code, 503)
                self.assertIn("chưa tích hợp", response.get_data(as_text=True))
                self.assertNotIn("test-input", response.get_data(as_text=True))
                self.assertNotIn("Set-Cookie", response.headers)
        with client.session_transaction() as session:
            self.assertEqual(dict(session), {})

    def test_private_routes_reject_get_and_post(self):
        for role in ROLE_MENUS:
            for path in (f"/{role}", f"/{role}/restricted"):
                for method in ("GET", "POST"):
                    with self.subTest(path=path, method=method):
                        response = self.client.open(path + "?role=management", method=method)
                        self.assertEqual(response.status_code, 403)
                        self.assertIn("chưa có quyền", response.get_data(as_text=True))
                        self.assertNotIn("Set-Cookie", response.headers)
