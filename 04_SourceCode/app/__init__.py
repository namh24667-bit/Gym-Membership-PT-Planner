import os
from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path

from flask import Flask, abort, render_template, request

from .db import DatabaseUnavailable, LOCAL_QA_LOGINS, QA_DATABASE, QA_SERVER, close_request_connection, portable_connection_scope
from .membership import METHOD, STATUS
from .routes import pages
from . import admin, schedule
from .preview import preview
from .session_store import SessionStoreUnavailable


def create_app(test_config=None):
    app = Flask(__name__)
    local_qa = os.environ.get("IRONPULSE_LOCAL_QA") == "1"
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SESSION_COOKIE_NAME="ironpulse_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        AUTH_ENABLED=os.environ.get("IRONPULSE_AUTH") == "1",
        AUTH_STATE_PATH=os.environ.get("IRONPULSE_AUTH_STATE_PATH") or Path(app.instance_path) / "ironpulse-auth.sqlite3",
        LOCAL_QA=local_qa,
        LOCAL_HTTP=False,
        SQL_SERVER=os.environ.get("IRONPULSE_SQL_SERVER", QA_SERVER if local_qa else None),
        SQL_WINDOWS_LOGIN=os.environ.get("IRONPULSE_SQL_WINDOWS_LOGIN", LOCAL_QA_LOGINS[0] if local_qa else None),
        SQL_DATABASE=os.environ.get("IRONPULSE_SQL_DATABASE", QA_DATABASE if local_qa else "IronPulse"),
        SQL_QA_BROKER_GUID=os.environ.get("IRONPULSE_SQL_QA_BROKER_GUID"),
        PREVIEW_ENABLED=os.environ.get("IRONPULSE_PREVIEW") == "1",
    )
    if test_config is not None:
        app.config.update(test_config)
    if app.config.get('PORTABLE_QA'):
        install_id = portable_connection_scope(app.config)[3]
        app.config["SESSION_COOKIE_NAME"] = f"ironpulse_team_{install_id.hex[:12]}"
    if app.config["SQL_DATABASE"] == QA_DATABASE and not app.config.get('PORTABLE_QA'):
        app.config["SESSION_COOKIE_NAME"] = "ironpulse_qa_session"
        if not os.environ.get("IRONPULSE_AUTH_STATE_PATH") and not (test_config or {}).get("AUTH_STATE_PATH"):
            app.config["AUTH_STATE_PATH"] = Path(app.instance_path) / "ironpulse-qa-auth.sqlite3"

    if app.config['LOCAL_HTTP']:
        if (not app.config.get('PORTABLE_QA') and
                (not app.config['LOCAL_QA'] or app.config['SQL_DATABASE'] != QA_DATABASE
                 or app.config['SQL_SERVER'] != QA_SERVER or app.config['SQL_WINDOWS_LOGIN'] not in LOCAL_QA_LOGINS)):
            raise ValueError('HTTP is available only for local SQL QA on MSI.')
        cookie = f'{app.config["SESSION_COOKIE_NAME"]}_http' if app.config.get('PORTABLE_QA') else 'ironpulse_qa_http_session'
        app.config.update(SESSION_COOKIE_NAME=cookie, SESSION_COOKIE_SECURE=False)
        state = Path(app.config['AUTH_STATE_PATH'])
        app.config['AUTH_STATE_PATH'] = state.with_name(f'{state.stem}-http{state.suffix}')

    app.register_blueprint(pages)
    app.register_blueprint(preview)
    app.teardown_request(close_request_connection)
    app.jinja_env.globals.update(membership_status=STATUS, payment_method=METHOD,
                                 local03_enabled=schedule.enabled, local04_enabled=admin.enabled)

    if app.config["LOCAL_QA"]:
        @app.before_request
        def require_direct_loopback():
            host, sep, port = request.host.casefold().partition(":")
            try:
                loopback = ip_address(request.remote_addr or "").is_loopback
            except ValueError:
                loopback = False
            if (not loopback or host not in {"localhost", "127.0.0.1"}
                    or (sep and (not port.isascii() or not port.isdecimal() or len(port) > 5 or int(port) > 65535))
                    or any(name.casefold() == "forwarded" or name.casefold().startswith("x-forwarded-")
                           for name in request.headers.keys())):
                abort(403)
            if app.config['LOCAL_HTTP'] and request.is_secure:
                abort(403)

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, title="Yêu cầu không hợp lệ",
                               detail="Tải lại trang và thử lại."), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, title="Bạn chưa có quyền truy cập",
                               detail="Khu vực này chỉ dành cho tài khoản được cấp quyền."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, title="Không tìm thấy trang",
                               detail="Kiểm tra lại địa chỉ hoặc quay về trang đăng nhập."), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("error.html", code=500, title="Không thể xử lý yêu cầu",
                               detail="Vui lòng quay lại trang chính và thử lại."), 500, {"Cache-Control": "no-store"}

    @app.errorhandler(503)
    def unavailable(error):
        return render_template("error.html", code=503, title="Chức năng chưa tích hợp",
                               detail=error.description), 503, {"Cache-Control": "no-store"}

    @app.errorhandler(DatabaseUnavailable)
    @app.errorhandler(SessionStoreUnavailable)
    def auth_unavailable(error):
        app.logger.warning("Không thể sử dụng dịch vụ xác thực (%s)", type(error).__name__)
        return render_template("error.html", code=503, title="Tạm thời không thể truy cập",
                               detail="Vui lòng thử lại sau."), 503, {"Cache-Control": "no-store"}

    return app
