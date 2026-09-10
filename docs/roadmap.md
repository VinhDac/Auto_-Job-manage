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
|x| **Chrome tự lái** — client WebSocket + CDP tự viết | `browser/` |
|x| **eFinancialCareers** — board tài chính lớn nhất London | `ingest/web/` |
| | Bright Network · Milkround · Prospects | `ingest/web/` |

**Kết quả lần chạy 04/09/2026:**

```
2.910 tin thật  ->  lọc còn 24  ->  gộp thành 20 việc duy nhất
```

Trong đó có: Jane Street Quantitative Researcher · Point72 Academy 2026 Investment
Analyst Program · Zopa 2027 Graduate Analyst · Man Group Quantitative Developer AHL ·
Squarepoint Junior Credit Research Analyst · GSA · Winton · Quadrature · IMC.
Tất cả ở London, tất cả đúng dải graduate/junior.

### Chrome — bổ sung sau khi rõ định hướng

Nút thắt nằm ở phía nhà tuyển dụng: họ mất **một tuần** mới trả lời. Máy nhanh
gấp trăm lần cũng không rút ngắn được ngày nào. Nên ngân sách đúng cho mỗi tin
là **hàng giờ máy chạy**, không phải vài giây — và điều đó mở ra việc đọc kỹ.

| | |
|---|---|
| `browser/ws.py` | Client WebSocket ~120 dòng, thư viện chuẩn. Không cài gì |
| `browser/chrome.py` | Chrome RIÊNG, profile riêng, cổng 9333 |
| `browser/cdp.py` | Mở trang, chờ, chạy JS, cuộn, bấm |
| `ingest/web/` | Một file một trang, trả về đúng kiểu `Posting` |

**Headed, không headless.** Headless bị Cloudflare chặn (`Just a moment…`, `403`).
Chrome thường thì vào bình thường — đây là dùng trình duyệt thật, không phải kỹ
thuật né tránh.

**Hai luật an toàn, có test chặn:**

1. Hộp cookie: **luôn bấm Reject, không bao giờ Accept.** Hệ thống không có quyền
   đồng ý điều khoản thay người dùng.
2. Trang nào trả về thử thách chống bot thì **ghi nhận rồi bỏ qua** — trang đó
   đang nói không với máy, không cãi lại.

### Đi thẳng nhà tuyển dụng, bỏ trung gian

Board trung gian có vấn đề: **19/28 tin lấy từ eFinancialCareers là của công ty
môi giới**, không phải chủ việc. Họ viết lại JD, giấu tên công ty thật, và nộp
qua đó là hồ sơ đi thêm một tầng lọc nữa.

| | |
|---|---|
| `ingest/web/agency.py` | Nhận diện tin môi giới — tên hãng + chữ trong JD |
| `ingest/web/careers.py` | Dò trang tuyển dụng của công ty, xác minh đúng chủ |
| `ingest/web/companies.py` | Bảng công ty mục tiêu, **tự lớn lên** |
| `config/companies.toml` | 55 công ty hạt giống: quỹ, quản lý tài sản, fintech UK |

**Tự mở rộng:** mỗi lần quét, chủ việc thật thấy trong tin được thêm vào bảng và
tự dò ATS. `boards.toml` gõ tay giờ chỉ còn là hạt giống.

**Kết quả:** 24/65 công ty dò ra ATS — thêm Qube Research (197 tin), Ebury (173),
Jump Trading (109), Schonfeld (67), Thought Machine (41), Quantexa (30).

```
việc khớp   20  →  68        (49 trực tiếp · 19 qua môi giới)
```

**Hai lỗi thật đã sửa:**

1. `norm_company` cắt cả `"Group"`, `"Capital"` — đúng khi so khớp tên nhưng sai
   khi đoán slug. *"Man Group"* thành `man`, mất `mangroup`.
2. Đoán slug bắt nhầm board công ty khác: *"London Stock Exchange Group"* → slug
   `london`. Giờ xác minh bằng tên công ty mà board tự khai.

**Kết quả trước đó:** eFinancialCareers cho **66 tin**, việc khớp từ 20 lên **48**.
Vòng đọc kỹ mở từng tin lấy mô tả đầy đủ: 66 tin trong **144 giây**.

Top bảng giờ có cả nguồn mới: *Eka Finance — Junior Quantitative Researcher* **100 điểm**.

**Lỗi thật đã sửa:** cache chặn luôn cả việc **bổ sung**. Vòng quét nhanh ghi tin
không mô tả, vòng đọc kỹ lấy được mô tả nhưng `INSERT OR IGNORE` bỏ qua nên không
ghi vào đâu được. Giờ: đã có mà đang thiếu mô tả thì cập nhật, và không bao giờ
đè mô tả dài bằng mô tả ngắn.

Test: 24/24 (`test_ingest`) + 28/28 (`test_browser`).

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

## Bước 4 — PROJECT   *(xong — bảy chặng)*

**Sửa lại theo đúng ý Vin:** không dùng project cũ. Chúng quá lớn, chi phí đọc cao,
người tuyển không bước vào. Hệ thống phải ĐỀ XUẤT bài nhỏ mới.

```
0 NHẮM         nhóm JD -> cần chứng minh cái gì          projects/cluster.py
1 NGHIÊN CỨU   đọc kỹ toàn bộ JD, lọc câu khuôn mẫu      projects/research.py
2 SINH         LLM đề xuất 4 phương án, không phải 1     core/llm.py
3 KIỂM CỨNG    8 luật, trượt là loại                     projects/brief.py
4 KIỂM DỮ LIỆU tải thật, nhìn BÊN TRONG                  projects/feasible.py
5 XẾP HẠNG     6 chiều                                   projects/rank.py
6 CHỌN         lấy đầu bảng, giữ cái bị loại kèm lý do   projects/pipeline.py
```

**Chặng 4 là chỗ phân biệt đề bài THẬT với đề bài NGHE HỢP LÝ.** `URL trả 200`
là hàng rào yếu. Hàng rào mạnh là tải vài KB đầu rồi nhìn vào: có cột ngày thật
không, có cột giá không, bao nhiêu dòng, có phải bảng tra cứu không.

Bắt được lỗi ngay trong đề bài tôi tự sinh ra: dataset S&P 500 constituents trả
200, qua hết 8 luật cứng — nhưng là **bảng tra cứu 399 dòng không có giá**, không
backtest được gì. Bốn lý do từ chối cụ thể, trong đó có
*"cột 'Date added' là siêu dữ liệu, không phải trục thời gian"*.

**Chặng 5, sáu chiều:** phủ · **bác bỏ được** · cụ thể · dữ liệu sẵn · gọn · mới.

Chiều *bác bỏ được* quan trọng nhất: câu hỏi phải có thể ra kết quả NGƯỢC. Đề bài
chỉ có thể xác nhận thì không phải nghiên cứu, là quảng cáo.

Test: 65/65 (`test_brief`).

|x| Gom JD thành nhóm bằng greedy set cover | `projects/cluster.py` |
|x| Đối chiếu project đã có với từng nhóm, chỉ ra chỗ trống | `projects/cluster.py` |
|x| Dựng trang kết quả 5 phần cho từng JD | `projects/page.py` |
|x| Báo trang còn thiếu gì (số đo, đánh đổi, link code) | `projects/page.py` |

**Vòng lặp khép ở đây.** Những câu `cv/rules.py` CẮT khỏi CV — tự phê bình, kể thất
bại — chính là nguyên liệu cho phần *"What I gave up, and got wrong"*. Không mất gì,
chỉ đổi tầng:

```
CV        -> bỏ chỗ làm sai   -> qua vòng lọc
Trang này -> chỗ làm sai là điểm mạnh nhất -> được gọi phỏng vấn
```

Có test chặn: mọi câu bị CV cắt phải rơi đúng vào phần Đánh đổi.

**Gom nhóm dùng greedy set cover, KHÔNG dùng k-means** — vì nó giải thích được:
*"nhóm này tồn tại vì 10 tin cùng đòi alpha research"*.

**Kết quả trên 24 tin thật:**

```
python + alpha research + statistics    10 tin   ✓ Quant Trading Studio
python + machine learning + statistics   6 tin   ✓ Quant Trading Studio
python + rust                            2 tin   ⚠ chưa project nào trả lời
portfolio + statistics                   2 tin   ✓ Quant Trading Studio
```

**Hai lỗi thật đã sửa:**

1. Greedy set cover lấy kỹ năng phổ biến nhất làm khoá -> `python` có ở 19/24 tin
   nên nuốt gọn tất cả vào một nhóm. Bỏ kỹ năng xuất hiện >60% khỏi danh sách khoá.
2. Từ vựng thiếu hẳn nhóm **validation** (`out-of-sample`, `look-ahead bias`,
   `data leakage`, `overfitting`) và `efficient frontier`, `sharpe`, `drawdown` —
   đúng phần chuyên môn phân biệt người biết việc với người mới học. Thêm rồi thì
   project mới khớp được với nhóm.

Test: 21/21 qua.

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
