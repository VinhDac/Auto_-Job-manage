"""Điều khiển Chrome — cho những nguồn không có API.

Vì sao tự viết client WebSocket thay vì cài Playwright: cả dự án này không cài
gì cả, chạy được ngay bằng Python có sẵn trên macOS. Việc cần làm với job board
rất đơn giản — mở trang, chờ, lấy HTML, cuộn, bấm — nên ~120 dòng là đủ.

Nếu về sau đụng trang phức tạp quá thì Playwright chỉ cách một lệnh pip, và
giao diện trong `cdp.py` không phải đổi.
"""
