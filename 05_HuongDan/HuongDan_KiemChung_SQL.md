# Kiểm chứng cơ sở dữ liệu bằng SSMS hoặc SQLCMD

Dùng Windows Authentication để kết nối đúng instance SQL Server cục bộ. Các script sử dụng cơ sở dữ liệu học thuật `IronPulse_SubmissionQA` và kiểm dấu định danh `IronPulseAcademicPackage` có giá trị `1.0.1`. Xem mô hình 18 bảng trong trang **Sơ đồ cơ sở dữ liệu** của [file Draw.io](../02_SoDo/UML_Diagram.drawio).

## A. Đã có cơ sở dữ liệu học thuật

Trong SSMS, chọn `IronPulse_SubmissionQA` ở danh sách cơ sở dữ liệu của từng cửa sổ truy vấn. Mở [04_Queries.sql](../03_SQL/04_Queries.sql) và chạy các truy vấn đọc dữ liệu. Khi cần kiểm chứng toàn bộ bộ mẫu, chạy [10_Verify_Data.sql](../03_SQL/10_Verify_Data.sql) trên cùng cơ sở dữ liệu. Tiếp tục dùng dữ liệu đang có. Nếu script báo sai tên hoặc dấu định danh, kiểm tra lại cơ sở dữ liệu đang chọn.

## B. Chưa có cơ sở dữ liệu học thuật

Dùng tài khoản có quyền tạo cơ sở dữ liệu. Trong SSMS, chọn `master` cho script 01. Sau bước tạo, chọn `IronPulse_SubmissionQA` cho từng cửa sổ còn lại. Chạy theo thứ tự **01 → 02 → 09 → 08 → 05 → 06 → 07 → 03 → 10 → 04**. Nếu báo lỗi, dừng ở bước đó và xem tab **Messages**.

| File | Chức năng |
|---|---|
| [01_Create_Database.sql](../03_SQL/01_Create_Database.sql) | Tạo cơ sở dữ liệu học thuật và dấu định danh. |
| [02_Create_Tables.sql](../03_SQL/02_Create_Tables.sql) | Tạo 18 bảng, khóa và ràng buộc. |
| [09_Indexes.sql](../03_SQL/09_Indexes.sql) | Tạo năm chỉ mục nghiệp vụ. |
| [08_Functions.sql](../03_SQL/08_Functions.sql) | Tạo hai hàm ánh xạ bộ môn và đối soát số lượt. |
| [05_Views.sql](../03_SQL/05_Views.sql) | Tạo hai view sĩ số lớp và doanh thu tháng. |
| [06_Triggers.sql](../03_SQL/06_Triggers.sql) | Tạo ba trigger kiểm tra lịch, đặt lớp và buổi huấn luyện cá nhân. |
| [07_Stored_Procedures.sql](../03_SQL/07_Stored_Procedures.sql) | Tạo 28 thủ tục nghiệp vụ. |
| [03_Sample_Data.sql](../03_SQL/03_Sample_Data.sql) | Nạp dữ liệu mẫu vào 18 bảng theo thứ tự khóa ngoại. |
| [10_Verify_Data.sql](../03_SQL/10_Verify_Data.sql) | Kiểm lược đồ, đếm dòng, chạy 26 phép kiểm dữ liệu và kiểm tra DBCC. |
| [04_Queries.sql](../03_SQL/04_Queries.sql) | Chạy 16 truy vấn đọc minh họa. |
| [11_Run_All.sql](../03_SQL/11_Run_All.sql) | Chạy tổng hợp chuỗi trên bằng SQLCMD khi tạo mới. |

Kết quả tham chiếu trên SQL Server Express 2025 được ghi nhận khi chạy bằng **SQLCMD**. Bộ mẫu có **13.658 dòng mô phỏng trên 18 bảng**, gồm 1.400 khoản thu mô phỏng với tổng giá trị 3.333.467.000 VND. Các bước thao tác trong SSMS ở trên là hướng dẫn chạy từng file.

Để chạy tổng hợp khi tạo mới, mở PowerShell trong thư mục chứa các file SQL. Ví dụ với instance `SQLEXPRESS` trên máy:

~~~powershell
sqlcmd -S '.\SQLEXPRESS' -E -C -d master -b -f 'i:65001,o:65001' -i 11_Run_All.sql
~~~

Với instance khác, dùng đúng tên instance của máy. Khi mở script tổng hợp trong SSMS, bật **Query → SQLCMD Mode** rồi sửa các đường dẫn sau `:r` theo [README bộ SQL](../03_SQL/README.md).

Website dùng cơ sở dữ liệu và tài khoản do [bộ cài website](HuongDan_CaiDat.md) tạo riêng.
