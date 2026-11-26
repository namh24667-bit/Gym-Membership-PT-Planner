from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from uuid import UUID

from . import auth, db


class InvalidForm(ValueError):
    pass


STATUS = {'PENDING_PAYMENT': 'Chờ thanh toán', 'PENDING_ACTIVATION': 'Chờ kích hoạt',
          'ACTIVE': 'Đang hoạt động', 'EXPIRED': 'Hết hạn'}
METHOD = {'CASH': 'Tiền mặt', 'BANK_TRANSFER': 'Chuyển khoản'}
ERRORS = {
    52101: (403, 'Tài khoản hiện không có quyền thực hiện.'),
    52102: (409, 'Email, số điện thoại hoặc CCCD đã được đăng ký.'),
    52103: (404, 'Gói tập hoặc hợp đồng không còn khả dụng.'),
    52104: (409, 'Giá niêm yết đã thay đổi. Xem lại số tiền hiện tại trước khi xác nhận.'),
    52105: (409, 'Trạng thái hợp đồng đã thay đổi hoặc chưa đủ điều kiện.'),
    52106: (409, 'Hội viên đang có một gói hoạt động. Có thể ghi nhận thanh toán trước.'),
    52107: (409, 'Yêu cầu không hợp lệ hoặc đã được dùng cho giao dịch khác.'),
    52201: (403, 'Tài khoản không có quyền thao tác trên lịch này.'),
    52202: (409, 'Cần gói đang có hiệu lực và bao phủ ngày bắt đầu, kết thúc buổi tập.'),
    52203: (409, 'Gói hiện tại chưa có quyền lợi phù hợp với dịch vụ.'),
    52204: (409, 'Bạn đã hết lượt sử dụng dịch vụ trong chu kỳ này.'),
    52205: (409, 'Khung giờ hoặc thông tin buổi tập không hợp lệ.'),
    52206: (409, 'Huấn luyện viên hoặc phòng không khả dụng.'),
    52207: (404, 'Không tìm thấy lịch hoặc lượt đặt thuộc quyền của bạn.'),
    52208: (409, 'Lượt đặt đã thay đổi. Hãy mở lại lịch trước khi thao tác.'),
    52209: (409, 'Lớp nhóm đã hết chỗ.'),
    52301: (403, 'Tài khoản hiện không có quyền thực hiện thao tác quản trị này.'),
    52302: (400, 'Thông tin quản trị không hợp lệ. Hãy kiểm tra các trường đã nhập.'),
    52303: (404, 'Không tìm thấy hồ sơ hoặc danh mục đã chọn.'),
    52304: (409, 'Hồ sơ đã thay đổi hoặc đang được cập nhật. Hãy mở lại để kiểm tra.'),
    52305: (409, 'Thông tin định danh, vai trò, chứng chỉ hoặc tên danh mục đã tồn tại.'),
    52306: (409, 'Huấn luyện viên còn lịch đã phân công. Chưa thể đổi trạng thái.'),
    52307: (409, 'Gói đã có hợp đồng. Hãy tạo mẫu mới nếu cần đổi tên, thời hạn hoặc quota.'),
    52308: (409, 'Sức chứa tối đa phải bằng hoặc lớn hơn số chỗ đã đăng ký.'),
    52309: (409, 'Lớp đã có lịch sử đặt chỗ. Bạn chỉ có thể cập nhật sức chứa.'),
    52310: (409, 'Trạng thái thiết bị hoặc phiếu bảo trì vừa chọn không phù hợp.'),
    51001: (409, 'Huấn luyện viên hiện không nhận lịch.'),
    51002: (409, 'Phòng đang bảo trì.'),
    51003: (409, 'Khung giờ trùng lịch của huấn luyện viên.'),
    51004: (409, 'Phòng đã có lịch trong khung giờ này.'),
    51005: (409, 'Lớp nhóm đã hết chỗ.'),
    51006: (409, 'Khung giờ trùng lịch lớp nhóm của hội viên.'),
    51007: (409, 'Khung giờ trùng lịch PT của hội viên.'),
    51008: (409, 'Khung giờ trùng lịch PT của hội viên.'),
    51009: (409, 'Khung giờ trùng lịch lớp nhóm của hội viên.'),
    1205: (409, 'Có thao tác cập nhật đồng thời. Hãy tải lại và kiểm tra trước khi thử lại.'),
    1222: (409, 'Dữ liệu đang được cập nhật. Hãy tải lại và kiểm tra trước khi thử lại.'),
}
REGISTRATION_FIELDS = (
    'full_name', 'ssn', 'date_of_birth', 'gender', 'address', 'email', 'phone',
    'emergency_contact_phone', 'health_notes', 'password', 'confirm_password',
)
PHONE = re.compile(r'\+?[0-9]{9,14}')
EMAIL = re.compile(r"[a-z0-9!#$%&'*+/=?^_{}|~.-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}")


def validate_fields(form, allowed):
    if set(form).difference((*allowed, 'csrf_token')) or (
        hasattr(form, 'getlist') and any(len(form.getlist(field)) != 1 for field in form)
    ):
        raise InvalidForm('Biểu mẫu có trường không hợp lệ.')


def validate_registration(form, *, today=None):
    validate_fields(form, REGISTRATION_FIELDS)
    values = {field: form.get(field, '').strip() for field in REGISTRATION_FIELDS
              if field not in ('password', 'confirm_password')}
    limits = {'full_name': 100, 'address': 255, 'health_notes': 500, 'email': 255}
    for field, length in limits.items():
        # SQL NVARCHAR sizes are measured in UTF-16 code units.
        if len(values[field].encode('utf-16-le')) > length * 2 or re.search(r'[\x00-\x08\x0b-\x1f\x7f]', values[field]):
            raise InvalidForm('Tên, email, địa chỉ hoặc ghi chú có ký tự hay độ dài không hợp lệ.')
    if not values['full_name'] or '\r' in values['full_name'] or '\n' in values['full_name']:
        raise InvalidForm('Nhập họ và tên hợp lệ.')
    if not re.fullmatch(r'[0-9]{12}', values['ssn']):
        raise InvalidForm('CCCD phải gồm đúng 12 chữ số.')
    values['email'] = values['email'].lower()
    if (not EMAIL.fullmatch(values['email']) or '..' in values['email']
            or values['email'].split('@')[0].startswith('.') or '.@' in values['email']):
        raise InvalidForm('Nhập email hợp lệ.')
    if (not PHONE.fullmatch(values['phone']) or not PHONE.fullmatch(values['emergency_contact_phone'])
            or len(values['phone']) > 15 or len(values['emergency_contact_phone']) > 15):
        raise InvalidForm('Số điện thoại cần có 9–14 chữ số và có thể bắt đầu bằng dấu +.')
    if values['phone'].lstrip('+') == values['emergency_contact_phone'].lstrip('+'):
        raise InvalidForm('Số điện thoại khẩn cấp phải khác số của hội viên.')
    if values['gender'] not in ('MALE', 'FEMALE', 'OTHER'):
        raise InvalidForm('Chọn giới tính hợp lệ.')
    try:
        birth = date.fromisoformat(values['date_of_birth'])
    except ValueError:
        raise InvalidForm('Nhập ngày sinh hợp lệ.') from None
    today = today or date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    if age < 15:
        raise InvalidForm('Hội viên phải đủ 15 tuổi.')
    values['date_of_birth'] = birth
    password = form.get('password', '')
    if not 12 <= len(password) <= 128 or password.isspace():
        raise InvalidForm('Mật khẩu phải có từ 12 đến 128 ký tự.')
    if password != form.get('confirm_password'):
        raise InvalidForm('Mật khẩu xác nhận chưa khớp.')
    return values


def register(form):
    data = validate_registration(form)
    password_hash = auth.HASHER.hash(form['password'])
    return db.workflow('register_member', *(data[field] or None for field in REGISTRATION_FIELDS[:-2]),
                       password_hash)[0]


def quote(value):
    if not re.fullmatch(r'\d{1,10}(?:\.\d{1,2})?', value or '', re.ASCII):
        raise InvalidForm('Số tiền phải hợp lệ, tối đa hai chữ số thập phân.')
    return Decimal(value)


def request_id(value):
    try:
        key = UUID(value or '')
    except ValueError:
        raise InvalidForm('Mã yêu cầu không hợp lệ. Tải lại trang để thử lại.') from None
    if key.version != 4:
        raise InvalidForm('Mã yêu cầu không hợp lệ. Tải lại trang để thử lại.')
    return str(key)


# Alias cũ chỉ dùng để hiển thị. CleanDemo xác định quyền theo SQL trong ops/portable/clean_compat.py.
PLAN_SERVICES = (
    ('gym', 'Tập gym tự do', 'pulse', ('Local-02 · Sử dụng phòng tập',)),
    ('pt', 'Huấn luyện cá nhân (PT)', 'person', ('PT cá nhân', 'Local-02 · Buổi PT')),
    ('group', 'Lớp nhóm', 'people', ('Lớp nhóm',)),
)
SERVICE_ALIASES = {alias.casefold(): (key, label) for key, label, _, aliases in PLAN_SERVICES for alias in aliases}


def service_label(name):
    match = SERVICE_ALIASES.get(name.rstrip().casefold())
    return match[1] if match else name


@dataclass(frozen=True)
class PlanBenefit:
    key: str
    label: str
    icon: str
    state: str
    quota: int | None = None
    source_names: tuple[str, ...] = ()


def plan_benefits(rows):
    matched = {key: [] for key, _, _, _ in PLAN_SERVICES}
    extras = []
    for service, limit in rows:
        match = SERVICE_ALIASES.get(service.rstrip().casefold())
        if match:
            matched[match[0]].append((service, limit))
        else:
            extras.append((service, limit))

    def summarize(key, label, icon, entries):
        names = tuple(name for name, _ in entries)
        if not entries:
            return PlanBenefit(key, label, icon, 'missing')
        if len(entries) > 1:
            return PlanBenefit(key, label, icon, 'ambiguous', source_names=names)
        limit = entries[0][1]
        if limit is None or limit < -1:
            state = 'unknown'
        else:
            state = {-1: 'unlimited', 0: 'empty'}.get(limit, 'finite')
        return PlanBenefit(key, label, icon, state, limit, names)

    return tuple(summarize(key, label, icon, matched[key]) for key, label, icon, _ in PLAN_SERVICES) + tuple(
        summarize('other', service, 'card', [(service, limit)]) for service, limit in extras)


def plan_purpose(benefits):
    activities = {'gym': 'tập gym tự do', 'pt': 'tập cùng huấn luyện viên', 'group': 'tham gia lớp nhóm'}
    available = [activities.get(entry.key, 'sử dụng ' + entry.label)
                 for entry in benefits if entry.state in ('finite', 'unlimited')]
    if not available:
        if all(entry.state == 'missing' for entry in benefits):
            return 'Chưa có quyền lợi dịch vụ được cấu hình cho gói này.'
        return 'Xem định mức từng dịch vụ trước khi đăng ký.'
    purpose = ' và '.join(filter(None, (', '.join(available[:-1]), available[-1])))
    return 'Phù hợp nếu bạn muốn ' + purpose + '.'


def plans(plan_id=None):
    result = {}
    for key, name, duration, price, description, service, quota in db.workflow('catalog', plan_id, many=True):
        plan = result.setdefault(key, dict(id=key, name=name, months=duration, price=price,
                                           description=description, benefits=[]))
        if service is not None:
            plan['benefits'].append((service, quota))
    for plan in result.values():
        plan['benefits'] = plan_benefits(plan['benefits'])
        plan['purpose'] = plan_purpose(plan['benefits'])
    return list(result.values())


def contracts(actor, *, staff=False, contract_id=None, member_id=None, status=None):
    fields = ('id', 'member_id', 'member_name', 'plan', 'status', 'start', 'end', 'paid',
              'price', 'payment_id', 'amount', 'method', 'payment_time', 'plan_id')
    rows = db.workflow('contracts', actor, staff, contract_id, member_id, status, many=True)
    return [dict(zip(fields, row, strict=True)) for row in rows]
