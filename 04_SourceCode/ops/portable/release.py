"""Allowlisted team archive, verified file updates and recoverable local rollback."""
import argparse
from contextlib import contextmanager, nullcontext
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import sys
import tempfile
from uuid import uuid4
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile


TOOL_ROOT = Path(__file__).resolve().parents[2]
ROOT = TOOL_ROOT
MANIFEST = 'package-manifest.json'
FIXED = set('''README.md version.json requirements.txt requirements-team.lock portable.example.json
Setup-IronPulse.cmd Mo-IronPulse.cmd Update-IronPulse.cmd docs/TEAM-TEST.md'''.split())
PORTABLE = set('''Setup.ps1 Launch.ps1 Update.ps1 New-TeamCertificate.ps1 main.py runtime.py common.py
database.py seed.py smoke.py release.py schema.sql'''.split())
UPGRADE_STEP = 'ops/portable/upgrade.py'
BASE_STEPS = ['ops/portable/schema.sql']
FINAL = '1.0.0'
PATCH = '1.0.1'
FINAL_STEPS = BASE_STEPS + ['ops/portable/clean_compat.py']
PATCH_STEPS = FINAL_STEPS + ['class-rules']
FINAL_DOCS = {'docs/INSTALLATION_AND_USER_GUIDE.md', 'docs/RELEASE_NOTES_v1.0.md'}
PATCH_DOCS = {'docs/INSTALLATION_AND_USER_GUIDE.md', 'docs/RELEASE_NOTES_v1.0.1.md'}
RELEASE_DOCS = {FINAL: FINAL_DOCS, PATCH: PATCH_DOCS}
FINAL_TOOLS = {'clean_seed.py', 'clean_checks.py', 'clean_compat.py', 'clean_compat.sql',
               'clean_quality.sql', 'clean_count.sql', 'update_v1.py'}
ASSETS = {'bootstrap.min.css', 'site.css', 'form-submit.js', 'ironpulse-mark.svg', 'ironpulse-lift.svg',
          'preview.css', 'preview-search.js', 'bootstrap.LICENSE.txt'}
# Keep reading older archives that contain the former authentication image.
LEGACY_ASSETS = {'ironpulse-training.jpg'}
CONFIG = ROOT / 'instance/portable.json'
ACTIVE = ROOT / 'instance/portable-venv.txt'
GATE = ROOT / 'instance/portable-update.lock'
PENDING = ROOT / 'instance/portable-update-pending.json'
LATEST = ROOT / 'instance/portable-update-last.json'
ENCODING = 'utf-8'


def allowed(name):
    path = PurePosixPath(name)
    if path.as_posix() != name or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..')
                                      or part.endswith('.') or re.fullmatch(r'(?i)(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?', part)
                                      for part in path.parts):
        return False
    if name in FIXED | FINAL_DOCS | PATCH_DOCS:
        return True
    part = path.parts
    if len(part) == 3 and part[:2] == ('ops', 'portable'):
        return part[-1] in PORTABLE | FINAL_TOOLS or name == UPGRADE_STEP
    if len(part) == 3 and part[:2] == ('app', 'static'):
        return part[-1] in ASSETS | LEGACY_ASSETS
    return bool(
        len(part) >= 3 and part[:2] == ('app', 'templates') and path.suffix == '.html'
        or len(part) == 2 and part[0] == 'app' and path.suffix == '.py'
        or len(part) == 2 and part[0] == 'tests' and path.name.startswith('test_') and path.suffix == '.py'
    )


def digest(data):
    return sha256(data).hexdigest()


def canonical(object_):
    return (json.dumps(object_, indent=2, sort_keys=True) + '\n').encode()


def version_tuple(value):
    if value == FINAL:
        return 1, 0, 0, 0
    if value == PATCH:
        return 1, 0, 1, 0
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)-test(?:\.(\d+))?', value)
    if not match:
        raise ValueError('Release phải theo dạng 0.9.0-test hoặc 0.9.0-test.1.')
    return tuple(int(item or 0) for item in match.groups())


def make_manifest(files):
    version = json.loads(files['version.json'])
    version_tuple(version['release'])
    return canonical({'format': 1, 'version': version,
                      'files': {name: digest(data) for name, data in sorted(files.items())}})


def validate_manifest(raw):
    package = json.loads(raw)
    if package['format'] != 1:
        raise ValueError('Định dạng manifest không được hỗ trợ.')
    files = package['files']
    release = package['version']['release']
    common_files = FIXED - {'docs/TEAM-TEST.md'} if release in RELEASE_DOCS else FIXED
    if not common_files <= files.keys() or not all(f'ops/portable/{item}' in files for item in PORTABLE):
        raise ValueError('Manifest thiếu thành phần bắt buộc.')
    if not all(allowed(name) and re.fullmatch(r'[a-f0-9]{64}', value) for name, value in files.items()):
        raise ValueError('Manifest có đường dẫn hoặc SHA-256 không hợp lệ.')
    if (len({name.casefold() for name in files}) != len(files)
            or {'app/__init__.py', 'app/db.py', 'app/templates/base.html', 'app/static/site.css'} - files.keys()):
        raise ValueError('Manifest thiếu mã nguồn hoặc chứa đường dẫn trùng.')
    version_tuple(release)
    if release in RELEASE_DOCS:
        required = RELEASE_DOCS[release] | {f'ops/portable/{name}' for name in FINAL_TOOLS}
        steps, previous = (PATCH_STEPS, FINAL) if release == PATCH else (FINAL_STEPS, '0.9.1-test')
        if (not required <= files.keys() or package['version']['sql_steps'] != steps
                or package['version'].get('update_from') != [previous]
                or package['version'].get('application') != release):
            raise ValueError(f'Manifest {release} thiếu thành phần hoặc khai báo nâng cấp không hợp lệ.')
    elif package['version']['sql_steps'] not in (BASE_STEPS, BASE_STEPS + [UPGRADE_STEP]):
        raise ValueError('Manifest chứa bước SQL ngoài phạm vi hỗ trợ.')
    if UPGRADE_STEP in package['version']['sql_steps'] and UPGRADE_STEP not in files:
        raise ValueError('Manifest thiếu bước SQL đã công bố.')
    return package


def scan_content(name, data):
    if name.endswith(('.md', '.py', '.json', '.ps1', '.cmd', '.html', '.css', '.js', '.sql', '.txt', '.lock', '.svg')):
        text = data.decode('utf-8-sig')
        if name == 'tests/test_local03.py':
            text = text.replace('test-only-key-for-local-http-tests', '')
        if name == 'tests/test_local04.py':
            text = text.replace('test-admin-session-key-only-123456', '')
        if (re.search(r'-----BEGIN (?:ENCRYPTED |RSA |EC )?PRIVATE KEY-----', text)
                or re.search(r'(?i)(?:password|secret_key|api_key)\s*[:=]\s*["\x27][A-Za-z0-9+/_=-]{24,}["\x27]', text)
                or re.search(r'AQAAANCMnd8BFdERjHoAwE/Cl[+]s|76492d1116743f04' + r'23413b16050a5345', text)):
            raise ValueError(f'Cần kiểm tra chuỗi nhạy cảm tại {name}.')


def checked_files(package, reader):
    files = {}
    for name, value in package['files'].items():
        data = reader(name)
        if digest(data) != value:
            raise ValueError(f'SHA-256 không khớp {name}.')
        scan_content(name, data)
        files[name] = data
    if json.loads(files['version.json']) != package['version']:
        raise ValueError('Version và manifest không khớp.')
    return files


def read_archive(path):
    with ZipFile(path) as archive:
        infos = archive.infolist()
        if (len(infos) > 300 or sum(item.file_size for item in infos) > 64 * 1024**2
                or len({item.filename.casefold() for item in infos}) != len(infos)
                or any(not (allowed(item.filename) or item.filename == MANIFEST) for item in infos)):
            raise ValueError('ZIP có đường dẫn, số lượng hoặc kích thước ngoài phạm vi.')
        raw = archive.read(MANIFEST)
        package = validate_manifest(raw)
        if set(archive.namelist()) != package['files'].keys() | {MANIFEST}:
            raise ValueError('ZIP có file nằm ngoài manifest.')
        return package, checked_files(package, archive.read), raw


def from_directory():
    raw = (ROOT / MANIFEST).read_bytes()
    package = validate_manifest(raw)
    return package, checked_files(package, lambda name: (ROOT / name).read_bytes()), raw


def build(path):
    files = {}
    version = json.loads((ROOT / 'version.json').read_bytes())
    docs = RELEASE_DOCS.get(version['release'])
    fixed = FIXED - {'docs/TEAM-TEST.md'} if docs else FIXED
    candidates = [ROOT / name for name in fixed]
    candidates += [ROOT / 'ops/portable' / name for name in PORTABLE]
    if docs:
        candidates += [ROOT / name for name in docs] + [ROOT / 'ops/portable' / name for name in FINAL_TOOLS]
    if UPGRADE_STEP in version['sql_steps']:
        candidates.append(ROOT / UPGRADE_STEP)
    legacy = {ROOT / 'app' / 'static' / name for name in LEGACY_ASSETS}
    directories = ('app',) if docs else ('app', 'tests')
    candidates += [item for directory in directories for item in (ROOT / directory).rglob('*')
                   if item.is_file() and item not in legacy and allowed(item.relative_to(ROOT).as_posix())]
    for item in candidates:
        name = item.relative_to(ROOT).as_posix()
        if not item.resolve().is_relative_to(ROOT):
            raise ValueError(f'File nằm ngoài workspace {name}')
        files[name] = item.read_bytes()
        if name == 'README.md':
            guide = 'INSTALLATION_AND_USER_GUIDE.md' if docs else 'TEAM-TEST.md'
            files[name] = f'# IronPulse {version["release"]}\n\n[Huong dan cai dat va su dung](docs/{guide}).\n'.encode()
        scan_content(name, files[name])
    raw = make_manifest(files)
    validate_manifest(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'x', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        archive.writestr(MANIFEST, raw)
    read_archive(path)
    print(f'ZIP_PASS {len(files) + 1} files {path.stat().st_size} bytes SHA256={digest(path.read_bytes())}')


def put(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
        stream.write(content)
    try:
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def no_listener(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            raise ValueError('Cổng đang phục vụ. Dừng bản cài bằng Mo-IronPulse.cmd --stop trước khi cập nhật.')


@contextmanager
def update_gate():
    config = json.loads(CONFIG.read_text(encoding=ENCODING))
    try:
        with GATE.open('x', encoding=ENCODING):
            pass
    except FileExistsError:
        raise ValueError('Đang cập nhật. Nếu phiên trước bị gián đoạn, xem hướng dẫn phục hồi.') from None
    try:
        no_listener(config['port'])
        yield config
    finally:
        GATE.unlink()


def active_venv():
    return ACTIVE.read_text(encoding=ENCODING).strip() if ACTIVE.exists() else '.venv'


def set_active_venv(name):
    if name == '.venv':
        ACTIVE.unlink(missing_ok=True)
    elif re.fullmatch(r'\.venv-team-[a-f0-9]{12}', name):
        put(ACTIVE, (name + '\n').encode())
    else:
        raise ValueError('Môi trường Python không hợp lệ.')


def stage_dependencies(files, previous, offline):
    lock = 'requirements-team.lock'
    if files[lock] == previous[lock]:
        return active_venv()
    name = '.venv-team-' + digest(files[lock])[:12]
    environment = ROOT / name
    candidate = environment / 'Scripts/python.exe'
    subprocess.run([sys._base_executable, '-I', '-m', 'venv', str(environment)], check=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'instance') as directory:
        lock_path = Path(directory) / lock
        lock_path.write_bytes(files[lock])
        command = [str(candidate), '-X', 'utf8', '-I', '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--require-hashes', '-r', str(lock_path)]
        if offline:
            command.extend(['--no-index', '--find-links', offline])
        subprocess.run(command, check=True)
    subprocess.run([candidate, '-I', '-m', 'pip', 'check'], check=True)
    return name


def replace(files, obsolete, manifest):
    for name, data in files.items():
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError('Đường dẫn cập nhật nằm ngoài thư mục cài.')
        if not path.exists() or path.read_bytes() != data:
            put(path, data)
    for name in obsolete:
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError('Đường dẫn cập nhật nằm ngoài thư mục cài.')
        path.unlink(missing_ok=True)
    put(ROOT / MANIFEST, manifest)


def select_target(target):
    global ROOT, CONFIG, ACTIVE, GATE, PENDING, LATEST
    if target is not None:
        root = target.resolve(strict=True)
        if not (root / MANIFEST).is_file() or not (root / 'instance/portable.json').is_file():
            raise ValueError('Chọn thư mục chứa bản IronPulse đã cài.')
        ROOT = root
        CONFIG = ROOT / 'instance/portable.json'
        ACTIVE = ROOT / 'instance/portable-venv.txt'
        GATE = ROOT / 'instance/portable-update.lock'
        PENDING = ROOT / 'instance/portable-update-pending.json'
        LATEST = ROOT / 'instance/portable-update-last.json'


def needs_sql_upgrade(old, new):
    if new['release'] == PATCH:
        if (old['release'] != FINAL or old['sql_steps'] != FINAL_STEPS or new['sql_steps'] != PATCH_STEPS):
            raise ValueError('v1.0.1 chỉ hỗ trợ cập nhật từ v1.0.')
        return True
    if new['release'] == FINAL and old['release'] != FINAL:
        if old['release'] != '0.9.1-test' or old['sql_steps'] != BASE_STEPS + [UPGRADE_STEP]:
            raise ValueError('v1.0 chỉ hỗ trợ cập nhật từ 0.9.1-test.')
        return False
    if old['sql_steps'] == new['sql_steps']:
        return False
    if (old['release'], new['release']) == ('0.9.0-test', '0.9.1-test') and (
            old['sql_steps'] == BASE_STEPS and new['sql_steps'] == BASE_STEPS + [UPGRADE_STEP]):
        return True
    raise ValueError('Phiên bản nguồn hoặc bước SQL không khớp đường nâng cấp hỗ trợ.')


def verified_update_tool(files, expected_hash):
    if not expected_hash or TOOL_ROOT == ROOT:
        raise ValueError('Dùng bộ cập nhật giải nén riêng và SHA-256 đã xác nhận.')
    if any(not (TOOL_ROOT / name).is_file() or (TOOL_ROOT / name).read_bytes() != data
           for name, data in files.items()):
        raise ValueError('Bộ cập nhật đã giải nén không khớp gói đã xác nhận.')


def backup_v1(config, *, patch_release=False):
    sys.path[:0] = [str(TOOL_ROOT / 'ops/portable'), str(TOOL_ROOT)]
    import pyodbc
    from update_v1 import backup_legacy, backup_patch
    try:
        return backup_patch(config) if patch_release else backup_legacy(config)
    except pyodbc.Error as error:
        raise RuntimeError(f'SQL preflight hoặc backup thất bại ({error.args[0]}).') from None


@contextmanager
def change_sql(config, snapshot, save=None, *, patch_release=False):
    sys.path[:0] = [str(TOOL_ROOT / 'ops/portable'), str(TOOL_ROOT)]
    import pyodbc
    from common import SetupError
    if patch_release:
        from update_v1 import patch_rules as change
    else:
        from upgrade import change

    try:
        with change(config, snapshot, save):
            yield
    except pyodbc.Error as error:
        raise RuntimeError(f'Bước SQL thất bại ({error.args[0]}).') from None
    except SetupError as error:
        raise RuntimeError(str(error)) from None


def restore(record, config):
    if not re.fullmatch(r'[a-f0-9]{32}', record['backup']):
        raise ValueError('Checkpoint hoàn tác không hợp lệ.')
    backup = ROOT / 'instance/version-backups' / record['backup']
    old, files, raw = read_archive(backup / 'previous.zip')
    applied = validate_manifest((backup / 'next-manifest.json').read_bytes())
    snapshot = backup / 'sql-before.json'
    patch_release = applied['version']['release'] == PATCH
    if snapshot.is_file() and not needs_sql_upgrade(old['version'], applied['version']):
        raise ValueError('Checkpoint SQL không khớp bản cập nhật.')
    migration = (change_sql(config, json.loads(snapshot.read_bytes()), patch_release=patch_release)
                 if snapshot.is_file() else nullcontext())
    with migration:
        replace(files, applied['files'].keys() - old['files'].keys(), raw)
        set_active_venv(record['venv'])
        from_directory()
    PENDING.unlink(missing_ok=True)
    LATEST.unlink(missing_ok=True)
    print(f'ROLLBACK_PASS {old["version"]["release"]}')


def update(path, offline, expected_hash=None):
    if expected_hash and (not re.fullmatch('[a-fA-F0-9]{64}', expected_hash) or
                          digest(path.read_bytes()) != expected_hash.lower()):
        raise ValueError('SHA-256 gói cập nhật không khớp mã đã xác nhận.')
    new, files, raw = read_archive(path)
    with update_gate() as config:
        if PENDING.exists():
            raise ValueError('Cập nhật trước bị gián đoạn. Chạy Update-IronPulse.cmd -Rollback.')
        old, previous, old_raw = from_directory()
        if new['version']['database'] != config['database_schema']:
            raise ValueError('Schema mới cần một migration riêng đã duyệt. Chưa thay file hay database.')
        if files['ops/portable/schema.sql'] != previous['ops/portable/schema.sql']:
            raise ValueError('Gói sửa bootstrap SQL. Cần quy trình SQL riêng có backup và kiểm chứng.')
        new_version = version_tuple(new['version']['release'])
        old_version = version_tuple(old['version']['release'])
        if new_version == old_version and raw == old_raw:
            print('UPDATE_ALREADY_APPLIED')
            return
        if new_version <= old_version:
            raise ValueError('Gói phải có phiên bản mới hơn.')
        upgrade = needs_sql_upgrade(old['version'], new['version'])
        final_update = new['version']['release'] == FINAL
        patch_release = new['version']['release'] == PATCH
        if upgrade or final_update:
            verified_update_tool(files, expected_hash)
        safety_backup = backup_v1(config, patch_release=patch_release) if final_update or patch_release else None
        old_env = active_venv()
        environment = stage_dependencies(files, previous, offline)
        record = {'backup': uuid4().hex, 'venv': old_env}
        backup = ROOT / 'instance/version-backups' / record['backup']
        backup.mkdir(parents=True)
        with ZipFile(backup / 'previous.zip', 'x', ZIP_DEFLATED) as archive:
            for name, data in previous.items():
                archive.writestr(name, data)
            archive.writestr(MANIFEST, old_raw)
        put(backup / 'next-manifest.json', raw)
        if safety_backup:
            put(backup / 'sql-backup.json', canonical(safety_backup))
        put(PENDING, canonical(record))
        try:
            migration = (change_sql(config, None, lambda state: put(backup / 'sql-before.json', canonical(state)),
                                    patch_release=patch_release) if upgrade else nullcontext())
            with migration:
                replace(files, old['files'].keys() - new['files'].keys(), raw)
                set_active_venv(environment)
                from_directory()
            put(LATEST, canonical(record))
            PENDING.unlink()
        except BaseException:
            restore(record, config)
            raise
        print(f'UPDATE_PASS {new["version"]["release"]}')


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='action', required=True)
    for name in ('build', 'verify-zip', 'update'):
        command = commands.add_parser(name)
        command.add_argument('archive', type=Path)
        if name == 'update':
            command.add_argument('--offline-wheels')
            command.add_argument('--target', type=Path)
            command.add_argument('--sha256')
    commands.add_parser('verify-dir')
    commands.add_parser('rollback').add_argument('--target', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        build(args.archive)
    elif args.action == 'verify-zip':
        package, _, _ = read_archive(args.archive)
        print('ZIP_VALID', package['version']['release'])
    elif args.action == 'verify-dir':
        package, _, _ = from_directory()
        print('FILES_VALID', package['version']['release'])
    elif args.action == 'update':
        select_target(args.target)
        update(args.archive, args.offline_wheels, args.sha256)
    else:
        select_target(args.target)
        with update_gate() as config:
            checkpoint = PENDING if PENDING.exists() else LATEST
            if not checkpoint.is_file():
                raise ValueError('Chưa có checkpoint hoàn tác.')
            restore(json.loads(checkpoint.read_bytes()), config)


if __name__ == '__main__':
    try:
        main()
    except (BadZipFile, ValueError, TypeError, KeyError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'BLOCKED {error}', file=sys.stderr)
        sys.exit(1)
