"""Synthetic records for a fresh portable QA database."""
from datetime import date, datetime, timedelta

from app.auth import HASHER
from app.demo_labels import DEMO_EQUIPMENT_RENAMES, DEMO_PLAN_RENAMES


ACCOUNTS = (
    ('member-a', 'Trần Hoàng Long', 'member'),
    ('member-b', 'Võ Ngọc Hân', 'member'),
    ('trainer-a', 'Lê Minh Khang', 'trainer'),
    ('trainer-b', 'Phạm Tuấn Kiệt', 'trainer'),
    ('staff', 'Nguyễn Thảo Linh', 'staff'),
    ('manager', 'Trần Quốc Huy', 'management'),
    ('schedule', 'Nguyễn Minh Anh', 'member'),
)


def email(account):
    return f'local-demo-{account}@example.invalid'


def seed(cursor, password):
    def insert(sql, *parameters):
        return cursor.execute(sql + '; SELECT CONVERT(int,SCOPE_IDENTITY())', *parameters).fetchval()

    today = cursor.execute('SELECT CONVERT(date,SYSDATETIME())').fetchval()
    people = {}
    for n, (account, name, role) in enumerate(ACCOUNTS, 1):
        person = insert('''INSERT dbo.person(ssn,full_name,email,phone,date_of_birth,gender,address,password_hash)
            VALUES(?,?,?,?,?,'OTHER',?,?)''', f'990000000{n:03}', name, email(account), f'0990000{n:03}',
                        date(2000, n, n), 'Địa chỉ tổng hợp', HASHER.hash(password))
        people[account] = person
        if role == 'member':
            cursor.execute('INSERT dbo.member(person_id,emergency_contact_phone) VALUES(?,?)',
                           person, f'0980000{n:03}')
        elif role == 'trainer':
            cursor.execute('INSERT dbo.trainer(person_id,hire_date) VALUES(?,?)', person, today)
            cursor.execute('INSERT dbo.trainer_certification VALUES(?,?)', person, 'Chứng chỉ huấn luyện tổng hợp')
        else:
            cursor.execute('INSERT dbo.staff(person_id,position,hire_date) VALUES(?,?,?)', person,
                           'Quản lý' if role == 'management' else 'Lễ tân', today)
    pt_room = insert("INSERT dbo.room(room_name,room_type) VALUES(?,'PT')", 'Phòng huấn luyện cá nhân')
    group_room = insert("INSERT dbo.room(room_name,room_type) VALUES(?,'GROUP')", 'Phòng tập nhóm')
    gym, pt, group = [insert('INSERT dbo.service_type(service_name) VALUES(?)', name) for name in (
        'Local-02 · Sử dụng phòng tập', 'Local-02 · Buổi PT', 'Lớp nhóm')]
    names = (DEMO_PLAN_RENAMES[1][1], DEMO_PLAN_RENAMES[2][1],
             'Gói tập tự do + 4 buổi PT – 1 tháng', 'Gói tập tự do + PT và lớp nhóm – 1 tháng')
    plans = [insert('INSERT dbo.membership_plan(plan_name,duration_months,base_price,is_for_sale) VALUES(?,1,?,1)',
                    name, price) for name, price in zip(names, (300000, 300000, 350000, 390000), strict=True)]
    for plan, pt_count, class_count in zip(plans, (1, 1, 4, 2), (0, 0, 0, 2), strict=True):
        for service, quota in ((gym, -1), (pt, pt_count), (group, class_count)):
            if quota:
                cursor.execute('INSERT dbo.plan_inclusion VALUES(?,?,?)', plan, service, quota)
    memberships = (
        ('member-a', plans[0], 'ACTIVE', 300000, today, today + timedelta(days=30)),
        ('member-b', plans[1], 'EXPIRED', 300000, today - timedelta(days=60), today - timedelta(days=30)),
        ('schedule', plans[3], 'ACTIVE', 390000, today, today + timedelta(days=30)),
        ('member-b', plans[2], 'PENDING_ACTIVATION', 350000, None, None),
        ('member-a', plans[3], 'PENDING_PAYMENT', None, None, None),
    )
    for account, plan, state, price, start, end in memberships:
        membership = insert('''INSERT dbo.membership(person_id,plan_id,status,total_price,start_date,end_date)
            VALUES(?,?,?,?,?,?)''', people[account], plan, state, price, start, end)
        if price is not None:
            cursor.execute("""INSERT dbo.payment(membership_id,amount,payment_method,recorded_by)
                VALUES(?,?,'CASH',?)""", membership, price, people['staff'])
    morning = datetime.combine(today + timedelta(days=1), datetime.min.time()) + timedelta(hours=10)
    for coach, member, start in (('trainer-a', 'member-a', morning), ('trainer-b', 'schedule', morning + timedelta(hours=1))):
        session = insert("""INSERT dbo.[session](trainer_id,room_id,start_time,end_time,session_type)
            VALUES(?,?,?,?,'PERSONAL')""", people[coach], pt_room, start, start + timedelta(hours=1))
        cursor.execute('INSERT dbo.pt_session(session_id,person_id,training_focus) VALUES(?,?,?)',
                       session, people[member], 'Buổi PT tổng hợp')
    start = morning + timedelta(days=1, hours=8)
    session = insert("""INSERT dbo.[session](trainer_id,room_id,start_time,end_time,session_type)
        VALUES(?,?,?,?,'GROUP')""", people['trainer-a'], group_room, start, start + timedelta(hours=1))
    cursor.execute('INSERT dbo.group_class_session(session_id,class_name,category,max_capacity) VALUES(?,?,?,?)',
                   session, 'Thể lực toàn thân', 'Fitness', 8)
    cursor.execute('INSERT dbo.equipment(equipment_name,serial_number,room_id) VALUES(?,?,?)',
                   DEMO_EQUIPMENT_RENAMES['DEMO-MAT-01'][1], 'DEMO-MAT-01', group_room)
    equipment = insert("""INSERT dbo.equipment(equipment_name,serial_number,room_id,status)
        VALUES(?,?,?,'MAINTENANCE')""", DEMO_EQUIPMENT_RENAMES['DEMO-BIKE-01'][1], 'DEMO-BIKE-01', pt_room)
    cursor.execute('INSERT dbo.equipment_maintenance_log(equipment_id,start_date,description) VALUES(?,?,?)',
                   equipment, today, 'Kiểm tra tổng hợp')
