from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

from app import create_app, db


class AdministrationRouteTests(unittest.TestCase):
    address = 'https://localhost'

    def setUp(self):
        self.app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='test-admin-session-key-only-123456',
                                   LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True,
                                   LOCAL03_ENABLED=True, LOCAL04_ENABLED=True))
        self.client = self.app.test_client()
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='synthetic-auth', csrf_token='synthetic-csrf')
        self.addCleanup(patch.stopall)
        patch('app.session_store.session_owner', return_value=19).start()
        self.principal = patch.object(db, 'get_principal').start()
        self.sql = patch.object(db, 'workflow').start()

    def role(self, *roles):
        self.principal.return_value = db.Principal(19, 'Nhân sự kiểm thử', roles)

    def test_role_guard_runs_before_sql_and_cannot_be_overridden_by_parameters(self):
        for roles in (('member',), ('trainer',), ('staff',)):
            self.role(*roles)
            with self.subTest(roles=roles):
                response = self.client.get('/management/reports?role=management&actor=1', base_url=self.address)
                self.assertEqual(response.status_code, 403)
        self.sql.assert_not_called()

    def test_reversed_dates_stop_before_report(self):
        self.role('staff', 'management')
        response = self.client.get('/management/reports?from=2026-12-01&to=2026-11-30', base_url=self.address)
        self.assertEqual(response.status_code, 400)
        self.sql.assert_not_called()

    def test_staff_contract_detail_reads_correct_member_benefits(self):
        self.role('staff')
        today = date.today()
        contract = [(41, 82, 'Hội viên kiểm thử', 'Gói kiểm thử', 'ACTIVE', today, today+timedelta(days=30),
                     Decimal('3300.00'), Decimal('3300.00'), None, None, None, None, 1)]
        self.sql.side_effect = [contract, [(41, 'Lớp nhóm', 2, 1)]]
        response = self.client.get('/staff/contracts/41', base_url=self.address)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Lớp nhóm'.encode(), response.data)
        self.assertIn(b'<td>1</td>', response.data)
        self.sql.assert_called_with('members', 19, 'benefits', 82, '41', many=True, group='local04')

    def test_unexpected_member_update_fields_never_reach_sql(self):
        self.role('staff')
        response = self.client.post('/staff/member-directory/82', base_url=self.address,
                                    data={'csrf_token': 'synthetic-csrf', 'role': 'management', 'quota': '99'})
        self.assertEqual(response.status_code, 400)
        self.sql.assert_not_called()
