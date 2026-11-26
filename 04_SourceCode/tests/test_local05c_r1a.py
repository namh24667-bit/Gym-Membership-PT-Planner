from datetime import date
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from flask import g

from app import create_app, db


class PersonalProfileTests(TestCase):
    def setUp(self):
        self.app = create_app(dict(TESTING=True, AUTH_ENABLED=True, LOCAL_QA=True, LOCALR1A_ENABLED=True,
                                   SQL_DATABASE=db.QA_DATABASE, SECRET_KEY='r1a-' * 10))
        self.client = self.app.test_client()
        self.url = 'https://localhost/profile'
        self.row = SimpleNamespace(person_id=7, full_name='Nguyễn <b>Thảo</b> Linh',
                                   email='demo@example.invalid', phone='0900000000',
                                   date_of_birth=date(1990, 2, 3), gender='FEMALE', address=None,
                                   join_date=None, position=None, staff_hire=None, staff_status=None,
                                   trainer_hire=None, trainer_status=None, membership_id=None,
                                   plan_name=None, start_date=None, end_date=None)

    def test_anonymous_cannot_read(self):
        with patch.object(db, 'personal_profile') as sql:
            self.assertEqual(self.client.get(self.url).status_code, 403)
            sql.assert_not_called()

    def test_profile_reads_only_authenticated_person_for_all_roles(self):
        for roles, label in ((('member',), 'Hội viên'), (('staff',), 'Nhân viên'),
                             (('trainer',), 'Huấn luyện viên'), (('staff', 'management'), 'Quản lý'),
                             (('member', 'trainer', 'staff', 'management'), 'Quản lý')):
            with self.subTest(roles=roles), patch('app.auth.load_principal',
                      side_effect=lambda: setattr(g, 'principal', db.Principal(7, 'Nguyễn Thảo Linh', roles))), \
                    patch.object(db, 'personal_profile', return_value=self.row) as sql:
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(label.encode(), response.data)
                self.assertIn(b'demo@example.invalid', response.data)
                self.assertIn('Nguyễn &lt;b&gt;Thảo&lt;/b&gt; Linh'.encode(), response.data)
                self.assertNotIn(b'<b>Th', response.data)
                sql.assert_called_once_with(7)

    def test_client_cannot_select_profile_or_write_fields(self):
        with patch('app.auth.load_principal', side_effect=lambda: setattr(
                g, 'principal', db.Principal(7, 'Hội viên', ('member',)))), patch.object(db, 'personal_profile') as sql:
            self.assertEqual(self.client.get(self.url + '?person_id=8').status_code, 400)
            self.assertEqual(self.client.get(self.url + '/8').status_code, 404)
            for method in ('POST', 'PATCH', 'PUT', 'DELETE'):
                self.assertEqual(self.client.open(self.url, method=method,
                    data={'person_id': '8', 'role': 'management', 'quota': '99', 'csrf_token': 'fake'}).status_code, 405)
            sql.assert_not_called()

    def test_trainer_uses_only_own_assignment_scope(self):
        self.app.config['LOCAL03_ENABLED'] = True
        soon = datetime.now() + timedelta(hours=2)
        assigned = [(8, 'GROUP', soon, soon + timedelta(hours=1), 'Phòng tập nhóm', 'Thể lực toàn thân',
                     None, None, None, 'ACTIVE', 1, 4)]
        with patch('app.auth.load_principal', side_effect=lambda: setattr(
                g, 'principal', db.Principal(7, 'Huấn luyện viên', ('trainer',)))), \
                patch.object(db, 'personal_profile', return_value=self.row), \
                patch('app.schedule.read', return_value=assigned) as read:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Thể lực toàn thân'.encode(), response.data)
        self.assertIn(b'href="/trainer/schedule/8"', response.data)
        self.assertNotIn(b'/staff/payments', response.data)
        read.assert_called_once_with(7, 'trainer')
