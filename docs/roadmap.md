|~| M0 | **Hồ sơ người dùng** | `profile/` |  |

> App đã chạy được: hỏi theo 3 vòng, lưu SQLite có phiên bản, 15/15 test qua.
> Còn `~` chứ chưa `x` vì **dữ liệu thật chưa điền**. Chạy `python3 run.py` rồi làm vòng 1.
# Roadmap — làm đến đâu test được đến đấy

Luật: **không sang module sau khi module trước chưa đạt "Xong khi".**
"Xong khi" phải là thứ nhìn thấy được hoặc chạy được — không phải "đã viết code".

Trạng thái: ` ` chưa làm · `~` đang làm · `x` xong

---

## Lát 0 — Mở bài  *(chặn mọi thứ phía sau)*

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
|~| M0 | **Hồ sơ người dùng** | `profile/` | Trả lời được: tuyển vai trò gì · băng tần nào · thị trường nào · nguyên liệu CV có gì · **không nhận cái gì** |

> App đã chạy được: hỏi theo 3 vòng, lưu SQLite có phiên bản, 15/15 test qua.
> Vẫn là `~` chứ chưa `x` vì **dữ liệu thật chưa điền** — chạy `python3 run.py` rồi làm vòng 1.

Không có M0 thì M2 kéo về tin không liên quan, M5 chấm điểm dựa trên không khí,
M7 không có nguyên liệu viết. Đây là gốc phụ thuộc của nửa hệ thống.

Hồ sơ là dữ liệu **sống**, không phải form điền một lần. Nhận theo vòng.

## Lát 1 — Xương sống

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M1 | Store + cache | `core/` | Lưu, đọc lại được, restart không mất dữ liệu |
| | M2 | Ingest | `ingest/` | Có tin tuyển dụng **thật** trong DB, từ ≥3 nguồn, đã lọc theo M0 |
| | M3 | Dedup | `dedup/` | 1.000 tin thô → N tin duy nhất, giải thích được vì sao gộp |
| | M4 | Dashboard | `dashboard/` | Mở trang thấy số nhảy live |

Xong lát 1 = nhìn thấy dữ liệu thật trên màn hình. Chưa chấm điểm, chưa CV, chưa gửi gì.

## Lát 2 — Ra quyết định

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M5 | Scoring CV↔JD | `scoring/` | Ra điểm **và giải thích được vì sao** ra điểm đó |
| | M6 | Proposal + Yes/No | `core/` | Bấm Yes → có thứ thật xảy ra; bấm No → ghi lại lý do |

## Lát 3 — Hành động ra ngoài  *(mọi thứ ở đây đều qua Yes/No)*

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M7 | CV builder | `cv/` | Ra file CV bám đúng ngôn ngữ một JD cụ thể |
| | M8 | Mail | `mail/` | Gửi được, và bắt được thư phản hồi khớp về đúng hồ sơ |
| | M9 | Thông báo | `notify/` | Có việc hợp → biết ngay, không phải mở dashboard |

## Lát 4 — Đo và mở rộng

| | # | Module | Thư mục | Xong khi |
|---|---|---|---|---|
| | M10 | Thống kê | `stats/` | Tỉ lệ phản hồi theo nguồn và theo điểm match |
| | M11 | Networking / profile / bài đăng | `outreach/` | Sau cùng. Rủi ro cao nhất, giá trị chưa chứng minh. |

---

## Vì sao thứ tự này

- **M0 trước tất cả.** Không biết người dùng muốn gì thì mọi thứ sau đều đoán mò.
- M1–M4 không đụng gì ra ngoài → sai cũng không mất gì → học được cách dữ liệu thật trông ra sao.
- M5 cần dữ liệu thật để chọn thuật toán. Chọn trước khi có dữ liệu là đoán mò.
- M7–M9 gửi ra ngoài → chỉ làm sau khi cổng Yes/No (M6) đã chạy chắc.
- M10 cần M8 chạy đủ lâu mới có gì để đếm.
- M11 để cuối vì rủi ro tài khoản cao nhất và giá trị chưa được chứng minh.

## Ghi chú

Số liệu M10 chính là nguyên liệu cho "một trang kết quả" ở `strategy.md` §5.
Ghi `audit` ngay từ M2 — thiếu nó thì đến M10 không có gì để đếm và không lấy lại được.
