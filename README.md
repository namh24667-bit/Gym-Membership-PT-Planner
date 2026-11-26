# IronPulse - Hệ thống quản lý phòng gym

## Thông tin đồ án

| Nội dung | Thông tin |
|---|---|
| Trường | Học viện Công nghệ Bưu chính Viễn thông cơ sở TP.HCM |
| Học phần | INT1313 - Cơ sở dữ liệu |
| Nhóm học phần | 4 |
| Năm học | 2026-2027 |
| Học kỳ | 1 |
| Lớp | D24CQCN02-N |
| Khóa | D24 (tuyển sinh năm 2024) |
| Đề tài | 9 |
| Nhóm thực hiện | Tam Thái Tử |
| Giảng viên hướng dẫn | Lê Hà Thanh |
| Email giảng viên | lehathanh@ptithcm.edu.vn |

## Thành viên nhóm

| Họ và tên | Mã sinh viên | Lớp |
|---|---|---|
| Lê Bảo Khanh | N24DCCN130 | D24CQCN02-N |
| Ngô Thanh Lực | N24DCCN139 | D24CQCN02-N |
| Nguyễn Hoài Nam | N24DCCN141 | D24CQCN02-N |

## Giới thiệu đề tài

IronPulse là hệ thống quản lý phòng gym được nhóm xây dựng trong học phần Cơ sở dữ liệu. Đề tài xuất phát từ nhu cầu quản lý thông tin hội viên, gói tập, hợp đồng và các khoản thanh toán tại phòng gym. Hệ thống còn hỗ trợ đặt lịch tập cá nhân với huấn luyện viên (PT), đăng ký lớp tập nhóm và theo dõi tình trạng thiết bị, lịch sử bảo trì.

Trọng tâm của đồ án là xử lý các trường hợp trùng lịch tập, vượt sức chứa của lớp và lưu trữ lịch sử thanh toán khi hội viên đăng ký hoặc gia hạn gói tập. Cơ sở dữ liệu gồm 18 bảng nghiệp vụ trên SQL Server Express, sử dụng các ràng buộc, trigger và thủ tục lưu trữ để kiểm soát dữ liệu. Ứng dụng được xây dựng bằng Python, Flask, Jinja và Bootstrap, kết nối với SQL Server qua pyodbc và ODBC Driver 18. Hệ thống phân quyền theo bốn vai trò gồm hội viên, nhân viên, huấn luyện viên và quản lý để phục vụ các công việc tương ứng.

## Hồ sơ đồ án

| Thư mục | Nội dung |
|---|---|
| 01 Báo cáo | [Báo cáo Word](01_BaoCao/BaoCao_IronPulse.docx) |
| 02 Sơ đồ | [Sơ đồ Draw.io](02_SoDo/UML_Diagram.drawio) |
| 03 SQL | [Hướng dẫn bộ SQL](03_SQL/README.md) · [Dữ liệu mẫu](03_SQL/03_Sample_Data.sql) · [Kiểm chứng dữ liệu](03_SQL/10_Verify_Data.sql) |
| 04 Mã nguồn | [Cách xem mã nguồn](04_SourceCode/README.md) |
| 05 Hướng dẫn | [Cài đặt](05_HuongDan/HuongDan_CaiDat.md) · [Sử dụng](05_HuongDan/HuongDan_SuDung.md) · [Kiểm chứng SQL](05_HuongDan/HuongDan_KiemChung_SQL.md) |
| 06 Bản cài | [ZIP cài mới v1.0.1](06_BanCaiDat/IronPulse_v1.0.1.zip) · [SHA-256](06_BanCaiDat/SHA256.txt) |

Báo cáo được lưu dưới dạng Word. Sơ đồ cơ sở dữ liệu (ERD) nằm trong trang **Sơ đồ cơ sở dữ liệu** của tệp Draw.io. Bộ SQL học thuật sử dụng cơ sở dữ liệu riêng `IronPulse_SubmissionQA`, với 13.658 dòng dữ liệu mô phỏng trên 18 bảng theo kết quả kiểm chứng của nhóm.

Để chạy ứng dụng trên Windows, tải bộ cài ZIP, kiểm tra mã SHA-256, giải nén và làm theo hướng dẫn cài đặt. Bộ cài tạo cơ sở dữ liệu và tài khoản trình diễn riêng cho ứng dụng.
