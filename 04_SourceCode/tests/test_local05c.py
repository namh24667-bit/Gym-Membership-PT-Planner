from datetime import date, datetime, timedelta
from unittest import TestCase
from unittest.mock import call, patch

from app import create_app, membership, schedule


class ContractPresentationTests(TestCase):
    def test_identifies_future_current_pending_and_expired_contracts(self):
        today = date(2026, 11, 24)
        template = create_app({'TESTING': True}).jinja_env.get_template('local04/ui.html')
        cases = (
            ('ACTIVE', today + timedelta(days=1), 'UPCOMING', 'Chưa đến ngày hiệu lực'),
            ('ACTIVE', today, 'ACTIVE', membership.STATUS['ACTIVE']),
            ('PENDING_PAYMENT', None, 'PENDING_PAYMENT', 'Chờ thanh toán'),
            ('PENDING_ACTIVATION', None, 'PENDING_ACTIVATION', 'Chưa kích hoạt'),
            ('EXPIRED', today - timedelta(days=1), 'EXPIRED', 'Hết hạn'),
        )
        for state, start, marker, label in cases:
            with self.subTest(state=state, start=start):
                html = template.module.contract_badge(state, start, today, membership.STATUS)
                self.assertIn(f'data-state="{marker}"', html)
                self.assertIn(f'>{label}<', html)


class SchedulePresentationTests(TestCase):
    def test_upcoming_only_reads_owned_pt_and_group_schedule(self):
        now = datetime(2026, 11, 24, 12)
        past, soon, later = now - timedelta(hours=2), now + timedelta(hours=1), now + timedelta(days=1)
        hour = timedelta(hours=1)
        pt = [(1, 'HLV', 'Phòng', later, later + hour, ''), (2, 'HLV', 'Phòng', past, past + hour, '')]
        groups = [(8, 'Đã đặt', soon, soon + hour, 'SUCCESS'), (9, 'Đã hủy', soon, soon + hour, 'CANCEL')]
        with patch.object(schedule, 'read', side_effect=[pt, groups]) as read:
            shown = schedule.member_upcoming(7, now)
        self.assertEqual(read.call_args_list, [call(7, 'member_pt'), call(7, 'member_group')])
        self.assertEqual([item[2] for item in shown], ['Đã đặt', 'PT cá nhân'])
        self.assertEqual(shown[1][-1], 1)

    def test_agenda_shows_today_and_future_before_past(self):
        now = datetime(2026, 11, 24, 12)
        rows = [(1, 'PT', now - timedelta(days=1)), (2, 'PT', now + timedelta(days=1)), (3, 'PT', now)]
        grouped = schedule.days_for_agenda(rows, now.date())
        self.assertEqual([group[0][0] for _, group in grouped], [3, 2, 1])
