# SOP TBANG STORE Telegram Bot

## Chức năng hiện có
- Menu cửa hàng, ví, đơn hàng.
- Admin tạo sản phẩm, nhập key theo lô.
- Trừ số dư và giao key riêng sau khi mua.
- Admin cộng số dư thủ công.
- SQLite lưu dữ liệu.

## Chạy thử
1. Cài Python 3.11+.
2. `pip install -r requirements.txt`
3. Đặt biến môi trường `BOT_TOKEN` và `ADMIN_ID`.
4. Chạy `python bot.py`.

Lấy Telegram ID: chạy bot rồi nhắn `/myid`. Đặt ID của chủ shop vào biến `ADMIN_ID`, khởi động lại bot.

## Lệnh admin
- `/addproduct Innova Cheat 7 ngày | 60000`
- `/products`
- `/addkeys 1` rồi gửi từng key, mỗi dòng một key; gửi `/done` để kết thúc.
- `/credit TELEGRAM_ID | 50000`

## Lưu ý quan trọng
- Bản này dùng cộng ví thủ công; chưa tích hợp VietQR tự động.
- Chỉ nhập key hợp pháp mà bạn có quyền phân phối.
- Khi triển khai Render, dùng Persistent Disk để giữ SQLite. Không commit token lên GitHub.
- Trước khi mở bán thật cần bổ sung xác minh thanh toán, chống spam, sao lưu và kiểm thử bảo mật.
