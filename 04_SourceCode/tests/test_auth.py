import re
import secrets
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pyodbc

from app import auth, create_app, db


HTTPS = 'https://localhost'
MEMBER = db.Principal(10, 'Hội viên kiểm thử', ('member',))
TRAINER = db.Principal(20, 'HLV kiểm thử', ('trainer',))
CSRF_INPUT = re.compile(rb'name="csrf_token" value="([^"]+)"')
COOKIE = 'ironpulse_session'


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.password_hash = auth.HASHER.hash(cls.password)

    def setUp(self):
        state = TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state_path = Path(state.name) / 'auth.sqlite3'
        self.app = create_app({'TESTING': True, 'AUTH_ENABLED': True, 'SECRET_KEY': secrets.token_hex(32),
                               'AUTH_STATE_PATH': self.state_path, 'PREVIEW_ENABLED': True})
        self.client = self.app.test_client()
        self.account = self.mock(db, 'find_account', return_value=(MEMBER, self.password_hash))
        self.identity = self.mock(db, 'get_principal', return_value=MEMBER)
        self.memberships = self.mock(db, 'list_memberships', return_value=[(1, 'Gói của hội viên')])
        self.trainer_schedule = self.mock(db, 'list_trainer_sessions', return_value=[(7, '18:30')])

    def mock(self, obj, name, **kwargs):
        mock = patch.object(obj, name, **kwargs)
        self.addCleanup(mock.stop)
        return mock.start()

    def get(self, path, client=None):
        return (client or self.client).get(path, base_url=HTTPS)

    def post(self, path, data, client=None):
        return (client or self.client).post(path, base_url=HTTPS, data=data)

    def signin(self, password=None, **extra):
        token = CSRF_INPUT.search(self.get('/login').data)[1].decode()
        return self.post('/login', {'email': 'test@example.invalid', 'csrf_token': token,
                                    'password': self.password if password is None else password, **extra})

    def test_successful_login_rotates_csrf_and_session(self):
        token = CSRF_INPUT.search(self.get('/login').data)[1]
        preauth = self.client.get_cookie(COOKIE).value
        response = self.signin(role='management')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/member')
        for flag in ('HttpOnly', 'Secure', 'SameSite=Lax'):
            self.assertIn(flag, response.headers['Set-Cookie'])
        self.assertNotEqual(self.client.get_cookie(COOKIE).value, preauth)
        html = self.get('/member').data
        self.assertNotEqual(CSRF_INPUT.search(html)[1], token)
        self.assertIn(b'href="/member/membership/1"', html)
        self.assertNotIn(b'href="/management"', html)
        self.assertTrue(self.state_path.is_file())
        prior_client = self.app.test_client()
        prior_client.set_cookie(COOKIE, preauth)
        self.assertEqual(self.get('/member', prior_client).status_code, 403)
        with self.client.session_transaction(base_url=HTTPS) as cookie_data:
            self.assertEqual(set(cookie_data), {'_permanent', 'csrf_token', 'auth_token'})

    def test_wrong_password_and_missing_or_invalid_account_are_generic(self):
        denied = self.signin('incorrect')
        self.assertEqual(denied.status_code, 401)
        for row in [(None, None), (MEMBER, 'legacy plaintext'), (db.Principal(10, 'Không vai trò', ()), self.password_hash)]:
            self.account.return_value = row
            response = self.signin()
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data, denied.data)
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self.get('/member').status_code, 403)

    def test_csrf_and_https(self):
        for token in ('', 'wrong', '🧪'):
            response = self.post('/login', {'email': 'test@example.invalid', 'csrf_token': token})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/login').status_code, 403)
        self.assertNotIn('Set-Cookie', self.client.get('/login').headers)
        self.account.assert_not_called()
        self.signin()
        self.assertEqual(self.get('/logout').status_code, 405)
        self.assertEqual(self.post('/logout', {'csrf_token': 'wrong'}).status_code, 400)
        self.assertEqual(self.get('/member').status_code, 200)

    def test_logout_revokes_cookie_replay_even_when_sql_unavailable(self):
        self.signin()
        token = CSRF_INPUT.search(self.get('/member').data)[1].decode()
        stolen = self.app.test_client()
        stolen.set_cookie(COOKIE, self.client.get_cookie(COOKIE).value)
        self.identity.side_effect = db.DatabaseUnavailable
        self.assertEqual(self.post('/logout', {'csrf_token': token}).status_code, 302)
        self.assertEqual(self.get('/member', stolen).status_code, 403)
        self.assertEqual(self.get('/member').status_code, 403)

    def test_expired_session_is_removed_without_loading_identity(self):
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
        with patch('app.session_store.time', return_value=1000):
            self.signin()
            self.assertEqual(self.get('/member').status_code, 200)
        self.identity.reset_mock()
        with patch('app.session_store.time', return_value=1300):
            response = self.get('/member')
        self.assertEqual(response.status_code, 403)
        self.identity.assert_not_called()
        self.assertIsNone(self.client.get_cookie(COOKIE))

    def test_anonymous_and_cross_role_requests_rejected(self):
        for role in ('member', 'trainer', 'staff', 'management'):
            self.assertEqual(self.get('/' + role).status_code, 403)
        self.signin()
        self.assertEqual(self.get('/management?role=management').status_code, 403)
        self.assertEqual(self.post('/member/membership/1', {}).status_code, 405)
        self.assertEqual(self.get('/trainer/session/7').status_code, 403)

    def test_member_detail_is_scoped_to_authenticated_owner(self):
        self.signin()
        lookup = self.mock(db, 'get_membership', side_effect=lambda owner, key:
                           ('Gói của hội viên', 'ACTIVE', None, None) if (owner, key) == (10, 1) else None)
        self.assertEqual(self.get('/member/membership/1').status_code, 200)
        self.assertEqual(self.get('/member/membership/2?person_id=11').status_code, 404)
        self.assertEqual(self.get('/member/membership/2147483648').status_code, 404)
        self.assertEqual([call.args for call in lookup.call_args_list], [(10, 1), (10, 2)])

    def test_trainer_scoped_access_and_role_change_on_next_request(self):
        self.account.return_value = (TRAINER, self.password_hash)
        self.identity.return_value = TRAINER
        self.signin()
        lookup = self.mock(db, 'get_trainer_session', side_effect=lambda owner, key:
                           ('PERSONAL', 'Phòng tập', '18:30', '19:30') if (owner, key) == (20, 7) else None)
        self.assertEqual(self.get('/trainer').status_code, 200)
        self.trainer_schedule.assert_called_once_with(20)
        self.assertEqual(self.get('/trainer/session/7').status_code, 200)
        self.assertEqual(self.get('/trainer/session/8?trainer_id=21').status_code, 404)
        self.assertEqual([call.args for call in lookup.call_args_list], [(20, 7), (20, 8)])
        self.identity.return_value = db.Principal(20, 'Cập nhật quyền', ('member',))
        self.assertEqual(self.get('/trainer/session/7').status_code, 403)
        self.assertEqual(self.get('/member').status_code, 200)

    def test_staff_and_manager_menus_and_backend(self):
        staff = db.Principal(30, 'Nhân viên', ('staff',))
        self.account.return_value = (staff, self.password_hash)
        self.identity.return_value = staff
        self.assertEqual(self.signin().location, '/staff')
        self.assertNotIn(b'href="/management"', self.get('/staff').data)
        self.assertEqual(self.get('/management').status_code, 403)
        self.identity.return_value = db.Principal(30, 'Quản lý', ('staff', 'management'))
        managed = self.get('/management')
        self.assertEqual(managed.status_code, 200)
        self.assertIn(b'href="/staff"', managed.data)
        self.assertEqual(self.post('/management/people', {'role': 'management'}).status_code, 405)

    def test_preview_does_not_load_private_identity_even_with_cookie(self):
        self.signin()
        self.identity.side_effect = AssertionError('Preview read real identity')
        response = self.get('/preview/member')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertNotIn(MEMBER.full_name.encode(), response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_database_error_is_redacted(self):
        self.account.side_effect = db.DatabaseUnavailable('Server=private;password_hash=secret')
        with self.assertLogs(self.app.logger, level='WARNING') as logs:
            response = self.signin()
        self.assertEqual(response.status_code, 503)
        for value in ('Server=private', 'password_hash', 'secret'):
            self.assertNotIn(value, response.get_data(as_text=True))
            self.assertNotIn(value, '\n'.join(logs.output))
        self.assertFalse(self.state_path.exists())


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'SQL_SERVER': r'host\SQLEXPRESS', 'SQL_WINDOWS_LOGIN': r'HOST\svc_ironpulse'})

    def test_sql_parameters_column_scope_and_connection_lifecycle(self):
        with self.app.app_context(), patch.object(pyodbc, 'connect') as connect:
            connection = connect.return_value
            cursor = connection.cursor.return_value
            cursor.execute.return_value = cursor
            cursor.fetchone.side_effect = [('IronPulse', r'HOST\svc_ironpulse', 1), ('Gói', 'ACTIVE', None, None)]
            self.assertEqual(db.get_membership(10, 1), ('Gói', 'ACTIVE', None, None))
            dsn = connect.call_args.args[0]
            for setting in ('Driver={ODBC Driver 18 for SQL Server}', 'Database=IronPulse',
                            'Trusted_Connection=yes', 'Encrypt=Mandatory', 'TrustServerCertificate=no'):
                self.assertIn(setting, dsn)
            self.assertEqual(connect.call_args.kwargs, {'timeout': 5, 'autocommit': True})
            self.assertEqual(connection.timeout, 5)
            statement, owner, key = cursor.execute.call_args.args
            self.assertIn('m.person_id = ?', statement)
            self.assertIn('m.membership_id = ?', statement)
            self.assertEqual((owner, key), (10, 1))
            cursor.close.assert_called_once()
            connection.close.assert_called_once()

    def test_privileged_or_wrong_sql_identity_fails_before_query(self):
        for identity in [('IronPulse', r'HOST\svc_ironpulse', 0), ('IronPulse', r'HOST\Other', 1), ('Different', r'HOST\svc_ironpulse', 1)]:
            with self.subTest(identity=identity), self.app.app_context(), patch.object(pyodbc, 'connect') as connect:
                cursor = connect.return_value.cursor.return_value
                cursor.execute.return_value.fetchone.return_value = identity
                with self.assertRaises(db.DatabaseUnavailable):
                    db.find_account('test@example.invalid')
                cursor.execute.assert_called_once_with(db.CONNECTION_IDENTITY)
                cursor.close.assert_called_once()
                connect.return_value.close.assert_called_once()

    def test_malicious_or_missing_database_server_does_not_connect(self):
        for server in (None, 'host;TrustServerCertificate=yes', 'host}'):
            self.app.config['SQL_SERVER'] = server
            with self.app.app_context(), patch.object(pyodbc, 'connect') as connect:
                with self.assertRaises(db.DatabaseUnavailable):
                    db.get_principal(10)
                connect.assert_not_called()

    def test_role_mapping_and_overlap(self):
        self.assertEqual(db._principal((10, 'Tên', 10, 'ON_LEAVE', 'ACTIVE', 'Quản lý')).roles,
                         ('member', 'trainer', 'staff', 'management'))
        self.assertEqual(db._principal((10, 'Tên', None, 'TERMINATED', 'ON_LEAVE', 'Quản lý')).roles, ())
        self.assertEqual(db._principal((10, 'Tên', 10, 'TERMINATED', 'ACTIVE', 'Lễ tân')).roles, ('member', 'staff'))

    def test_local_qa_odbc_exception_is_scoped_to_the_exact_target(self):
        self.app.config.update(LOCAL_QA=True, SQL_SERVER=db.QA_SERVER,
                               SQL_WINDOWS_LOGIN=db.LOCAL_QA_LOGINS[0], SQL_DATABASE=db.QA_DATABASE)
        with self.app.app_context(), patch.object(pyodbc, 'connect') as connect:
            cursor = connect.return_value.cursor.return_value
            cursor.execute.return_value = cursor
            cursor.fetchone.side_effect = [
                (db.QA_DATABASE, db.LOCAL_QA_LOGINS[0], 1),
                ('MSI', 'SQLEXPRESS', 'unused-in-local-mode', 'Shared memory'),
                None,
            ]
            self.assertIsNone(db.get_principal(42))
            self.assertIn('Encrypt=Mandatory;TrustServerCertificate=yes;', connect.call_args.args[0])
            self.assertEqual(cursor.execute.call_args.args[1:], (42,))
        for key, value in (
            ('SQL_SERVER', r'tcp:MSI\SQLEXPRESS'), ('SQL_SERVER', r'lpc:other\SQLEXPRESS'),
            ('SQL_DATABASE', 'IronPulse'), ('SQL_WINDOWS_LOGIN', r'MSI\Administrator'),
        ):
            with self.subTest(key=key, value=value), self.app.app_context(), patch.dict(self.app.config, {key: value}):
                with patch.object(pyodbc, 'connect') as connect, self.assertRaises(db.DatabaseUnavailable):
                    db.get_principal(42)
                connect.assert_not_called()

    def test_local_qa_web_rejects_remote_and_forwarded_requests(self):
        client = create_app({'LOCAL_QA': True, 'AUTH_ENABLED': False}).test_client()
        self.assertEqual(client.get('/login', base_url=HTTPS).status_code, 200)
        self.assertEqual(client.get('/login', base_url=HTTPS,
                                    environ_overrides={'REMOTE_ADDR': '192.0.2.1'}).status_code, 403)
        self.assertEqual(client.get('/login', base_url='https://example.invalid').status_code, 403)
        for header in ('Forwarded', 'X-Forwarded-For'):
            self.assertEqual(client.get('/login', base_url=HTTPS, headers={header: '127.0.0.1'}).status_code, 403)

    def test_local_odbc_failure_logs_stage_and_codes_without_driver_text(self):
        self.app.config.update(LOCAL_QA=True, SQL_SERVER=db.QA_SERVER,
                               SQL_WINDOWS_LOGIN=db.LOCAL_QA_LOGINS[0], SQL_DATABASE=db.QA_DATABASE)
        error = pyodbc.OperationalError('08001', 'Shared Memory Provider (258); private driver text')
        with self.app.app_context(), patch.object(pyodbc, 'connect', side_effect=error):
            with self.assertLogs(self.app.logger, level='WARNING') as logs, self.assertRaises(db.DatabaseUnavailable):
                db.find_account('test@example.invalid')
        self.assertIn('stage=connect sqlstate=08001 native=258', logs.output[0])
        self.assertNotIn('private driver text', logs.output[0])


if __name__ == '__main__':
    unittest.main()
