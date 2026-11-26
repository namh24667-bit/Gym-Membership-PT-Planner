PUBLIC_MENU = (
    ("Đăng nhập", "pages.login", "login"),
    ("Đăng ký hội viên", "pages.register", "person"),
)

# Labels retained for the UI-02 preview and its regression tests.
ROLE_MENUS = {
    "member": ("Gói tập của tôi", "Danh mục gói tập", "Lớp nhóm", "Đặt PT", "Lịch đã đặt"),
    "trainer": ("Lịch dạy của tôi", "Chứng chỉ chuyên môn"),
    "staff": ("Hợp đồng và thu tiền", "Hội viên và dịch vụ lẻ", "Phòng, thiết bị và bảo trì"),
    "management": ("Lớp nhóm", "Dịch vụ và mẫu gói", "Nhân sự", "Phòng và thiết bị", "Thống kê"),
}

ROLE_NAVIGATION = {
    "member": ("Hội viên", "person"),
    "trainer": ("Huấn luyện viên", "pulse"),
    "staff": ("Nhân viên", "people"),
    "management": ("Quản lý", "overview"),
}
