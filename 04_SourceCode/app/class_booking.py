"""Present advisory class eligibility without changing booking decisions."""
from dataclasses import dataclass
from datetime import datetime


CLASS_STATES = {
    'open': ('Đang nhận đăng ký', 'AVAILABLE'),
    'full': ('Hết chỗ', 'PENDING_PAYMENT'),
    'ended': ('Đã kết thúc', 'EXPIRED'),
    'in_progress': ('Đang diễn ra', 'PENDING_PAYMENT'),
    'closed': ('Đã đóng đăng ký', 'EXPIRED'),
}

REASONS = {
    'eligible': ('Bạn có thể đăng ký lớp này.', None),
    'booked': ('Bạn đã đăng ký lớp này.', 'schedule'),
    'ended': ('Lớp này đã kết thúc.', None),
    'in_progress': ('Lớp đã bắt đầu và đã đóng đăng ký.', None),
    'closed': ('Huấn luyện viên hoặc phòng tập hiện chưa khả dụng.', None),
    'full': ('Lớp đã đủ số lượng học viên. Hãy chọn lớp khác hoặc kiểm tra lại sau.', None),
    'future': ('Gói tập của bạn chưa đến ngày hiệu lực.', 'membership'),
    'no_contract': ('Bạn chưa có hợp đồng phù hợp để đăng ký lớp nhóm.', 'catalog'),
    'outside_dates': ('Thời gian lớp nằm ngoài thời hạn của gói đang dùng.', 'membership'),
    'pending_payment': ('Hãy hoàn tất thanh toán hợp đồng tại quầy.', 'membership'),
    'pending_activation': ('Hợp đồng đã thanh toán. Hãy liên hệ quầy để kích hoạt gói.', 'membership'),
    'expired': ('Gói tập của bạn đã hết hạn.', 'catalog'),
    'no_benefit': ('Gói tập hiện tại của bạn không bao gồm quyền lợi lớp nhóm.', 'catalog'),
    'benefit_unknown': ('Quyền lợi lớp nhóm cần được kiểm tra lại tại quầy.', 'membership'),
    'quota': ('Bạn đã sử dụng hết lượt lớp nhóm trong chu kỳ này.', 'membership'),
    'conflict': ('Bạn đã có lịch tập trùng thời gian.', 'schedule'),
    'unchecked': ('Điều kiện đăng ký sẽ được kiểm tra khi bạn gửi yêu cầu.', None),
}


@dataclass(frozen=True)
class GroupClass:
    id: int
    name: str
    category: str
    trainer: str
    room: str
    start: datetime
    end: datetime
    capacity: int
    enrolled: int
    remaining: int
    booking_status: str | None
    last_booking: int
    class_state: str
    reason: str
    quota_remaining: int | None

    @property
    def week(self):
        return self.start.strftime('%G-W%V')

    @property
    def may_book(self):
        return self.reason in ('eligible', 'unchecked')


def legacy_class(row):
    *fields, opened = row
    remaining, booking, _ = fields[-3:]
    state = ('full' if remaining < 1 else 'open') if opened else 'closed'
    reason = 'booked' if booking == 'SUCCESS' else 'unchecked' if state == 'open' else state
    return GroupClass(*fields, state, reason, None)
