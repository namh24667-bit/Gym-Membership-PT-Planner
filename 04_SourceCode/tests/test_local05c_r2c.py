from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from app import create_app, db
from app.class_eligibility_sql import target_definition


class EligibilityMigrationTests(unittest.TestCase):
    def test_read_scope_preserves_full_legacy_definition_and_is_reversible(self):
        text = (Path(__file__).resolve().parents[1] / 'ops/portable/schema.sql').read_text(encoding='utf-8')
        legacy = next(batch.strip() for batch in re.split(r'(?m)^GO[ \t]*$', text)
                      if batch.strip().startswith('CREATE PROCEDURE dbo.local03_schedule '))
        upgraded = target_definition(legacy)
        self.assertIsNone(target_definition(upgraded))
        self.assertEqual(target_definition(upgraded, undo=True), legacy.replace('CREATE', 'ALTER', 1))
        self.assertIsNone(target_definition(legacy, undo=True))
        with self.assertRaises(ValueError):
            target_definition(legacy.replace('TOP (150)', 'TOP (42)'))


class ClassEligibilityTests(unittest.TestCase):
    address = 'https://localhost'
    csrf = 'synthetic-csrf'

    def setUp(self):
        app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                              LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True,
                              LOCAL03_ENABLED=True))
        self.client = app.test_client()
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='synthetic-session', csrf_token=self.csrf)
        self.enterContext(patch('app.session_store.session_owner', return_value=42))
        self.actor = self.enterContext(patch.object(db, 'get_principal', return_value=db.Principal(42, 'Hội viên', ('member',))))
        self.workflow = self.enterContext(patch.object(db, 'workflow'))

    def fixture(self, reason='eligible', state='open', history=None, left=2):
        return (9, 'Thể lực', 'Fitness', 'HLV Demo', 'Phòng nhóm',
                datetime(2026, 11, 27, 11), datetime(2026, 11, 27, 12),
                4, 2, 2, history, 10 if history else 0, state, reason, left)

    def get(self, path):
        return self.client.get(path, base_url=self.address)

    def book(self, token=None):
        return self.client.post('/member/classes/9/book?week=2026-W48',
                                data={'csrf_token': self.csrf if token is None else token, 'last_booking': '0'},
                                base_url=self.address)

    def test_one_read_for_list_and_detail_and_only_eligible_gets_a_form(self):
        self.workflow.return_value = [self.fixture(), self.fixture('full', 'full')]
        content = self.get('/member/classes').get_data(as_text=True)
        self.assertEqual(content.count('/book?week=2026-W48'), 1)
        self.assertIn('Còn 2 lượt lớp nhóm', content)
        self.assertIn('Xem chi tiết', content)
        self.workflow.assert_called_once_with('schedule', 42, 'class_eligibility', None, many=True, group='local03')
        self.workflow.reset_mock()
        self.workflow.return_value = [self.fixture(history='CANCEL', left=-1)]
        detail = self.get('/member/classes/9?week=2026-W48').get_data(as_text=True)
        self.assertIn('Đặt lại', detail)
        self.assertIn('Quota lớp nhóm không giới hạn', detail)
        self.workflow.assert_called_once_with('schedule', 42, 'class_eligibility', 9, many=True, group='local03')

    def test_blocked_reasons_are_visible_and_actions_link_to_existing_features(self):
        expected = {
            'no_benefit': 'không bao gồm quyền lợi lớp nhóm', 'quota': 'hết lượt',
            'expired': 'đã hết hạn', 'pending_payment': 'thanh toán hợp đồng',
            'pending_activation': 'kích hoạt gói', 'future': 'chưa đến ngày hiệu lực',
            'no_contract': 'chưa có hợp đồng phù hợp', 'outside_dates': 'ngoài thời hạn',
            'full': 'đủ số lượng', 'ended': 'đã kết thúc', 'in_progress': 'đã bắt đầu',
            'closed': 'chưa khả dụng', 'conflict': 'trùng thời gian', 'booked': 'đã đăng ký',
            'benefit_unknown': 'cần được kiểm tra lại',
        }
        for reason, label in expected.items():
            with self.subTest(reason=reason):
                self.workflow.return_value = [self.fixture(reason, left=0 if reason == 'quota' else None)]
                page = self.get('/member/classes/9').get_data(as_text=True)
                self.assertIn(label, page)
                self.assertNotIn('/member/classes/9/book', page)
                if reason == 'no_benefit':
                    self.assertIn('/member/plans?benefit=group', page)
                if reason in ('conflict', 'booked'):
                    self.assertIn('/member/schedule', page)

    def test_stale_post_retains_409_and_uses_fresh_read_and_week(self):
        self.workflow.side_effect = [db.WorkflowRejected(52209), [self.fixture('full', 'full')]]
        result = self.book()
        self.assertEqual(result.status_code, 409)
        text = result.get_data(as_text=True)
        self.assertIn('Lớp nhóm đã hết chỗ', text)
        self.assertIn('/member/classes?week=2026-W48', text)
        self.assertNotIn('/member/classes/9/book', text)
        self.assertEqual([item.args[:3] for item in self.workflow.call_args_list],
                         [('book_group', 42, 9), ('schedule', 42, 'class_eligibility')])

    def test_wrong_role_and_invalid_csrf_are_rejected_before_sql(self):
        self.assertEqual(self.book('invalid').status_code, 400)
        self.actor.return_value = db.Principal(42, 'Nhân viên', ('staff',))
        self.assertEqual(self.get('/member/classes/9').status_code, 403)
        self.assertEqual(self.book().status_code, 403)
        self.workflow.assert_not_called()

    def test_filter_reuses_sale_catalog_and_includes_only_positive_group_benefits(self):
        def row(key, label, quota):
            return (key, label, 1, Decimal('100.00'), None, 'Lớp nhóm', quota)

        self.workflow.return_value = [row(1, 'Có quota', 1), row(2, 'Quota bằng không', 0),
                                      row(3, 'Chưa xác định', None), row(4, 'Không giới hạn hợp lệ', -1)]
        text = self.get('/member/plans?benefit=group').get_data(as_text=True)
        self.assertIn('Có quota', text)
        self.assertIn('Không giới hạn hợp lệ', text)
        self.assertNotIn('Quota bằng không', text)
        self.assertNotIn('Chưa xác định', text)
        self.workflow.assert_called_once_with('catalog', None, many=True)

    def test_old_portable_database_shows_preflight_unavailable_without_lying(self):
        row = self.fixture()
        self.workflow.side_effect = [db.WorkflowRejected(52201), [(*row[:12], True)]]
        result = self.get('/member/classes')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'data-eligibility="unchecked"', result.data)
