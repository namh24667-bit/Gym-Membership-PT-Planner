"""Run the team application under its configured standard Windows token."""
from contextlib import contextmanager
import csv
import ctypes
from ctypes import wintypes
import json
import msvcrt
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
from threading import Thread
from time import monotonic, sleep

from werkzeug.serving import make_server

from app import create_app, db, membership
from common import ROOT, SetupError, atomic_write, dpapi, windows_profile
from smoke import verify_accounts


def verify_windows_token(login):
    executable = Path(os.environ['SystemRoot']) / 'System32/whoami.exe'

    def read(option):
        process = subprocess.run([executable, option, '/fo', 'csv', '/nh'],
                                 capture_output=True, check=True)
        return list(csv.reader(process.stdout.decode('oem').splitlines()))

    actual = read('/user')[0][0]
    groups = {row[2] for row in read('/groups')}
    if actual.casefold() != login.casefold() or 'S-1-16-8192' not in groups or groups & {'S-1-5-32-544', 'S-1-5-114'}:
        raise SetupError('Flask phải chạy dưới tài khoản Windows cục bộ tiêu chuẩn đã cấu hình.')


def application(config, state, https):
    from clean_compat import CLASS_RULES_PROPERTY

    if config.get('dataset'):
        labels = {'gym': 'Tập gym tự do', 'group': 'Lớp nhóm phổ thông'}
        membership.PLAN_SERVICES = tuple(
            (key, labels[key], icon, (labels[key],)) if key in labels else (key, label, icon, aliases)
            for key, label, icon, aliases in membership.PLAN_SERVICES)
        membership.SERVICE_ALIASES.update({label.casefold(): (key, label) for key, label in labels.items()})
    secret = state / 'flask-key.dpapi'
    if not secret.exists():
        atomic_write(secret, dpapi(secrets.token_bytes(48)))
    app = create_app(dict(
        SECRET_KEY=dpapi(secret.read_bytes(), decrypt=True),
        AUTH_STATE_PATH=state / 'session.sqlite3', AUTH_ENABLED=True, PREVIEW_ENABLED=False,
        LOCAL_QA=True, PORTABLE_QA=True, LOCAL_HTTP=not https,
        SQL_SERVER=config['server'], SQL_DATABASE=config['database'], SQL_WINDOWS_LOGIN=config['login'],
        SQL_QA_BROKER_GUID=config['broker'], PORTABLE_INSTALL_ID=config['install_id']))
    with app.app_context():
        for group in db.PROCEDURES:
            if not db.workflow_available(group):
                raise SetupError(f'SQL preflight thiếu quyền {group}.')
            app.config[f'{group.upper()}_ENABLED'] = True
        if not db.personal_profile_available():
            raise SetupError('SQL preflight thiếu quyền đọc hồ sơ.')
        app.config['LOCALR1A_ENABLED'] = True
        if config.get('dataset'):
            app.config['CLASS_RULES_ENABLED'] = db._fetch("""SELECT 1 FROM sys.extended_properties
                WHERE class=0 AND name=? AND CONVERT(nvarchar(10),value)=N'1'""", CLASS_RULES_PROPERTY) is not None
    return app


@contextmanager
def exclusive_marker(path):
    with path.open('a+b') as stream:
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
        else:
            try:
                yield True
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def stop_worker(state):
    lock = state / 'listener.lock'
    stop = state / 'stop'
    deadline = monotonic() + 15
    while monotonic() < deadline:
        with exclusive_marker(lock) as acquired:
            if acquired:
                stop.unlink(missing_ok=True)
                return
            stop.touch()
        sleep(.15)
    raise SetupError('IronPulse chưa dừng. Kiểm tra cửa sổ runtime.')


def listener_options(state, https):
    if not https:
        return None, None
    certdir = state / 'tls'
    pem, key = certdir / 'localhost.pem', certdir / 'localhost-key.pem'
    if not pem.is_file() or not key.is_file():
        powershell = Path(os.environ['ProgramFiles']) / 'PowerShell/7/pwsh.exe'
        subprocess.run([powershell, '-NoProfile', '-File', ROOT / 'ops/portable/New-TeamCertificate.ps1',
                        '-Target', certdir], check=True, stdout=subprocess.DEVNULL)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.load_verify_locations(cafile=pem)
    return (str(pem), str(key)), tls


def check_port(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise SetupError(f'Cổng {port} đang được sử dụng. Chọn cổng khác hoặc dừng đúng ứng dụng.') from None


def runtime_state(install_id):
    # Alternate Windows credentials can inherit the launching user's environment.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    open_token = ctypes.WinDLL('advapi32', use_last_error=True).OpenProcessToken
    open_token.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    profile = ctypes.WinDLL('userenv', use_last_error=True).GetUserProfileDirectoryW
    profile.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    token = wintypes.HANDLE()
    if not open_token(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        profile(token, None, ctypes.byref(size))
        value = ctypes.create_unicode_buffer(size.value)
        if not profile(token, value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return Path(value.value) / 'AppData/Local/IronPulse' / install_id
    finally:
        kernel.CloseHandle(token)


def run(config, mode, password, *, https=False):
    verify_windows_token(config['login'])
    state = runtime_state(config['install_id'])
    state.mkdir(parents=True, exist_ok=True)
    if mode in ('stop', 'restart'):
        stop_worker(state)
        if mode == 'stop':
            print('STOPPED', flush=True)
            return
    lock = state / 'listener.lock'
    with exclusive_marker(lock) as acquired:
        if not acquired:
            raise SetupError('IronPulse của bản cài này đang chạy. Dùng --restart hay --stop.')
        check_port(config['port'])
        app = application(config, state, https)
        certificate, tls = listener_options(state, https)
        address = f'{"https" if https else "http"}://127.0.0.1:{config["port"]}'
        stop = state / 'stop'
        stop.unlink(missing_ok=True)
        try:
            server = make_server('127.0.0.1', config['port'], app, threaded=True, ssl_context=certificate)
        except SystemExit:
            raise SetupError(f'Không thể mở cổng {config["port"]}.') from None
        with server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                credentials = json.loads(password) if config.get('dataset') else password
                verify_accounts(address, credentials, tls)
                del credentials
                del password
                if mode == 'check':
                    print('CHECK_PASS', flush=True)
                    return
                print('READY', flush=True)
                while not stop.exists():
                    sleep(.25)
            finally:
                server.shutdown()
                thread.join()
                stop.unlink(missing_ok=True)
