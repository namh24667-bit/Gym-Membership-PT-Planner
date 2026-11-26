"""Verify login, scoped pages and logout against the local HTTP(S) listener."""
from http.cookiejar import CookieJar
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, HTTPCookieProcessor, HTTPSHandler, ProxyHandler, Request

from common import SetupError
from seed import ACCOUNTS, email
from clean_seed import ACCOUNTS as CLEAN_ACCOUNTS


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, address, tls=None):
        self.address = address
        self.opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls),
                                   HTTPCookieProcessor(CookieJar()), NoRedirect())

    def request(self, path, fields=None):
        request = Request(self.address + path, data=urlencode(fields).encode() if fields is not None else None)
        try:
            response = self.opener.open(request, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers.get('Location')

    def post(self, path, page, **fields):
        form = re.search(rb'name="csrf_token" value="([^"]+)"', page)
        if not form:
            raise SetupError('Thiếu trường CSRF trên trang kiểm tra.')
        return self.request(path, {'csrf_token': form[1].decode(), **fields})


def verify_accounts(address, password, tls=None):
    if isinstance(password, dict):
        if password.keys() != CLEAN_ACCOUNTS.keys():
            raise SetupError('Bộ tài khoản CleanDemo không đúng cấu hình.')
        rows = [(row['email'], row['name'], 'management' if tag == 'manager' else tag.split('-')[0],
                 row['password']) for tag, row in password.items()]
    else:
        rows = [(email(tag), name, role, password) for tag, name, role in ACCOUNTS]
    for login, name, role, secret in rows:
        client = Client(address, tls)
        status, login_page, _ = client.request('/login')
        if status != 200:
            raise SetupError(f'HTTP preflight /login trả {status}.')
        status, _, _ = client.post('/login', login_page, email=login, password=secret)
        if status != 302:
            raise SetupError(f'HTTP preflight không đăng nhập được vai trò {role}.')
        status, profile, _ = client.request('/profile')
        if status != 200 or name.encode() not in profile or login.encode() not in profile:
            raise SetupError(f'HTTP preflight hồ sơ sai phạm vi ({role}).')
        if client.request(f'/{role}')[0] != 200 or (role != 'management' and client.request('/management')[0] != 403):
            raise SetupError(f'HTTP preflight phân quyền không đạt ({role}).')
        if client.post('/logout', profile)[0] != 302 or client.request('/profile')[0] != 403:
            raise SetupError('HTTP preflight đăng xuất không đạt.')
