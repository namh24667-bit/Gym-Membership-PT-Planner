import re
import unittest
from unittest.mock import patch

from app import create_app, db, membership, schedule


class LocalHttpTests(unittest.TestCase):
    def make_app(self, **settings):
        config = dict(TESTING=True, LOCAL_QA=True, LOCAL_HTTP=True, AUTH_ENABLED=True,
                      SECRET_KEY='test-only-key-for-local-http-tests', SQL_SERVER=db.QA_SERVER,
                      SQL_DATABASE=db.QA_DATABASE, SQL_WINDOWS_LOGIN=db.LOCAL_QA_LOGINS[0])
        return create_app(config | settings)

    def test_http_uses_its_own_cookie_and_state_and_checks_origin(self):
        app = self.make_app()
        https = self.make_app(LOCAL_HTTP=False)
        self.assertNotEqual(app.config['AUTH_STATE_PATH'], https.config['AUTH_STATE_PATH'])
        self.assertEqual(https.config['SESSION_COOKIE_NAME'], 'ironpulse_qa_session')
        self.assertTrue(https.config['SESSION_COOKIE_SECURE'])
        client = app.test_client()
        address = 'http://localhost:5443'
        form = client.get('/login', base_url=address)
        token = re.search(rb'name="csrf_token" value="([^"]+)"', form.data)[1].decode()
        cookie = form.headers['Set-Cookie']
        self.assertTrue(cookie.startswith('ironpulse_qa_http_session='))
        self.assertNotIn('; Secure', cookie)
        self.assertIn('; HttpOnly', cookie)
        self.assertIn('; SameSite=Lax', cookie)
        with patch('app.auth.authenticate', return_value=None) as auth:
            data = dict(csrf_token=token, email='synthetic@example.invalid', password='synthetic')
            self.assertEqual(client.post('/login', base_url=address, data=data,
                                         headers={'Origin': 'http://localhost:8000'}).status_code, 403)
            self.assertEqual(client.post('/login', base_url=address, data=data,
                                         headers={'Origin': address}).status_code, 401)
            auth.assert_called_once()

    def test_http_is_scoped_to_loopback_and_qa(self):
        for overrides in (dict(LOCAL_QA=False), dict(SQL_DATABASE='IronPulse'),
                          dict(SQL_SERVER=r'tcp:MSI\SQLEXPRESS')):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.make_app(**overrides)
        client = self.make_app().test_client()
        self.assertEqual(client.get('/login', base_url='http://localhost:5443',
                                    environ_overrides={'REMOTE_ADDR': '192.0.2.20'}).status_code, 403)
        self.assertEqual(client.get('/login', base_url='http://localhost:5443',
                                    headers={'X-Forwarded-Proto': 'https'}).status_code, 403)


class ScheduleValidationTests(unittest.TestCase):
    def test_local_naive_time_and_positive_interval(self):
        form = dict(trainer='42', room='5', start='2026-11-26T10:00', end='2026-11-26T11:00')
        trainer, room, start, end = schedule.slot(form)
        self.assertEqual((trainer, room, start.hour, end.hour, start.tzinfo), (42, 5, 10, 11, None))
        for fields in ({'start': form['end']}, {'end': '2026-11-26T11:00+07:00'},
                       {'trainer': '2147483648'}, {'room': '0'}):
            with self.subTest(fields=fields), self.assertRaises(membership.InvalidForm):
                schedule.slot(form | fields)

    def test_member_cannot_inject_person_or_quota(self):
        app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                              LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL03_ENABLED=True))
        client = app.test_client()
        addr = 'https://localhost'
        with client.session_transaction(base_url=addr) as session:
            session.update(auth_token='synthetic-token', csrf_token='synthetic-csrf')
        with (patch('app.session_store.session_owner', return_value=42),
              patch.object(db, 'get_principal', return_value=db.Principal(42, 'Demo', ('member',))),
              patch.object(db, 'workflow', return_value=(8,)) as sql):
            form = dict(csrf_token='synthetic-csrf', last_booking='0')
            self.assertEqual(client.post('/member/classes/3/book', data=form | {'person_id': '8', 'quota': '99'},
                                         base_url=addr).status_code, 400)
            sql.assert_not_called()
            self.assertEqual(client.post('/member/classes/3/book', data=form, base_url=addr).status_code, 303)
            sql.assert_called_once_with('book_group', 42, 3, 0, many=False, group='local03')
