# Bộ cài hỗ trợ tiếng Việt cho Kobo

[English guide](README.md)

Đây là công cụ cài đặt chạy cục bộ trên máy tính, tập trung vào các thành phần hỗ trợ tiếng Việt cho Kobo:

- 20 font tương thích với Kobo và gói ngôn ngữ tiếng Việt tùy chọn, lấy từ dự án [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) của redphx
- Từ điển Anh–Việt cho trình đọc sách mặc định của Kobo
- Từ điển Anh–Việt dạng StarDict cho KOReader đã được cài sẵn

Công cụ này **không cài đặt hoặc cập nhật** NickelMenu, KOReader, SimpleUI hay các tiện ích khác. Dữ liệu từ Kobo không được tải lên mạng. Sách, tiến độ đọc, thiết lập, plugin và các tệp không liên quan đều được giữ nguyên.

## Thứ tự cài đặt khuyến nghị

1. Nếu muốn dùng NickelMenu hoặc KOReader, hãy cài chúng trước bằng [KoboPatch Web UI](https://kp.nicoverbruggen.be) của Nico Verbruggen.
2. Tháo thiết bị an toàn và chờ Kobo cài đặt, khởi động lại hoàn tất. Không chạy hai bộ cài trong cùng một lần kết nối USB vì cả hai có thể tạo tệp `.kobo/KoboRoot.tgz`.
3. Kết nối lại Kobo, khởi động bộ cài này và chọn **Install Vietnamese support**.
4. Tháo thiết bị an toàn một lần nữa, rút cáp và chờ Kobo khởi động lại để áp dụng font và gói ngôn ngữ.
5. Nếu Kobo chưa tự chọn tiếng Việt, vào **More → Settings → Language and dictionaries → Select your Language → Extra: vi**.

KOReader là tùy chọn. Nếu phát hiện KOReader, nút cài đặt chính sẽ cài thêm từ điển cho KOReader. Nếu không có KOReader, công cụ chỉ cài bản sửa font và từ điển cho trình đọc mặc định của Kobo.

## Khởi động bộ cài

Yêu cầu duy nhất là Python 3.

### macOS

Nhấp đúp vào `start.command`, hoặc mở Terminal trong thư mục dự án và chạy:

```sh
./start.command
```

Nếu macOS chặn tệp, hãy chạy lệnh trên từ Terminal.

### Windows

1. Cài [Python 3](https://www.python.org/downloads/) và chọn **Add python.exe to PATH** trong lúc cài đặt.
2. Nhấp đúp vào `start.bat`, hoặc chạy trong Command Prompt:

```bat
start.bat
```

### Linux

```sh
python3 server.py
```

Trình duyệt sẽ mở địa chỉ <http://127.0.0.1:8765>. Kết nối Kobo bằng cáp USB rồi chọn **Connect** trên màn hình Kobo. Thẻ trạng thái sẽ tự động tìm thiết bị; bạn cũng có thể chọn thiết bị hoặc thư mục Kobo thủ công.

## Cách sử dụng

1. Kiểm tra thẻ trạng thái hiển thị **Kobo ready** và đúng phiên bản firmware.
2. Chọn **Install Vietnamese support**.
3. Chờ trạng thái báo hoàn tất. Không rút cáp trong lúc đang sao chép tệp.
4. Đóng các tệp Kobo đang mở, tháo Kobo thủ công bằng Finder/trình quản lý tệp, rút cáp và chờ Kobo khởi động lại hoàn toàn. Trang web chỉ hiển thị hướng dẫn; không tự gọi lệnh tháo thiết bị.

Muốn chỉ cài một thành phần, mở **Advanced options**, chọn một hoặc nhiều mục sau rồi nhấn **Install selected items**:

- **Vietnamese font fix**: bản sửa font tiếng Việt, chỉ dành cho firmware Kobo 4.x.
- **Vietnamese language pack**: thêm `Extra: vi` vào danh sách ngôn ngữ và cài phần dịch tiếng Việt cho Kobo; có thể cài độc lập không cần bản sửa font.
- **Kobo dictionary**: từ điển Anh–Việt cho trình đọc mặc định.
- **KOReader dictionary**: từ điển Anh–Việt cho KOReader; yêu cầu thư mục `.adds/koreader` đã tồn tại.

## Những thay đổi được thực hiện trên Kobo

### Font và gói ngôn ngữ tiếng Việt

Tệp dựng sẵn `build/KoboRoot.tgz` chỉ chứa font:

- 16 font thay thế Avenir, Georgia, Rakuten Sans và Rakuten Serif trong thư mục font hệ thống của Kobo
- 4 font Courier tương thích trong thư mục font người dùng để hiển thị đúng nội dung monospace

Các font được lấy từ bản phát hành `v20260319` đã xác minh của redphx. Khi chọn **Vietnamese language pack**, bộ cài thêm `trans_vi.qm`, `libtiengviet.so` và hook cấu hình để thêm `Extra: vi` vào danh sách ngôn ngữ Kobo. Gói này không chứa NickelMenu hoặc KOReader.

Bản sửa font và gói ngôn ngữ chỉ được cài trên firmware 4.x. Nếu `.kobo/KoboRoot.tgz` đã tồn tại, công cụ sẽ sao lưu tệp đó trước khi thay thế.

Nếu muốn cài thêm đầy đủ bàn phím và tính năng tự sửa sau khi cập nhật firmware, hãy sử dụng trực tiếp dự án [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) của redphx.

### Từ điển cho Kobo

Công cụ tải tệp chính thức từ dự án `redphx/tudien`, xác minh SHA-256 rồi sao chép đến:

```text
.kobo/custom-dict/dicthtml-en-vi.zip
```

### Từ điển cho KOReader

Nếu KOReader đã được cài, công cụ tải và xác minh bản StarDict chính thức, sau đó cài ba tệp từ điển vào:

```text
.adds/koreader/data/dict/tudien-en-vi/
```

Công cụ không sửa thiết lập, lịch sử, plugin hoặc tệp chương trình của KOReader. Nếu KOReader chưa được cài, hãy cài bằng KoboPatch Web UI rồi chạy lại bộ cài này.

Các tệp từ điển được cố định ở bản phát hành `redphx/tudien` `v20260411` và được lưu vào bộ nhớ đệm cục bộ sau khi xác minh checksum. Từ điển cũ tại đúng vị trí đích sẽ được sao lưu trước khi cập nhật.

## Sao lưu và an toàn dữ liệu

Các bản sao lưu được lưu trong thư mục `backups/` trên máy tính. Thư mục này có thể chứa dữ liệu từ thiết bị, vì vậy không nên chia sẻ công khai.

Bộ cài chỉ ghi vào các vị trí cần thiết cho thành phần đã chọn. Nó không xóa sách, tiến độ đọc, cấu hình KOReader, plugin hoặc các tệp từ điển không liên quan.

Nếu bạn vừa dùng KoboPatch Web UI, bắt buộc phải tháo Kobo và chờ lần khởi động lại đầu tiên hoàn tất trước khi chạy bộ cài này. Nếu không, gói font có thể thay thế tệp `KoboRoot.tgz` đang chờ cài của công cụ trước đó.

## Dựng lại KoboRoot.tgz

Trong **Advanced options**, chọn **Rebuild KoboRoot.tgz** để dựng lại gói font từ 20 tệp đã kèm theo dự án.

Quá trình này dùng trực tiếp thư viện chuẩn của Python. Không cần Docker, trình biên dịch, NickelTC hoặc công cụ phát triển khác.

Các liên kết nguồn chính thức được hiển thị trực tiếp trong phần **Advanced options**: [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet), [redphx/tudien](https://github.com/redphx/tudien) và [KoboPatch Web UI](https://github.com/nicoverbruggen/kobopatch-webui).

Tùy chọn **Repair a KoboRoot.tgz only** dành cho nhà phát triển. Nó thêm 20 font vào một gói có sẵn, giữ nguyên các tệp thông thường không phải font và từ chối đường dẫn không an toàn, liên kết hoặc tệp đầu vào quá lớn.

## Ghi công và nguồn gốc

- Font và cơ chế sửa lỗi hiển thị font Kobo: [Kobo Tiếng Việt](https://github.com/redphx/kobo-tieng-viet) của **redphx**, bản `v20260319`. Thông tin nguồn chi tiết nằm trong [`vendor/vietnamese-fonts/SOURCE.md`](vendor/vietnamese-fonts/SOURCE.md).
- Từ điển Kobo và KOReader: [redphx/tudien](https://github.com/redphx/tudien) của **redphx**. Tệp được tải trực tiếp từ bản phát hành chính thức và không được phát hành lại trong kho mã này.
- Công cụ cài các tiện ích tùy chọn: [KoboPatch Web UI](https://github.com/nicoverbruggen/kobopatch-webui) của **Nico Verbruggen**. Hãy dùng công cụ này để cài NickelMenu, KOReader và các tiện ích khác trước khi quay lại đây.

Dự án này hoạt động độc lập với các dự án nguồn nói trên. Quyền tác giả và điều khoản sử dụng của từng dự án vẫn thuộc về tác giả tương ứng.

Thông tin kỹ thuật và lệnh kiểm thử nằm trong [TECHNICAL-NOTES.md](TECHNICAL-NOTES.md).
