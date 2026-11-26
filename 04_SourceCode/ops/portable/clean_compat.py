"""Install the audited category-specific quota SQL on a freshly seeded catalogue."""
from pathlib import Path
import re

from app.class_eligibility_sql import READ_SCOPE, definition_hash
from clean_seed import CLASSES, MARKER, MARKER_PROPERTY, SERVICES

CLASS_RULES_PROPERTY = 'IronPulseClassRules'


def alter(definition):
    return re.sub(r'^(?:CREATE|ALTER)\s+PROCEDURE\b', 'ALTER PROCEDURE', definition.strip(), count=1, flags=re.I)


def exactly(body, old, new):
    if body.count(old) != 1:
        raise RuntimeError('Compatibility patch does not match the expected SQL definition.')
    return body.replace(old, new, 1)


def cached_eligibility(read_scope):
    read_scope = exactly(read_scope, '  WITH classes AS (', """  DECLARE @demo_quotas TABLE (
    service_type_id int PRIMARY KEY, quota_per_cycle int NOT NULL, used bigint NOT NULL, uncertain bit NOT NULL);
  INSERT @demo_quotas(service_type_id,quota_per_cycle,used,uncertain)
  SELECT i.service_type_id,i.quota_per_cycle,
    (SELECT COUNT_BIG(*) FROM dbo.member_service_usage u WHERE u.membership_id=@r2c_membership
         AND u.service_type_id=i.service_type_id AND u.usage_status='USED'),
    CASE WHEN i.quota_per_cycle>=0
         THEN dbo.demo_unreconciled_quota(@r2c_membership,i.service_type_id) ELSE 0 END
  FROM dbo.plan_inclusion i WHERE i.plan_id=@r2c_plan AND i.service_type_id IN (2,4,5,6,7);
  WITH classes AS (""")
    start = read_scope.index('  LEFT JOIN dbo.plan_inclusion i ON i.plan_id=@r2c_plan AND i.service_type_id=svc.service_type_id')
    stop = read_scope.index('  CROSS APPLY(SELECT COUNT(*) AS enrolled', start)
    read_scope = read_scope[:start] + '  LEFT JOIN @demo_quotas i ON i.service_type_id=svc.service_type_id\n' + read_scope[stop:]
    return read_scope.replace('ledger.uncertain', 'i.uncertain').replace('used.total', 'i.used')


def compatibility(cursor):
    procedure_names = ('local03_entitlement', 'local03_book_group', 'local03_schedule')
    original = {name: cursor.execute('SELECT OBJECT_DEFINITION(OBJECT_ID(?))', 'dbo.' + name)
                .fetchval().replace('\r\n', '\n') for name in procedure_names}
    expected = [(index, name) for index, (name, _) in enumerate(SERVICES, 1)]
    actual = [tuple(r) for r in cursor.execute('SELECT service_type_id,service_name FROM dbo.service_type ORDER BY service_type_id')]
    if actual != expected:
        raise RuntimeError('SQL catalogue does not match the audited service identifiers.')
    for batch in Path(__file__).with_name('clean_compat.sql').read_text(encoding='utf-8').split('\nGO\n'):
        if batch.strip():
            cursor.execute(batch)
    entitlement = exactly(original['local03_entitlement'], '@membership int OUTPUT,@service int OUTPUT',
                          '@membership int OUTPUT,@service int OUTPUT,@session int=NULL')
    entitlement = exactly(entitlement, "(@kind='GROUP' AND t.service_name=N'Lớp nhóm')",
                          """(@kind='GROUP' AND i.service_type_id=(SELECT dbo.demo_class_service(category)
                          FROM dbo.group_class_session WHERE session_id=@session))""")
    entitlement = exactly(entitlement, "(@kind='PT' AND t.service_name IN (N'PT cá nhân',N'Local-02 · Buổi PT'))",
                          "(@kind='PT' AND i.service_type_id=3)")
    entitlement = exactly(entitlement, " IF @quota<>-1 AND",
                          """ IF @quota<>-1 AND dbo.demo_unreconciled_quota(@membership,@service)=1
   THROW 52203,'Unreconciled historical quota',1;
 IF @quota<>-1 AND""")
    booking = exactly(original['local03_book_group'], '@membership OUTPUT,@service OUTPUT;',
                      '@membership OUTPUT,@service OUTPUT,@session;')
    read_scope = exactly(READ_SCOPE,
                          '      @r2c_service int,@r2c_matches int,@r2c_quota int,@r2c_used bigint=0,@r2c_pending varchar(25);',
                          '      @r2c_pending varchar(25);')
    start = read_scope.index('  ELSE\n  BEGIN\n    -- Match')
    stop = read_scope.index('  WITH classes', start)
    read_scope = read_scope[:start] + read_scope[stop:]
    read_scope = read_scope.replace('@r2c_matches=0', 'svc.service_type_id IS NOT NULL AND i.service_type_id IS NULL')
    read_scope = read_scope.replace('@r2c_matches<>1 OR @r2c_quota IS NULL',
                                    'svc.service_type_id IS NULL OR (i.quota_per_cycle>=0 AND ledger.uncertain=1)')
    read_scope = read_scope.replace('@r2c_matches=1', 'i.service_type_id IS NOT NULL AND ledger.uncertain=0')
    read_scope = read_scope.replace('@r2c_quota', 'i.quota_per_cycle').replace('@r2c_used', 'used.total')
    read_scope = exactly(read_scope, '  FROM classes c\n', """  FROM classes c
  CROSS APPLY(SELECT dbo.demo_class_service(c.category) AS service_type_id) svc
  LEFT JOIN dbo.plan_inclusion i ON i.plan_id=@r2c_plan AND i.service_type_id=svc.service_type_id
  CROSS APPLY(SELECT CASE WHEN i.quota_per_cycle>=0
           THEN dbo.demo_unreconciled_quota(@r2c_membership,svc.service_type_id) ELSE 0 END AS uncertain) ledger
  CROSS APPLY(SELECT COUNT_BIG(*) AS total FROM dbo.member_service_usage
      WHERE membership_id=@r2c_membership AND service_type_id=svc.service_type_id AND usage_status='USED') used
""")
    schedule = exactly(original['local03_schedule'], READ_SCOPE, cached_eligibility(read_scope))
    for name, sql in zip(procedure_names, (entitlement, booking, schedule)):
        cursor.execute(alter(sql))
        sql_live = cursor.execute('SELECT OBJECT_DEFINITION(OBJECT_ID(?))', 'dbo.' + name).fetchval()
        assert definition_hash(sql_live) == definition_hash(sql)
    return {name: definition_hash(sql) for name, sql in original.items()}


def deploy_class_rules(cursor, *, undo=False):
    """Deploy or reverse the three CleanDemo guards inside the caller's transaction."""
    if not cursor.execute("""SELECT 1 FROM sys.extended_properties
        WHERE class=0 AND name=? AND CONVERT(nvarchar(100),value)=?""",
                          MARKER_PROPERTY, MARKER).fetchone():
        raise RuntimeError('Chỉ áp dụng quy tắc bộ môn cho dataset CleanDemo.')
    cursor.execute("""DECLARE @status int;
        EXEC @status=sys.sp_getapplock @Resource=N'IronPulseClassRules',@LockMode=N'Exclusive',
            @LockOwner=N'Transaction',@LockTimeout=0;
        IF @status<0 THROW 52701,'Class rule migration in progress',1;""")
    source = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
    names = ('local03_create_group', 'local04_classes', 'local04_services')
    batches = re.split(r'(?m)^GO[ \t]*$', source)
    original = {name: next(batch.strip() for batch in batches
                           if re.match(rf'CREATE PROCEDURE dbo\.{name}\b', batch.lstrip()))
                for name in names}
    mapped = {category: cursor.execute('SELECT dbo.demo_class_service(?)', category).fetchval()
              for category, *_ in CLASSES}
    if mapped != {category: service for category, service, *_ in CLASSES}:
        raise RuntimeError('Danh mục bộ môn khác ánh xạ CleanDemo đã xác minh.')
    scheduled = ','.join(str(service) for service in sorted(set(mapped.values()) | {3}))
    unmapped = ('NOT EXISTS(SELECT 1 FROM dbo.service_type '
                'WHERE service_type_id=dbo.demo_class_service(@category))')
    rejection = "THROW 52205,'Unknown class category',1;"
    lock = " EXEC dbo.local03_lock_slot @trainer,@room,@start,@end;"
    create = exactly(original[names[0]], lock, f' IF {unmapped} {rejection}\n{lock}')
    detail = " IF @action='detail'"
    edit = exactly(original[names[1]], detail, f""" IF @action='category'
 BEGIN
   SELECT CONVERT(bit,CASE WHEN {unmapped} THEN 0 ELSE 1 END) AS supported;
   RETURN;
 END;
{detail}""")
    update = ' UPDATE dbo.group_class_session SET max_capacity='
    edit = exactly(edit, update, f""" IF {unmapped}
    AND (@category<>@old_category OR NOT EXISTS(SELECT 1 FROM dbo.booking WHERE session_id=@id))
   {rejection}
{update}""")
    filter_ = "s.service_name NOT IN (N'PT cá nhân',N'Local-02 · Buổi PT',N'Lớp nhóm')"
    services = original[names[2]]
    if services.count(filter_) != 2:
        raise RuntimeError('Hai phạm vi dịch vụ lẻ khác định nghĩa đã xác minh.')
    services = services.replace(filter_, f'{filter_} AND i.service_type_id NOT IN ({scheduled})')
    patched = dict(zip(names, (create, edit, services), strict=True))
    live = {name: definition_hash(cursor.execute('SELECT OBJECT_DEFINITION(OBJECT_ID(?))',
                                                'dbo.' + name).fetchval())
            for name in names}
    marker = cursor.execute("""SELECT CONVERT(nvarchar(10),value) FROM sys.extended_properties
        WHERE class=0 AND name=?""", CLASS_RULES_PROPERTY).fetchone()
    if marker is not None and marker[0] != '1':
        raise RuntimeError('Dấu phiên bản quy tắc bộ môn không hợp lệ.')
    applied = marker is not None
    source_sql, target_sql = (patched, original) if undo else (original, patched)
    if applied != undo and live == {name: definition_hash(target_sql[name]) for name in names}:
        return False
    if applied != undo or live != {name: definition_hash(source_sql[name]) for name in names}:
        raise RuntimeError('SQL dịch vụ/lớp hoặc dấu cài đặt khác phiên bản hỗ trợ.')
    for name in names:
        cursor.execute(alter(target_sql[name]))
        observed = cursor.execute('SELECT OBJECT_DEFINITION(OBJECT_ID(?))', 'dbo.' + name).fetchval()
        if definition_hash(observed) != definition_hash(target_sql[name]):
            raise RuntimeError(f'Không xác minh được định nghĩa dbo.{name}.')
    if undo:
        cursor.execute('EXEC sys.sp_dropextendedproperty @name=?', CLASS_RULES_PROPERTY)
    else:
        cursor.execute("EXEC sys.sp_addextendedproperty @name=?,@value=N'1'", CLASS_RULES_PROPERTY)
    return True


