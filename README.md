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

Nhóm xây dựng hệ thống IronPulse để quản lý hội viên, gói tập, hợp đồng, thanh toán mô phỏng, lịch tập với huấn luyện viên, lớp tập nhóm và bảo trì thiết bị.

Cơ sở dữ liệu gồm 18 bảng nghiệp vụ, sử dụng SQL Server Express. Phần ứng dụng được xây dựng bằng Python với Flask, Jinja và Bootstrap, kết nối cơ sở dữ liệu qua pyodbc và ODBC Driver 18.

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
