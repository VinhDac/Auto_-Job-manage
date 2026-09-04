"""M1 — Kéo tin tuyển dụng về, mỗi nguồn một file.

Ở đây:
    - Một file cho một nguồn (greenhouse.py, lever.py, ashby.py, mail_alert.py, ...)
    - Mỗi nguồn: fetch -> chuẩn hóa về Job -> trả ra. Hết.

KHÔNG ở đây:
    - Dedup (-> dedup/)     - Chấm điểm (-> scoring/)
    - Ghi DB trực tiếp (-> core/store)

Nguồn đã xác minh chạy: greenhouse, lever, ashby, arbeitnow, remotive.
Nguồn không có API công khai: chạy trong cửa sổ giống người, không 24/7 (design.md §3).
"""
