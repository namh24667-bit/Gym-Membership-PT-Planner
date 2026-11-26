# IronPulse – Hệ thống quản lý phòng Gym

**Học phần** INT1313 – Cơ sở dữ liệu  
**Đề tài** 9  
**Nhóm** Tam Thái Tử  
**Giảng viên hướng dẫn** Lê Hà Thanh

| Thành viên | Mã sinh viên |
|---|---|
| Lê Bảo Khanh | N24DCCN130 |
| Ngô Thanh Lực | N24DCCN139 |
| Nguyễn Hoài Nam | N24DCCN141 |

IronPulse quản lý hội viên, gói tập, hợp đồng, khoản thu mô phỏng, lịch huấn luyện cá nhân (PT), lớp nhóm và thiết bị. Thiết kế cơ sở dữ liệu chính thức của đồ án gồm 18 bảng nghiệp vụ. Ứng dụng dùng Flask, Jinja và Bootstrap. Python kết nối SQL Server Express qua pyodbc và ODBC Driver 18.

## Hồ sơ đồ án

| Thư mục | Nội dung |
|---|---|
| 01 Báo cáo | [Báo cáo Word](01_BaoCao/BaoCao_IronPulse.docx) |
| 02 Sơ đồ | [Sơ đồ Draw.io](02_SoDo/UML_Diagram.drawio) |
| 03 SQL | [Hướng dẫn bộ SQL](03_SQL/README.md) · [Dữ liệu mẫu](03_SQL/03_Sample_Data.sql) · [Kiểm chứng dữ liệu](03_SQL/10_Verify_Data.sql) |
| 04 Mã nguồn | [Cách xem mã nguồn](04_SourceCode/README.md) |
| 05 Hướng dẫn | [Cài đặt](05_HuongDan/HuongDan_CaiDat.md) · [Sử dụng](05_HuongDan/HuongDan_SuDung.md) · [Kiểm chứng SQL](05_HuongDan/HuongDan_KiemChung_SQL.md) |
| 06 Bản cài | [ZIP cài mới v1.0.1](06_BanCaiDat/IronPulse_v1.0.1.zip) · [SHA-256](06_BanCaiDat/SHA256.txt) |

Mở báo cáo bằng Word. Để xem mô hình dữ liệu, mở file bằng Draw.io và chọn trang **Sơ đồ cơ sở dữ liệu** (ERD). Bộ SQL học thuật có kết quả tham chiếu 13.658 dòng mô phỏng trên 18 bảng trong cơ sở dữ liệu riêng `IronPulse_SubmissionQA`.

Để chạy website trên Windows, kiểm SHA-256 của ZIP, giải nén và làm theo hướng dẫn cài đặt ở trên. Bộ cài tạo cơ sở dữ liệu và tài khoản trình diễn riêng cho website.
