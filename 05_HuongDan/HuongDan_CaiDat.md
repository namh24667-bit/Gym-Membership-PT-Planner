# Hướng dẫn cài đặt IronPulse

## 1. Yêu cầu phần mềm

- Windows x64, Python 3.12 x64 cài cho mọi người dùng và PowerShell 7 x64 cài bằng MSI tại `C:\Program Files\PowerShell\7\pwsh.exe`.
- SQL Server Express 2022 hoặc 2025 chạy trên máy, bật Shared Memory, và Microsoft ODBC Driver 18 x64. Cài thêm SSMS nếu cần kiểm chứng SQL.

## 2. Chuẩn bị môi trường

Dùng tài khoản Windows có quyền quản trị SQL Server cục bộ để chạy Setup. Tạo một tài khoản Windows cục bộ tiêu chuẩn khác để chạy ứng dụng, ví dụ `IronPulseTeamApp`. Setup thông thường cần Internet để tải thư viện Python. Cách dùng bộ wheel có sẵn được nêu trong [hướng dẫn đầy đủ](../04_SourceCode/docs/INSTALLATION_AND_USER_GUIDE.md).

## 3. Kiểm tra và giải nén

Nhận [IronPulse_v1.0.1.zip](../06_BanCaiDat/IronPulse_v1.0.1.zip) và [SHA256.txt](../06_BanCaiDat/SHA256.txt). Mở PowerShell trong thư mục chứa ZIP. Chạy lệnh dưới đây và so kết quả với SHA256.txt. Khi mã trùng khớp, giải nén vào thư mục cục bộ mới mà tài khoản chạy ứng dụng có quyền đọc.

~~~powershell
Get-FileHash .\IronPulse_v1.0.1.zip -Algorithm SHA256
~~~

## 4. Cài đặt

Mở PowerShell trong thư mục vừa giải nén, chạy `.\Setup-IronPulse.cmd`. Điền lần lượt các thông tin Setup yêu cầu.

- **Instance SQL Server.** Dùng tên trong **SQL Server Configuration Manager → SQL Server Services**, ví dụ `SQLEXPRESS` nếu thấy **SQL Server (SQLEXPRESS)**. Với **SQL Server (MSSQLSERVER)**, nhập `MSSQLSERVER`.
- **Cơ sở dữ liệu.** Chọn tên mới dành cho bản cài, ví dụ `IronPulse_CleanDemoQA` nếu chưa tồn tại. Dùng tiền tố `IronPulse_`, tối đa 32 chữ cái không dấu hoặc chữ số ở giữa và hậu tố `QA`.
- **Tài khoản chạy ứng dụng.** Nhập tên tài khoản Windows cục bộ tiêu chuẩn đã chuẩn bị.
- **Cổng.** Dùng `5443` nếu đang trống, hoặc chọn một cổng cục bộ chưa sử dụng trong khoảng 1024–65535.

Nhập `CAI DAT` để xác nhận. Với bản cài mới, chờ `CLEAN_DATASET_PASS` và `SETUP_DATABASE_PASS`.

## 5. Khởi động

Khi website đang dừng, chạy `.\Mo-IronPulse.cmd --check`. Sau khi thấy `CHECK_PASS`, chạy `.\Mo-IronPulse.cmd`. Khi thấy `READY`, mở [trang đăng nhập ở cổng 5443](http://localhost:5443/login) hoặc địa chỉ chương trình in ra.

## 6. Đăng nhập

Dùng tài khoản Windows đã chạy Setup để chạy `.\Mo-IronPulse.cmd --credentials` trong thư mục bản cài. Chọn tài khoản trình diễn theo vai trò rồi nhập email và mật khẩu ứng dụng trên trang đăng nhập. Mật khẩu của tài khoản Windows chạy ứng dụng dùng tại lời nhắc Windows nếu xuất hiện.

## 7. Sử dụng

Làm theo [hướng dẫn sử dụng](HuongDan_SuDung.md) để thử các chức năng dành cho hội viên, nhân viên, huấn luyện viên hoặc quản lý.

## 8. Dừng chương trình

Trong thư mục bản cài, chạy `.\Mo-IronPulse.cmd --stop`.

## 9. Xử lý lỗi thường gặp

- **Lỗi kết nối SQL hoặc HTTP 503.** Kiểm tra dịch vụ SQL Server, tên instance, Shared Memory, ODBC x64 và tài khoản chạy ứng dụng. Chạy lại `.\Mo-IronPulse.cmd --check` khi website đang dừng.
- **Cơ sở dữ liệu hoặc cổng đã được dùng.** Với bản cài mới, chọn tên cơ sở dữ liệu và cổng riêng.
- **Không đọc được tài khoản trình diễn.** Chạy `--credentials` dưới đúng tài khoản Windows đã chạy Setup. Giữ mật khẩu Windows và mật khẩu ứng dụng ngoài báo cáo lỗi.

Xem hướng dẫn cài nâng cao và cập nhật ở [hướng dẫn đầy đủ](../04_SourceCode/docs/INSTALLATION_AND_USER_GUIDE.md).
