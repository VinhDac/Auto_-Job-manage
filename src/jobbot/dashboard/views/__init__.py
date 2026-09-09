"""Các trang của app. Một file một trang.

Trang CHỈ VẼ: nhận dữ liệu, trả HTML. Không đọc DB, không quyết định gì.
Dữ liệu lấy từ dashboard/live.py — đọc thẳng DB thật, không còn mock.

Tab CÓ THỜI GIAN CHẠY (search, score, projects) dùng chung khuôn runtime.py:
đang chạy · nhật ký riêng · thống kê · biểu đồ · cài đặt · debug.
"""
