from datetime import date, datetime
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for

from . import auth, db, membership
from .navigation import PUBLIC_MENU, ROLE_NAVIGATION


pages = Blueprint("pages", __name__)


def _profile_enabled():
    config = current_app.config
    return config.get('LOCALR1A_ENABLED') and db.is_workflow_qa(config) and auth.enabled()


@pages.app_context_processor
def navigation():
    from . import admin, schedule

    principal = g.get('principal')
    sections = []
    if principal:
        local04 = admin.enabled()
        local03 = schedule.enabled()
        if 'management' in principal.roles:
            items = [('Tổng quan', 'pages.management_area', 'overview')]
            if local04:
                items.extend((('Báo cáo', 'pages.admin_reports', 'chart'), ('Nhân sự', 'pages.personnel_list', 'people'),
                              ('Gói tập và dịch vụ', 'pages.admin_catalog', 'card')))
            if local03:
                items.append(('Quản lý lịch lớp', 'pages.management_schedule', 'calendar'))
            sections.append(('Quản lý', items))
        if 'staff' in principal.roles:
            items = [('Tại quầy', 'pages.staff_area', 'overview')]
            if _local02():
                items.extend((('Hội viên', 'pages.member_directory' if local04 else 'pages.staff_members', 'person'),
                              ('Hợp đồng', 'pages.admin_contracts' if local04 else 'pages.staff_contracts', 'stack'),
                              ('Tư vấn gói tập', 'pages.staff_plan_catalog', 'card')))
            if local04:
                items.extend((('Thanh toán', 'pages.admin_payments', 'card'), ('Phòng và thiết bị', 'pages.asset_directory', 'tool')))
            if local03:
                items.extend((('Huấn luyện viên', 'pages.staff_trainers', 'person'),
                              ('Lớp nhóm', 'pages.staff_classes', 'people')))
            if local03 and 'management' not in principal.roles:
                items.append(('Lịch PT và lớp nhóm', 'pages.operations_schedule', 'calendar'))
            sections.append(('Vận hành', items))
        if 'member' in principal.roles:
            items = [('Gói tập của tôi', 'pages.member_area', 'overview')]
            if _local02():
                items.append(('Danh mục gói tập', 'pages.catalog', 'card'))
            if local03:
                items.extend((('Đặt lịch PT', 'pages.schedule_form', 'pulse'), ('Đăng ký lớp nhóm', 'pages.member_classes', 'people'),
                              ('Lịch đã đặt', 'pages.member_schedule', 'calendar')))
            sections.append(('Hội viên', items))
        if 'trainer' in principal.roles:
            items = [('Lịch dạy', 'pages.trainer_schedule' if local03 else 'pages.trainer_area', 'calendar')]
            if local04:
                items.append(('Chứng chỉ', 'pages.trainer_certifications', 'award'))
            sections.append(('Huấn luyện viên', items))
    else:
        sections.append((None, PUBLIC_MENU))
    return {'navigation_sections': sections, 'identity': principal, 'profile_available': bool(principal and _profile_enabled()),
            'logout_token': session.get('csrf_token') if principal else None, 'ui_today': date.today()}


@pages.before_request
def restore_identity():
    # Logout must be available even while SQL Server is unreachable.
    if request.endpoint != 'pages.logout':
        auth.load_principal()


@pages.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def _area_for(principal):
    return redirect(url_for(f'pages.{principal.roles[0]}_area'))


@pages.get("/")
def home():
    principal = g.get('principal')
    return _area_for(principal) if principal else redirect(url_for('pages.login'))


@pages.get("/login")
def login():
    principal = g.get('principal')
    if principal:
        return _area_for(principal)
    token = auth.csrf_token() if auth.enabled() and auth.allowed_transport() else None
    return render_template('login.html', login_token=token, https_required=auth.enabled() and not auth.allowed_transport())


@pages.get("/register")
def register():
    enabled = _local02() and auth.allowed_transport() and g.get('principal') is None
    return _registration_form(enabled=enabled)


@pages.post("/login")
def login_submit():
    if not auth.enabled():
        abort(503, description="Đăng nhập chưa tích hợp. Không có phiên đăng nhập nào được tạo.")
    auth.require_csrf()
    principal = g.get('principal')
    if principal:
        return _area_for(principal)
    principal = auth.authenticate(request.form.get('email', '').strip(), request.form.get('password', ''))
    if not principal:
        return render_template('login.html', login_token=auth.csrf_token(),
                               login_error='Email hoặc mật khẩu không hợp lệ.'), 401
    auth.sign_in(principal.person_id)
    return _area_for(principal)


@pages.post('/logout')
def logout():
    if not auth.enabled():
        abort(403)
    auth.require_csrf()
    auth.sign_out()
    return redirect(url_for('pages.login'))


@pages.post("/register")
def register_unavailable():
    if not _local02():
        abort(503, description="Đăng ký hội viên chưa tích hợp. Thông tin gửi lên không được lưu.")
    if g.get('principal') is not None:
        abort(403)
    return _register_member(at_counter=False)


def _authorize(role):
    principal = g.get('principal')
    if principal is None or role not in principal.roles:
        abort(403)
    return principal


def _local02():
    config = current_app.config
    return config.get('LOCAL02_ENABLED') and db.is_workflow_qa(config) and auth.enabled()


def _workflow_role(role):
    principal = _authorize(role)
    if not _local02() or not auth.allowed_transport():
        abort(403)
    return principal


@pages.get('/profile')
def personal_profile():
    from . import admin, schedule

    principal = g.get('principal')
    if not principal or not auth.allowed_transport():
        abort(403)
    if not _profile_enabled():
        abort(404)
    if request.args:
        abort(400)
    profile = db.personal_profile(principal.person_id)
    if profile is None:
        abort(403)
    roles = tuple(role for role in principal.roles if role != 'staff' or 'management' not in principal.roles)
    member = 'member' in roles
    trainer = 'trainer' in roles
    benefits = (db.workflow('benefits', principal.person_id, profile.membership_id, many=True)
                if member and profile.membership_id and _local02() else ())
    schedule_available = schedule.enabled()
    now = datetime.now()
    upcoming = schedule.member_upcoming(principal.person_id, now) if member and schedule_available else ()
    assigned = ()
    if trainer and schedule_available:
        assignments = schedule.read(principal.person_id, 'trainer')
        assigned = sorted((row for row in assignments if row[3] > now), key=lambda row: row[2])[:4]
    certificates = (admin.personnel(principal.person_id, 'certs', person_id=principal.person_id, many=True)
                    if trainer and admin.enabled() else ())
    return render_template('personal_profile.html', profile=profile, roles=roles,
                           role_labels=dict((role, label) for role, (label, _) in ROLE_NAVIGATION.items()),
                           employment=admin.EMPLOYMENT, member=member, trainer=trainer, benefits=benefits,
                           upcoming=upcoming, assigned=assigned, certificates=[row[2] for row in certificates if row[2]],
                           certificates_available=trainer and admin.enabled(), contracts_available=member and _local02())


def _registration_form(*, enabled=True, at_counter=False, error=None, values=None, status=200):
    fields = values or {}
    return render_template('register.html', enabled=enabled, counter=at_counter, error=error, values=fields,
                           registration_token=auth.csrf_token() if enabled else None), status


def _register_member(*, at_counter):
    auth.require_csrf()
    try:
        member_id = membership.register(request.form)
    except (membership.InvalidForm, db.WorkflowRejected) as error:
        status, message = _workflow_error(error)
        fields = {key: request.form.get(key, '') for key in membership.REGISTRATION_FIELDS[:-2]}
        return _registration_form(at_counter=at_counter, error=message, values=fields, status=status)
    flash('Đã đăng ký hội viên.')
    return redirect(url_for('pages.staff_member', member_id=member_id) if at_counter else url_for('pages.login'), 303)


def _workflow_error(error):
    return (400, str(error)) if isinstance(error, membership.InvalidForm) else membership.ERRORS[error.args[0]]


@pages.errorhandler(db.WorkflowRejected)
def rejected_workflow(error):
    status, message = _workflow_error(error)
    return render_template('error.html', code=status, title='Chưa thể thực hiện', detail=message), status


@pages.route('/staff/members/new', methods=['GET', 'POST'])
def staff_register():
    _workflow_role('staff')
    if request.method == 'POST':
        return _register_member(at_counter=True)
    return _registration_form(at_counter=True)


@pages.route('/staff/members', methods=['GET', 'POST'])
def staff_members():
    staff = _workflow_role('staff')
    query = ''
    if request.method == 'POST':
        auth.require_csrf()
        try:
            membership.validate_fields(request.form, ('q',))
        except membership.InvalidForm:
            abort(400)
        query = request.form.get('q', '').strip()
    if len(query) > 100 or '\0' in query:
        abort(400)
    members = db.workflow('staff_members', staff.person_id, None, query or None, many=True)
    return render_template('local02/staff_members.html', members=members, query=query, token=auth.csrf_token())


@pages.get('/staff/members/<int:member_id>')
def staff_member(member_id):
    staff = _workflow_role('staff')
    if not 1 <= member_id <= 2_147_483_647:
        abort(404)
    from . import admin

    if admin.enabled():
        return redirect(url_for('pages.member_profile', member_id=member_id))
    members = db.workflow('staff_members', staff.person_id, member_id, None, many=True)
    if not members:
        abort(404)
    records = membership.contracts(staff.person_id, staff=True, member_id=member_id)
    return render_template('local02/contracts.html', profiles=members, records=records)


@pages.get('/member/plans')
def catalog():
    _workflow_role('member')
    group_only = request.args.get('benefit') == 'group'
    return render_template('local02/catalog.html', plans=catalog_plans(group_only), group_only=group_only)


def catalog_plans(group_only):
    plans = membership.plans()
    if not group_only:
        return plans
    return [plan for plan in plans if any(entry.key == 'group' and entry.state in ('finite', 'unlimited')
                                         for entry in plan['benefits'])]


@pages.get('/staff/plan-catalog')
def staff_plan_catalog():
    _workflow_role('staff')
    group_only = request.args.get('benefit') == 'group'
    return render_template('local02/catalog.html', plans=catalog_plans(group_only), advice=True, group_only=group_only)


@pages.route('/member/plans/<int:plan_id>', methods=['GET', 'POST'])
def plan_detail(plan_id):
    principal = _workflow_role('member')
    if not 1 <= plan_id <= 2_147_483_647:
        abort(404)
    key, error, status = str(uuid4()), None, 200
    if request.method == 'POST':
        auth.require_csrf()
        try:
            membership.validate_fields(request.form, ('amount', 'request_id'))
            key = membership.request_id(request.form.get('request_id'))
            amount = membership.quote(request.form.get('amount'))
            contract_id = db.workflow('create_contract', principal.person_id, plan_id, amount, key)[0]
        except (membership.InvalidForm, db.WorkflowRejected) as rejected:
            status, error = _workflow_error(rejected)
        else:
            flash('Đã lập hợp đồng. Vui lòng thanh toán tại quầy.')
            return redirect(url_for('pages.membership_detail', record_id=contract_id), 303)
    plans = membership.plans(plan_id)
    if not plans:
        abort(404)
    return render_template('local02/catalog.html', plan=plans[0], request_id=key,
                           token=auth.csrf_token(), error=error), status


@pages.get('/staff/contracts')
def staff_contracts():
    staff = _workflow_role('staff')
    status = request.args.get('status') or None
    if status is not None and status not in membership.STATUS:
        abort(400)
    return render_template('local02/contracts.html',
                           records=membership.contracts(staff.person_id, staff=True, status=status),
                           selected_status=status)


def _contract_details(actor, record_id, *, staff=False, error=None, status=200):
    if not 1 <= record_id <= 2_147_483_647:
        abort(404)
    records = membership.contracts(actor, staff=staff, contract_id=record_id)
    if not records:
        abort(404)
    from . import admin

    if staff and admin.enabled():
        contract = records[0]
        benefits = admin.execute('members', actor, 'benefits', contract['member_id'], str(record_id), many=True)
        effective = (contract['status'] == 'ACTIVE' and contract['start'] is not None
                     and contract['end'] is not None and contract['start'] <= date.today() <= contract['end'])
        benefits = [(name, quota, used, effective) for _, name, quota, used in benefits]
    else:
        benefits = () if staff else db.workflow('benefits', actor, record_id, many=True)
    return render_template('local02/contract.html', service_label=membership.service_label, contract=records[0], staff=staff,
                           token=auth.csrf_token(), benefits=benefits, error=error), status


@pages.get('/staff/contracts/<int:record_id>')
def staff_contract(record_id):
    staff = _workflow_role('staff')
    return _contract_details(staff.person_id, record_id, staff=True)


@pages.post('/staff/contracts/<int:record_id>/payment', endpoint='staff_payment')
@pages.post('/staff/contracts/<int:record_id>/activate', endpoint='staff_activate')
def staff_contract_action(record_id):
    staff = _workflow_role('staff')
    auth.require_csrf()
    if not 1 <= record_id <= 2_147_483_647:
        abort(404)
    try:
        if request.path.endswith('/payment'):
            membership.validate_fields(request.form, ('amount', 'method', 'mode'))
            method, mode = request.form.get('method'), request.form.get('mode')
            if method not in membership.METHOD or mode not in ('now', 'later'):
                raise membership.InvalidForm('Chọn cách thanh toán và thời điểm kích hoạt.')
            amount = membership.quote(request.form.get('amount'))
            db.workflow('collect_payment', staff.person_id, record_id, amount, method, mode == 'now')
            flash('Đã ghi nhận thanh toán.')
        else:
            membership.validate_fields(request.form, ())
            db.workflow('activate', staff.person_id, record_id)
            flash('Đã kích hoạt gói tập.')
    except (membership.InvalidForm, db.WorkflowRejected) as rejected:
        status, error = _workflow_error(rejected)
        return _contract_details(staff.person_id, record_id, staff=True, error=error, status=status)
    return redirect(url_for('pages.staff_contract', record_id=record_id), 303)


def private_area(role):
    principal = _authorize(role)
    from . import admin, schedule

    if role == 'management' and admin.enabled():
        return admin.dashboard()
    records = ()
    if role == 'member':
        if _local02():
            contracts = membership.contracts(principal.person_id)
            today = date.today()
            current = next((c for c in contracts if c['status'] == 'ACTIVE' and c['start'] and c['end']
                            and c['start'] <= today <= c['end']), None)
            benefits = db.workflow('benefits', principal.person_id, current['id'], many=True) if current else ()
            upcoming = schedule.member_upcoming(principal.person_id, datetime.now()) if schedule.enabled() else ()
            return render_template('local02/member_home.html', contracts=contracts, current=current, benefits=benefits,
                                   days_left=(current['end']-today).days if current else None, upcoming=upcoming)
        records = db.list_memberships(principal.person_id)
    elif role == 'trainer':
        records = db.list_trainer_sessions(principal.person_id)
    return render_template('private.html', title=ROLE_NAVIGATION[role][0], role=role, records=records,
                           local02=_local02())


def unavailable_private_page(role, path=None):
    _authorize(role)
    abort(405 if request.method == 'POST' else 404)


def _scoped_record(role, record_id, read):
    principal = _authorize(role)
    if not 1 <= record_id <= 2_147_483_647:
        abort(404)
    record = read(principal.person_id, record_id)
    if record is None:
        abort(404)
    return record


@pages.get('/member/membership/<int:record_id>')
def membership_detail(record_id):
    if _local02():
        return _contract_details(_workflow_role('member').person_id, record_id)
    record = _scoped_record('member', record_id, db.get_membership)
    return render_template('private.html', title='Chi tiết gói tập', role='member',
                           details=zip(('Gói tập', 'Trạng thái', 'Ngày bắt đầu', 'Ngày hết hạn'), record))


@pages.get('/trainer/session/<int:record_id>')
def trainer_session_detail(record_id):
    record = _scoped_record('trainer', record_id, db.get_trainer_session)
    return render_template('private.html', title='Chi tiết buổi tập', role='trainer',
                           details=zip(('Loại buổi', 'Phòng', 'Bắt đầu', 'Kết thúc'), record))


for role in ROLE_NAVIGATION:
    pages.add_url_rule(f'/{role}', f'{role}_area', private_area, defaults={'role': role})
    pages.add_url_rule(f'/{role}', f'{role}_write', unavailable_private_page, defaults={'role': role}, methods=['POST'])
    pages.add_url_rule(f'/{role}/<path:path>', f'{role}_page', unavailable_private_page,
                       defaults={'role': role}, methods=['GET', 'POST'])
