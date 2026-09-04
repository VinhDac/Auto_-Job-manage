"""M0 — Hồ sơ người dùng.  KHÔNG CÓ CÁI NÀY THÌ KHÔNG MODULE NÀO CHẠY ĐÚNG.

Đây là bước MỞ BÀI. Trước khi kéo một tin nào về, hệ thống phải biết
người dùng là ai và muốn gì. Thiếu nó thì:
    ingest   kéo về tin không liên quan
    scoring  chấm điểm dựa trên không khí
    cv       không có nguyên liệu để viết
    mail     không có tên, địa chỉ, chữ ký
    outreach không biết đang đại diện cho ai

Ở đây:
    - Chia câu hỏi theo AI DÙNG: muc_tieu / rang_buoc / nang_luc / danh_tinh / project
    - Chỉ 2 câu bắt buộc: job_titles + markets. Còn lại điền dần.
    - Hỏi cái ingest DÙNG ĐƯỢC: chức danh thật, không phải phân loại
    - Nguyên liệu thô: CV, kinh nghiệm, dự án, kỹ năng
    - Mong muốn: vai trò, băng tần, thị trường, mức lương, giới hạn
    - Ràng buộc: cái gì KHÔNG nhận (đây là thứ hay bị quên nhất)
    - Lưu có phiên bản. Hồ sơ thay đổi theo thời gian.

Luật: hồ sơ là dữ liệu SỐNG, không phải form điền một lần.
Sau 50 lần bị từ chối thì mong muốn sẽ khác lúc đầu. Hệ thống phải
nhận ra khoảng trống và tự đề xuất hỏi lại — qua đúng hàng đợi Yes/No
như mọi module khác (design.md §1).

KHÔNG ở đây:
    - Chấm điểm khớp (-> scoring/)
    - Dựng file CV (-> cv/)
"""
