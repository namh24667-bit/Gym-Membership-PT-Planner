"""LOCAL-03 routes and request validation."""
from datetime import date, datetime, timedelta
from itertools import groupby
import re
from typing import NamedTuple

from flask import abort, current_app, flash, redirect, render_template, request, url_for

from . import auth, db, membership
from .class_booking import CLASS_STATES, REASONS, GroupClass, legacy_class
from .routes import _authorize, _workflow_error, pages
from .staff_directory_sql import PAGE_SIZE


TEACHING_KINDS = {'PERSONAL': 'PT cá nhân', 'GROUP': 'Lớp nhóm'}
TEACHING_STATES = {'upcoming': ('Sắp tới', 'AVAILABLE'), 'in_progress': ('Đang diễn ra', 'PENDING_PAYMENT'),
                   'ended': ('Đã kết thúc', 'EXPIRED')}


class TrainerSlot(NamedTuple):
    id: int
    kind: str
    start: datetime
    end: datetime
    room: str
    name: str | None
    member: str | None
    capacity: int | None
    enrolled: int | None
    remaining: int | None
    state: str


class TrainerDetail(NamedTuple):
    id: int
    kind: str
    start: datetime
    end: datetime
    room: str
    name: str | None
    member: str | None
    member_id: int | None
    focus: str | None
    capacity: int | None
    enrolled: int | None
    remaining: int | None
    state: str
    class_state: str | None
    employment: str
    phone: str | None


def teaching_week(day):
    return day.strftime('%G-W%V')


def teaching_dates(today):
    show_today = request.args.get('day') == 'today'
    week = request.args.get('week') or teaching_week(today)
    try:
        if not re.fullmatch(r'[0-9]{4}-W[0-9]{2}', week):
            raise ValueError
        monday = date.fromisocalendar(int(week[:4]), int(week[6:]), 1)
        sunday = monday + timedelta(days=6)
        if monday.year < 2 or sunday.year > 9998:
            raise ValueError
    except (ValueError, OverflowError):
        raise membership.InvalidForm('Chọn tuần hợp lệ.') from None
    return (today, today) if show_today else (monday, sunday)


def teaching_filter(name, choices):
    value = request.args.get(name) or None
    if value is not None and value not in choices:
        raise membership.InvalidForm('Giá trị lọc lịch không hợp lệ.')
    return value


def teaching_page():
    page = integer(request.args.get('page', '1'))
    if page > 2_147_483_647 // PAGE_SIZE:
        raise membership.InvalidForm('Số trang không hợp lệ.')
    return page


def teaching_pagination(page, total, endpoint, **params):
    pages_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > pages_count:
        abort(404)
    return dict(total=total, page=page, page_count=pages_count,
                previous=url_for(endpoint, **params, page=page - 1) if page > 1 else None,
                following=url_for(endpoint, **params, page=page + 1) if page < pages_count else None)


def trainer_agenda(actor):
    today = date.today()
    first, last = teaching_dates(today)
    kind, state = teaching_filter('kind', TEACHING_KINDS), teaching_filter('status', TEACHING_STATES)
    page = teaching_page()
    results = run('schedule', actor, 'teach_agenda', None, kind, state, first, last, None, (page - 1) * PAGE_SIZE, many=True)
    if not results:
        abort(403)
    total, pt, groups, upcoming, ended, running, hired, employment = results[0][:8]
    selected = dict(kind=kind, status=state)
    week = teaching_week(first)
    day = 'today' if first == last else None
    base = 'pages.trainer_schedule'
    days = [(-7, 'Tuần trước'), (7, 'Tuần sau')] if not day else []
    shortcuts = [(label, url_for(base, week=teaching_week(first + timedelta(days=shift)), **selected)) for shift, label in days]
    return render_template(
        'local03/teaching_agenda.html', rows=[TrainerSlot(*row[8:]) for row in results if row[8] is not None],
        first=first, last=last, week=week, day=day, kind=kind, state=state,
        kinds=TEACHING_KINDS, states=TEACHING_STATES, shortcuts=shortcuts, hired=hired, employment=employment,
        state_options=[(key, label) for key, (label, _) in TEACHING_STATES.items()],
        counts=(('Buổi PT', pt), ('Lớp nhóm', groups), ('Sắp tới', upcoming), ('Đang diễn ra', running), ('Đã kết thúc', ended)),
        today_url=url_for(base, day='today', **selected), week_url=url_for(base, **selected),
        **teaching_pagination(page, total, base, week=week, day=day, **selected))


def phone_link(phone):
    if not phone or not re.fullmatch(r'\+?[0-9 ().-]+', phone):
        return None
    number = re.sub(r'[ ().-]', '', phone)
    return 'tel:' + number if re.fullmatch(r'\+?[0-9]{9,15}', number) else None


def enabled():
    config = current_app.config
    return config.get('LOCAL03_ENABLED') and db.is_workflow_qa(config) and auth.enabled()


def actor_for(role):
    principal = _authorize(role)
    if not enabled() or not auth.allowed_transport():
        abort(403)
    return principal.person_id


def run(name, *params, many=False):
    return db.workflow(name, *params, many=many, group='local03')


def read(actor, scope, key=None):
    return run('schedule', actor, scope, key, many=True)


def member_upcoming(actor, now):
    items = [(start, end, 'PT cá nhân', coach, room, sid)
             for sid, coach, room, start, end, _ in read(actor, 'member_pt') if end > now]
    items.extend((start, end, name, None, None, None)
                 for _, name, start, end, state, *_ in read(actor, 'member_group') if state == 'SUCCESS' and end > now)
    return sorted(items, key=lambda item: item[0])[:4]


def days_for_agenda(rows, today):
    ordered = sorted(rows, key=lambda item: item[2])
    groups = [(day, list(items)) for day, items in groupby(ordered, key=lambda item: item[2].date())]
    return sorted(groups, key=lambda group: (group[0] < today, abs((group[0] - today).days)))


def integer(value, minimum=1):
    if not re.fullmatch(r'[0-9]{1,10}', value or '') or not minimum <= int(value) <= 2_147_483_647:
        raise membership.InvalidForm('Mã lựa chọn hoặc số lượng không hợp lệ.')
    return int(value)


def slot(form):
    def parse(field):
        value = form.get(field, '')
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}', value):
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.year < 2000:
            raise ValueError
        return parsed

    try:
        start, end = parse('start'), parse('end')
    except ValueError:
        raise membership.InvalidForm('Nhập ngày giờ bắt đầu và kết thúc hợp lệ.') from None
    if start >= end:
        raise membership.InvalidForm('Giờ kết thúc phải sau giờ bắt đầu.')
    return integer(form.get('trainer')), integer(form.get('room')), start, end


def label(value, limit):
    text = (value or '').strip()
    if not text or len(text.encode('utf-16-le')) > 2 * limit or re.search(r'[\x00-\x1f\x7f]', text):
        raise membership.InvalidForm(f'Nhập nội dung hợp lệ, tối đa {limit} ký tự.')
    return text


def class_category(actor, value):
    category = label(value, 50)
    if current_app.config.get('CLASS_RULES_ENABLED'):
        supported, = db.workflow('classes', actor, 'category', None, None, None, None, None, None,
                                 category, group='local04')
        if not supported:
            raise membership.InvalidForm('Nhập bộ môn đã được hỗ trợ để hội viên có thể đặt lớp.')
    return category


def invalid(error):
    status, message = _workflow_error(error)
    return render_template('error.html', code=status, title='Chưa thể thực hiện', detail=message), status


@pages.get('/member/schedule')
def member_schedule():
    actor = actor_for('member')
    return render_template('local03/schedule.html', mode='member', pt=read(actor, 'member_pt'),
                           groups=read(actor, 'member_group'), token=auth.csrf_token())


@pages.get('/member/pt/<int:record_id>')
def member_pt_detail(record_id):
    actor = actor_for('member')
    if not 1 <= record_id <= 2_147_483_647:
        abort(404)
    rows = read(actor, 'member_pt', record_id)
    if not rows:
        abort(404)
    return render_template('local03/schedule.html', mode='member', pt=rows, groups=(),
                           token=auth.csrf_token())


@pages.route('/member/pt', methods=['GET', 'POST'])
@pages.route('/management/classes/new', methods=['GET', 'POST'], endpoint='new_group_class')
def schedule_form():
    manager = request.endpoint == 'pages.new_group_class'
    actor = actor_for('management' if manager else 'member')
    form, error, status = {}, None, 200
    fields = ('trainer', 'room', 'start', 'end', 'name', 'category', 'capacity') if manager else (
        'trainer', 'room', 'start', 'end', 'focus')
    if request.method == 'POST':
        auth.require_csrf()
        form = {key: request.form.get(key, '') for key in fields}
        try:
            membership.validate_fields(request.form, fields)
            selected = slot(form)
            if manager:
                run('create_group', actor, *selected, label(form['name'], 100), class_category(actor, form['category']),
                    integer(form['capacity']))
                flash('Đã tạo lớp nhóm.')
                return redirect(url_for('pages.management_schedule'), 303)
            reservation = run('book_pt', actor, *selected, label(form['focus'], 200))
            flash('Đã ghi nhận lịch PT.')
            return redirect(url_for('pages.member_pt_detail', record_id=reservation[0]), 303)
        except (membership.InvalidForm, db.WorkflowRejected) as rejected:
            status, error = _workflow_error(rejected)
    trainers = read(actor, 'trainers')
    selected_trainer = next((row[0] for row in trainers if str(row[0]) == request.args.get('trainer')), None)
    if selected_trainer is not None and not form:
        form['trainer'] = str(selected_trainer)
    busy = read(actor, 'busy', selected_trainer) if selected_trainer else ()
    return render_template('local03/form.html', manager=manager, trainers=trainers, rooms=read(actor, 'rooms'),
                           trainer_options=[(t[0], t[1]) for t in trainers],
                           busy=busy, inspected=selected_trainer, form=form, error=error,
                           token=auth.csrf_token()), status


def class_rows(actor, session_id=None):
    try:
        return [GroupClass(*row) for row in read(actor, 'class_eligibility', session_id)]
    except db.WorkflowRejected as error:
        # A portable database can still serve the older read scope during the staged upgrade.
        if error.args[0] != 52201:
            raise
        return [legacy_class(row) for row in read(actor, 'classes', session_id)]


def class_week():
    value = request.args.get('week', '')
    return value if re.fullmatch(r'[0-9]{4}-W(?:0[1-9]|[1-4][0-9]|5[0-3])', value) else None


def class_page(*, records=(), item=None, error=None, status=200, detail=False):
    return render_template('local03/class_detail.html' if detail else 'local03/classes.html',
                           records=records, item=item, error=error, selected_week=class_week(),
                           class_states=CLASS_STATES, reasons=REASONS, token=auth.csrf_token()), status


@pages.get('/member/classes')
def member_classes():
    return class_page(records=class_rows(actor_for('member')))


@pages.get('/member/classes/<int:session_id>')
def member_class_detail(session_id):
    actor = actor_for('member')
    if not 1 <= session_id <= 2_147_483_647:
        abort(404)
    rows = class_rows(actor, session_id)
    if not rows:
        abort(404)
    return class_page(item=rows[0], detail=True)


@pages.post('/member/classes/<int:session_id>/book')
@pages.post('/member/bookings/<int:session_id>/cancel', endpoint='cancel_group')
def group_action(session_id):
    actor = actor_for('member')
    auth.require_csrf()
    if not 1 <= session_id <= 2_147_483_647:
        abort(404)
    cancel = request.endpoint == 'pages.cancel_group'
    try:
        if cancel:
            membership.validate_fields(request.form, ())
            refunded = run('cancel_group', actor, session_id)[0]
            flash('Đã hủy chỗ và hoàn một lượt.' if refunded else 'Đã hủy chỗ. Không có lượt được hoàn.')
        else:
            membership.validate_fields(request.form, ('last_booking',))
            run('book_group', actor, session_id, integer(request.form.get('last_booking'), 0))
            flash('Đã đăng ký lớp nhóm.')
    except (membership.InvalidForm, db.WorkflowRejected) as error:
        status, message = _workflow_error(error)
        if status != 409:
            return invalid(error)
        if cancel:
            return render_template('local03/class_detail.html', error=message, cancelling=True), status
        rows = class_rows(actor, session_id)
        return class_page(item=rows[0] if rows else None, detail=True, error=message, status=status)
    return redirect(url_for('pages.member_schedule'), 303)


@pages.get('/trainer/schedule')
@pages.route('/trainer/schedule/<int:record_id>', methods=['GET', 'POST'], endpoint='trainer_schedule_detail')
def trainer_schedule(record_id=None):
    actor = actor_for('trainer')
    if record_id is not None and not 1 <= record_id <= 2_147_483_647:
        abort(404)
    if request.method == 'POST':
        auth.require_csrf()
        try:
            membership.validate_fields(request.form, ('focus',))
            run('focus', actor, record_id, label(request.form.get('focus'), 200))
        except (membership.InvalidForm, db.WorkflowRejected) as error:
            return invalid(error)
        flash('Đã cập nhật mục tiêu PT.')
        return redirect(url_for('pages.trainer_schedule_detail', record_id=record_id), 303)
    try:
        if record_id is None:
            return trainer_agenda(actor)
        rows = run('schedule', actor, 'teach_detail', record_id, many=True)
        if not rows:
            abort(404)
        item = TrainerDetail(*rows[0])
        return render_template('local03/teaching_detail.html', item=item, class_states=CLASS_STATES,
                               states=TEACHING_STATES, phone_href=phone_link(item.phone), token=auth.csrf_token())
    except db.WorkflowRejected as error:
        if error.args[0] != 52201:
            raise
        # Keep the previous scoped UI available while an existing install applies the SQL update.
        return legacy_trainer_schedule(actor, record_id)


def legacy_trainer_schedule(actor, record_id):
    rows = read(actor, 'trainer', record_id)
    if record_id is not None and not rows:
        abort(404)
    participants = read(actor, 'participants', record_id) if record_id and rows[0][1] == 'GROUP' else ()
    now = datetime.now()
    return render_template('local03/schedule.html', mode='trainer', records=rows, details=record_id is not None,
                           agenda=days_for_agenda(rows, now.date()), now=now, participants=participants,
                           token=auth.csrf_token())


@pages.get('/trainer/schedule/<int:record_id>/participants')
def trainer_roster(record_id):
    actor = actor_for('trainer')
    if not 1 <= record_id <= 2_147_483_647:
        abort(404)
    page = teaching_page()
    try:
        rows = run('schedule', actor, 'teach_roster', record_id, None, None, None, None, None,
                   (page - 1) * PAGE_SIZE, many=True)
    except db.WorkflowRejected as error:
        if error.args[0] != 52201:
            raise
        abort(503, description='Danh sách lớp sẽ khả dụng sau khi cập nhật tra cứu lịch.')
    if not rows:
        abort(404)
    total, name = rows[0][:2]
    return render_template('local03/teaching_roster.html', name=name, record_id=record_id,
                           roster=[tuple(row[2:]) for row in rows if row[2] is not None],
                           **teaching_pagination(page, total, 'pages.trainer_roster', record_id=record_id))


@pages.get('/staff/schedule')
@pages.route('/management/schedule', methods=['GET', 'POST'], endpoint='management_schedule')
def operations_schedule():
    manager = request.endpoint == 'pages.management_schedule'
    actor = actor_for('management' if manager else 'staff')
    if request.method == 'POST':
        auth.require_csrf()
        try:
            membership.validate_fields(request.form, ())
            result = run('expire', actor, True)[0]
        except (membership.InvalidForm, db.WorkflowRejected) as error:
            return invalid(error)
        flash(f'Đã cập nhật {result} gói hết hạn.')
        return redirect(url_for('pages.management_schedule'), 303)
    now = datetime.now()
    return render_template('local03/schedule.html', mode='operations', manager=manager,
                           agenda=days_for_agenda(read(actor, 'staff'), now.date()), now=now, token=auth.csrf_token())
