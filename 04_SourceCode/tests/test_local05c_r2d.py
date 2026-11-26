from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
from unittest import TestCase
from unittest.mock import patch

from app import create_app, db
from app.class_eligibility_sql import target_definition as r2c
from app.staff_directory_sql import target_definition as r2d


class StaffDirectoryTests(TestCase):
    address = 'https://localhost'
    start = datetime(2026, 11, 27, 15)

    def setUp(self):
        self.app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                                   LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True,
                                   LOCAL03_ENABLED=True, LOCAL04_ENABLED=True))
        self.client = self.app.test_client()
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='synthetic-session', csrf_token='test-csrf')
        self.enterContext(patch('app.session_store.session_owner', return_value=42))
        self.actor = self.enterContext(patch.object(db, 'get_principal', return_value=db.Principal(42, 'Nhân viên', ('staff',))))
        self.sql = self.enterContext(patch.object(db, 'workflow'))

    def get(self, path):
        return self.client.get(path, base_url=self.address)

    def test_trainer_filter_page_and_total_use_sql(self):
        self.sql.return_value = [(12, 73, 'Nguyễn Demo', 'ACTIVE', 'Fitness', 3, self.start, 'GROUP', 'Lớp thử')]
        response = self.get('/staff/trainers?q=%2373&status=ACTIVE&page=2')
        self.assertEqual(response.status_code, 200)
        self.assertIn('12 kết quả · Trang 2/2'.encode(), response.data)
        self.assertIn(b'q=%2373&amp;status=ACTIVE&amp;page=1', response.data)
        self.sql.assert_called_once_with('schedule', 42, 'desk_trainers', None, '#73', 'ACTIVE',
                                         None, None, None, 10, many=True, group='local03')

    def test_trainer_detail_keeps_only_public_work_fields_and_bounded_dates(self):
        self.sql.side_effect = [[(1, 73, 'Nguyễn Demo', 'ACTIVE', 'Fitness', None, None, None, None)],
                                [(1, 26, 'PERSONAL', self.start, self.start.replace(hour=16), 'Phòng PT', None)]]
        response = self.get('/staff/trainers/73?from=2026-11-25&to=2026-11-28&kind=PERSONAL')
        self.assertEqual(response.status_code, 200)
        for label in ('Fitness', 'Thông tin làm việc', 'Phòng PT'):
            self.assertIn(label.encode(), response.data)
        for field in ('name="email"', 'name="phone"', 'password_hash', 'method="post" action="/staff'):
            self.assertNotIn(field.encode(), response.data)
        self.assertEqual(len(self.sql.call_args_list), 2)
        self.assertEqual(self.sql.call_args.args[3:6], (73, None, 'PERSONAL'))

    def test_classes_filter_before_page_and_show_empty_and_detail_with_correct_seats(self):
        row = (1, 17, 'Lớp A', 'Fitness', 73, 'Nguyễn Demo', 'Phòng A',
               self.start, self.start.replace(hour=16), 10, 9, 1, 'open')
        self.sql.side_effect = [[(73, 'Nguyễn Demo')], [row], [row], [(73, 'Nguyễn Demo')], [(0,) + (None,)*12]]
        self.assertEqual(self.get('/staff/classes?trainer=73&status=open').status_code, 200)
        self.assertEqual(self.sql.call_args_list[1].args[5:9], ('open', None, None, 73))
        detail = self.get('/staff/classes/17')
        self.assertIn('9 học viên'.encode(), detail.data)
        self.assertIn('1 chỗ'.encode(), detail.data)
        self.assertIn(b'/staff/plan-catalog?benefit=group', detail.data)
        self.assertIn('Không tìm thấy lớp nhóm'.encode(), self.get('/staff/classes?q=none').data)

    def test_denies_other_roles_and_write_methods_without_sql(self):
        for roles in (('trainer',), ('member',), ('management',)):
            self.actor.return_value = db.Principal(42, 'Demo', roles)
            for route in ('/staff/trainers', '/staff/trainers/73', '/staff/classes', '/staff/classes/17'):
                self.assertEqual(self.get(route).status_code, 403)
        self.actor.return_value = db.Principal(42, 'Demo', ('staff',))
        for route in ('/staff/trainers/73', '/staff/classes/17'):
            self.assertEqual(self.client.post(route, base_url=self.address).status_code, 405)
        self.sql.assert_not_called()

    def test_staff_plan_advice_reuses_sold_only_catalog_and_group_filter(self):
        self.sql.return_value = [(1, 'Gói phù hợp', 1, Decimal('100'), None, 'Lớp nhóm', 2),
                                 (2, 'Hết quota', 1, Decimal('100'), None, 'Lớp nhóm', 0)]
        page = self.get('/staff/plan-catalog?benefit=group')
        self.assertIn('Gói phù hợp'.encode(), page.data)
        self.assertNotIn('Hết quota'.encode(), page.data)
        self.assertIn(b'href="/staff/classes"', page.data)
        self.sql.assert_called_once_with('catalog', None, many=True)


class DirectoryUpgradeTests(TestCase):
    def test_preserves_legacy_and_r2c_scope_on_rollback(self):
        file = Path(__file__).resolve().parents[1] / 'ops/portable/schema.sql'
        legacy = next(batch.strip() for batch in re.split(r'(?m)^GO[ \t]*$', file.read_text(encoding='utf-8'))
                      if batch.strip().startswith('CREATE PROCEDURE dbo.local03_schedule '))
        current = r2c(legacy)
        upgraded = r2d(current)
        self.assertIsNone(r2d(upgraded))
        self.assertEqual(r2d(upgraded, undo=True), current)
        with self.assertRaises(ValueError):
            r2d(legacy)
