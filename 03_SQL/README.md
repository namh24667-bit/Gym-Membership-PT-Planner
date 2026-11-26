# Bộ SQL thực hành IronPulse · INT1313

Bộ thực hành tạo **`IronPulse_SubmissionQA`**. Nghiệm thu trên SQL Server Express 2025 cho kết quả **18 bảng, 92 cột, 18 khóa chính, 23 khóa ngoại và 13.658 dòng**. Dữ liệu là mô phỏng, được sinh lại bằng bộ sinh CleanDemo với mốc **24/11/2026 lúc 23:00**. Mỗi lần cài bộ SQL này nạp cùng một bộ mẫu. Để xem dữ liệu mẫu dạng `INSERT`, mở **`03_Sample_Data.sql`**.

## Chạy trong SSMS

1. Kết nối SQL Server bằng Windows Authentication với tài khoản được phép tạo database. Mở **`01_Create_Database.sql`**, chọn **master** rồi bấm **Execute**. Script dừng nếu `IronPulse_SubmissionQA` đã tồn tại.
2. Trong Object Explorer, bấm phải **Databases → Refresh**. Chọn **`IronPulse_SubmissionQA`** ở hộp database cho **từng cửa sổ query mới**. Các file từ bước 02 kiểm cả tên database và dấu định danh học thuật trước khi làm việc.
3. Mở và chạy mỗi file bên dưới bằng **Execute**. Khi một bước báo lỗi, dừng ở bước đó. Giữ database và thông báo trong tab **Messages** để kiểm tra.

| Thứ tự | File | Nội dung |
|---|---|---|
| 1 | `01_Create_Database.sql` | Tạo database và dấu định danh. |
| 2 | `02_Create_Tables.sql` | Tạo 18 bảng, khóa, cột mở rộng và ràng buộc. |
| 3 | `09_Indexes.sql` | Tạo năm chỉ mục nghiệp vụ. |
| 4 | `08_Functions.sql` | Tạo hai hàm ánh xạ bộ môn và đối soát quota. |
| 5 | `05_Views.sql` | Tạo hai view sĩ số lớp và doanh thu tháng. |
| 6 | `06_Triggers.sql` | Tạo ba trigger kiểm lịch, đặt lớp và buổi PT. |
| 7 | `07_Stored_Procedures.sql` | Tạo 28 thủ tục nghiệp vụ. |
| 8 | `03_Sample_Data.sql` | Nạp dữ liệu Unicode vào 18 bảng, theo thứ tự khóa ngoại. |
| 9 | `10_Verify_Data.sql` | Đếm dòng, chạy 26 phép kiểm và DBCC. Mong đợi 13.658 dòng và 0 lỗi. |
| 10 | `04_Queries.sql` | Chạy 16 truy vấn học thuật và xem từng bảng kết quả. |

Git hoặc ứng dụng soạn thảo nên giữ mã hóa UTF-8. Khi chạy bằng CLI, mở PowerShell **ngay trong thư mục chứa các file SQL**, ví dụ với SQL Server Express đặt tên `SQLEXPRESS`:

```powershell
sqlcmd -S '.\SQLEXPRESS' -E -C -d master -b -f 'i:65001,o:65001' -i 11_Run_All.sql
```

Tham số `-C` phù hợp cho instance SQL Server học tập cục bộ đã biết. Nếu chạy **`11_Run_All.sql` trong SSMS**, bật **Query → SQLCMD Mode**. Đổi các đối số `.` của `:r` thành đường dẫn tuyệt đối đến từng file SQL trên máy đó và dùng dấu ngoặc kép nếu có khoảng trắng. Cách bấm **Execute** từng file ở bảng trên dùng được trong chế độ truy vấn SSMS thông thường.

## Trình bày khi bảo vệ

- **Dữ liệu mẫu** nằm trong `03_Sample_Data.sql`. Tên tiếng Việt, định danh và giao dịch đều mô phỏng. Tám hash Argon2id được tạo mới từ giá trị ngẫu nhiên đã hủy để giữ cấu trúc và kiểm tra dữ liệu. Để thử đăng nhập website, dùng ZIP cài v1.0.1 và lệnh lấy tài khoản demo cục bộ của bản cài.
- **View** `vw_monthly_revenue` tính từ ngày ghi nhận trên bảng thanh toán. Dashboard gọi `local04_dashboard`, lọc thêm khoảng ngày, trạng thái hợp đồng và khoản thu khớp giá chốt. View sĩ số đếm booking `SUCCESS`.
- **Trigger** chạy sau `INSERT` hoặc `UPDATE`. Trigger trên `session` kiểm HLV và phòng khả dụng cùng các giao lịch. Trigger trên `booking` kiểm sức chứa và trùng giờ với lịch lớp hoặc PT. Trigger trên `pt_session` kiểm giao lịch của hội viên. Vi phạm được trả về bằng `THROW`, nên thao tác ghi phải được xử lý trong transaction tương ứng.
- **Chỉ mục** gồm một hợp đồng `ACTIVE` mỗi hội viên, một booking `SUCCESS` mỗi cặp hội viên/lớp, chống trùng request tạo hợp đồng, một dòng usage mỗi booking và chỉ mục phục vụ đếm sĩ số lớp. Các chỉ mục khóa chính và ràng buộc UNIQUE được tạo cùng bảng.
- **Mốc ngày** của dữ liệu là cố định. Câu hỏi “còn hiệu lực” trong truy vấn học thuật dùng mốc dataset. Thủ tục nghiệp vụ v1.0.1 dùng ngày giờ SQL Server hiện tại, nên các ca đặt/hủy lịch theo thời gian sẽ cần chọn khung ngày thích hợp khi demo lại.
- Bộ này dành cho SSMS và kiểm chứng CSDL. Installer chính thức tạo riêng cấu hình runtime và quyền Windows/SQL cần thiết cho website.
