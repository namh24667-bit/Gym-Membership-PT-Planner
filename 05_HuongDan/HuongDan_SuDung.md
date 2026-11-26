# Hướng dẫn sử dụng IronPulse

Sau khi [cài đặt](HuongDan_CaiDat.md), mở PowerShell trong thư mục bản cài, chạy `.\Mo-IronPulse.cmd` và mở địa chỉ chương trình in ra. Để xem tám tài khoản trình diễn, chạy `.\Mo-IronPulse.cmd --credentials` bằng tài khoản Windows đã chạy Setup. Đăng nhập bằng email và mật khẩu ứng dụng. PT là huấn luyện cá nhân. Quota là số lượt sử dụng dịch vụ được cấp theo gói tập.

| Vai trò | Thao tác có thể trình diễn |
|---|---|
| Hội viên | Xem gói tập, hợp đồng và số lượt còn lại. Đặt lịch PT, đăng ký hoặc hủy lớp nhóm theo điều kiện của gói. |
| Nhân viên | Tra cứu hội viên, tư vấn gói, ghi khoản thu mô phỏng, kích hoạt hợp đồng và xem biên lai. |
| Huấn luyện viên | Xem lịch được phân công, chi tiết buổi PT và lớp phụ trách. |
| Quản lý | Xem báo cáo, quản lý gói tập, nhân sự, lớp nhóm, phòng, thiết bị và bảo trì. |

Mỗi bản cài có cơ sở dữ liệu và tài khoản trình diễn riêng. Khi trình diễn đặt lịch, cần một lịch sắp diễn ra và hợp đồng còn hiệu lực.

- **Lịch mẫu đã qua.** Chọn lịch sắp diễn ra khác. Nếu chưa có lịch phù hợp, người có quyền có thể tạo lịch trên bản cài trình diễn.
- **Hợp đồng hết hiệu lực.** Chọn tài khoản trình diễn có hợp đồng còn hiệu lực và còn lượt, hoặc mua và kích hoạt gói trên bản cài trình diễn trước khi đặt lịch.

Muốn dừng website, chạy `.\Mo-IronPulse.cmd --stop`. Khi website đang dừng, lệnh `.\Mo-IronPulse.cmd --check` giúp chẩn đoán lỗi.

Để xem lược đồ và truy vấn trên bộ dữ liệu học thuật, mở [hướng dẫn kiểm chứng SQL](HuongDan_KiemChung_SQL.md).
