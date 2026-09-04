# Roadmap — làm đến đâu test được đến đấy

Luật: **không sang module sau khi module trước chưa đạt "Xong khi".**
"Xong khi" phải là thứ nhìn thấy được hoặc chạy được — không phải "đã viết code".

Trạng thái: ` ` chưa làm · `~` đang làm · `x` xong

---

## Lát 1 — Xương sống  *(mục tiêu trước mắt)*

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M0 | Store + cache | `core/` | Lưu, đọc lại được, restart không mất dữ liệu |
| | M1 | Ingest | `ingest/` | Có tin tuyển dụng **thật** trong DB, từ ≥3 nguồn |
| | M2 | Dedup | `dedup/` | 1.000 tin thô → N tin duy nhất, giải thích được vì sao gộp |
| | M3 | Dashboard | `dashboard/` | Mở trang thấy số nhảy live |

Xong lát 1 = nhìn thấy dữ liệu thật trên màn hình. Chưa chấm điểm, chưa CV, chưa gửi gì.

## Lát 2 — Ra quyết định

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M4 | Scoring CV↔JD | `scoring/` | Ra điểm **và giải thích được vì sao** ra điểm đó |
| | M5 | Proposal + Yes/No | `core/` | Bấm Yes → có thứ thật xảy ra; bấm No → ghi lại lý do |

## Lát 3 — Hành động ra ngoài  *(mọi thứ ở đây đều qua Yes/No)*

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M6 | CV builder | `cv/` | Ra file CV bám đúng ngôn ngữ một JD cụ thể |
| | M7 | Mail | `mail/` | Gửi được, và bắt được thư phản hồi khớp về đúng hồ sơ |
| | M8 | Thông báo | `notify/` | Có việc hợp → biết ngay, không phải mở dashboard |

## Lát 4 — Đo và mở rộng

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M9 | Thống kê | `stats/` | Tỉ lệ phản hồi theo nguồn và theo điểm match |
| | M10 | Networking / profile / bài đăng | `outreach/` | Sau cùng. Rủi ro cao nhất, giá trị chưa chứng minh. |

---

## Vì sao thứ tự này

- M0–M3 không đụng gì ra ngoài → làm sai cũng không mất gì → học được cách dữ liệu thật trông ra sao.
- M4 cần dữ liệu thật để chọn thuật toán. Chọn trước khi có dữ liệu là đoán mò.
- M6–M8 gửi ra ngoài → chỉ làm sau khi cổng Yes/No (M5) đã chạy chắc.
- M9 cần M7 chạy đủ lâu mới có gì để đếm.
- M10 để cuối vì rủi ro tài khoản cao nhất và giá trị chưa được chứng minh.

## Ghi chú

Số liệu M9 chính là nguyên liệu cho "một trang kết quả" ở `strategy.md` §5.
Ghi `audit` ngay từ M1 — thiếu nó thì đến M9 không có gì để đếm và không lấy lại được.
