# DataArchive Server Monitor 1.1.1

Ứng dụng desktop PySide6 để theo dõi Ubuntu qua SSH/Tailscale và quản lý kho dữ liệu SFTP.

## Chạy dự án

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-pyside6.txt
.\.venv\Scripts\python.exe server_monitor_pyside6.py
```

Bản đóng gói Windows nằm tại `pyinstaller-dist/DataArchive-ServerMonitor-1.1.1.exe` và không được commit vào Git.

Ứng dụng hỗ trợ đăng nhập SSH bằng mật khẩu của `huy1111`, `servermonitor`, `thacsikhai`, hoặc SSH key. Mật khẩu/passphrase chỉ giữ trong bộ nhớ; PIN cục bộ được lưu hash tại `%APPDATA%\ServerMonitorPySide6\security.json`.

## Cấu trúc dự án

```text
server_monitor_pyside6.py        # Điểm khởi động và cửa sổ chính
dataarchive/
  config.py                      # Cấu hình server, hằng số, parser và tiện ích
  workers.py                     # Tác vụ nền Qt cho SSH/SFTP và PowerShell
requirements-pyside6.txt         # Dependency Python
DataArchive-ServerMonitor-1.1.1.spec  # Cấu hình đóng gói PyInstaller
```

Các phần giao diện, dịch vụ SSH/SFTP và tác vụ nền được giữ tách ranh giới để có thể tiếp tục tách thành module riêng mà không làm thay đổi luồng ứng dụng.

## Tải tệp lên server

Chọn thư mục đích trong danh sách, sau đó chọn **Tải tệp lên**, chọn tối đa 20 tệp (mỗi tệp tối đa 2 GB) rồi nhập mật khẩu SSH để xác nhận. Bộ chọn có nhóm **Tệp nén** cho `.zip`, `.zipx`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`, `.zst`, `.cab` và các biến thể phổ biến. App tải qua SFTP vào `/data/uploads` hoặc thư mục con đã chọn và tự tạo thư mục này nếu chưa có. App thêm thời gian vào tên tệp trên server để không ghi đè dữ liệu có sẵn. Nút **Hủy** trong popup sẽ hủy thao tác trước khi bất kỳ tệp nào được tải lên.

Sau khi tải lên hoặc tải xuống thành công, app hiển thị thời điểm hoàn thành. Khi chọn nhiều tệp, app truyền tối đa 3 tệp song song để tăng tốc mà không làm quá tải kết nối; mỗi tệp được truyền qua file tạm `.part`, kiểm tra dung lượng, rồi mới đổi tên thành tệp hoàn chỉnh. Các chỉ số server cũng được tự làm mới mỗi 5 phút sau khi kết nối SSH thành công.

## Quản lý thư mục tải lên

App có thể tạo, đổi tên và xóa thư mục **chỉ trong** `/data/uploads`. Xóa sẽ chuyển dữ liệu vào `/data/uploads/.trash` thay vì xóa vĩnh viễn. Mỗi thao tác yêu cầu xác nhận và SSH key.

## Quản lý tệp

App hiển thị tối đa 120 tệp trong kho upload. Bạn có thể chọn một tệp để đổi tên hoặc chọn nhiều tệp/thư mục để tải xuống hay chuyển vào thùng rác cùng lúc. Khi tải xuống, app mở hộp thoại Windows để bạn chọn thư mục lưu; file trùng tên sẽ không bị ghi đè.

## Thùng rác server

Mục bị xóa từ kho HDD được chuyển vào `/data/uploads/.trash`. Mở **🗑 Thùng rác** ở sidebar để khôi phục các mục đã chọn, xóa vĩnh viễn các mục đã chọn hoặc dọn sạch toàn bộ thùng rác. Khôi phục đưa dữ liệu về thư mục gốc `/data/uploads` và sẽ từ chối nếu tên đích đã tồn tại.

## Trình duyệt kho dữ liệu

Trong phần **Kho dữ liệu**, chọn **HDD** để duyệt `/data/uploads` (có thể quản lý tệp) hoặc **SSD** để xem thư mục home thực tế của tài khoản SSH. Đường dẫn SSD được tự động xác định khi đăng nhập, nên không phụ thuộc vào tên tài khoản hoặc cấu trúc `/home` trên server. SSD là chế độ chỉ xem để bảo vệ tệp hệ thống. Kho HDD hoạt động theo kiểu File Explorer cơ bản: bấm vào thư mục để mở, dùng **Lên thư mục cha** để quay lại và **Làm mới** để tải lại nội dung. Nút tải lên sẽ đưa tệp vào thư mục đang mở. Mật khẩu SSH chỉ được giữ trong bộ nhớ trong khi app đang mở để hỗ trợ duyệt thư mục; nó không được ghi xuống ổ đĩa.

### Chia sẻ quyền xem HDD

Mặc định `/data/uploads` chỉ thuộc `servermonitor`. Để thiết lập quyền chung, đăng nhập bằng một tài khoản có `sudo`, vào **Cài đặt** và chọn **Thiết lập quyền HDD**. Ứng dụng tạo nhóm biên tập cho `servermonitor` và `thacsikhai`, nên cả hai có thể tạo, đổi tên, xóa và tải lên; `huy1111` được cấp ACL chỉ đọc để xem, duyệt và tải xuống. Mật khẩu sudo chỉ được dùng cho lần thiết lập đó và không được lưu lại.

## PowerShell tích hợp

Sau khi mở khóa PIN, bảng **Windows PowerShell** chạy lệnh cục bộ dưới tài khoản Windows hiện tại; nó không chạy lệnh trên Ubuntu. Lệnh không được lưu vào lịch sử. Chỉ chạy lệnh bạn hiểu rõ vì PowerShell có thể thay đổi hoặc xóa dữ liệu trên laptop.

## Đóng gói bản Windows

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --distpath pyinstaller-dist --workpath pyinstaller-build-1.1.1 DataArchive-ServerMonitor-1.1.1.spec
```

## Bảo mật

Mật khẩu chỉ được gửi qua SSH để thực hiện kết nối hiện tại; ứng dụng không ghi nó vào cấu hình.
