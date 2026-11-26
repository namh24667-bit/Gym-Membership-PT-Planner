"""Local Windows QA target shared by the app and the portable installer."""
import os
import re
from uuid import UUID


DRIVER = 'ODBC Driver 18 for SQL Server'
DATABASE_SCHEMA = 'local05c-r1b.1'
SCHEMA_PROPERTY = 'IronPulsePortableSchema'
INSTALL_PROPERTY = 'IronPulsePortableInstall'
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,62}')
DATABASE = re.compile(r'IronPulse_[A-Za-z0-9]{0,32}QA', re.IGNORECASE)
ACCOUNT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,19}')


def validate_scope(server, database, login, machine=None):
    machine = machine or os.environ.get('COMPUTERNAME', '')
    if not NAME.fullmatch(machine) or not isinstance(server, str):
        raise ValueError('Invalid local Windows SQL host.')
    host, _, instance = server[4:].partition('\\')
    if (not server.startswith('lpc:') or host.casefold() != machine.casefold()
            or (instance and not NAME.fullmatch(instance)) or server.endswith('\\')):
        raise ValueError('Use the local Windows SQL instance through Shared Memory.')
    if not isinstance(database, str) or not DATABASE.fullmatch(database) or database.casefold() == 'ironpulse_perfqa':
        raise ValueError('Use a dedicated IronPulse QA database.')
    if not isinstance(login, str):
        raise ValueError('Use a separate local Windows account.')
    domain, _, user = login.partition('\\')
    if domain.casefold() != machine.casefold() or not ACCOUNT.fullmatch(user):
        raise ValueError('Use a separate local Windows account.')
    return machine, instance


def identifier(value):
    result = UUID(str(value))
    if not result.int:
        raise ValueError('Missing installation identity.')
    return result
