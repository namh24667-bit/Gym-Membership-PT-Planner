from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app, db, membership


class BenefitMappingTests(unittest.TestCase):
    def test_distinguishes_missing_zero_unknown_finite_and_unlimited(self):
        benefits = membership.plan_benefits([
            ('Local-02 · Sử dụng phòng tập', 0), ('PT cá nhân', -1),
            ('Lớp nhóm', None), ('Tủ đồ', 4),
        ])
        self.assertEqual([(item.key, item.state, item.quota) for item in benefits], [
            ('gym', 'empty', 0), ('pt', 'unlimited', -1), ('group', 'unknown', None), ('other', 'finite', 4),
        ])
        self.assertTrue(all(item.state == 'missing' for item in membership.plan_benefits([])))

    def test_duplicate_pt_aliases_match_ambiguous_entitlement_instead_of_adding_limits(self):
        _, pt, _ = membership.plan_benefits([('PT cá nhân', 2), ('Local-02 · Buổi PT', 3)])
        self.assertEqual(pt.state, 'ambiguous')
        self.assertIsNone(pt.quota)
        self.assertEqual(pt.source_names, ('PT cá nhân', 'Local-02 · Buổi PT'))


class CatalogRouteTests(unittest.TestCase):
    address = 'https://localhost'
    active = [(17, 'Gói điện thử', 2, Decimal('349000.25'), 'PT không giới hạn từ quảng cáo cũ',
               'Local-02 · Sử dụng phòng tập', 0),
              (17, 'Gói điện thử', 2, Decimal('349000.25'), None, 'PT cá nhân', 2)]

    def setUp(self):
        app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                              LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True,
                              LOCAL04_ENABLED=True))
        self.client = app.test_client()
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='synthetic-session', csrf_token='synthetic-csrf')
        self.enterContext(patch('app.session_store.session_owner', return_value=42))
        self.actor = self.enterContext(patch.object(db, 'get_principal', return_value=db.Principal(42, 'Demo', ('member',))))
        self.sql = self.enterContext(patch.object(db, 'workflow'))

    def get(self, url):
        return self.client.get(url, base_url=self.address)

    def post(self, url, **fields):
        return self.client.post(url, base_url=self.address, data=fields)

    def test_catalog_and_order_detail_use_sql_and_show_absent_services(self):
        self.sql.return_value = self.active
        for url in ('/member/plans', '/member/plans/17'):
            with self.subTest(url=url):
                page = self.get(url)
                self.assertEqual(page.status_code, 200)
                for phrase in ('349.000,25 ₫', '2 tháng', '0 lượt / chu kỳ', '2 lượt / chu kỳ', 'Không bao gồm'):
                    self.assertIn(phrase.encode(), page.data)
                self.assertNotIn('không giới hạn từ quảng cáo cũ'.encode(), page.data)
        self.assertIn(b'name="amount" value="349000.25"', page.data)

    def test_no_active_plan_explains_empty_catalog_and_stale_purchase_is_rejected(self):
        self.sql.return_value = []
        self.assertIn('Chưa có gói đang mở bán'.encode(), self.get('/member/plans').data)
        self.assertEqual(self.get('/member/plans/17').status_code, 404)
        request_id = str(uuid4())
        self.sql.reset_mock(side_effect=True)
        self.sql.side_effect = [db.WorkflowRejected(52103), []]
        result = self.post('/member/plans/17', csrf_token='synthetic-csrf', request_id=request_id, amount='349000.25')
        self.assertEqual(result.status_code, 404)
        self.assertEqual(self.sql.call_args_list[0].args, ('create_contract', 42, 17, Decimal('349000.25'), request_id))

    def test_advice_reads_catalog_only_and_obeys_role(self):
        self.sql.return_value = self.active
        self.assertEqual(self.get('/staff/plan-catalog').status_code, 403)
        self.sql.assert_not_called()
        self.actor.return_value = db.Principal(42, 'Demo', ('staff',))
        reply = self.get('/staff/plan-catalog')
        self.assertEqual(reply.status_code, 200)
        self.assertNotIn(b'name="request_id"', reply.data)
        self.assertNotIn(b'href="/member/plans/17"', reply.data)
        self.sql.assert_called_once_with('catalog', None, many=True)
        self.assertEqual(self.post('/staff/plan-catalog').status_code, 405)
        self.assertEqual(self.post('/member/plans/17', csrf_token='synthetic-csrf').status_code, 403)

    def test_purchase_csrf_and_forged_quota_never_call_write(self):
        fields = dict(amount='349000.25', request_id=str(uuid4()))
        self.sql.return_value = self.active
        self.assertEqual(self.post('/member/plans/17', csrf_token='invalid', **fields).status_code, 400)
        self.sql.assert_not_called()
        self.assertEqual(self.post('/member/plans/17', csrf_token='synthetic-csrf', quota='-1', **fields).status_code, 400)
        self.sql.assert_called_once_with('catalog', 17, many=True)

    def test_successful_purchase_routes_to_the_contract_returned_by_sql(self):
        self.sql.return_value = (71,)
        request_id = str(uuid4())
        response = self.post('/member/plans/17', csrf_token='synthetic-csrf',
                             request_id=request_id, amount='349000.25')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, '/member/membership/71')
        self.sql.assert_called_once_with('create_contract', 42, 17, Decimal('349000.25'), request_id)

    def test_historic_member_contract_uses_granted_rights_even_when_plan_is_outside_catalog(self):
        today = date.today()
        self.sql.side_effect = [[(71, 42, 'Demo', 'Gói cũ', 'ACTIVE', today, today + timedelta(days=30),
                                 Decimal('50000'), Decimal('80000'), 19, Decimal('50000'),
                                 'CASH', today, 203)], [('PT cá nhân', 2, 1, True)]]
        response = self.get('/member/membership/71')
        self.assertEqual(response.status_code, 200)
        self.assertIn('50.000,00 ₫'.encode(), response.data)
        self.assertIn('Huấn luyện cá nhân (PT)'.encode(), response.data)
        self.assertIn(b'Bi\xc3\xaan lai #19', response.data)
        self.assertEqual([call.args[0] for call in self.sql.call_args_list], ['contracts', 'benefits'])
