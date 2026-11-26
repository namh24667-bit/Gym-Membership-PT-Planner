"""CLI invoked by the two Windows wrappers."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

script = Path(__file__).resolve()
sys.path[:0] = [str(script.parent), str(script.parents[2])]

import pyodbc
from app.class_eligibility_sql import deploy as deploy_class_eligibility
from app.staff_directory_sql import deploy as deploy_staff_directory
from app.trainer_schedule_sql import deploy as deploy_trainer_schedule
from app.db import DatabaseUnavailable
from app.portable_config import DATABASE_SCHEMA, DRIVER

from clean_compat import deploy_class_rules
from common import ROOT, SetupError, current_installation, dpapi, new_installation, read_json, windows_profile
from database import (database_guard, install, refresh_demo_labels,
                      server_guard, sql_connect, transaction, validate_schema)
from seed import ACCOUNTS, email


def main():
    parser = argparse.ArgumentParser()
    routes = parser.add_subparsers(dest='action', required=True)
    installer = routes.add_parser('setup')
    for name in ('instance', 'database', 'account'):
        installer.add_argument(f'--{name}', required=True)
    installer.add_argument('--port', type=int, required=True)
    routes.add_parser('version')
    routes.add_parser('configuration')
    eligibility = routes.add_parser('class-eligibility')
    eligibility.add_argument('--undo', action='store_true')
    directory = routes.add_parser('staff-directory')
    directory.add_argument('--undo', action='store_true')
    trainer_schedule = routes.add_parser('trainer-schedule')
    trainer_schedule.add_argument('--undo', action='store_true')
    class_rules = routes.add_parser('class-rules')
    class_rules.add_argument('--undo', action='store_true')
    names = routes.add_parser('demo-labels')
    writing = names.add_mutually_exclusive_group()
    writing.add_argument('--apply', action='store_true')
    writing.add_argument('--undo', action='store_true')
    credentials = routes.add_parser('credentials')
    credentials.add_argument('--pipe', action='store_true')
    runtime = routes.add_parser('runtime')
    runtime.add_argument('mode', choices=['serve', 'check', 'restart', 'stop'])
    runtime.add_argument('--https', action='store_true')
    args = parser.parse_args()

    if args.action == 'version':
        version = read_json(ROOT / 'version.json')
        if version['database'] != DATABASE_SCHEMA:
            raise SetupError('Phiên bản code và manifest không khớp.')
        print(f'IronPulse {version["release"]} | app {version["application"]} | SQL {version["database"]}')
    elif args.action == 'setup':
        if DRIVER not in pyodbc.drivers():
            raise SetupError('Thiếu Microsoft ODBC Driver 18 x64.')
        instance = '' if args.instance.casefold() == 'mssqlserver' else args.instance
        if '\\' in instance or '/' in instance:
            raise SetupError('Chỉ nhập tên instance trên máy này.')
        install(new_installation(instance, args.database, args.account, args.port))
    else:
        config = current_installation()
        if args.action == 'configuration':
            print(config['login'])
            print(config['port'])
        elif args.action in ('class-eligibility', 'staff-directory', 'trainer-schedule'):
            if config.get('dataset'):
                raise SetupError('Phạm vi lịch theo bộ môn đã được cài trong CleanDemo.')
            if config['database'].casefold() == 'ironpulse_installqa':
                raise SetupError('IronPulse_InstallQA dành riêng cho bằng chứng LOCAL-06A.')
            with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
                server_guard(cursor, config)
                database_guard(cursor, config)
                validate_schema(cursor, config)
                with transaction(cursor):
                    apply = {'class-eligibility': deploy_class_eligibility, 'staff-directory': deploy_staff_directory,
                             'trainer-schedule': deploy_trainer_schedule}[args.action]
                    changed = apply(cursor, undo=args.undo)
            print('READ_SCOPE_CHANGED' if changed else 'READ_SCOPE_ALREADY_CURRENT')
        elif args.action == 'class-rules':
            from runtime import check_port

            check_port(config['port'])
            with closing(sql_connect(config)) as connection, closing(connection.cursor()) as cursor:
                server_guard(cursor, config)
                validate_schema(cursor, config)
                try:
                    with transaction(cursor):
                        changed = deploy_class_rules(cursor, undo=args.undo)
                except RuntimeError as error:
                    raise SetupError(str(error)) from None
            print('CLASS_RULES_CHANGED' if changed else 'CLASS_RULES_ALREADY_CURRENT')
        elif args.action == 'demo-labels':
            refresh_demo_labels(config, apply=args.apply, undo=args.undo)
        elif args.action == 'credentials':
            state = windows_profile(config['install_id'])
            if config.get('dataset'):
                accounts = json.loads(dpapi((state / 'clean-accounts.dpapi').read_bytes(), decrypt=True))
                if args.pipe:
                    print(json.dumps(accounts, ensure_ascii=True))
                else:
                    for label, row in accounts.items():
                        print(f'{label} | {row["name"]} | {row["email"]} | {row["password"]}')
            else:
                password = dpapi((state / 'demo.dpapi').read_bytes(), decrypt=True).decode()
                if not args.pipe:
                    for role, name, _ in ACCOUNTS:
                        print(f'{name} | {email(role)}')
                    print('Demo password:')
                print(password)
        else:
            from runtime import run
            password = '' if args.mode == 'stop' else sys.stdin.readline(8193).strip()
            if args.mode != 'stop' and len(password) < 16:
                raise SetupError('Không nhận được mật khẩu demo bằng kênh cục bộ.')
            run(config, args.mode, password, https=args.https)


if __name__ == '__main__':
    try:
        main()
    except pyodbc.Error as error:
        import re
        codes = re.findall(r'\((-?\d{1,10})\)', str(error))
        print(f'BLOCKED SQL ({error.args[0]}, {",".join(codes[:5])})', file=sys.stderr)
        sys.exit(1)
    except (SetupError, DatabaseUnavailable, ValueError, KeyError, OSError) as error:
        explanation = 'SQL runtime từ chối đích hoặc danh tính.' if isinstance(error, DatabaseUnavailable) else str(error)
        print(f'BLOCKED {explanation}', file=sys.stderr)
        sys.exit(1)
