"""Deterministic operational history for an empty CleanDemo installation."""
from calendar import monthrange
from collections import Counter
from datetime import datetime, time, timedelta
from random import Random
import re

from app.auth import HASHER

SEED = 20261124
TARGETS = ('IronPulse_CleanDemo', 'IronPulse_CleanDemoQA')
MARKER = 'local05d-c.synthetic.v1'
MARKER_PROPERTY = 'IronPulseSyntheticDataset'
REFERENCE_PROPERTY = 'IronPulseSyntheticReference'


def fresh_target(database):
    return bool(re.fullmatch(r'IronPulse_Clean[A-Za-z0-9]{0,27}QA', database, re.IGNORECASE)
                and not database.casefold().endswith('restoreqa'))
SERVICES = (
    ('Tập gym', 'Sử dụng khu tập gym tự do'), ('Lớp học nhóm', 'Cardio, phục hồi và sức mạnh theo lớp'),
    ('PT cá nhân', 'Tập một kèm một cùng huấn luyện viên'), ('Yoga', 'Quota riêng cho các lớp Yoga'),
    ('Đạp xe trong nhà', 'Quota riêng cho các lớp đạp xe'), ('Zumba', 'Quota riêng cho các lớp Zumba'),
    ('Boxing Fitness', 'Quota riêng cho các lớp Boxing'),
)
# The original catalogue's duration, price, and service-specific quota. Gym is unlimited.
PLANS = (
    ('Gym cơ bản', 1, 399000, {2: 8}), ('Gym cơ bản', 3, 1050000, {2: 18}),
    ('Gym cơ bản', 6, 1950000, {2: 30, 3: 3}), ('Gym tiêu chuẩn', 1, 550000, {2: 12}),
    ('Gym tiêu chuẩn', 3, 1490000, {2: 30, 3: 4}),
    ('Gym tiêu chuẩn đa bộ môn', 6, 2790000, {2: 48, 3: 6, 4: 10, 5: 8}),
    ('Gym đồng hành PT', 1, 2190000, {2: 4, 3: 8}), ('Gym đồng hành PT', 3, 5990000, {2: 12, 3: 18}),
    ('Gym nâng cao đa bộ môn', 6, 4390000, {2: 60, 3: 24, 4: 12, 5: 8}),
    ('Gym nâng cao đa bộ môn', 12, 7990000, {2: 96, 3: 32, 4: 24, 5: 20, 6: 16, 7: 12}),
    ('Gym và Yoga', 1, 690000, {2: 4, 4: 8}), ('Gym và Yoga', 3, 1790000, {2: 12, 4: 30}),
    ('Gym và đạp xe trong nhà', 3, 1890000, {2: 8, 5: 24}),
    ('Gym và Zumba', 1, 650000, {2: 4, 6: 12}), ('Gym và Zumba', 3, 1750000, {2: 12, 6: 36}),
    ('Gym và Boxing', 1, 890000, {2: 4, 7: 12}), ('Gym, Boxing và PT', 3, 2490000, {2: 8, 3: 4, 7: 30}),
    ('Gym toàn diện đa bộ môn', 6, 5490000, {2: 48, 3: 12, 4: 20, 5: 20, 6: 20, 7: 20}),
)
CATALOG = tuple((pid, months_, price, sid, quota) for pid, (_, months_, price, quotas)
                in enumerate(PLANS, 1) for sid, quota in {1: -1, **quotas}.items())
ROOMS = (
    ('Khu Cardio', 'GYM'), ('Khu Cardio tầng hai', 'GYM'), ('Khu máy sức mạnh', 'GYM'),
    ('Khu tạ tự do', 'GYM'), ('Phòng tập thể lực 01', 'GYM'), ('Khu tập chức năng', 'GYM'),
    ('Phòng tập thể lực 02', 'GYM'),
    ('Phòng huấn luyện cá nhân 01', 'PT'), ('Phòng huấn luyện cá nhân 02', 'PT'),
    ('Phòng huấn luyện cá nhân 03', 'PT'), ('Phòng huấn luyện cá nhân 04', 'PT'),
    ('Phòng huấn luyện cá nhân 05', 'PT'),
    ('Phòng tập nhóm A', 'STUDIO'), ('Phòng tập nhóm B', 'STUDIO'), ('Phòng Yoga', 'STUDIO'),
    ('Phòng đạp xe trong nhà', 'STUDIO'), ('Phòng Zumba', 'STUDIO'), ('Phòng Boxing', 'STUDIO'),
    ('Phòng giãn cơ và phục hồi', 'STUDIO'), ('Phòng tập nhóm C', 'STUDIO'),
)
# category, service, compatible room, capacity, display names, coaching certificate
CLASSES = (
    ('CARDIO', 2, 13, 16, ('Cardio toàn thân', 'Aerobic cơ bản'), 'Huấn luyện nhóm cơ bản'),
    ('STRENGTH', 2, 14, 14, ('Sức mạnh toàn thân', 'Body Pump cơ bản'), 'Huấn luyện nhóm cơ bản'),
    ('RECOVERY', 2, 19, 12, ('Giãn cơ và phục hồi', 'Pilates cơ bản'), 'Huấn luyện nhóm cơ bản'),
    ('YOGA', 4, 15, 12, ('Yoga cơ bản', 'Yoga thư giãn'), 'Yoga Alliance'),
    ('CYCLING', 5, 16, 10, ('Đạp xe theo nhịp', 'Đạp xe sức bền'), 'Đạp xe trong nhà'),
    ('ZUMBA', 6, 17, 18, ('Zumba năng động', 'Zumba cơ bản'), 'Hướng dẫn Zumba'),
    ('BOXING', 7, 18, 10, ('Boxing Fitness cơ bản', 'Cardio với Boxing'), 'Boxing Fitness'),
)
EQUIPMENT = (
    ('Máy chạy bộ', (1, 2), 9, 'Kiểm tra dây curoa và căn băng chạy'),
    ('Xe đạp tập', (1, 2), 7, 'Kiểm tra bàn đạp và bánh đà'),
    ('Máy elliptical', (1, 2), 6, 'Bôi trơn trục truyền động'),
    ('Máy kéo cáp', (3, 5), 7, 'Kiểm tra cáp và thay tay cầm'),
    ('Máy đạp chân', (3, 5, 7), 6, 'Kiểm tra chốt an toàn và ray trượt'),
    ('Ghế đẩy ngực', (4, 5), 6, 'Kiểm tra chân ghế và đệm tựa'),
    ('Giàn squat', (4, 7), 5, 'Kiểm tra khung và chốt đỡ'),
    ('Bộ kettlebell', (6, 8, 9, 10, 11, 12), 8, 'Kiểm tra bề mặt tay nắm'),
    ('Bộ tạ tay', (4, 8, 9, 10, 11, 12), 8, 'Kiểm tra lớp bọc và giá đỡ'),
    ('Bộ thảm tập', (13, 14, 15, 19, 20), 11, 'Vệ sinh và kiểm tra độ bám của thảm'),
    ('Bục aerobic', (13, 14, 17, 20), 8, 'Kiểm tra khớp đế và mặt chống trượt'),
    ('Xe đạp lớp nhóm', (16,), 12, 'Cân chỉnh bàn đạp và tăng chỉnh kháng lực'),
    ('Bao đấm', (18,), 7, 'Kiểm tra dây treo và đường may'),
)
ACCOUNTS = {'member-pt': 1, 'member-class': 2, 'member-expired': 3, 'member-quota': 4,
            'trainer-pt': 1101, 'trainer-class': 1102, 'manager': 1171, 'staff': 1176}
SURNAMES = 'Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý'.split()
MIDDLE = 'Anh Bảo Đức Gia Hải Hoài Hồng Khánh Kim Mai Minh Ngọc Nhật Như Phúc Quang Quốc Tâm Thanh Thiên Thảo Thùy Trọng Tuyết Văn Xuân'.split()
GIVEN = {
    'MALE': 'Bách Bình Cường Duy Đạt Hào Hiếu Hòa Hoàng Huy Hùng Khang Khiêm Khôi Kiên Long Lâm Nam Nghĩa Nhân Phong Quân Quý Sơn Thành Thắng Thiện Toàn Trung Tuấn Tùng Vinh Việt Vũ'.split(),
    'FEMALE': 'An Ánh Chi Diệp Dung Duyên Giang Hà Hạnh Hân Hiền Hoa Huệ Hương Huyền Lan Linh Ly Mi Na Nga Ngân Nhi Nhiên Nhung Oanh Phương Quỳnh Thảo Thi Thư Trang Trâm Trinh Tú Uyên Vân Vi Vy Yến'.split(),
}
DEMO_NAMES = {1: 'Nguyễn Minh Anh', 2: 'Trần Hoàng Long', 3: 'Võ Ngọc Hân', 4: 'Đặng Quang Minh',
              1101: 'Lê Minh Khang', 1102: 'Phạm Tuấn Kiệt', 1171: 'Nguyễn Quốc Huy', 1176: 'Trần Thảo Linh'}
DAY = timedelta(days=1)

FIELDS = (
    ('service_type', 'service_type_id service_name description', True),
    ('room', 'room_id room_name room_type status', True),
    ('membership_plan', 'plan_id plan_name duration_months base_price description is_for_sale', True),
    ('plan_inclusion', 'plan_id service_type_id quota_per_cycle', False),
    ('equipment', 'equipment_id equipment_name serial_number room_id status', True),
    ('person', 'person_id ssn full_name email phone date_of_birth gender address created_at password_hash', True),
    ('staff', 'person_id position hire_date employment_status', False),
    ('trainer', 'person_id hire_date employment_status', False),
    ('trainer_certification', 'person_id certification', False),
    ('member', 'person_id emergency_contact_phone join_date', False),
    ('membership', 'membership_id person_id plan_id start_date end_date status total_price created_at', True),
    ('payment', 'payment_id membership_id amount payment_time payment_method recorded_by', True),
    ('session', 'session_id trainer_id room_id start_time end_time session_type created_at', True),
    ('pt_session', 'session_id person_id training_focus', False),
    ('group_class_session', 'session_id class_name category max_capacity', False),
    ('booking', 'booking_id person_id session_id booked_at booking_status cancelled_at', True),
    ('member_service_usage', 'usage_id membership_id service_type_id session_id used_at usage_status booking_id', True),
    ('equipment_maintenance_log', 'maintenance_id equipment_id start_date cost end_date description', True),
)


def months(day, offset):
    year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    return day.replace(year=year, month=month + 1, day=min(day.day, monthrange(year, month + 1)[1]))


def at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute))


def asset_rows(data, ref):
    for label, rooms, count, description in EQUIPMENT:
        for n in range(1, count + 1):
            key = len(data['equipment']) + 1
            retired = key % 13 == 0 and key <= 88
            pending = key % 9 == 0 and not retired and key <= 88
            room = None if key in (87, 88, 89, 90, 91, 92, 93, 94) else rooms[(n - 1) % len(rooms)]
            status = 'RETIRED' if retired else 'MAINTENANCE' if pending else 'ACTIVE'
            data['equipment'].append((key, f'{label} số {n:02d}', f'TB{key:04d}', room, status))
            if room is None:
                continue
            history = [(ref - (110 + key % 27) * DAY, 2 + key % 3)]
            if key % 2:
                history.append((ref - (49 + key % 14) * DAY, 1))
            if pending:
                history.append((ref - (1 + key % 5) * DAY, None))
            for opened, duration in history:
                data['equipment_maintenance_log'].append((len(data['equipment_maintenance_log']) + 1,
                    key, opened, 90000 + (key % 21) * 10000, opened + duration * DAY if duration else None, description))


def people_rows(data, ref, rng, passwords):
    credential = {}
    alias_by_id = {key: alias for alias, key in ACCOUNTS.items()}
    for key in range(1, 1201):
        gender = 'FEMALE' if key in (1, 3, 1176) else 'MALE' if key in DEMO_NAMES else rng.choice(tuple(GIVEN))
        first, middle = rng.choice(GIVEN[gender]), rng.choice(MIDDLE)
        given = (first,) if rng.randrange(7) == 0 or first == middle else (middle, first)
        name = DEMO_NAMES.get(key) or ' '.join((rng.choice(SURNAMES), *given))
        alias = alias_by_id.get(key)
        email = f'{alias or f"gym-{key:04d}"}@example.invalid'
        age = rng.randint(19 if key <= 1100 else 24, 62 if key <= 1100 else 48)
        birth = ref - (age * 365 + rng.randint(2, 364)) * DAY
        if key <= 1100:
            created = ref - rng.randint(550, 1500) * DAY if key < 381 else ref - rng.randint(150, 320) * DAY
            if 623 <= key <= 650:
                created = ref - rng.randint(15, 22) * DAY
            data['member'].append((key, f'00042{key:05d}', created))
        else:
            created = ref - rng.randint(700, 1400) * DAY
            if key <= 1170:
                status = 'ACTIVE' if key <= 1157 else 'ON_LEAVE' if key <= 1166 else 'TERMINATED'
                data['trainer'].append((key, created, status))
                data['trainer_certification'].append((key, ('ACE', 'NASM', 'ISSA', 'ACSM')[key % 4]))
                class_index = 6 if key == 1102 else (key - 1101) % len(CLASSES)
                data['trainer_certification'].append((key, CLASSES[class_index][-1]))
            else:
                status = 'ACTIVE' if key <= 1195 else 'ON_LEAVE' if key <= 1198 else 'TERMINATED'
                position = 'Quản lý' if key <= 1175 else ('Lễ tân', 'Tư vấn hội viên', 'Kế toán', 'Kỹ thuật viên')[(key - 1176) % 4]
                data['staff'].append((key, position, created, status))
        password_hash = '!disabled-local05d'
        if alias and passwords:
            password_hash = HASHER.hash(passwords[alias])
            credential[alias] = {'name': name, 'email': email, 'password': passwords[alias]}
        data['person'].append((key, f'00041{key:07d}', name, email, f'00041{key:05d}', birth, gender,
                               'Khu dân cư mô phỏng', at(created, 8), password_hash))
    return credential


def contract_rows(data, ref, rng):
    plan_ids = tuple(range(1, len(PLANS) + 1))
    passes = []
    collectors = [key for key, position, _, status in data['staff']
                  if status == 'ACTIVE' and position in ('Lễ tân', 'Kế toán', 'Quản lý')]

    def add(person, plan, status, start, day):
        key = len(data['membership']) + 1
        duration, price = PLANS[plan - 1][1:3]
        end = months(start, duration) if start else None
        if start:
            passes.append((key, person, start, end, {1: -1, **PLANS[plan - 1][3]}))
        paid = status != 'PENDING_PAYMENT'
        data['membership'].append((key, person, plan, start, end, status, price if paid else None, at(day, 9)))
        if paid:
            data['payment'].append((len(data['payment']) + 1, key, price, at(day, 10),
                                    rng.choice(('BANK_TRANSFER', 'BANK_TRANSFER', 'CASH')), rng.choice(collectors)))

    for person, _, join in data['member']:
        plan = {1: 7, 2: 18, 3: 1, 4: 1}.get(person, rng.choice(plan_ids))
        if person != 3 and person <= 650:
            start = ref - (16 if person in (1, 2, 4) else rng.randint(4, 13)) * DAY
            status = 'ACTIVE'
        elif person == 3 or person <= 950:
            hint = ref - rng.randint(3, 137) * DAY
            start = max(join, months(hint, -PLANS[plan - 1][1]))
            # Preserve a realistic enrolment date for newly joined members and long contracts.
            if months(start, PLANS[plan - 1][1]) >= ref:
                plan = rng.choice((1, 4, 7, 11, 14, 16))
                start = max(join, months(hint, -1))
            status = 'EXPIRED'
        else:
            start = None
            status = 'PENDING_ACTIVATION' if person <= 1020 else 'PENDING_PAYMENT'
        if 5 <= person <= 384:
            previous_plan = rng.choice(plan_ids if person <= 300 else (1, 3, 7, 8, 11, 17, 18))
            cutoff = start - rng.randint(7, 44) * DAY
            old = months(cutoff, -PLANS[previous_plan - 1][1])
            if old < join:
                previous_plan, old = 1, months(cutoff, -1)
            if old < join:
                raise ValueError('Member joined too recently for the modeled renewal.')
            add(person, previous_plan, 'EXPIRED', old, old)
        add(person, plan, status, start, start or ref - rng.randint(1, 20) * DAY)
        if 5 <= person <= 24:
            add(person, rng.choice(plan_ids), 'PENDING_PAYMENT', None, ref - rng.randint(1, 3) * DAY)
    return passes


def schedule_rows(data, passes, as_of, rng):
    ref = as_of.date()
    coaches = [row[0] for row in data['trainer'] if row[2] == 'ACTIVE']
    certificates = set(data['trainer_certification'])
    slots, roster = [], {'accounts': ACCOUNTS.copy()}
    for offset in range(-134, 16):
        day = ref + offset * DAY
        for i, (hour, minute) in enumerate(((7, 0), (9, 0), (17, 30), (19, 0))):
            category = 6 if (offset, i) == (2, 0) else (offset * 4 + i) % len(CLASSES)
            slots.append((at(day, hour, minute), 'GROUP', category, (offset, i)))
        for i in range(2 if offset % 3 == 0 else 3):
            slots.append((at(day, (10, 13, 16)[i]), 'PERSONAL', i, (offset, i)))
    spent = Counter()
    reserved = set(range(1, 5))
    reserved_class_days = set(range(-13, -5))

    def candidates(service, starts, ends, specific=None):
        for key, person, first, last, quotas in passes:
            if (person in reserved if specific is None else person != specific):
                continue
            quota = quotas.get(service, 0)
            made = max(at(first, 11), min(starts - 3 * DAY, as_of - timedelta(minutes=20)))
            if (first <= starts.date() and ends.date() <= last and made < starts and made <= as_of
                    and (quota == -1 or spent[key, service] < quota)):
                yield key, person, made

    for starts, kind, spec, (offset, index) in sorted(slots):
        key = len(data['session']) + 1
        ends = starts + timedelta(minutes=50 if kind == 'GROUP' else 55)
        if kind == 'PERSONAL':
            special = (offset, index) == (1, 0)
            chosen = list(candidates(3, starts, ends, 1 if special else None))
            if not chosen:
                raise RuntimeError(f'No valid PT allocation on day {offset}.')
            contract, person, made = rng.choice(chosen)
            coach = 1101 if special else rng.choice(coaches)
            room = rng.randint(8, 12)
            focus = rng.choice(('Kỹ thuật squat và lunge', 'Sức mạnh thân trên', 'Thăng bằng và linh hoạt', 'Sức bền toàn thân'))
            data['pt_session'].append((key, person, focus))
            data['member_service_usage'].append((len(data['member_service_usage']) + 1, contract, 3, key, made, 'USED', None))
            spent[contract, 3] += 1
            if special:
                roster['pt_session'] = key
        else:
            category, service, room, capacity, names, cert = CLASSES[spec]
            special = (offset, index) == (2, 0)
            coach = 1102 if special else rng.choice([person for person in coaches if (person, cert) in certificates])
            made = min(starts - 6 * DAY, as_of - DAY)
            data['group_class_session'].append((key, rng.choice(names), category, capacity))
            full = (offset, index) in ((-8, 1), (-2, 3), (0, 3), (3, 1), (10, 0))
            eligible = list(candidates(service, starts, ends))
            target = capacity if full else min(capacity - 1, rng.randint(3, 5))
            selection = rng.sample(eligible, min(len(eligible), target))
            if full and len(selection) != capacity:
                raise RuntimeError('Planned full class cannot be filled within policy.')
            if offset in reserved_class_days and service == 2 and not full:
                # Ordinary class visits consume the Basic plan's eight visits.
                for item in candidates(2, starts, ends, 4):
                    if len(selection) < capacity:
                        selection.append(item)
                        break
            for contract, person, booked in selection:
                booked = max(booked, made)
                early = starts - timedelta(hours=5)
                late = starts - timedelta(hours=2)
                draw = rng.random()
                cancelled = None
                if not full and person != 4 and draw < 0.12 and booked < early <= as_of:
                    cancelled = late if draw < 0.03 and late <= as_of else early
                booking = len(data['booking']) + 1
                state = 'CANCEL' if cancelled else 'SUCCESS'
                usage = 'REFUNDED' if cancelled and cancelled <= early else 'USED'
                data['booking'].append((booking, person, key, booked, state, cancelled))
                data['member_service_usage'].append((len(data['member_service_usage']) + 1,
                                                    contract, service, key, booked, usage, booking))
                # Allocate against all scheduled charges, including those later refunded.
                # This bounds quota even when the historical event stream is replayed by timestamp.
                spent[contract, service] += 1
            if special:
                roster.update(class_session=key, class_service=service)
            if full and offset == 3:
                roster['full_session'] = key
            if (offset, index) == (1, 0) and service == 2:
                roster['generic_session'] = key
            if offset > 0 and service == 2:
                roster.setdefault('generic_session', key)
        data['session'].append((key, coach, room, starts, ends, kind, made))
    quota_id = next(key for key, person, first, _, _ in passes if person == 4 and first >= ref - 16 * DAY)
    assert spent[quota_id, 2] == 8
    for key, _, first, last, _ in passes:
        if rng.random() < .42:
            visit = at(min(last, ref), 16) - rng.randint(0, min(6, (min(last, ref) - first).days)) * DAY
            if at(first, 11) <= visit <= as_of:
                data['member_service_usage'].append((len(data['member_service_usage']) + 1, key, 1, None, visit, 'USED', None))
    return roster


def generate(as_of, passwords=None):
    rng = Random(SEED)
    data = {table: [] for table, _, _ in FIELDS}
    data['service_type'] = [(key, *row) for key, row in enumerate(SERVICES, 1)]
    data['room'] = [(key, *row, 'MAINTENANCE' if key == 7 else 'AVAILABLE') for key, row in enumerate(ROOMS, 1)]
    for key, (name, duration, price, quotas) in enumerate(PLANS, 1):
        terms = ['Gym tự do'] + [f'{SERVICES[service - 1][0]}: {n} lượt' for service, n in quotas.items()]
        data['membership_plan'].append((key, f'{name} – {duration} tháng', duration, price, ' · '.join(terms), key != 4))
    data['plan_inclusion'] = [(plan, service, quota) for plan, _, _, service, quota in CATALOG]
    asset_rows(data, as_of.date())
    credentials = people_rows(data, as_of.date(), rng, passwords)
    passes = contract_rows(data, as_of.date(), rng)
    roster = schedule_rows(data, passes, as_of, rng)
    return data, roster, credentials


def seed_clean(cursor, database, data):
    if (database not in TARGETS and not fresh_target(database)) or cursor.execute('SELECT DB_NAME()').fetchval() != database:
        raise ValueError('Clean seed requires a dedicated CleanDemo database.')
    if cursor.execute('SELECT @@TRANCOUNT').fetchval() != 1:
        raise RuntimeError('Clean seed requires its own transaction.')
    for table, _, _ in FIELDS:
        if cursor.execute(f'SELECT TOP(1) 1 FROM dbo.[{table}]').fetchone():
            raise RuntimeError(f'Refusing to seed occupied table {table}.')
    for table, fields, explicit in FIELDS:
        names = fields.split()
        columns = ','.join(f'[{field}]' for field in names)
        values = ','.join('?' for _ in names)
        if explicit:
            cursor.execute(f'SET IDENTITY_INSERT dbo.[{table}] ON')
        try:
            cursor.executemany(f'INSERT dbo.[{table}]({columns}) VALUES({values})', data[table])
        finally:
            if explicit:
                cursor.execute(f'SET IDENTITY_INSERT dbo.[{table}] OFF')
        actual = cursor.execute(f'SELECT COUNT_BIG(*) FROM dbo.[{table}]').fetchval()
        if actual != len(data[table]):
            raise RuntimeError(f'{table}: inserted {actual}, expected {len(data[table])}.')
