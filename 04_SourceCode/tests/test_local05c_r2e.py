from datetime import datetime
from pathlib import Path
import re
from unittest import TestCase
from unittest.mock import patch

from app import create_app, db


class TrainerScheduleTests(TestCase):
    origin = 'https://localhost'
    start = datetime(2026, 11, 25, 10)
    end = datetime(2026, 11, 25, 11)

    def setUp(self):
        self.app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                                   LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL03_ENABLED=True))
        self.client = self.app.test_client()
        with self.client.session_transaction(base_url=self.origin) as session:
            session.update(auth_token='trainer-session', csrf_token='csrf-trainer')
        self.enterContext(patch('app.session_store.session_owner', return_value=3))
        self.principal = self.enterContext(patch.object(db, 'get_principal', return_value=db.Principal(3, 'HLV', ('trainer',))))
        self.sql = self.enterContext(patch.object(db, 'workflow'))

    def get(self, path):
        return self.client.get(path, base_url=self.origin)

    def test_agenda_filters_and_paginates_using_authenticated_actor(self):
        self.sql.return_value = [(12, 13, 7, 14, 4, 2, self.start.date(), 'ACTIVE',
                                  42, 'PERSONAL', self.start, self.end, 'Phòng PT', None, 'Hội viên thử',
                                  None, None, None, 'upcoming')]
        response = self.get('/trainer/schedule?week=2026-W48&kind=PERSONAL&status=upcoming&page=2&trainer_id=9')
        self.assertEqual(response.status_code, 200)
        self.assertIn('12 kết quả · Trang 2/2'.encode(), response.data)
        self.assertIn('Hội viên thử'.encode(), response.data)
        self.assertNotIn(b'member_id=', response.data)
        self.sql.assert_called_once_with('schedule', 3, 'teach_agenda', None, 'PERSONAL', 'upcoming',
                                         datetime(2026, 11, 23).date(), datetime(2026, 11, 29).date(), None,
                                         10, many=True, group='local03')

    def test_no_sessions_and_invalid_week(self):
        self.sql.return_value = [(0, 0, 0, 0, 0, 0, self.start.date(), 'ACTIVE') + (None,) * 11]
        self.assertIn('Không có buổi dạy phù hợp'.encode(), self.get('/trainer/schedule').data)
        self.assertEqual(self.get('/trainer/schedule?week=2026-W57').status_code, 400)

    def test_pt_phone_is_from_assigned_sql_row_and_handles_missing_contact(self):
        personal = (42,'PERSONAL',self.start,self.end,'Phòng PT',None,'Hội viên thử',7,
                    'Luyện thăng bằng',None,None,None,'upcoming',None,'ACTIVE')
        self.sql.side_effect = [[personal + ('0900000012',)], [personal + (None,)], [personal + ('javascript:bad',)]]
        response = self.get('/trainer/schedule/42?member_id=99&trainer_id=8')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="tel:0900000012"', response.data)
        self.assertIn('#7'.encode(), response.data)
        for path in ('/trainer/schedule/42', '/trainer/schedule/42'):
            missing = self.get(path)
            self.assertIn('Chưa có số điện thoại khả dụng'.encode(), missing.data)
            for forbidden in (b'mailto:', b'tel:', b'password_hash', b'javascript:bad'):
                self.assertNotIn(forbidden, missing.data)
        self.sql.assert_called_with('schedule', 3, 'teach_detail', 42, many=True, group='local03')

    def test_group_detail_and_roster_keep_booking_semantics_and_no_contact(self):
        group = (18,'GROUP',self.start,self.end,'Studio','Lớp thử',None,None,None,2,1,1,
                 'upcoming','open','ACTIVE',None)
        self.sql.side_effect = [[group], [(1,'Lớp thử',12,'Hội viên thử','SUCCESS')]]
        detail = self.get('/trainer/schedule/18')
        self.assertIn('1 chỗ'.encode(), detail.data)
        self.assertIn(b'/trainer/schedule/18/participants', detail.data)
        roster = self.get('/trainer/schedule/18/participants?trainer_id=999')
        self.assertIn('Đã đăng ký'.encode(), roster.data)
        self.assertIn(b'#12', roster.data)
        self.assertNotIn(b'tel:', roster.data)
        self.assertNotIn(b'mailto:', roster.data)
        self.sql.assert_called_with('schedule', 3, 'teach_roster', 18, None, None, None, None, None, 0,
                                    many=True, group='local03')

    def test_cross_access_and_unauthorized_roles(self):
        self.sql.return_value = []
        for path in ('/trainer/schedule/99', '/trainer/schedule/99/participants'):
            self.assertEqual(self.get(path).status_code, 404)
        self.sql.reset_mock()
        for roles in (('member',), ('staff',), ('staff','management')):
            self.principal.return_value = db.Principal(3, 'demo', roles)
            for path in ('/trainer/schedule', '/trainer/schedule/42', '/trainer/schedule/42/participants'):
                self.assertEqual(self.get(path).status_code, 403)
        self.sql.assert_not_called()

    def test_does_not_accept_write_to_roster_or_reassignment_from_form(self):
        self.assertEqual(self.client.post('/trainer/schedule/42/participants', base_url=self.origin).status_code, 405)
        tamper = dict(csrf_token='csrf-trainer', focus='Mục tiêu', trainer_id='8', member_id='9')
        self.assertEqual(self.client.post('/trainer/schedule/42', data=tamper, base_url=self.origin).status_code, 400)
        self.sql.assert_not_called()


class TrainerScheduleUpgradeTests(TestCase):
    def test_only_new_read_scopes_are_added_and_rollback_restores_r2d(self):
        from app.class_eligibility_sql import target_definition as r2c
        from app.staff_directory_sql import target_definition as r2d
        from app.trainer_schedule_sql import target_definition as r2e
        source = (Path(__file__).resolve().parents[1] / 'ops/portable/schema.sql').read_text(encoding='utf-8')
        legacy = next(batch.strip() for batch in re.split(r'(?m)^GO[ \t]*$', source)
                      if batch.strip().startswith('CREATE PROCEDURE dbo.local03_schedule '))
        staff = r2d(r2c(legacy))
        changed = r2e(staff.replace('ALTER PROCEDURE', 'CREATE PROCEDURE', 1))
        self.assertTrue(changed.startswith('ALTER PROCEDURE'))
        self.assertIsNone(r2e(changed))
        self.assertEqual(r2e(changed, undo=True), staff)
        with self.assertRaises(ValueError):
            r2e(legacy)
