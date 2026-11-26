import secrets
from functools import lru_cache

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from flask import abort, current_app, g, request, session

from . import db, session_store


HASHER = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def enabled():
    secret = current_app.secret_key
    return bool(current_app.config['AUTH_ENABLED'] and secret and len(secret) >= 32)


@lru_cache(maxsize=1)
def _dummy_hash():
    return HASHER.hash(secrets.token_urlsafe(32))


def _supported_hash(value):
    if not value or len(value) > 255:
        return False
    try:
        params = extract_parameters(value)
    except (InvalidHashError, ValueError):
        return False
    return (params.type is Type.ID and params.version == 19
            and 19456 <= params.memory_cost <= 65536 and 2 <= params.time_cost <= 4
            and 1 <= params.parallelism <= 4 and 16 <= params.salt_len <= 32
            and 32 <= params.hash_len <= 64)


def authenticate(email, password):
    if not email or len(email) > 255 or '@' not in email or not password or len(password.encode('utf-8')) > 1024:
        return None
    principal, stored_hash = db.find_account(email)
    supported = _supported_hash(stored_hash)
    try:
        match = HASHER.verify(stored_hash if supported else _dummy_hash(), password)
    except (InvalidHashError, VerificationError, ValueError):
        return None
    return principal if match and supported and principal and principal.roles else None


def csrf_token():
    token = session.get('csrf_token')
    if token is None:
        token = session['csrf_token'] = secrets.token_urlsafe(32)
    return token


def allowed_transport():
    return request.is_secure or bool(current_app.config['LOCAL_HTTP'] and request.scheme == 'http')


def require_csrf():
    origin = request.headers.get('Origin')
    if (not allowed_transport() or request.headers.get('Sec-Fetch-Site') == 'cross-site'
            or (origin and origin.casefold() != request.host_url.rstrip('/').casefold())):
        abort(403)
    request.max_content_length = 16 * 1024
    expected = session.get('csrf_token')
    submitted = request.form.get('csrf_token', '')
    if not expected or not submitted.isascii() or not secrets.compare_digest(expected, submitted):
        abort(400)


def load_principal():
    token = session.get('auth_token')
    if not enabled() or not allowed_transport() or not token:
        return
    person_id = session_store.session_owner(token)
    principal = db.get_principal(person_id) if person_id is not None else None
    if principal and principal.roles:
        g.principal = principal
    else:
        if person_id is not None:
            session_store.revoke_session(token)
        session.clear()


def sign_in(person_id):
    token = session_store.create_session(person_id)
    session.clear()
    session.permanent = True
    session['auth_token'] = token
    csrf_token()


def sign_out():
    token = session.get('auth_token')
    if token:
        session_store.revoke_session(token)
    session.clear()
