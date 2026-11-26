from collections import Counter
from ipaddress import ip_address
import re

from flask import Blueprint, abort, current_app, render_template, request

from .preview_data import DATA, TRAINER_SCHEDULE


preview = Blueprint("preview", __name__, url_prefix="/preview")

ROLES = {
    "member": "Hội viên",
    "trainer": "Huấn luyện viên",
    "staff": "Nhân viên",
    "management": "Quản lý",
}

# Key, title and visual marker. Detail screens use their parent item in the menu.
MENUS = {
    "member": (
        ("overview", "Tổng quan", "overview"), ("memberships", "Gói tập của tôi", "card"),
        ("plans", "Danh mục gói tập", "stack"), ("classes", "Lớp nhóm", "people"),
        ("pt", "Đăng ký PT", "pulse"), ("schedule", "Lịch đã đặt", "calendar"),
    ),
    "trainer": (
        ("overview", "Tổng quan lịch dạy", "overview"), ("schedule", "Lịch dạy của tôi", "calendar"),
        ("certificates", "Chứng chỉ chuyên môn", "award"),
    ),
    "staff": (
        ("contracts", "Hợp đồng gói tập", "card"), ("members", "Tra cứu hội viên", "people"),
        ("usage", "Dịch vụ lẻ", "pulse"), ("rooms", "Phòng tập", "grid"),
        ("equipment", "Thiết bị", "stack"), ("maintenance", "Phiếu bảo trì", "tool"),
    ),
    "management": (
        ("overview", "Tổng quan quản lý", "overview"), ("classes", "Quản lý lớp nhóm", "calendar"),
        ("catalog", "Mẫu gói và dịch vụ", "card"), ("quotas", "Hạn mức dịch vụ", "stack"),
        ("people", "Nhân sự và vai trò", "people"), ("assets", "Phòng và thiết bị", "grid"),
        ("reports", "Thống kê", "chart"),
    ),
}

DETAILS = {
    "member": {
        "membership": ("Chi tiết gói tập", "memberships", "memberships"),
        "plan": ("Chi tiết mẫu gói", "plans", "plans"),
    },
    "trainer": {
        "pt-detail": ("Chi tiết buổi PT", "schedule", "pt_sessions"),
        "class-detail": ("Chi tiết lớp nhóm", "schedule", "classes"),
    },
    "staff": {
        "payment": ("Thu tiền và kích hoạt", "contracts", "memberships"),
        "registration": ("Đăng ký hội viên tại quầy", "members", None),
    },
}

LOCAL_HOST = re.compile(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", re.IGNORECASE)


def preview_available():
    if not current_app.config["PREVIEW_ENABLED"] or not LOCAL_HOST.fullmatch(request.host):
        return False
    if any(name in request.headers for name in ("Forwarded", "X-Forwarded-For", "X-Forwarded-Host")):
        return False
    try:
        return ip_address(request.remote_addr).is_loopback
    except ValueError:
        return False


@preview.app_context_processor
def preview_context():
    return {"preview_available": preview_available()}


@preview.before_request
def require_local_preview():
    if not preview_available():
        abort(404)


@preview.after_request
def preview_cache_control(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@preview.get("/")
@preview.get("/<role>")
@preview.get("/<role>/<page>")
@preview.get("/<role>/<page>/<record_id>")
def screen(role="member", page=None, record_id=None):
    if role not in ROLES:
        abort(404)
    page = page or MENUS[role][0][0]
    groups = (role, "staff") if role == "management" else (role,)
    for group in groups:
        detail = DETAILS.get(group, {}).get(page)
        if detail:
            title, parent, collection = detail
            record = DATA[collection].get(record_id) if collection else None
            if (collection and record is None) or (not collection and record_id is not None):
                abort(404)
            break
        title = next((label for slug, label, _ in MENUS[group] if slug == page), None)
        if title and record_id is None:
            parent, record = page, None
            break
    else:
        abort(404)

    filter_value = request.args.get("status", "")
    session_kind = request.args.get("type", "")
    membership_counts = Counter(item["status"] for item in DATA["memberships"].values())
    revenue = Counter()
    for item in DATA["memberships"].values():
        if item["payment"]:
            revenue[item["payment"][0]] += item["price"]
    return render_template(
        f"preview/{group}.html",
        role=role, page=page, parent=parent, title=title, record=record, record_id=record_id,
        group_is_staff=group == "staff",
        roles=ROLES, menus=MENUS, data=DATA, trainer_schedule=TRAINER_SCHEDULE,
        usage_count=Counter(row["service"] for row in DATA["usage"]
                            if row["membership"] == record_id and row["status"] == "USED"),
        filter_value=filter_value, session_kind=session_kind,
        membership_counts=membership_counts, revenue=revenue,
    )
