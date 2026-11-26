import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple
from urllib.parse import urlencode

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from . import auth, db, membership, schedule
from .routes import _authorize, pages
from .class_booking import CLASS_STATES
from .staff_directory_sql import PAGE_SIZE as DESK_PAGE_SIZE


EMPLOYMENT = {'ACTIVE': 'Đang làm việc', 'ON_LEAVE': 'Nghỉ phép', 'TERMINATED': 'Đã nghỉ việc'}
PERSONNEL_ROLES = {'staff': 'Nhân viên', 'trainer': 'Huấn luyện viên'}
ROOM_STATES = {'AVAILABLE': 'Khả dụng', 'MAINTENANCE': 'Bảo trì'}
ROOM_TYPES = {'GYM': 'Phòng gym', 'PT': 'PT cá nhân', 'STUDIO': 'Studio', 'GROUP': 'Lớp nhóm'}
ASSET_STATES = {'ACTIVE': 'Đang sử dụng', 'MAINTENANCE': 'Bảo trì', 'RETIRED': 'Ngừng sử dụng'}
PAGE_SIZE = 50


def enabled():
    config = current_app.config
    return config.get('LOCAL04_ENABLED') and db.is_workflow_qa(config) and auth.enabled()


def actor_for(role):
    principal = _authorize(role)
    if not enabled() or not auth.allowed_transport():
        abort(403)
    return principal.person_id


def execute(proc, *params, many=False):
    return db.workflow(proc, *params, group='local04', many=many)


def record(proc, *params):
    row = execute(proc, *params)
    if row is None:
        abort(404)
    return row


def form(*fields):
    auth.require_csrf()
    membership.validate_fields(request.form, fields)
    return request.form


def selected(value, choices, *, optional=False):
    if optional and not value:
        return None
    if value not in choices:
        raise membership.InvalidForm('Giá trị đã chọn không hợp lệ.')
    return value


def content(value, length):
    value = (value or '').strip()
    if len(value.encode('utf-16-le')) > 2 * length or re.search(r'[\x00-\x08\x0b-\x1f\x7f]', value):
        raise membership.InvalidForm(f'Nội dung phải hợp lệ và có tối đa {length} ký tự.')
    return value or None


def day(value, *, optional=False):
    if optional and not value:
        return None
    try:
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value or ''):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise membership.InvalidForm('Nhập ngày hợp lệ.') from None


def date_range(start, end):
    if end == date.max or (start and end and start > end):
        raise membership.InvalidForm('Ngày kết thúc phải bằng hoặc sau ngày bắt đầu và nhỏ hơn ngày tối đa.')
    return start, end


def options(name, values, *, fallback=None):
    return selected(request.args.get(name, fallback), values, optional=fallback is None)


def offset():
    page = schedule.integer(request.args.get('page', '1'))
    if page > 2_147_483_647 // PAGE_SIZE:
        raise membership.InvalidForm('Số trang không hợp lệ.')
    return (page - 1) * PAGE_SIZE


def paged(rows, skip):
    def link(page):
        return request.path + '?' + urlencode({**request.args.to_dict(), 'page': page})

    current = skip // PAGE_SIZE + 1
    return dict(rows=rows[:PAGE_SIZE], previous=link(current - 1) if skip else None,
                following=link(current + 1) if len(rows) > PAGE_SIZE else None)


def contact(data, *, emergency=False):
    name = schedule.label(data.get('full_name'), 100)
    email = schedule.label(data.get('email'), 255).lower()
    phone = data.get('phone', '').strip()
    extra = data.get('emergency', '').strip()
    if not membership.EMAIL.fullmatch(email) or '..' in email or email.startswith('.') or '.@' in email:
        raise membership.InvalidForm('Nhập email hợp lệ.')
    if not membership.PHONE.fullmatch(phone) or (emergency and not membership.PHONE.fullmatch(extra)):
        raise membership.InvalidForm('Nhập số điện thoại gồm 9–14 chữ số và dấu + tùy chọn.')
    if emergency and phone.lstrip('+') == extra.lstrip('+'):
        raise membership.InvalidForm('Số liên hệ khẩn cấp phải khác số của hội viên.')
    return name, email, phone, content(data.get('address'), 255)


def render(screen, **context):
    return render_template(f'local04/{screen}.html', token=auth.csrf_token(), today=date.today(),
                           employment=EMPLOYMENT, personnel_roles=PERSONNEL_ROLES,
                           room_states=ROOM_STATES, room_types=ROOM_TYPES, asset_states=ASSET_STATES, **context)


@pages.errorhandler(membership.InvalidForm)
def bad_admin_input(error):
    return schedule.invalid(error)


@pages.get('/staff/member-directory')
def member_directory():
    actor = actor_for('staff')
    query, status, skip = content(request.args.get('q'), 100), options('status', ('ACTIVE', 'INACTIVE')), offset()
    if query and re.fullmatch(r'[0-9]{12}', query):
        return redirect(url_for('pages.staff_members'))
    rows = execute('members', actor, 'list', None, query, status, skip, many=True)
    return render('members', query=query, selected_status=status, **paged(rows, skip))


@pages.route('/staff/member-directory/<int:member_id>', methods=['GET', 'POST'])
def member_profile(member_id):
    actor = actor_for('staff')
    member_id = schedule.integer(str(member_id))
    if request.method == 'POST':
        data = form('full_name', 'email', 'phone', 'address', 'emergency', 'revision')
        revision = data.get('revision', '')
        if not re.fullmatch('[A-F0-9]{64}', revision):
            raise membership.InvalidForm('Hãy tải lại hồ sơ trước khi lưu.')
        execute('members', actor, 'save', member_id, None, None, 0, *contact(data, emergency=True),
                data['emergency'].strip(), revision)
        flash('Đã cập nhật hồ sơ hội viên.')
        return redirect(url_for('pages.member_profile', member_id=member_id), 303)
    profile = record('members', actor, 'profile', member_id)
    skip = offset()
    services = execute('services', actor, 'list', member_id, many=True)
    return render('member', profile=profile, contracts=membership.contracts(actor, staff=True, member_id=member_id),
                  benefits=execute('members', actor, 'benefits', member_id, many=True),
                  services=[(row.service_type_id, row.service_name) for row in services
                            if row.quota_per_cycle == -1 or row.used < row.quota_per_cycle],
                  **paged(execute('members', actor, 'history', member_id, None, None, skip, many=True), skip))


@pages.post('/staff/member-directory/<int:member_id>/service')
def use_member_service(member_id):
    actor = actor_for('staff')
    member_id = schedule.integer(str(member_id))
    service = schedule.integer(form('service').get('service'))
    if current_app.config.get('CLASS_RULES_ENABLED'):
        services = execute('services', actor, 'list', member_id, many=True)
        if services and not any(row.service_type_id == service for row in services):
            raise db.WorkflowRejected(52203)
    execute('services', actor, 'use', member_id, service)
    flash('Đã ghi nhận một lượt sử dụng dịch vụ.')
    return redirect(url_for('pages.member_profile', member_id=member_id), 303)


def personnel(actor, action, *, person_id=None, role=None, status=None, skip=0, name=None, email=None,
              phone=None, address=None, ssn=None, birth=None, gender=None, password_hash=None,
              hire=None, position=None, certificate=None, many=False):
    return execute('personnel', actor, action, person_id, role, status, skip, name, email, phone,
                   address, ssn, birth, gender, password_hash, hire, position, certificate, many=many)


@pages.get('/management/personnel')
def personnel_list():
    actor = actor_for('management')
    query, role = content(request.args.get('q'), 100), options('role', PERSONNEL_ROLES)
    status, skip = options('status', EMPLOYMENT), offset()
    rows = personnel(actor, 'list', role=role, status=status, name=query, skip=skip, many=True)
    return render('personnel', query=query, role=role, status=status, **paged(rows, skip))


@pages.route('/management/personnel/new', methods=['GET', 'POST'])
@pages.route('/management/personnel/assign', methods=['GET', 'POST'], endpoint='personnel_assign')
def personnel_create():
    actor = actor_for('management')
    assign = request.endpoint == 'pages.personnel_assign'
    if request.method == 'GET':
        return render('person', assign=assign)
    shared = ('role', 'hire', 'position')
    data = form(*shared, 'person_id') if assign else form(*shared, 'full_name', 'email', 'phone', 'address',
                                                         'ssn', 'birth', 'gender', 'password', 'confirm_password')
    role = selected(data.get('role'), PERSONNEL_ROLES)
    hire = day(data.get('hire'))
    position = schedule.label(data.get('position'), 50) if role == 'staff' else None
    if assign:
        person_id = schedule.integer(data.get('person_id'))
        personnel(actor, 'assign', person_id=person_id, role=role, hire=hire, position=position)
    else:
        name, email, phone, address = contact(data)
        ssn, birth = data.get('ssn', '').strip(), day(data.get('birth'))
        gender = selected(data.get('gender'), ('MALE', 'FEMALE', 'OTHER'))
        password = data.get('password', '')
        if not re.fullmatch(r'[0-9]{12}', ssn) or birth > date.today() or hire < birth:
            raise membership.InvalidForm('Kiểm tra CCCD, ngày sinh và ngày vào làm.')
        if not 12 <= len(password) <= 128 or password.isspace() or password != data.get('confirm_password'):
            raise membership.InvalidForm('Mật khẩu cần 12–128 ký tự và phải khớp với ô xác nhận.')
        person_id = personnel(actor, 'create', role=role, hire=hire, position=position, name=name, email=email,
                              phone=phone, address=address, ssn=ssn, birth=birth, gender=gender,
                              password_hash=auth.HASHER.hash(password))[0]
    flash('Đã lưu hồ sơ nhân sự.')
    return redirect(url_for('pages.personnel_detail', person_id=person_id, role=role), 303)


@pages.route('/management/personnel/<int:person_id>/<role>', methods=['GET', 'POST'])
def personnel_detail(person_id, role):
    actor = actor_for('management')
    person_id = schedule.integer(str(person_id))
    if role not in PERSONNEL_ROLES:
        abort(404)
    if request.method == 'POST':
        data = form('full_name', 'email', 'phone', 'address', 'position', 'status')
        name, email, phone, address = contact(data)
        position = schedule.label(data.get('position'), 50) if role == 'staff' else None
        personnel(actor, 'save', person_id=person_id, role=role, status=selected(data.get('status'), EMPLOYMENT),
                  name=name, email=email, phone=phone, address=address, position=position)
        flash('Đã lưu thay đổi nhân sự.')
        return redirect(url_for('pages.personnel_detail', person_id=person_id, role=role), 303)
    profile = personnel(actor, 'detail', person_id=person_id, role=role)
    if not profile:
        abort(404)
    skip = offset()
    sessions = personnel(actor, 'schedule', person_id=person_id, skip=skip, many=True) if role == 'trainer' else ()
    return render('person', profile=profile, role=role, editable=actor != person_id, **paged(sessions, skip))


@pages.route('/trainer/certifications', methods=['GET', 'POST'])
@pages.route('/management/personnel/<int:person_id>/certifications', methods=['GET', 'POST'], endpoint='trainer_cert_admin')
def trainer_certifications(person_id=None):
    own = person_id is None
    actor = actor_for('trainer' if own else 'management')
    person_id = actor if own else schedule.integer(str(person_id))
    if request.method == 'POST':
        data = form('operation', 'certificate')
        action = selected(data.get('operation'), ('cert_add', 'cert_remove'))
        personnel(actor, action, person_id=person_id, certificate=schedule.label(data.get('certificate'), 100))
        flash('Đã cập nhật chứng chỉ.')
        destination = url_for('pages.trainer_certifications') if own else url_for('pages.trainer_cert_admin', person_id=person_id)
        return redirect(destination, 303)
    rows = personnel(actor, 'certs', person_id=person_id, many=True)
    if not rows:
        abort(404)
    return render('certifications', rows=rows, person_id=person_id, own=own)


@pages.route('/management/catalog', methods=['GET', 'POST'])
def admin_catalog():
    actor = actor_for('management')
    if request.method == 'POST':
        data = form('name', 'description')
        execute('catalog', actor, 'service', None, None, schedule.label(data.get('name'), 100),
                None, None, content(data.get('description'), 500))
        flash('Đã thêm dịch vụ.')
        return redirect(url_for('pages.admin_catalog'), 303)
    query, skip = content(request.args.get('q'), 100), offset()
    rows = execute('catalog', actor, 'list', None, None, query, None, None, None, None, None, skip, many=True)
    return render('catalog', query=query, services=execute('catalog', actor, 'services', many=True), **paged(rows, skip))


@pages.route('/management/catalog/new', methods=['GET', 'POST'])
@pages.route('/management/catalog/<int:plan_id>', methods=['GET', 'POST'], endpoint='admin_plan_detail')
def admin_plan(plan_id=None):
    actor = actor_for('management')
    if plan_id is not None:
        plan_id = schedule.integer(str(plan_id))
    if request.method == 'POST':
        auth.require_csrf()
        action = selected(request.form.get('operation'), ('save', 'sale', 'quota') if plan_id else ('save',))
        fields = {'save': ('name', 'months', 'price', 'description'), 'sale': ('for_sale',),
                  'quota': ('service', 'quota')}
        membership.validate_fields(request.form, ('operation', *fields[action]))
        data = request.form
        if action == 'save':
            months = schedule.integer(data.get('months'))
            if months > 1200:
                raise membership.InvalidForm('Thời hạn tối đa 1.200 tháng.')
            plan_id = execute('catalog', actor, action, plan_id, None, schedule.label(data.get('name'), 100),
                              months, membership.quote(data.get('price')), content(data.get('description'), 500))[0]
        elif action == 'sale':
            execute('catalog', actor, action, plan_id, None, None, None, None, None, None,
                    selected(data.get('for_sale'), ('1', '0')) == '1')
        else:
            quota = -1 if data.get('quota') == '-1' else schedule.integer(data.get('quota'), 0)
            execute('catalog', actor, action, plan_id, schedule.integer(data.get('service')), None, None, None, None, quota)
        flash('Đã cập nhật gói tập.')
        return redirect(url_for('pages.admin_plan_detail', plan_id=plan_id), 303)
    plan = record('catalog', actor, 'detail', plan_id) if plan_id else None
    inclusions = execute('catalog', actor, 'inclusions', plan_id, many=True) if plan else ()
    services = execute('catalog', actor, 'services', many=True) if plan and not plan.referenced else ()
    benefits = membership.plan_benefits((item.service_name, item.quota_per_cycle) for item in inclusions)
    return render('plan', plan=plan, benefits=benefits, services=services)


@pages.route('/management/classes/<int:class_id>', methods=['GET', 'POST'])
def admin_class(class_id):
    actor = actor_for('management')
    class_id = schedule.integer(str(class_id))
    item = record('classes', actor, 'detail', class_id)
    if request.method == 'POST':
        if item.has_history:
            data = form('capacity')
            details = (item.trainer_id, item.room_id, item.start_time, item.end_time, item.class_name, item.category)
        else:
            data = form('trainer', 'room', 'start', 'end', 'name', 'category', 'capacity')
            details = (*schedule.slot(data), schedule.label(data.get('name'), 100),
                       schedule.class_category(actor, data.get('category')))
        execute('classes', actor, 'save', class_id, *details, schedule.integer(data.get('capacity')))
        flash('Đã cập nhật lớp nhóm.')
        return redirect(url_for('pages.admin_class', class_id=class_id), 303)
    trainers = schedule.read(actor, 'trainers') if not item.has_history else ()
    rooms = schedule.read(actor, 'rooms') if not item.has_history else ()
    trainer_options = dict((row[0], row[1]) for row in trainers)
    room_options = dict((row[0], row[1]) for row in rooms)
    trainer_options.setdefault(item.trainer_id, item.full_name)
    room_options.setdefault(item.room_id, item.room_name)
    return render('class', item=item, trainer_options=trainer_options.items(), room_options=room_options.items(),
                  upcoming=item.start_time > datetime.now())


def assets(actor, action, *, asset_id=None, room=None, name=None, room_type=None, serial=None,
           status=None, on_date=None, description=None, cost=None, ticket=None, skip=0, many=False):
    return execute('assets', actor, action, asset_id, room, name, room_type, serial, status,
                   on_date, description, cost, ticket, skip, many=many)


@pages.route('/staff/assets', methods=['GET', 'POST'])
def asset_directory():
    actor = actor_for('staff')
    manager = 'management' in g.principal.roles
    if request.method == 'POST':
        auth.require_csrf()
        data = request.form
        action = selected(data.get('operation'), ('room_add', 'equipment_add', 'room_status'))
        if action in ('room_add', 'equipment_add'):
            _authorize('management')
        if action == 'room_add':
            membership.validate_fields(data, ('operation', 'name', 'room_type'))
            assets(actor, action, name=schedule.label(data.get('name'), 100),
                   room_type=selected(data.get('room_type'), ROOM_TYPES))
        elif action == 'equipment_add':
            membership.validate_fields(data, ('operation', 'name', 'serial', 'room'))
            serial = data.get('serial', '').strip()
            if not re.fullmatch(r'[A-Za-z0-9._/\-]{1,50}', serial):
                raise membership.InvalidForm('Số sê-ri tối đa 50 ký tự và không có khoảng trắng.')
            result = assets(actor, action, name=schedule.label(data.get('name'), 100), serial=serial,
                            room=schedule.integer(data['room']) if data.get('room') else None)
            flash('Đã thêm thiết bị.')
            return redirect(url_for('pages.asset_detail', equipment_id=result[0]), 303)
        else:
            membership.validate_fields(data, ('operation', 'room', 'status'))
            assets(actor, action, asset_id=schedule.integer(data.get('room')), status=selected(data.get('status'), ROOM_STATES))
        flash('Đã cập nhật danh sách phòng.')
        return redirect(url_for('pages.asset_directory'), 303)
    query, status, skip = content(request.args.get('q'), 100), options('status', ASSET_STATES), offset()
    rows = assets(actor, 'equipment', name=query, status=status, skip=skip, many=True)
    return render('assets', rooms=assets(actor, 'rooms', many=True), manager=manager, query=query, status=status,
                  **paged(rows, skip))


@pages.route('/staff/assets/<int:equipment_id>', methods=['GET', 'POST'])
def asset_detail(equipment_id):
    actor = actor_for('staff')
    equipment_id = schedule.integer(str(equipment_id))
    if request.method == 'POST':
        auth.require_csrf()
        data = request.form
        action = selected(data.get('operation'), ('equipment_save', 'open', 'close'))
        if action == 'equipment_save':
            membership.validate_fields(data, ('operation', 'room', 'status'))
            assets(actor, action, asset_id=equipment_id, status=selected(data.get('status'), ASSET_STATES),
                   room=schedule.integer(data['room']) if data.get('room') else None)
        else:
            fields = ('status', 'cost', 'ticket') if action == 'close' else ()
            membership.validate_fields(data, ('operation', 'on_date', 'description', *fields))
            assets(actor, action, asset_id=equipment_id, on_date=day(data.get('on_date')),
                   description=schedule.label(data.get('description'), 500),
                   status=selected(data.get('status'), ('ACTIVE', 'RETIRED')) if action == 'close' else None,
                   cost=membership.quote(data.get('cost')) if action == 'close' else None,
                   ticket=schedule.integer(data.get('ticket')) if action == 'close' else None)
        flash('Đã cập nhật thiết bị và nhật ký bảo trì.')
        return redirect(url_for('pages.asset_detail', equipment_id=equipment_id), 303)
    item = assets(actor, 'detail', asset_id=equipment_id)
    if item is None:
        abort(404)
    skip = offset()
    return render('equipment', item=item, rooms=assets(actor, 'rooms', many=True),
                  **paged(assets(actor, 'logs', asset_id=equipment_id, skip=skip, many=True), skip))


def transaction_list(kind):
    actor = actor_for('staff')
    start, end = date_range(day(request.args.get('from'), optional=True), day(request.args.get('to'), optional=True))
    query, skip = content(request.args.get('q'), 100), offset()
    status, method = options('status', membership.STATUS), options('method', membership.METHOD)
    rows = execute('transactions', actor, kind, start, end, query, status, method, skip, many=True)
    return render('transactions', kind=kind, start=start, end=end, query=query, status=status, method=method,
                  **paged(rows, skip))


@pages.get('/staff/transactions')
def admin_contracts():
    return transaction_list('contracts')


@pages.get('/staff/payments')
def admin_payments():
    return transaction_list('payments')


@pages.get('/staff/payments/<int:contract_id>')
def admin_receipt(contract_id):
    actor = actor_for('staff')
    item = record('transactions', actor, 'receipt', None, None, None, None, None, 0, schedule.integer(str(contract_id)))
    return render('receipt', item=item)


@pages.get('/management/overview')
@pages.get('/management/reports', endpoint='admin_reports')
def dashboard():
    actor = actor_for('management')
    now = date.today()
    start, end = date_range(day(request.args.get('from', now.replace(day=1).isoformat())),
                            day(request.args.get('to', now.isoformat())))
    rows = execute('dashboard', actor, start, end, many=True)
    values = {(row.metric, row.segment): (row.quantity, row.amount or Decimal(0)) for row in rows}
    quantities = {key: value[0] for key, value in values.items()}
    capacity = values['classes', ''][1]
    fill = Decimal(quantities['seats', '']) * 100 / capacity if capacity else None
    reports = request.endpoint == 'pages.admin_reports'
    upcoming = ()
    receipts = ()
    if not reports:
        receipts = execute('transactions', actor, 'payments', start, end, many=True)[:5]
        if schedule.enabled():
            now_time = datetime.now()
            upcoming = sorted((item for item in schedule.read(actor, 'staff') if item[3] > now_time),
                              key=lambda item: item[2])[:5]
    return render('dashboard', values=values, count=quantities, start=start, end=end, fill=fill,
                  receipts_by_month=sorted(row.segment for row in rows if row.metric == 'receipt_month'),
                  reports=reports, upcoming=upcoming, recent_receipts=receipts)



class DeskTrainer(NamedTuple):
    id: int
    name: str
    status: str
    certifications: str | None
    next_id: int | None
    next_time: datetime | None
    next_type: str | None
    next_class: str | None


class DeskSlot(NamedTuple):
    id: int
    kind: str
    start: datetime
    end: datetime
    room: str
    class_name: str | None


class DeskClass(NamedTuple):
    id: int
    name: str
    category: str
    trainer_id: int
    trainer: str
    room: str
    start: datetime
    end: datetime
    capacity: int
    enrolled: int
    remaining: int
    state: str


def desk_read(actor, scope, key=None, *, query=None, state=None, first=None, last=None, trainer=None, skip=0):
    try:
        return schedule.run('schedule', actor, scope, key, query, state, first, last, trainer, skip, many=True)
    except db.WorkflowRejected as error:
        if error.args[0] != 52201:
            raise
        # A portable installation can apply the read scope after updating application files.
        abort(503, description='Tra cứu tại quầy chưa khả dụng. Hãy dùng lịch PT và lớp nhóm trong lúc cập nhật.')


def desk_page(actor, scope, row_type, key=None, **filters):
    page = schedule.integer(request.args.get('page', '1'))
    if page > 2_147_483_647 // DESK_PAGE_SIZE:
        raise membership.InvalidForm('Số trang không hợp lệ.')
    rows = desk_read(actor, scope, key, skip=(page - 1) * DESK_PAGE_SIZE, **filters)
    total = rows[0][0]
    pages_count = max(1, (total + DESK_PAGE_SIZE - 1) // DESK_PAGE_SIZE)
    if page > pages_count:
        abort(404)

    def link(value):
        return request.path + '?' + urlencode({**request.args.to_dict(), 'page': value})

    return dict(rows=[row_type(*row[1:]) for row in rows if row[1] is not None], total=total,
                page=page, page_count=pages_count, previous=link(page - 1) if page > 1 else None,
                following=link(page + 1) if page < pages_count else None)


def desk_dates(*, teaching=False):
    today = date.today()
    default = (today, today + timedelta(days=6)) if teaching else (None, None)
    if not request.args.get('from') and not request.args.get('to'):
        return default
    return date_range(day(request.args.get('from'), optional=True), day(request.args.get('to'), optional=True))


@pages.get('/staff/trainers')
def staff_trainers():
    actor = schedule.actor_for('staff')
    query = content(request.args.get('q'), 100)
    state = options('status', EMPLOYMENT)
    return render('staff_trainers', query=query, state=state,
                  **desk_page(actor, 'desk_trainers', DeskTrainer, query=query, state=state))


@pages.get('/staff/trainers/<int:trainer_id>')
def staff_trainer(trainer_id):
    actor = schedule.actor_for('staff')
    trainer_id = schedule.integer(str(trainer_id))
    profiles = desk_read(actor, 'desk_trainer', trainer_id)
    if profiles[0][1] is None:
        abort(404)
    first, last = desk_dates(teaching=True)
    kinds = {'PERSONAL': 'Lịch PT', 'GROUP': 'Lớp nhóm'}
    kind = options('kind', kinds)
    return render('staff_trainer', trainer=DeskTrainer(*profiles[0][1:]), first=first, last=last, kinds=kinds, kind=kind,
                  **desk_page(actor, 'desk_trainer_slots', DeskSlot, trainer_id, state=kind, first=first, last=last))


@pages.get('/staff/classes')
def staff_classes():
    actor = schedule.actor_for('staff')
    query = content(request.args.get('q'), 100)
    state = options('status', CLASS_STATES)
    first, last = desk_dates()
    trainer = schedule.integer(request.args['trainer']) if request.args.get('trainer') else None
    coaches = [tuple(row) for row in desk_read(actor, 'desk_coaches')]
    return render('staff_classes', query=query, state=state, first=first, last=last,
                  trainer=trainer, coaches=coaches, class_states=CLASS_STATES,
                  state_options=[(key, value[0]) for key, value in CLASS_STATES.items()],
                  **desk_page(actor, 'desk_classes', DeskClass, query=query, state=state, first=first, last=last, trainer=trainer))


@pages.get('/staff/classes/<int:class_id>')
def staff_class(class_id):
    actor = schedule.actor_for('staff')
    rows = desk_read(actor, 'desk_classes_one', schedule.integer(str(class_id)))
    if rows[0][1] is None:
        abort(404)
    return render('staff_class', item=DeskClass(*rows[0][1:]), class_states=CLASS_STATES)
