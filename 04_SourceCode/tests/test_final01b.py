from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app import create_app, db


class ClassRulesTests(TestCase):
    address = 'https://localhost'

    def setUp(self):
        app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                              LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL03_ENABLED=True, LOCAL04_ENABLED=True,
                              CLASS_RULES_ENABLED=True))
        self.client = app.test_client()
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='test-token', csrf_token='test-csrf')
        self.enterContext(patch('app.session_store.session_owner', return_value=19))
        self.principal = self.enterContext(patch.object(db, 'get_principal'))
        self.sql = self.enterContext(patch.object(db, 'workflow'))

    def post(self, path, **data):
        return self.client.post(path, base_url=self.address, data={'csrf_token': 'test-csrf', **data})

    def test_staff_cannot_submit_service_missing_from_sql_list(self):
        self.principal.return_value = db.Principal(19, 'Nhân viên', ('staff',))
        self.sql.return_value = [SimpleNamespace(service_type_id=1)]
        response = self.post('/staff/member-directory/82/service', service='7')
        self.assertEqual(response.status_code, 409)
        self.sql.assert_called_once_with('services', 19, 'list', 82, many=True, group='local04')

    def test_staff_can_submit_eligible_incidental_service(self):
        self.principal.return_value = db.Principal(19, 'Nhân viên', ('staff',))
        self.sql.return_value = [SimpleNamespace(service_type_id=1)]
        response = self.post('/staff/member-directory/82/service', service='1')
        self.assertEqual(response.status_code, 303)
        self.sql.assert_called_with('services', 19, 'use', 82, 1, many=False, group='local04')

    def test_manager_cannot_create_or_edit_with_unmapped_category(self):
        self.principal.return_value = db.Principal(19, 'Quản lý', ('staff', 'management'))
        data = dict(trainer='10', room='15', start='2027-06-01T11:00', end='2027-06-01T12:00',
                    name='Lớp kiểm thử', category='UNMAPPED', capacity='8')

        def read_only(proc, actor, scope, *args, **kwargs):
            if scope == 'category':
                return (False,)
            if scope == 'detail':
                return SimpleNamespace(has_history=False)
            self.assertIn(scope, ('trainers', 'rooms'))
            return ()

        self.sql.side_effect = read_only
        for path in ('/management/classes/new', '/management/classes/13'):
            with self.subTest(path=path):
                self.assertEqual(self.post(path, **data).status_code, 400)

    def test_legacy_target_keeps_existing_service_write(self):
        self.principal.return_value = db.Principal(19, 'Nhân viên', ('staff',))
        self.client.application.config['CLASS_RULES_ENABLED'] = False
        self.assertEqual(self.post('/staff/member-directory/82/service', service='7').status_code, 303)
        self.sql.assert_called_once_with('services', 19, 'use', 82, 7, many=False, group='local04')
