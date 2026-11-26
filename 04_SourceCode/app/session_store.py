import secrets
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from time import time

from flask import current_app


class SessionStoreUnavailable(Exception):
    pass


def _token_digest(token):
    return sha256(token.encode('ascii')).digest()


def _state_path():
    return Path(current_app.config['AUTH_STATE_PATH'])


def create_session(person_id):
    token = secrets.token_urlsafe(32)
    now = int(time())
    expires_at = now + int(current_app.permanent_session_lifetime.total_seconds())
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=3)) as connection, connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS auth_session (
                token_digest BLOB PRIMARY KEY, person_id INTEGER NOT NULL, expires_at INTEGER NOT NULL
            )''')
            connection.execute('DELETE FROM auth_session WHERE expires_at <= ?', (now,))
            connection.execute('INSERT INTO auth_session VALUES (?, ?, ?)',
                               (_token_digest(token), person_id, expires_at))
    except (sqlite3.Error, OSError):
        raise SessionStoreUnavailable from None
    return token


def session_owner(token):
    path = _state_path()
    try:
        if not path.is_file():
            return None
        with closing(sqlite3.connect(path, timeout=3)) as connection:
            row = connection.execute('SELECT person_id FROM auth_session WHERE token_digest = ? AND expires_at > ?',
                                     (_token_digest(token), int(time()))).fetchone()
            return row[0] if row else None
    except (sqlite3.Error, OSError):
        raise SessionStoreUnavailable from None


def revoke_session(token):
    path = _state_path()
    try:
        if not path.is_file():
            return
        with closing(sqlite3.connect(path, timeout=3)) as connection, connection:
            connection.execute('DELETE FROM auth_session WHERE token_digest = ?', (_token_digest(token),))
    except (sqlite3.Error, OSError):
        raise SessionStoreUnavailable from None
