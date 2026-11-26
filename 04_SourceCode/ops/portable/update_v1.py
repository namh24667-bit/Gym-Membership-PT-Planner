"""Protect local SQL data during supported v1 updates."""
from contextlib import closing, contextmanager
from pathlib import PureWindowsPath
from uuid import uuid4

from app.trainer_schedule_sql import target_definition
from clean_compat import CLASS_RULES_PROPERTY, deploy_class_rules
from clean_seed import MARKER
from common import SetupError, validate
from database import quoted, server_guard, sql_connect, transaction, validate_grants, validate_schema


def finish(cursor):
    while cursor.nextset():
        pass


def backup_legacy(config):
    config = validate(config)
    if config.get('dataset') or config['database'].casefold() in {
            'ironpulse_installqa', 'ironpulse_workflowqa', 'ironpulse_perfqa'}:
        raise SetupError('Đích không phải bản cài portable 0.9.1 được phép cập nhật.')
    with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
        server_guard(cursor, config)
        validate_grants(cursor, config, validate_schema(cursor, config))
        definition = cursor.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.local03_schedule'))").fetchval()
        if target_definition(definition) is not None:
            raise SetupError('SQL nguồn chưa có đầy đủ phạm vi lịch R2G của 0.9.1.')
        return backup_database(cursor, config['database'])


def backup_database(cursor, database):
    base = cursor.execute("SELECT CONVERT(nvarchar(500),SERVERPROPERTY('InstanceDefaultBackupPath'))").fetchval()
    if not base:
        raise SetupError('Instance chưa có đường dẫn backup.')
    label = f'{database}_pre1_{uuid4().hex}'
    path = str(PureWindowsPath(base) / (label + '.bak'))
    if tuple(cursor.execute('SELECT file_exists,file_is_a_directory,parent_directory_exists FROM sys.dm_os_file_exists(?)',
                            path).fetchone()) != (0, 0, 1):
        raise SetupError('Không thể tạo tệp backup mới an toàn.')
    finish(cursor.execute(f'BACKUP DATABASE {quoted(database)} TO DISK=? WITH COPY_ONLY,CHECKSUM,NAME=?', path, label))
    finish(cursor.execute('RESTORE VERIFYONLY FROM DISK=? WITH CHECKSUM,FILE=1', path))
    result = cursor.execute("""SELECT CONVERT(varchar(36),b.backup_set_uuid),CONVERT(bigint,b.backup_size)
        FROM msdb.dbo.backupset b JOIN msdb.dbo.backupmediafamily f ON f.media_set_id=b.media_set_id
        WHERE b.database_name=? AND b.name=? AND f.physical_device_name=? AND b.position=1
            AND b.is_copy_only=1 AND b.has_backup_checksums=1 AND b.is_damaged=0""", database, label, path).fetchall()
    if len(result) != 1:
        raise SetupError('Không xác minh được bản backup mới.')
    uuid, size = result[0]
    return {'database': database, 'backup': path, 'uuid': uuid, 'bytes': size}


def validate_patch_target(config):
    config = validate(config)
    if config.get('dataset') != MARKER:
        raise SetupError('Đường nâng cấp v1.0.1 này yêu cầu bản cài v1.0 có dataset CleanDemo.')
    return config


def backup_patch(config):
    config = validate_patch_target(config)
    with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
        server_guard(cursor, config)
        validate_grants(cursor, config, validate_schema(cursor, config))
        if cursor.execute('SELECT 1 FROM sys.extended_properties WHERE class=0 AND name=?',
                          CLASS_RULES_PROPERTY).fetchone():
            raise SetupError('SQL nguồn đã có bản vá ngoài checkpoint cập nhật.')
        return backup_database(cursor, config['database'])


@contextmanager
def patch_rules(config, snapshot, save=None):
    config = validate_patch_target(config)
    target = {key: config[key] for key in ('server', 'database', 'login', 'broker', 'install_id')}
    if snapshot is not None and snapshot != target:
        raise SetupError('Checkpoint quy tắc lớp không khớp bản cài.')
    with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
        server_guard(cursor, config)
        validate_grants(cursor, config, validate_schema(cursor, config))
        with transaction(cursor):
            changed = deploy_class_rules(cursor, undo=snapshot is not None)
            if snapshot is None:
                if not changed or save is None:
                    raise SetupError('Không thể ghi checkpoint quy tắc lớp.')
                save(target)
            yield
