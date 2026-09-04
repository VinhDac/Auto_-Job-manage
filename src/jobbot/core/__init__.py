"""Lõi — xương sống dùng chung cho mọi module.

Ở đây:
    - Kiểu dữ liệu chung: Job, Proposal, Application, AuditEntry
    - Store SQLite + 4 tầng raw / derived / state / audit
    - Cache (chống fetch lại, chống chấm điểm lại)
    - Hàng đợi đề xuất và cổng Yes/No
    - Thực thi đề xuất sau khi được duyệt

KHÔNG ở đây:
    - Logic riêng của bất kỳ nguồn nào (-> ingest/)
    - Luật chấm điểm (-> scoring/)
    - Bất cứ thứ gì biết LinkedIn/Greenhouse/... là gì
"""
