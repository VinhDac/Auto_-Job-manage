# Roadmap — 6 bước, theo đúng đề bài

Đề bài Vin giao:

```
24/7  tìm việc khớp
      -> sửa CV bám sát yêu cầu từng JD
      -> dựng personal project chứng minh độ khớp
      -> gửi đi (autoclick qua Chrome)
      -> theo dõi: đã gửi gì, cho ai, bao giờ
      -> nhắc kiểm tra hộp thư
```

Không cần nhanh. Cần **thay được người**. Phải có cache vì việc kéo dài nhiều tuần.

**Luật:** không sang bước sau khi bước trước chưa đạt "Xong khi".
"Xong khi" phải nhìn thấy được hoặc chạy được — không phải "đã viết code".

Trạng thái: ` ` chưa làm · `~` đang làm · `x` xong

---

## Đã xong

| | Việc | Kết quả |
|---|---|---|
|x| **Hồ sơ người dùng** | 5 phần · 35 câu · lưu SQLite có phiên bản · hồ sơ Vin đã nạp |
|x| **Giao diện đầy đủ** | 8 trang bấm được, dữ liệu giả trong `dashboard/mock.py` |

`mock.py` là **bản hợp đồng**: nối backend = thay ruột hàm, giữ nguyên hình dạng trả về.
Trang không phải sửa dòng nào.

---

## Bước 1 — TÌM   *(xong)*

Kéo tin thật về, gộp trùng, lưu cache.

| | Việc | Thư mục |
|---|---|---|
|x| Store + cache 4 tầng: raw / posting / source_run / audit | `core/` |
|x| Arbeitnow · Remotive · Greenhouse ×14 · Lever ×3 · Ashby ×4 | `ingest/` |
|x| Lọc theo hồ sơ, LUÔN ghi lý do bỏ | `ingest/filter.py` |
|x| Gộp trùng theo vân tay công ty + chức danh | `dedup/group.py` |
|x| Nối `/` và `/jobs` vào dữ liệu thật | `dashboard/live.py` |
| | **Adzuna GB** — cần key miễn phí của Vin | `ingest/adzuna.py` |
| | Nguồn qua Chrome (grad scheme UK không có API) | `browser/` |

**Kết quả lần chạy 04/09/2026:**

```
2.910 tin thật  ->  lọc còn 24  ->  gộp thành 20 việc duy nhất
```

Trong đó có: Jane Street Quantitative Researcher · Point72 Academy 2026 Investment
Analyst Program · Zopa 2027 Graduate Analyst · Man Group Quantitative Developer AHL ·
Squarepoint Junior Credit Research Analyst · GSA · Winton · Quadrature · IMC.
Tất cả ở London, tất cả đúng dải graduate/junior.

Test: 21/21 qua (`python3 tests/test_ingest.py`).

**Ba lỗi thật đã sửa trong lúc làm:**

1. `"analyst"` từng nằm trong `JUNIOR_WORDS` -> mọi tin *"Senior ... Analyst"* lọt qua
   bộ lọc cấp bậc. Trong tài chính "Analyst" là chức danh ở MỌI cấp.
2. Greenhouse: dùng `first_published` -> Jane Street hiện "2228 ngày trước" vì tin để mở
   từ 2020. Đổi sang `updated_at`.
3. Arbeitnow trả ngày kiểu Unix timestamp, không phải ISO -> mọi tin mất ngày.

**Đã bỏ:** đối chiếu sponsor register — Vin đang có Graduate visa (design.md §8).

**Board rỗng đã loại:** `marshallwace`, `optiver` trả 200 nhưng 0 tin.

## Bước 2 — CHẤM   *(xong)*

Chấm điểm khớp, và **giải thích được vì sao**.

| | Việc | Thư mục |
|---|---|---|
|x| Tách yêu cầu khỏi JD — theo tiêu đề phần + gạch đầu dòng | `scoring/extract.py` |
|x| Vòng dự phòng cho JD viết văn xuôi, loại câu phúc lợi | `scoring/extract.py` |
|x| Đối chiếu từng yêu cầu, kèm bằng chứng trích từ hồ sơ | `scoring/score.py` |
|x| Phân biệt bằng chứng MẠNH (CV, học vấn) và YẾU (từ khoá) | `scoring/score.py` |
|x| Điểm 100 chia 4 phần, giải thích được từng phần | `scoring/score.py` |
|x| Lọc + sắp theo điểm trên giao diện | `dashboard/` |

**Thang điểm:** 55 yêu cầu bắt buộc · 15 điểm cộng · 20 đúng cấp bậc · 10 chức danh.

**Không bịa:** yêu cầu không nhận ra được KHÔNG tính vào mẫu số. JD không đọc
được yêu cầu thì `score = NULL` và nói thẳng *"can't read requirements"*.

Chạy 24 tin trong **12ms**, không gọi LLM lần nào. Test: 31/31 qua.

**Ba lỗi thật đã sửa:**

1. `strip_html` bỏ thẻ TRƯỚC rồi mới giải mã `&lt;` -> thẻ mã hoá biến thành thẻ
   thật sau khi đã bỏ xong. **1.522 tin dính HTML nguyên trong mô tả.**
2. Lấy bằng cấp CAO NHẤT được nhắc rồi đòi đúng cái đó -> dòng *"Undergraduate,
   MS, or PhD"* bị chấm trượt dù có MSc. JD viết "hoặc" thì phải là hoặc.
3. `"ba"` và `"ms"` so kiểu chuỗi con -> `"database"` thành bằng BA, `"systems"`
   thành bằng MS. Đổi sang so theo ranh giới từ.

**Còn thiếu:** CV đầy đủ của Vin. Hiện nhiều bằng chứng phải dựa vào *từ khoá tìm
kiếm* thay vì CV — hệ thống có đánh dấu chỗ nào yếu, nhưng điền CV vào là chắc hẳn.

## Bước 3 — SỬA CV   *(xong)*

|x| Tách CV thành khối rời (vai trò, project, học vấn, kỹ năng) | `cv/blocks.py` |
|x| Bộ luật viết CV, rút từ CV thật đang bị từ chối | `cv/rules.py` |
|x| Chọn + sắp câu theo từng JD | `cv/build.py` |
|x| Trang `/jobs/<id>/cv` kèm phần kiểm chứng | `cv/render.py` |

**Cơ chế: CHỌN và SẮP XẾP, không viết mới.** Mọi câu trên CV sinh ra đều là câu
Vin đã viết. Hệ thống chỉ quyết định câu nào lên, thứ tự nào, bỏ câu nào — và
luôn hiện lý do bỏ.

**Bộ luật (áp cho mọi JD, không phải sửa tay một lần):**

| Luật | Vì sao |
|---|---|
| Gạch đầu dòng, không đoạn văn | Vòng quét 6 giây phải có chỗ đậu mắt |
| Câu trúng thứ JD đòi lên trước | Bước 2 đã tách sẵn yêu cầu |
| **Bỏ thất bại về KẾT QUẢ** | Người đọc 200 CV chỉ nhớ câu tệ nhất |
| **GIỮ kiến thức kỹ thuật** | Đây mới là thứ tách khỏi 40 người cùng khớp |
| Bỏ ý kiến, giữ bằng chứng | *"Profit means nothing"* không chứng minh gì |
| Bỏ nhóm Compute và Method | Dạy người đọc kiến thức cơ bản = tín hiệu non tay |
| Câu nhạy cảm mà có số -> ĐÁNH DẤU, không vứt | Vứt cả câu thì mất luôn con số |

**Phân biệt quan trọng nhất:**

```
"A random train/test split leaks"      -> KIẾN THỨC   -> giữ
"Live drawdown ran 30% deeper"          -> KẾT QUẢ HỎNG -> chuyển sang trang project
```

Bản đầu tôi bắt cả chữ `leaks` nên bỏ mất phần chuyên môn giá trị nhất. Đã sửa,
có test chặn tái phát.

**Chạy trên tin thật:**

```
Point72 Quant Researcher Intern   thiếu: — (danh sách "hoặc" đã đủ)
IMC Quant Researcher Equities     thiếu: derivatives, equities
Jane Street Quant Researcher      thiếu: market data
```

Test: 28/28 qua. Không gọi LLM lần nào.

**Chưa làm:** xuất PDF/DOCX. Hiện xem trên web, copy ra được.

## Bước 4 — PROJECT

Gom JD thành nhóm, mỗi nhóm một project, mỗi JD một trang kết quả.

| | Việc |
|---|---|
| | Gom cụm JD (200 tin ≈ 5–8 nhóm) |
| | Chọn project cho mỗi nhóm |
| | Sinh trang kết quả 5 phần cho từng JD |

**Xong khi:** có **một** project thật, đang chạy, kèm **một** trang kết quả viết riêng
cho một JD cụ thể.

> Phần xây project là **việc người làm**, không phải việc hệ thống.
> Chạy song song được, không cần đợi bước 1–3.

## Bước 5 — GỬI

Duyệt theo lô, rồi máy tự gửi.

| | Việc | Thư mục |
|---|---|---|
| | Hàng đợi Yes/No chạy thật | `core/` |
| | Điều khiển Chrome, điền form, bấm gửi | `browser/` |
| | Chống gửi trùng — cùng công ty, cùng vị trí | `core/` |
| | Nhật ký: gửi gì, cho ai, lúc nào, kết quả ra sao | `core/` |

**Xong khi:** bấm duyệt một lô → **một đơn thật được gửi thành công**, có ghi nhật ký.

**Cần chuẩn bị:** một profile Chrome riêng, đăng nhập một lần.

## Bước 6 — THEO DÕI + NHẮC

| | Việc | Thư mục |
|---|---|---|
| | State machine vòng đời ứng tuyển | `core/` |
| | Đọc hộp thư, khớp thư trả lời về đúng đơn | `mail/` |
| | Nhắc kiểm tra thư · nhắc follow-up khi im lặng quá lâu | `notify/` |
| | Thống kê: tỉ lệ phản hồi theo nguồn, theo điểm | `stats/` |

**Xong khi:** gửi → thấy trong `/pipeline` → có thư trả lời → khớp đúng về đơn đó →
nhắc đúng lúc.

---

## Vì sao thứ tự này

- **Bước 1 chặn tất cả.** Chưa có tin thật thì chấm điểm, sửa CV, dựng project đều là đoán.
- Bước 2 cần dữ liệu thật mới chọn được thuật toán. Chọn trước là đoán mò.
- Bước 3–4 cần bước 2 để biết JD đòi gì.
- Bước 5 gửi ra ngoài → chỉ làm sau khi CV và project đã đủ tốt.
- Bước 6 cần bước 5 chạy đủ lâu mới có gì để đếm.

Ghi `audit` **ngay từ bước 1**. Thiếu nó thì đến bước 6 không có gì để đếm và không lấy lại được.

## Việc gấp hơn cả roadmap này

Tháng 9 là mùa graduate scheme UK mở đơn cho intake 2027, nhiều nơi đóng khi đủ người.
Vin nộp tay ngay từ bây giờ, song song với việc xây hệ thống. Hệ thống là bộ khuếch đại,
không phải cái cớ để hoãn.
