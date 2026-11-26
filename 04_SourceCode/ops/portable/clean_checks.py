"""Independent SQL invariants shared with the local acceptance tools."""
from pathlib import Path

from clean_seed import ACCOUNTS, CATALOG, EQUIPMENT, FIELDS
CHECKS = {
    'unmasked_people': """SELECT COUNT(*) FROM person WHERE email NOT LIKE '%@example.invalid'
        OR phone NOT LIKE '00041%' OR ssn NOT LIKE '00041%' OR address<>N'Khu dân cư mô phỏng'
        OR (password_hash<>'!disabled-local05d' AND password_hash NOT LIKE '$argon2id$%')""",
    'unmasked_member': "SELECT COUNT(*) FROM member WHERE emergency_contact_phone NOT LIKE '00042%' OR health_notes IS NOT NULL",
    'invalid_role_count': """SELECT COUNT(*) FROM person p WHERE
        (SELECT COUNT(*) FROM member WHERE person_id=p.person_id)+
        (SELECT COUNT(*) FROM staff WHERE person_id=p.person_id)+
        (SELECT COUNT(*) FROM trainer WHERE person_id=p.person_id)<>1""",
    'technical_names': """SELECT COUNT(*) FROM (
          SELECT full_name AS label FROM person UNION ALL SELECT plan_name FROM membership_plan
          UNION ALL SELECT room_name FROM room UNION ALL SELECT equipment_name FROM equipment
          UNION ALL SELECT class_name FROM group_class_session
        ) n WHERE UPPER(label) LIKE '% QA %' OR UPPER(label) LIKE '%TEST%' OR UPPER(label) LIKE '%FIXTURE%'
         OR CHARINDEX(NCHAR(65533),label COLLATE Latin1_General_100_BIN2)>0
         OR DATALENGTH(label)<>DATALENGTH(TRIM(label))""",
    'unrecognized_category': """SELECT COUNT(*) FROM group_class_session
          WHERE dbo.demo_class_service(category) IS NULL""",
    'invalid_used_scope': """SELECT COUNT(*) FROM member_service_usage u
         JOIN membership m ON m.membership_id=u.membership_id LEFT JOIN [session] s ON s.session_id=u.session_id
         LEFT JOIN group_class_session g ON g.session_id=u.session_id
         LEFT JOIN plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
         WHERE i.plan_id IS NULL OR CONVERT(date,COALESCE(s.start_time,u.used_at))<m.start_date
         OR CONVERT(date,COALESCE(s.end_time,u.used_at))>m.end_date
         OR (s.session_type='GROUP' AND u.service_type_id<>dbo.demo_class_service(g.category))
         OR (s.session_type='PERSONAL' AND u.service_type_id<>3)""",
    'recorded_over_quota': """SELECT COUNT(*) FROM (SELECT u.membership_id,u.service_type_id
        FROM member_service_usage u JOIN membership m ON m.membership_id=u.membership_id
        JOIN plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
        WHERE u.usage_status='USED' AND i.quota_per_cycle>=0
        GROUP BY u.membership_id,u.service_type_id,i.quota_per_cycle HAVING COUNT(*)>i.quota_per_cycle) q""",
    'wrong_link': """SELECT COUNT(*) FROM member_service_usage u
        JOIN membership m ON m.membership_id=u.membership_id JOIN booking b ON b.booking_id=u.booking_id
        WHERE u.session_id<>b.session_id OR m.person_id<>b.person_id OR (u.usage_status='USED' AND b.booking_status<>'SUCCESS')
           OR (u.usage_status='REFUNDED' AND b.booking_status<>'CANCEL')""",
    'bad_rooms': """SELECT COUNT(*) FROM [session] s JOIN room r ON r.room_id=s.room_id
         WHERE (s.session_type='PERSONAL' AND r.room_type<>'PT')
         OR (s.session_type='GROUP' AND r.room_type<>'STUDIO')""",
    'future_staff_or_room_unavailable': """SELECT COUNT(*) FROM [session] s JOIN room r ON r.room_id=s.room_id
         JOIN trainer t ON t.person_id=s.trainer_id
         WHERE s.start_time>SYSDATETIME() AND (t.employment_status<>'ACTIVE' OR r.status<>'AVAILABLE')""",
    'overlap_trainer_or_room': """SELECT COUNT(*) FROM [session] a JOIN [session] b ON a.session_id<b.session_id
          AND a.start_time<b.end_time AND b.start_time<a.end_time AND (a.trainer_id=b.trainer_id OR a.room_id=b.room_id)""",
    'overlap_member': """WITH history AS (SELECT person_id,session_id FROM pt_session
         UNION ALL SELECT person_id,session_id FROM booking WHERE booking_status='SUCCESS')
         SELECT COUNT(*) FROM history x JOIN history y ON y.person_id=x.person_id AND y.session_id>x.session_id
         JOIN [session] a ON a.session_id=x.session_id JOIN [session] b ON b.session_id=y.session_id
         WHERE a.start_time<b.end_time AND b.start_time<a.end_time""",
    'over_capacity': "SELECT COUNT(*) FROM vw_group_class_enrollment WHERE available_slots<0",
    'pending_or_expired_finance': """SELECT COUNT(*) FROM membership m LEFT JOIN payment p ON p.membership_id=m.membership_id
         WHERE (m.status='PENDING_PAYMENT' AND p.payment_id IS NOT NULL)
         OR (m.status<>'PENDING_PAYMENT' AND (p.payment_id IS NULL OR m.total_price IS NULL OR m.total_price<>p.amount))""",
    'stale_active': """SELECT COUNT(*) FROM membership WHERE status='ACTIVE' AND end_date<CONVERT(date,SYSDATETIME())""",
    'maintenance_mismatch': """SELECT COUNT(*) FROM equipment e OUTER APPLY(
         SELECT COUNT(*) AS opened FROM equipment_maintenance_log l WHERE l.equipment_id=e.equipment_id AND l.end_date IS NULL
         ) n WHERE (e.status='MAINTENANCE' AND n.opened<>1) OR (e.status<>'MAINTENANCE' AND n.opened<>0)""",
}


def validate_seed(cursor, reference):
    checks = dict(cursor.execute(Path(__file__).with_name('clean_quality.sql').read_text(encoding='utf-8'),
                                 reference).fetchall())
    checks.update({name: cursor.execute(sql).fetchval() for name, sql in CHECKS.items()
                   if name not in ('stale_active', 'wrong_link')})
    enabled = cursor.execute("SELECT COUNT(*) FROM dbo.person WHERE password_hash LIKE '$argon2id$%'").fetchval()
    checks['credentials'] = abs(enabled - len(ACCOUNTS))
    checks['equipment_room'] = sum(
        room is not None and room not in valid
        for title, valid, _, _ in EQUIPMENT
        for room, in cursor.execute('SELECT room_id FROM dbo.equipment WHERE equipment_name LIKE ?', title + ' số %'))
    if any(checks.values()):
        raise ValueError(f'Dataset không đạt: {[(name, value) for name, value in checks.items() if value]}')
    tables = set(row[0] for row in cursor.execute("SELECT name FROM sys.tables WHERE is_ms_shipped=0"))
    counts = {table: cursor.execute(f'SELECT COUNT_BIG(*) FROM dbo.[{table}]').fetchval() for table, _, _ in FIELDS}
    if tables != counts.keys() or sum(counts.values()) <= 10000:
        raise ValueError('Dataset phải có đúng 18 bảng nghiệp vụ và hơn 10.000 dòng.')
    catalog = cursor.execute("""SELECT p.plan_id,p.duration_months,p.base_price,i.service_type_id,i.quota_per_cycle
        FROM dbo.membership_plan p JOIN dbo.plan_inclusion i ON i.plan_id=p.plan_id ORDER BY p.plan_id,i.service_type_id""")
    if [tuple(row) for row in catalog] != list(CATALOG):
        raise ValueError('Danh mục quyền lợi sai cấu hình.')
    rows = cursor.execute('DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS, ALL_ERRORMSGS')
    while True:
        if rows.description and rows.fetchone():
            raise ValueError('DBCC CHECKCONSTRAINTS phát hiện lỗi.')
        if not rows.nextset():
            break
    return counts, checks


