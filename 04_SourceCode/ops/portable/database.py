"""Bootstrap a vacant local SQL Server Express QA database with a bounded login."""
from contextlib import closing, contextmanager
from datetime import datetime
import json
import re
import secrets
from itertools import chain

import pyodbc

from app import db
from app.trainer_schedule_sql import deploy as deploy_trainer_schedule
from app.demo_labels import DEMO_PLAN_RENAMES
from app.portable_config import DATABASE_SCHEMA, DRIVER, INSTALL_PROPERTY, SCHEMA_PROPERTY, validate_scope

from common import CONFIG, ROOT, SetupError, atomic_write, dpapi, read_json, validate, windows_profile, write_json
from clean_checks import validate_seed
from clean_compat import compatibility, deploy_class_rules
from clean_seed import ACCOUNTS, MARKER, MARKER_PROPERTY, REFERENCE_PROPERTY, fresh_target, generate, seed_clean


COLUMN_GRANTS = {
    'person': 'person_id full_name email password_hash',
    'member': 'person_id',
    'trainer': 'person_id employment_status',
    'staff': 'person_id employment_status position',
    'membership': 'membership_id person_id plan_id status start_date end_date',
    'membership_plan': 'plan_id plan_name',
    'session': 'session_id trainer_id room_id session_type start_time end_time',
    'room': 'room_id room_name',
}
PROCEDURE_GRANTS = {f'{group}_{name}' for group, names in db.PROCEDURES.items() for name in names} | {'localr1a_profile'}
SESSION_SETTINGS = """SET NOCOUNT ON; SET XACT_ABORT ON; SET LOCK_TIMEOUT 5000;
SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON; SET QUOTED_IDENTIFIER ON; SET NUMERIC_ROUNDABORT OFF;"""


def sql_connect(config, *, master=False):
    validate(config, installed=False)
    if DRIVER not in pyodbc.drivers():
        raise SetupError('Thiếu Microsoft ODBC Driver 18 x64.')
    database = 'master' if master else config['database']
    try:
        conn = pyodbc.connect(
            f'Driver={{{DRIVER}}};Server={config["server"]};Database={database};'
            'Trusted_Connection=yes;Encrypt=Mandatory;TrustServerCertificate=yes;ConnectRetryCount=0;',
            timeout=8, autocommit=True)
    except pyodbc.Error:
        raise SetupError('Không kết nối được SQL cục bộ. Kiểm tra instance, Shared Memory và quyền Windows.') from None
    conn.timeout = 60
    return conn


def quoted(name):
    return '[' + name.replace(']', ']]') + ']'


def server_guard(cursor, config, *, master=False):
    machine, instance = validate_scope(config['server'], config['database'], config['login'])
    result = cursor.execute("""SELECT DB_NAME(),CONVERT(sysname,SERVERPROPERTY('MachineName')),
        COALESCE(CONVERT(sysname,SERVERPROPERTY('InstanceName')),N''),
        CONVERT(int,SERVERPROPERTY('ProductMajorVersion')),CONVERT(int,SERVERPROPERTY('EngineEdition')),
        CONNECTIONPROPERTY('net_transport'),CONNECTIONPROPERTY('auth_scheme'),
        IS_SRVROLEMEMBER('sysadmin'),ORIGINAL_LOGIN(),c.encrypt_option
        FROM sys.dm_exec_connections c WHERE c.session_id=@@SPID
          AND EXISTS(SELECT 1 FROM sys.configurations WHERE name=N'cross db ownership chaining' AND value_in_use=0)
          AND NOT EXISTS(SELECT 1 FROM sys.server_triggers WHERE is_disabled=0)""").fetchone()
    name = 'master' if master else config['database']
    if (not result or result[0].casefold() != name.casefold()
            or tuple(value.casefold() for value in result[1:3]) != (machine.casefold(), instance.casefold())
            or result[3] < 16 or result[4] != 4 or result[5] != 'Shared memory'
            or result[6] not in ('NTLM', 'KERBEROS') or result[7] != 1 or result[9] != 'TRUE'):
        raise SetupError('Cần SQL Server Express 2022/2025 cục bộ, Shared Memory mã hóa và quyền sysadmin cho bước setup.')
    if result[8].casefold() == config['login'].casefold():
        raise SetupError('Danh tính setup và runtime phải khác nhau.')
    return result[3]


def database_guard(cursor, config):
    row = cursor.execute("""SELECT DB_ID(), CONVERT(varchar(36),service_broker_guid)
        FROM sys.databases WHERE database_id=DB_ID() AND state_desc=N'ONLINE' AND is_read_only=0
          AND is_trustworthy_on=0 AND is_db_chaining_on=0 AND is_auto_close_on=0 AND source_database_id IS NULL""").fetchone()
    if not row or row[0] <= 4 or row[1].casefold() != config['broker']:
        raise SetupError('Database không khớp định danh cài đặt.')


def schema_batches():
    source = (ROOT / 'ops/portable/schema.sql').read_text(encoding='utf-8')
    _, source = source.split('\n', 1)
    batches = [part.strip() for part in re.split(r'(?m)^GO[ \t]*$', source) if part.strip()]
    if len(batches) != 46 or any(re.search(r'(?im)^\s*(?:USE |CREATE DATABASE |ALTER DATABASE |GRANT |EXECUTE AS LOGIN)', s)
                                 for s in batches):
        raise SetupError('Gói SQL bootstrap không hợp lệ.')
    return batches


def validate_schema(cursor, config):
    database_guard(cursor, config)
    expected = {SCHEMA_PROPERTY: DATABASE_SCHEMA, INSTALL_PROPERTY: config['install_id']}
    actual = dict(cursor.execute("""SELECT name,CONVERT(nvarchar(100),value) FROM sys.extended_properties
        WHERE class=0 AND name IN (?,?)""", SCHEMA_PROPERTY, INSTALL_PROPERTY).fetchall())
    if actual != expected:
        raise SetupError('Database đã tồn tại với schema hoặc mã cài khác.')
    observed_dataset = cursor.execute("""SELECT CONVERT(nvarchar(100),value) FROM sys.extended_properties
        WHERE class=0 AND name=?""", MARKER_PROPERTY).fetchone()
    if (observed_dataset[0] if observed_dataset else None) != config.get('dataset'):
        raise SetupError('Dấu nhận diện dataset SQL khác cấu hình bản cài.')
    if config.get('dataset') is not None:
        routines = {row[0] for row in cursor.execute("""SELECT name FROM sys.objects
            WHERE schema_id=SCHEMA_ID(N'dbo') AND type='FN' AND name IN ('demo_class_service','demo_unreconciled_quota')""")}
        if routines != {'demo_class_service', 'demo_unreconciled_quota'}:
            raise SetupError('Thiếu SQL quyền lợi theo bộ môn.')
    source = '\n'.join(schema_batches())
    for kind, catalog in (('TABLE', 'tables'), ('VIEW', 'views'), ('TRIGGER', 'triggers'), ('PROCEDURE', 'procedures')):
        names = set(re.findall(r'(?im)^CREATE ' + kind + r' (?:dbo\.)?\[?(\w+)\]?', source))
        actual_names = {r[0] for r in cursor.execute(f'SELECT name FROM sys.{catalog} WHERE is_ms_shipped=0')}
        if actual_names != names:
            raise SetupError(f'Danh mục SQL không khớp ({kind}).')
    procedures = set(re.findall(r'(?im)^(?:CREATE|ALTER) PROCEDURE dbo\.(\w+)', source))
    indexes = set(re.findall(r'(?im)^CREATE (?:UNIQUE )?INDEX (\w+)', source))
    available = {r[0] for r in cursor.execute('SELECT name FROM sys.indexes WHERE is_disabled=0')}
    if not indexes <= available:
        raise SetupError('Thiếu index nghiệp vụ.')
    if cursor.execute("""SELECT 1 FROM sys.foreign_keys WHERE is_disabled=1 OR is_not_trusted=1
                         UNION ALL SELECT 1 FROM sys.check_constraints WHERE is_disabled=1 OR is_not_trusted=1
                         UNION ALL SELECT 1 FROM sys.triggers WHERE is_disabled=1""").fetchone():
        raise SetupError('Constraint hoặc trigger bị tắt.')
    return procedures


def validate_grants(cursor, config, procedures, *, retained_databases=()):
    other_db = [r[0] for r in cursor.execute('SELECT name FROM sys.databases WHERE database_id>4 AND database_id<>DB_ID()')]
    tables = {}
    for name, col in cursor.execute('SELECT t.name,c.name FROM sys.tables t JOIN sys.columns c ON c.object_id=t.object_id WHERE t.is_ms_shipped=0'):
        tables.setdefault(name, []).append(col)
    login = config['login']
    cursor.execute(f"EXECUTE AS LOGIN=N'{login}';")
    try:
        result = cursor.execute(db.CONNECTION_IDENTITY.replace('ORIGINAL_LOGIN()', 'SUSER_SNAME()', 1)).fetchone()
        if not result or result[1].casefold() != login.casefold() or result[2] != 1:
            raise SetupError('Danh tính runtime có quyền ngoài phạm vi.')
        db.verify_portable_connection(cursor, db.portable_connection_scope({
            'LOCAL_QA': True, 'SQL_SERVER': config['server'], 'SQL_DATABASE': config['database'],
            'SQL_WINDOWS_LOGIN': login, 'SQL_QA_BROKER_GUID': config['broker'],
            'PORTABLE_INSTALL_ID': config['install_id']}))
        for name in other_db:
            expected = int(name in retained_databases)
            if cursor.execute('SELECT ISNULL(HAS_DBACCESS(?),0)', name).fetchval() != expected:
                raise SetupError('Danh tính runtime đã có quyền trên database khác.')
        objects = [(f'dbo.{quoted(name)}', 'EXECUTE', int(name in PROCEDURE_GRANTS)) for name in procedures]
        objects.extend((f'dbo.{quoted(name)}', action, 0) for name in tables
                       for action in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CONTROL'))
        verify_permission_rows(cursor, objects, "ISNULL(HAS_PERMS_BY_NAME(n,'OBJECT',p),0)")
        columns = [(f'dbo.{quoted(name)}', col, int(col in COLUMN_GRANTS.get(name, '').split()))
                   for name, fields in tables.items() for col in fields]
        verify_permission_rows(cursor, columns, "ISNULL(HAS_PERMS_BY_NAME(n,'OBJECT','SELECT',p,'COLUMN'),0)")
    finally:
        cursor.execute('REVERT;')


def verify_permission_rows(cursor, rows, predicate):
    values = ','.join('(?,?,?)' for _ in rows)
    checked = cursor.execute(f'SELECT TOP(1) n,p FROM (VALUES {values}) AS grants(n,p,expected) '
                             f'WHERE {predicate} <> expected', *chain.from_iterable(rows)).fetchone()
    if checked:
        raise SetupError(f'Quyền runtime sai phạm vi với {checked[0]} ({checked[1]}).')


@contextmanager
def transaction(cursor):
    cursor.execute(SESSION_SETTINGS + ' BEGIN TRANSACTION;')
    try:
        yield
        cursor.execute('COMMIT TRANSACTION;')
    except BaseException:
        cursor.execute('IF XACT_STATE()<>0 ROLLBACK TRANSACTION;')
        raise


def install(config):
    if CONFIG.is_file():
        installed = validate(read_json(CONFIG))
        with closing(sql_connect(installed)) as con, closing(con.cursor()) as cursor:
            server_guard(cursor, installed)
            validate_grants(cursor, installed, validate_schema(cursor, installed))
        print('SETUP_ALREADY_INSTALLED (read only)')
        return installed
    if not fresh_target(config['database']):
        raise SetupError('Bản cài mới cần database trống theo mẫu IronPulse_Clean...QA.')
    database, login = map(quoted, (config['database'], config['login']))
    pending = CONFIG.with_name('portable-setup-pending.json')
    with closing(sql_connect(config, master=True)) as con, closing(con.cursor()) as cursor:
        major = server_guard(cursor, config, master=True)
        cursor.execute("""DECLARE @status int;
            EXEC @status=sys.sp_getapplock @Resource=?,@LockMode=N'Exclusive',@LockOwner=N'Session',@LockTimeout=0;
            IF @status<0 THROW 52701,'Portable setup in progress',1;""", 'IronPulsePortable:' + config['database'].casefold())
        occupied = cursor.execute('SELECT DB_ID(?)', config['database']).fetchval()
        if pending.is_file():
            previous = validate(read_json(pending))
            if any(config[key].casefold() != previous[key].casefold() for key in ('server', 'database', 'login')):
                raise SetupError('Có lần cài dở. Chạy lại đúng instance, database và tài khoản đã chọn.')
            config = previous
            if not occupied:
                raise SetupError('Database của lần cài dở không còn tồn tại.')
            envelope = json.loads(dpapi((windows_profile(config['install_id']) / 'clean-credentials.dpapi').read_bytes(),
                                        decrypt=True))
        else:
            if occupied:
                raise SetupError('Database đã tồn tại. Giữ nguyên dữ liệu và dùng đúng cấu hình cài đặt.')
            verify_vacant_login(cursor, config)
            if (cursor.execute('SELECT 1 FROM model.sys.objects WHERE is_ms_shipped=0').fetchone()
                    or cursor.execute("""SELECT 1 FROM model.sys.database_principals
                                         WHERE principal_id>4 AND is_fixed_role=0""").fetchone()):
                raise SetupError('Database model có object hoặc quyền riêng, không thể bảo đảm bootstrap sạch.')
            reference = cursor.execute("SELECT CONVERT(varchar(19),SYSDATETIME(),126)").fetchval()
            envelope = {'reference': reference, 'passwords': {name: secrets.token_urlsafe(24) for name in ACCOUNTS}}
            credential = windows_profile(config['install_id']) / 'clean-credentials.dpapi'
            atomic_write(credential, dpapi(json.dumps(envelope).encode()))
            cursor.execute(f'CREATE DATABASE {database}')
            cursor.execute(f'ALTER DATABASE {database} SET AUTO_CLOSE OFF')
            cursor.execute(f'ALTER DATABASE {database} SET RECOVERY SIMPLE')
            config['broker'] = str(cursor.execute('SELECT service_broker_guid FROM sys.databases WHERE name=?',
                                                  config['database']).fetchval()).lower()
            config['database_schema'] = DATABASE_SCHEMA
            config['dataset'] = MARKER
            write_json(pending, config)
        with closing(sql_connect(config)) as setup, closing(setup.cursor()) as deployment:
            server_guard(deployment, config)
            database_guard(deployment, config)
            if not deployment.execute('SELECT 1 FROM sys.objects WHERE is_ms_shipped=0').fetchone():
                verify_vacant_login(cursor, config)
                install_objects(deployment, config, login, database, envelope)
            validate_grants(deployment, config, validate_schema(deployment, config))
            deployment.execute(f'ALTER LOGIN {login} ENABLE;')
        write_json(CONFIG, config)
        pending.unlink(missing_ok=True)
    print(f'SETUP_DATABASE_PASS {config["database"]} SQL_MAJOR={major}')
    return config


def verify_vacant_login(cursor, config):
    if cursor.execute('SELECT 1 FROM sys.server_principals WHERE name=? OR sid=SUSER_SID(?)',
                      config['login'], config['login']).fetchone():
        raise SetupError('Tài khoản Windows đã có SQL login. Dùng tài khoản tiêu chuẩn riêng cho bản cài này.')


def install_objects(deployment, config, login, database, envelope):
    reference = datetime.fromisoformat(envelope['reference'])
    data, roster, accounts = generate(reference, envelope['passwords'])
    with transaction(deployment):
        for step, batch in enumerate(schema_batches(), 1):
            try:
                deployment.execute(batch)
            except pyodbc.Error:
                print(f'SQL_BOOTSTRAP_BATCH_FAILED {step}', flush=True)
                raise
        deploy_trainer_schedule(deployment)
        seed_clean(deployment, config['database'], data)
        compatibility(deployment)
        deployment.execute("""UPDATE dbo.service_type SET service_name=CASE service_type_id
            WHEN 1 THEN N'Tập gym tự do' ELSE N'Lớp nhóm phổ thông' END WHERE service_type_id IN (1,2)""")
        deployment.execute('EXEC sys.sp_addextendedproperty @name=?,@value=?', MARKER_PROPERTY, MARKER)
        deploy_class_rules(deployment)
        deployment.execute('EXEC sys.sp_addextendedproperty @name=?,@value=?', REFERENCE_PROPERTY, reference.isoformat())
        deployment.execute(f'CREATE LOGIN {login} FROM WINDOWS WITH DEFAULT_DATABASE={database};')
        deployment.execute(f'ALTER LOGIN {login} DISABLE;')
        deployment.execute(f'CREATE USER {login} FOR LOGIN {login} WITH DEFAULT_SCHEMA=dbo; GRANT CONNECT TO {login};')
        for table, cols in COLUMN_GRANTS.items():
            deployment.execute(f'GRANT SELECT ON OBJECT::dbo.{quoted(table)} ({", ".join(cols.split())}) TO {login};')
        for name in sorted(PROCEDURE_GRANTS):
            deployment.execute(f'GRANT EXECUTE ON OBJECT::dbo.{quoted(name)} TO {login};')
        deployment.execute('EXEC sys.sp_addextendedproperty @name=?,@value=?', SCHEMA_PROPERTY, DATABASE_SCHEMA)
        deployment.execute('EXEC sys.sp_addextendedproperty @name=?,@value=?', INSTALL_PROPERTY, config['install_id'])
        validate_schema(deployment, config)
        counts, checks = validate_seed(deployment, reference)
        write_json(CONFIG.with_name('clean-roster.json'), roster)
        write_json(CONFIG.with_name('clean-install-check.json'), {'counts': counts, 'rules': checks, 'reference': reference.isoformat()})
        atomic_write(windows_profile(config['install_id']) / 'clean-accounts.dpapi',
                     dpapi(json.dumps(accounts, ensure_ascii=False).encode()))
        print(f'CLEAN_DATASET_PASS {len(counts)} tables {sum(counts.values())} rows {len(checks)} checks')


def rename_demo_plans(cursor, *, portable, write=False, undo=False, only=None):
    """Validate both known rows before touching either, then check the full plan table."""
    mode = 'UPDLOCK,HOLDLOCK' if write else 'HOLDLOCK'
    rows = [list(row) for row in cursor.execute(
        f'SELECT * FROM dbo.membership_plan WITH ({mode}) ORDER BY plan_id').fetchall()]
    columns = {col[0]: i for i, col in enumerate(cursor.description)}
    keys = {row[columns['plan_id']]: row for row in rows}
    planned = []
    for key, (original, replacement) in DEMO_PLAN_RENAMES.items():
        row = keys.get(key)
        if row is None or (row[columns['base_price']], row[columns['duration_months']]) != (300000, 1):
            raise SetupError(f'Gói #{key} không khớp seed.')
        name = row[columns['plan_name']]
        if name not in (original, replacement):
            raise SetupError(f'Gói #{key} đã có tên khác. Giữ nguyên dữ liệu.')
        rights = dict(cursor.execute(f"""SELECT s.service_name,i.quota_per_cycle
            FROM dbo.plan_inclusion i WITH ({mode})
            JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
            WHERE i.plan_id=?""", key).fetchall())
        expected = {'Local-02 · Buổi PT': 1, 'Local-02 · Sử dụng phòng tập': -1} if portable else {}
        if rights != expected:
            raise SetupError(f'Quyền lợi của gói #{key} đã khác seed.')
        target = original if undo else replacement
        if any(other != key and record[columns['plan_name']] == target for other, record in keys.items()):
            raise SetupError(f'Tên đích của gói #{key} trùng với gói khác.')
        if name != target and (only is None or key in only):
            planned.append((key, name, target))
    if write:
        for key, name, target in planned:
            touched = cursor.execute("""UPDATE dbo.membership_plan SET plan_name=? OUTPUT inserted.plan_id
                WHERE plan_id=? AND plan_name COLLATE Latin1_General_100_BIN2=?""", target, key, name).fetchall()
            if len(touched) != 1 or touched[0][0] != key:
                raise SetupError(f'Số dòng cập nhật của gói #{key} không khớp.')
            keys[key][columns['plan_name']] = target
        actual = [list(row) for row in cursor.execute('SELECT * FROM dbo.membership_plan ORDER BY plan_id')]
        if actual != rows:
            raise SetupError('Danh mục đã thay đổi ngoài hai tên được phép.')
    return planned


def refresh_demo_labels(config, *, apply=False, undo=False):
    if config['database'].casefold() == 'ironpulse_installqa':
        raise SetupError('IronPulse_InstallQA dành riêng cho bằng chứng LOCAL-06A.')
    checkpoint = CONFIG.with_name('r2a-demo-labels.json')
    previous = read_json(checkpoint) if checkpoint.exists() else None
    if previous and previous['install_id'] != config['install_id']:
        raise SetupError('Checkpoint hoàn tác thuộc bản cài khác.')
    if undo and previous is None:
        raise SetupError('Chưa có lần đổi tên để hoàn tác.')
    with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
        server_guard(cursor, config)
        database_guard(cursor, config)
        validate_schema(cursor, config)
        with transaction(cursor):
            approved = set(previous['ids']) if undo else None
            planned = rename_demo_plans(cursor, portable=True, write=apply or undo, undo=undo, only=approved)
            if apply and planned:
                ids = set(previous['ids']) if previous else set()
                write_json(checkpoint, {'install_id': config['install_id'], 'ids': sorted(ids | {r[0] for r in planned})})
    if undo:
        checkpoint.unlink()
    for key, before, after in planned:
        print(f'#{key} {before} → {after}')
    print(f'R2A {"CHANGED" if apply or undo else "PREVIEW"} {len(planned)}')
