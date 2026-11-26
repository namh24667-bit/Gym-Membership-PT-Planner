"""Installation identity and private Windows state."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from app.portable_config import DATABASE_SCHEMA, identifier, validate_scope


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'instance/portable.json'


class SetupError(Exception):
    pass


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, data):
    atomic_write(path, (json.dumps(data, indent=2) + '\n').encode())


def windows_profile(install_id):
    return Path(os.environ['LOCALAPPDATA']) / 'IronPulse' / str(identifier(install_id))


def validate(config, *, installed=True):
    validate_scope(config['server'], config['database'], config['login'])
    identifier(config['install_id'])
    if type(config['port']) is not int or not 1024 <= config['port'] <= 65535:
        raise SetupError('Chọn cổng từ 1024 đến 65535.')
    if installed:
        identifier(config['broker'])
        if config['database_schema'] != DATABASE_SCHEMA:
            raise SetupError('Phiên bản schema không tương thích với ứng dụng.')
    return config


def current_installation():
    if not CONFIG.is_file():
        raise SetupError('Chưa có cấu hình. Chạy Setup-IronPulse.cmd.')
    return validate(read_json(CONFIG))


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(data, *, decrypt=False):
    raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), raw)
    result = Blob()
    library = ctypes.WinDLL('crypt32', use_last_error=True)
    action = library.CryptUnprotectData if decrypt else library.CryptProtectData
    if not action(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise SetupError('DPAPI cần đúng tài khoản Windows đã tạo thông tin này.')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.memset(result.data, 0, result.size)
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(result.data)
        ctypes.memset(raw, 0, len(raw))


def new_installation(instance, database, account, port):
    machine = os.environ['COMPUTERNAME']
    server = 'lpc:' + machine + (f'\\{instance}' if instance else '')
    return validate({'server': server, 'database': database, 'login': f'{machine}\\{account}',
                     'port': port, 'install_id': str(uuid4())}, installed=False)
