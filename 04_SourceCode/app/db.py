import re
from contextlib import ExitStack, closing
from dataclasses import dataclass
from uuid import UUID

import pyodbc
from flask import current_app, g, has_request_context

from .portable_config import DATABASE_SCHEMA, DRIVER, INSTALL_PROPERTY, SCHEMA_PROPERTY, identifier, validate_scope


class DatabaseUnavailable(Exception):
    pass


class WorkflowRejected(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    person_id: int
    full_name: str
    roles: tuple[str, ...]


SERVER_NAME = re.compile(r"(?:(?:tcp|lpc):)?[A-Za-z0-9_.\\,-]+", re.IGNORECASE)
QA_DATABASE = 'IronPulse_QA'
QA_SERVER = r'lpc:MSI\SQLEXPRESS'
QA_LOGIN = r'MSI\IronPulseQAApp'
LOCAL_QA_LOGINS = (r'MSI\IronPulseApp', QA_LOGIN)
QA_IDENTITY = """
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('MachineName')),
       CONVERT(nvarchar(128), SERVERPROPERTY('InstanceName')),
       CONVERT(varchar(36), service_broker_guid),
       CONVERT(varchar(40), CONNECTIONPROPERTY('net_transport'))
FROM sys.databases
WHERE database_id = DB_ID() AND state_desc = N'ONLINE'
  AND is_trustworthy_on = 0 AND is_db_chaining_on = 0
  AND HAS_DBACCESS(N'IronPulse') = 0
"""

CONNECTION_IDENTITY = """
SELECT DB_NAME(), ORIGINAL_LOGIN(),
       CASE WHEN CONNECTIONPROPERTY('auth_scheme') IN ('NTLM', 'KERBEROS')
                 AND IS_SRVROLEMEMBER('sysadmin') = 0
                 AND HAS_PERMS_BY_NAME(NULL, NULL, 'CONTROL SERVER') = 0
                 AND NOT EXISTS (
                     SELECT 1
                     FROM (VALUES ('securityadmin'), ('serveradmin'), ('dbcreator'),
                                  ('setupadmin'), ('processadmin'), ('diskadmin'), ('bulkadmin')) AS r(name)
                     WHERE ISNULL(IS_SRVROLEMEMBER(r.name), 1) <> 0
                 )
                 AND USER_NAME() NOT IN ('dbo', 'guest')
                 AND IS_ROLEMEMBER('db_owner') = 0
                 AND IS_ROLEMEMBER('db_ddladmin') = 0
                 AND IS_ROLEMEMBER('db_securityadmin') = 0
                 AND IS_ROLEMEMBER('db_accessadmin') = 0
                 AND IS_ROLEMEMBER('db_backupoperator') = 0
                 AND IS_ROLEMEMBER('db_datareader') = 0
                 AND IS_ROLEMEMBER('db_datawriter') = 0
                 AND HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL') = 0
                 AND HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT') = 0
                 AND HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT') = 0
                 AND HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE') = 0
                 AND HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE') = 0
                 AND HAS_PERMS_BY_NAME('dbo.person', 'OBJECT', 'SELECT') = 0
                 AND HAS_PERMS_BY_NAME('dbo.person', 'OBJECT', 'SELECT', 'ssn', 'COLUMN') = 0
                 AND HAS_PERMS_BY_NAME('dbo.member', 'OBJECT', 'SELECT', 'health_notes', 'COLUMN') = 0
            THEN 1 ELSE 0 END
"""


def is_workflow_qa(config):
    return config.get('LOCAL_QA') and (
        config['SQL_DATABASE'] == QA_DATABASE or config.get('PORTABLE_QA'))


def portable_connection_scope(config):
    if not config.get('LOCAL_QA'):
        raise ValueError('Portable mode requires local QA.')
    machine, instance = validate_scope(config['SQL_SERVER'], config['SQL_DATABASE'], config['SQL_WINDOWS_LOGIN'])
    return (machine.casefold(), instance.casefold(), identifier(config['SQL_QA_BROKER_GUID']),
            identifier(config['PORTABLE_INSTALL_ID']))


def verify_portable_connection(cursor, scope):
    host, instance, broker, install_id = scope
    row = cursor.execute(QA_IDENTITY.replace("HAS_DBACCESS(N'IronPulse')", "ISNULL(HAS_DBACCESS(N'IronPulse'),0)")).fetchone()
    if (not row or str(row[0]).casefold() != host or (row[1] or '').casefold() != instance
            or str(row[2]).casefold() != str(broker) or row[3] != 'Shared memory'):
        raise DatabaseUnavailable
    properties = dict(cursor.execute("""SELECT name,CONVERT(nvarchar(100),value)
        FROM sys.extended_properties WHERE class=0 AND name IN (?,?)""", SCHEMA_PROPERTY, INSTALL_PROPERTY).fetchall())
    if properties != {SCHEMA_PROPERTY: DATABASE_SCHEMA, INSTALL_PROPERTY: str(install_id)}:
        raise DatabaseUnavailable


def close_request_connection(_error=None):
    connection = g.pop('ironpulse_connection', None)
    if connection is not None:
        connection.close()


def _fetch(statement, *params, many=False, workflow_errors=False):
    config = current_app.config
    server = config['SQL_SERVER']
    login = config['SQL_WINDOWS_LOGIN']
    database = config.get('SQL_DATABASE', 'IronPulse')
    local_qa = config.get('LOCAL_QA', False)
    if not server or not SERVER_NAME.fullmatch(server) or not login or '\\' not in login:
        raise DatabaseUnavailable
    portable = config.get('PORTABLE_QA')
    if portable:
        try:
            scope = portable_connection_scope(config)
        except (ValueError, KeyError):
            raise DatabaseUnavailable from None
    elif database not in ('IronPulse', QA_DATABASE) or (local_qa and database != QA_DATABASE):
        raise DatabaseUnavailable
    elif database == QA_DATABASE:
        broker = config.get('SQL_QA_BROKER_GUID')
        try:
            guid = UUID(broker) if broker else None
        except ValueError:
            raise DatabaseUnavailable from None
        logins = LOCAL_QA_LOGINS if local_qa else (QA_LOGIN,)
        if (not (local_qa or guid) or (guid and not guid.int)
                or server.casefold() != QA_SERVER.casefold()
                or login.casefold() not in {name.casefold() for name in logins}):
            raise DatabaseUnavailable
    elif login.casefold() == QA_LOGIN.casefold() or config.get('SQL_QA_BROKER_GUID'):
        raise DatabaseUnavailable

    connection_string = (
        f'Driver={{{DRIVER}}};'
        f'Server={server};Database={database};Trusted_Connection=yes;'
        f'Encrypt=Mandatory;TrustServerCertificate={"yes" if local_qa else "no"};'
    )
    reuse = local_qa and has_request_context()
    connection = g.get('ironpulse_connection') if reuse else None
    new_connection = connection is None
    stage = 'connect' if new_connection else 'query'
    try:
        with ExitStack() as lease:
            if new_connection:
                connection = lease.enter_context(closing(pyodbc.connect(connection_string, timeout=5, autocommit=True)))
                connection.timeout = 5
            with closing(connection.cursor()) as cursor:
                if new_connection:
                    stage = 'identity'
                    identity = cursor.execute(CONNECTION_IDENTITY).fetchone()
                    if (not identity or identity[0] != database or identity[2] != 1
                            or not identity[1] or identity[1].casefold() != login.casefold()):
                        raise DatabaseUnavailable
                    if portable:
                        stage = 'portable_qa_target'
                        verify_portable_connection(cursor, scope)
                    elif database == QA_DATABASE:
                        stage = 'qa_target'
                        target = cursor.execute(QA_IDENTITY).fetchone()
                        if (not target or str(target[0]).casefold() != 'msi'
                                or str(target[1]).casefold() != 'sqlexpress'
                                or str(target[3]).casefold() != 'shared memory'
                                or (guid and str(target[2]).casefold() != str(guid))):
                            raise DatabaseUnavailable
                    if reuse:
                        g.ironpulse_connection = connection
                        lease.pop_all()  # Teardown closes the verified connection after the request.
                stage = 'query'
                cursor.execute(statement, *params)
                return cursor.fetchall() if many else cursor.fetchone()
    except pyodbc.Error as error:
        if reuse:
            close_request_connection()
        if workflow_errors and (match := re.search(r'\((5210[1-7]|5220[1-9]|523(?:0[1-9]|10)|5100[1-9]|1205|1222)\)', str(error))):
            raise WorkflowRejected(int(match[1])) from None
        if local_qa:
            state = str(error.args[0]) if error.args else ''
            codes = re.findall(r'\((-?\d{1,10})\)', str(error))
            current_app.logger.warning('Local QA ODBC failure stage=%s sqlstate=%s native=%s', stage,
                                       state if re.fullmatch(r'[A-Z0-9]{5}', state) else 'unknown',
                                       ','.join(codes[:4]) or 'unknown')
        raise DatabaseUnavailable from None
    except DatabaseUnavailable:
        if local_qa:
            current_app.logger.warning('Local QA SQL connection rejected stage=%s', stage)
        raise DatabaseUnavailable from None


WORKFLOW_PROCEDURES = ('register_member', 'catalog', 'staff_members', 'create_contract', 'contracts',
                       'benefits', 'collect_payment', 'activate')
SCHEDULE_PROCEDURES = ('schedule', 'book_pt', 'book_group', 'cancel_group', 'create_group', 'expire', 'focus')
ADMIN_PROCEDURES = ('members', 'personnel', 'catalog', 'classes', 'assets', 'transactions', 'dashboard', 'services')
PROCEDURES = {'local02': WORKFLOW_PROCEDURES, 'local03': SCHEDULE_PROCEDURES, 'local04': ADMIN_PROCEDURES}


def workflow_available(group='local02'):
    procedures = PROCEDURES[group]
    names = ', '.join(f"(N'dbo.{group}_{name}')" for name in procedures)
    row = _fetch("SELECT COUNT(*) FROM (VALUES " + names + ") AS p(name) "
                 "WHERE HAS_PERMS_BY_NAME(p.name,'OBJECT','EXECUTE')=1")
    return bool(row and row[0] == len(procedures))


def workflow(name, *params, many=False, group='local02'):
    if (name not in PROCEDURES.get(group, ()) or not current_app.config.get(f'{group.upper()}_ENABLED')
            or not is_workflow_qa(current_app.config)):
        raise DatabaseUnavailable
    placeholders = ', '.join('?' for _ in params)
    return _fetch(f'EXEC dbo.{group}_{name} {placeholders}', *params, many=many, workflow_errors=True)


PERSON_COLUMNS = "p.person_id, p.full_name, m.person_id, t.employment_status, s.employment_status, s.position"
PERSON_ROLES = """
FROM dbo.person AS p
LEFT JOIN dbo.member AS m ON m.person_id = p.person_id
LEFT JOIN dbo.trainer AS t ON t.person_id = p.person_id
LEFT JOIN dbo.staff AS s ON s.person_id = p.person_id
"""


def _principal(row):
    person_id, full_name, member_id, trainer_status, staff_status, position = row[:6]
    roles = []
    if member_id is not None:
        roles.append('member')
    if trainer_status in ('ACTIVE', 'ON_LEAVE'):
        roles.append('trainer')
    if staff_status == 'ACTIVE':
        roles.append('staff')
        if position == 'Quản lý':
            roles.append('management')
    return Principal(person_id, full_name, tuple(roles))


def find_account(email):
    row = _fetch(f'SELECT {PERSON_COLUMNS}, p.password_hash {PERSON_ROLES} WHERE p.email = ?', email)
    return (_principal(row), row[6]) if row is not None else (None, None)


def get_principal(person_id):
    row = _fetch(f'SELECT {PERSON_COLUMNS} {PERSON_ROLES} WHERE p.person_id = ?', person_id)
    return _principal(row) if row is not None else None


def personal_profile_available():
    row = _fetch("SELECT HAS_PERMS_BY_NAME('dbo.localr1a_profile','OBJECT','EXECUTE')")
    return bool(row and row[0] == 1)


def personal_profile(person_id):
    config = current_app.config
    if not config.get('LOCALR1A_ENABLED') or not is_workflow_qa(config):
        raise DatabaseUnavailable
    return _fetch('EXEC dbo.localr1a_profile ?', person_id)


MEMBERSHIPS = """
FROM dbo.membership AS m
JOIN dbo.membership_plan AS p ON p.plan_id = m.plan_id
WHERE m.person_id = ?
"""


def list_memberships(person_id):
    return _fetch(f'SELECT m.membership_id, p.plan_name {MEMBERSHIPS} ORDER BY m.membership_id DESC',
                  person_id, many=True)


def get_membership(person_id, membership_id):
    return _fetch(f'SELECT p.plan_name, m.status, m.start_date, m.end_date {MEMBERSHIPS} AND m.membership_id = ?',
                  person_id, membership_id)


TRAINER_SESSIONS = """
FROM dbo.[session] AS s
JOIN dbo.room AS r ON r.room_id = s.room_id
WHERE s.trainer_id = ?
"""


def list_trainer_sessions(person_id):
    return _fetch(f'SELECT s.session_id, s.start_time {TRAINER_SESSIONS} ORDER BY s.start_time, s.session_id',
                  person_id, many=True)


def get_trainer_session(person_id, session_id):
    return _fetch(f'SELECT s.session_type, r.room_name, s.start_time, s.end_time {TRAINER_SESSIONS} AND s.session_id = ?',
                  person_id, session_id)
