# Hướng dẫn cài đặt và sử dụng IronPulse

IronPulse chạy cục bộ trên Windows. Mỗi bản cài có cơ sở dữ liệu và tài khoản trình diễn riêng. Website mặc định nhận kết nối từ chính máy cài. Dữ liệu giữa các máy không tự đồng bộ. Các khoản thu ở bản cài mới là số liệu mô phỏng.

## 1. Yêu cầu phần mềm

| Thành phần | Yêu cầu |
|---|---|
| Windows | Windows x64. Xem **Settings → System → About → System type**. |
| Python | Python 3.12 x64 cài cho mọi người dùng. Bật Python Launcher hoặc xác định đường dẫn `python.exe`. [Python 3.12.10](https://www.python.org/downloads/release/python-31210/) |
| PowerShell | PowerShell 7 x64, bản MSI, tại `C:\Program Files\PowerShell\7\pwsh.exe`. [Hướng dẫn cài PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows) |
| SQL Server | SQL Server Express 2022 hoặc 2025 cục bộ với Windows Authentication. Cài SSMS nếu cần chạy script kiểm đếm. [SQL Server Express và SSMS](https://www.microsoft.com/en-us/sql-server/sql-server-downloads) |
| ODBC | Microsoft ODBC Driver 18 x64. Cài Visual C++ Redistributable x64 nếu driver yêu cầu. [ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |

## 2. Chuẩn bị môi trường

Trong **SQL Server Configuration Manager**, tìm dịch vụ đang chạy ở **SQL Server Services** rồi kiểm tra **Shared Memory** của instance trong **SQL Server Network Configuration**. Nếu dịch vụ là **SQL Server (MSSQLSERVER)**, nhập `MSSQLSERVER` khi Setup hỏi.

~~~powershell
py -3.12 -c "import struct; print(struct.calcsize('P') * 8)"
Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit'
~~~

Tạo một tài khoản Windows cục bộ tiêu chuẩn để chạy ứng dụng, ví dụ `IronPulseTeamApp`, trong **Settings → Accounts → Other users**. Dùng một tài khoản Windows khác có quyền quản trị SQL Server cục bộ để chạy Setup. Setup tạo cơ sở dữ liệu, tài khoản đăng nhập SQL và cấp quyền cần thiết cho tài khoản chạy ứng dụng.

## 3. Kiểm tra và giải nén ZIP

Nhận `IronPulse_v1.0.1.zip` và tệp `SHA256.txt` từ hồ sơ hoặc bản phát hành. Mở PowerShell trong thư mục chứa ZIP. Tính mã rồi so với dòng tương ứng trong SHA256.txt. Khi mã trùng khớp, giải nén vào thư mục cục bộ mới mà tài khoản chạy ứng dụng có thể đọc, ví dụ `C:\IronPulse-v1`.

~~~powershell
Get-FileHash .\IronPulse_v1.0.1.zip -Algorithm SHA256
~~~

## 4. Cài đặt

Mở PowerShell trong thư mục đã giải nén và chạy `.\Setup-IronPulse.cmd`. Điền lần lượt thông tin Setup yêu cầu.

- **Instance SQL Server.** Dùng tên hiển thị trong **SQL Server Services**, ví dụ `SQLEXPRESS` cho **SQL Server (SQLEXPRESS)**. Với instance mặc định, nhập `MSSQLSERVER`.
- **Cơ sở dữ liệu.** Chọn tên mới, ví dụ `IronPulse_CleanDemoQA` nếu chưa tồn tại. Dùng tiền tố `IronPulse_`, tối đa 32 chữ cái không dấu hoặc chữ số ở giữa và hậu tố `QA`.
- **Tài khoản chạy ứng dụng.** Nhập tên tài khoản Windows tiêu chuẩn đã chuẩn bị.
- **Cổng.** Dùng `5443` nếu đang trống, hoặc chọn một cổng cục bộ chưa sử dụng trong khoảng 1024–65535.

Nhập `CAI DAT` để xác nhận. Với bản cài mới, chờ `CLEAN_DATASET_PASS` và `SETUP_DATABASE_PASS`.

Nếu cần chọn Python theo đường dẫn, thêm `-Python 'C:\Duong dan\python.exe'` vào lệnh Setup. Setup thông thường cần Internet để tải thư viện Python. Nếu đã có bộ wheel ngoại tuyến khớp `requirements-team.lock`, thêm `-OfflineWheels` và đường dẫn đến thư mục wheel.

~~~powershell
.\Setup-IronPulse.cmd -OfflineWheels 'C:\Goi\wheels'
~~~

Thay `C:\Goi\wheels` bằng thư mục wheel thực tế.

Khi chạy Setup lại trên bản đã cài, bước cài cơ sở dữ liệu xác minh đích và quyền hiện có.

## 5. Khởi động

Chạy các lệnh sau trong thư mục bản cài. Chạy `--check` khi website đang dừng. `CHECK_PASS` xác nhận kiểm tra kết nối cơ sở dữ liệu và đăng nhập đã thành công. Lệnh cuối khởi động website. Chờ `READY`.

~~~powershell
.\Mo-IronPulse.cmd --version
.\Mo-IronPulse.cmd --check
.\Mo-IronPulse.cmd
~~~

Mở [trang đăng nhập ở cổng mặc định](http://localhost:5443/login) hoặc địa chỉ chương trình in ra. Nhập mật khẩu Windows của tài khoản chạy ứng dụng tại lời nhắc `runas` nếu xuất hiện.

## 6. Đăng nhập

Dùng tài khoản Windows đã chạy Setup để chạy `.\Mo-IronPulse.cmd --credentials`. Lệnh hiển thị email và mật khẩu ứng dụng của tám tài khoản trình diễn. Các nhãn gồm `member-pt`, `member-class`, `member-expired`, `member-quota`, `staff`, `trainer-pt`, `trainer-class` và `manager`. Dùng email và mật khẩu ứng dụng trên trang đăng nhập.

## 7. Sử dụng

| Vai trò | Nội dung trình diễn |
|---|---|
| Hội viên | Xem hồ sơ, gói, hợp đồng và số lượt. Đặt lịch huấn luyện cá nhân (PT), đăng ký hoặc hủy lớp theo quyền. Hủy trước ít nhất 5 giờ để được hoàn lượt. |
| Nhân viên | Tra hội viên, huấn luyện viên và lớp, tư vấn gói, ghi khoản thu, kích hoạt hợp đồng và mở biên lai. |
| Huấn luyện viên | Xem lịch được phân công, buổi PT, thông tin liên hệ khi đủ điều kiện và lớp phụ trách. |
| Quản lý | Xem báo cáo, quản lý nhân sự, phòng tập, thiết bị, bảo trì, gói và lớp. |

Lịch trình diễn được tạo theo ngày cài đặt. Khi lịch mẫu đã qua, chọn lịch sắp diễn ra hoặc dùng chức năng nghiệp vụ để tạo lịch trên bản cài trình diễn nếu có quyền. Nếu hợp đồng không còn hiệu lực, dùng tài khoản có hợp đồng còn hiệu lực và còn lượt, hoặc mua và kích hoạt gói trên bản cài trình diễn.

Để kiểm đếm dữ liệu trên bản cài, mở SSMS bằng Windows Authentication, chọn đúng cơ sở dữ liệu CleanDemo rồi chạy [clean_count.sql](../ops/portable/clean_count.sql). Script chỉ đọc, kiểm tra tên và dấu định danh cơ sở dữ liệu. Dòng cuối cho biết số bảng nghiệp vụ được tính và kết quả so với mốc trên 10.000 dòng.

## 8. Dừng hoặc khởi động lại

Dùng `.\Mo-IronPulse.cmd --stop` để dừng hoặc `.\Mo-IronPulse.cmd --restart` để khởi động lại website.

## 9. Xử lý lỗi thường gặp

- **Lỗi SQL hoặc HTTP 503.** Kiểm tên instance, dịch vụ, Shared Memory, ODBC x64 và tài khoản chạy ứng dụng. Khi website đang dừng, dùng `--check`. Khi báo lỗi, ghi phiên bản, thao tác, thông báo HTTP hoặc SQLSTATE và che thông tin riêng.
- **Cơ sở dữ liệu đã tồn tại.** Để tiếp tục dùng bản cũ, mở đúng thư mục của bản đó. Khi cài riêng, chọn cơ sở dữ liệu và tài khoản chạy ứng dụng mới. Setup không ghi đè cơ sở dữ liệu có sẵn.
- **Cổng đã được dùng.** Chọn cổng cục bộ khác cho bản cài mới hoặc dừng đúng website đang chiếm cổng.
- **Không đọc được tài khoản trình diễn.** Chạy `--credentials` bằng đúng tài khoản Windows đã chạy Setup. Giữ cả hai loại mật khẩu ngoài báo cáo lỗi.
- **Lỗi SHA-256 hoặc cập nhật.** Đối chiếu SHA-256 với tệp đi kèm ZIP. Nếu cập nhật báo khóa `instance/portable-update.lock`, giữ ZIP và bản lưu trước cập nhật, rồi nhờ người phụ trách bản cài kiểm tra tiến trình cập nhật và bản lưu.

## Cập nhật bản v1.0 dùng dữ liệu CleanDemo

1. Trong thư mục bản đang dùng, chạy `.\Mo-IronPulse.cmd --version` để xác nhận **1.0.0**, rồi chạy `.\Mo-IronPulse.cmd --stop`.
2. Dùng `Get-FileHash .\IronPulse_Update_v1.0.1.zip -Algorithm SHA256` và so với SHA256.txt. Giải nén ZIP cập nhật vào thư mục mới. Giữ nguyên nội dung đã giải nén để chương trình đối chiếu với manifest.
3. Mở PowerShell trong thư mục vừa giải nén bằng tài khoản Windows quản trị SQL đã dùng khi Setup. Thay đường dẫn bản cài, đường dẫn ZIP và mã SHA-256 theo máy rồi chạy lệnh sau.

   ~~~powershell
   .\Update-IronPulse.cmd -InstalledRoot 'C:\IronPulse-v1' -Package 'C:\Goi\IronPulse_Update_v1.0.1.zip' -SHA256 '<SHA-256 trong SHA256.txt>'
   ~~~

4. Sau `UPDATE_PASS 1.0.1`, dùng `--version`, `--check` rồi mở website từ thư mục **bản đã cập nhật**. Bản cập nhật giữ cơ sở dữ liệu, cấu hình và tài khoản đang dùng. Chương trình tạo bản sao lưu `COPY_ONLY` có `CHECKSUM` trước khi đổi tệp, lưu biên nhận trong `instance/version-backups` và cập nhật định nghĩa ba thủ tục SQL. Lược đồ bảng giữ nguyên.
5. Khi cần hoàn tác, dừng website rồi chạy `.\Update-IronPulse.cmd -InstalledRoot 'C:\IronPulse-v1' -Rollback` từ thư mục bộ cập nhật đã giải nén. Chương trình khôi phục tệp, manifest và định nghĩa SQL theo bản lưu trước cập nhật. Các giao dịch đã ghi được giữ lại. Kiểm tra lại bằng `--version` và `--check`.

Gói cập nhật này áp dụng cho v1.0 dùng CleanDemo. Nâng cấp trực tiếp từ 0.9.1-test hoặc từ v1.0 dùng bộ dữ liệu cũ nằm ngoài phạm vi hỗ trợ. Để khởi tạo bộ dữ liệu trên 10.000 dòng, cài mới từ ZIP vào thư mục, cơ sở dữ liệu, tài khoản Windows và cổng riêng.
