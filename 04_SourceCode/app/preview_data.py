"""Synthetic UI fixtures, written for the preview and independent of Phase 3 data."""

from datetime import datetime

DATA = {
    "plans": {
        "strength": {"name": "Strength Plus", "months": 3, "price": 1490000,
                     "description": "Tập tự do và kết hợp PT với các lớp nhóm hằng tuần.",
                     "benefits": (("Tập tự do", -1), ("PT cá nhân", 8), ("Lớp nhóm", 12))},
        "studio": {"name": "Studio Flow", "months": 1, "price": 690000,
                   "description": "Gói tập ngắn hạn dành cho hội viên yêu thích lớp nhóm.",
                   "benefits": (("Tập tự do", 4), ("Lớp nhóm", 8))},
        "starter": {"name": "Gym Starter", "months": 1, "price": 490000,
                    "description": "Tập tự do tại khu tạ và cardio trong một tháng.",
                    "benefits": (("Tập tự do", -1),)},
    },
    "memberships": {
        "IP-104": {"plan": "strength", "member": "Hội viên Mẫu 01", "status": "ACTIVE",
                   "start": "01/11/2026", "end": "01/02/2027", "price": 1290000,
                   "payment": ("BANK_TRANSFER", "01/11/2026 · 08:10")},
        "IP-108": {"plan": "studio", "member": "Hội viên Mẫu 01", "status": "PENDING_PAYMENT",
                   "start": None, "end": None, "price": None, "payment": None},
        "IP-107": {"plan": "starter", "member": "Hội viên Mẫu 01", "status": "PENDING_ACTIVATION",
                   "start": None, "end": None, "price": 490000, "payment": ("CASH", "19/11/2026 · 17:20")},
        "IP-098": {"plan": "starter", "member": "Hội viên Mẫu 01", "status": "EXPIRED",
                   "start": "01/10/2026", "end": "01/11/2026", "price": 490000,
                   "payment": ("CASH", "01/10/2026 · 07:45")},
    },
    "usage": (
        {"membership": "IP-104", "service": "PT cá nhân", "status": "USED"},
        {"membership": "IP-104", "service": "Lớp nhóm", "status": "USED"},
        {"membership": "IP-104", "service": "Lớp nhóm", "status": "USED"},
        {"membership": "IP-104", "service": "Lớp nhóm", "status": "REFUNDED"},
        {"membership": "IP-098", "service": "Tập tự do", "status": "USED"},
    ),
    "classes": {
        "yoga": {"name": "Morning Flow", "category": "Yoga", "trainer": "HLV Mẫu 01",
                 "room": "Studio A", "room_type": "Studio", "date": "24/11/2026", "time": "07:00 – 08:00",
                 "enrolled": 8, "capacity": 12, "attendees": ("Hội viên Mẫu 01", "Hội viên Mẫu 02",
                 "Hội viên Mẫu 03", "Hội viên Mẫu 04", "Hội viên Mẫu 05", "Hội viên Mẫu 06",
                 "Hội viên Mẫu 07", "Hội viên Mẫu 08")},
        "hiit": {"name": "Power Circuit", "category": "HIIT", "trainer": "HLV Mẫu 01",
                 "room": "Studio B", "room_type": "Studio", "date": "25/11/2026", "time": "18:00 – 18:45",
                 "enrolled": 9, "capacity": 16, "attendees": ("Hội viên Mẫu 02", "Hội viên Mẫu 03",
                 "Hội viên Mẫu 04", "Hội viên Mẫu 05", "Hội viên Mẫu 06", "Hội viên Mẫu 07",
                 "Hội viên Mẫu 08", "Hội viên Mẫu 09", "Hội viên Mẫu 10")},
        "box": {"name": "Boxing Basics", "category": "Boxing", "trainer": "HLV Mẫu 01",
                "room": "Studio B", "room_type": "Studio", "date": "27/11/2026", "time": "17:30 – 18:30",
                "enrolled": 6, "capacity": 6, "attendees": ("Hội viên Mẫu 05", "Hội viên Mẫu 06",
                "Hội viên Mẫu 07", "Hội viên Mẫu 08", "Hội viên Mẫu 09", "Hội viên Mẫu 10")},
    },
    "pt_sessions": {
        "pt-01": {"name": "PT sức mạnh", "trainer": "HLV Mẫu 01", "room": "Khu PT",
                  "room_type": "PT Zone", "date": "24/11/2026", "time": "10:00 – 11:00",
                  "member": "Hội viên Mẫu 01", "focus": "Kỹ thuật squat và ổn định phần thân giữa."},
        "pt-02": {"name": "PT thể lực", "trainer": "HLV Mẫu 01", "room": "Khu PT",
                  "room_type": "PT Zone", "date": "26/11/2026", "time": "16:00 – 17:00",
                  "member": "Hội viên Mẫu 02", "focus": "Thăng bằng và nhịp thở khi tập."},
    },
    "bookings": (("yoga", "SUCCESS", None), ("hiit", "CANCEL", "23/11/2026 · 11:30")),
    "trainers": (
        ("HLV Mẫu 01", "Nữ", "ACTIVE", ("ACE", "NASM")),
        ("HLV Mẫu 02", "Nam", "ON_LEAVE", ("ISSA",)),
    ),
    "trainer_hire_date": "15/03/2026",
    "people": (
        {"id": "HV-01", "name": "Hội viên Mẫu 01", "email": "hoivien01@example.invalid",
         "phone": "000-000-0101", "status": "ACTIVE"},
        {"id": "HV-02", "name": "Hội viên Mẫu 02", "email": "hoivien02@example.invalid",
         "phone": "000-000-0102", "status": "EXPIRED"},
    ),
    "rooms": (("Studio A", "Studio", "AVAILABLE"), ("Studio B", "Studio", "AVAILABLE"),
              ("Khu PT", "PT Zone", "AVAILABLE"), ("Khu Cardio", "Cardio Zone", "MAINTENANCE")),
    "equipment": (
        ("EQ-01", "Máy chạy bộ", "MẪU-RUN-01", "Khu Cardio", "MAINTENANCE"),
        ("EQ-02", "Giá đỡ squat", "MẪU-SQT-02", "Khu PT", "ACTIVE"),
        ("EQ-03", "Xe đạp tập", "MẪU-BIKE-03", None, "RETIRED"),
    ),
    "maintenance": (
        ("BT-01", "Máy chạy bộ", "20/11/2026", None, None, "Kiểm tra dây đai."),
        ("BT-02", "Giá đỡ squat", "10/11/2026", "10/11/2026", 250000, "Siết lại khớp và kiểm tra an toàn."),
    ),
    "services": (("Tập tự do", "Sử dụng khu tập theo gói."), ("PT cá nhân", "Buổi tập 1–1."),
                 ("Lớp nhóm", "Các buổi tập theo lịch lớp.")),
    "personnel": (
        ("NS-01", "HLV Mẫu 01", "Huấn luyện viên", None, "ACTIVE"),
        ("NS-02", "HLV Mẫu 02", "Huấn luyện viên · Hội viên", None, "ON_LEAVE"),
        ("NS-03", "Nhân viên Mẫu 03", "Nhân viên", "Lễ tân", "ACTIVE"),
        ("NS-04", "Nhân viên Mẫu 04", "Nhân viên", "Quản lý", "ACTIVE"),
        ("NS-05", "Nhân viên Mẫu 05", "Nhân viên", "Kỹ thuật viên", "TERMINATED"),
    ),
}

TRAINER_SCHEDULE = sorted(
    [("PERSONAL", key, item) for key, item in DATA["pt_sessions"].items()]
    + [("GROUP", key, item) for key, item in DATA["classes"].items()],
    key=lambda entry: datetime.strptime(
        entry[2]["date"] + " " + entry[2]["time"].split(" – ")[0], "%d/%m/%Y %H:%M"
    ),
)
