# Thiết kế hệ thống

> Đọc `strategy.md` trước. File này chỉ nói *làm thế nào*, không nói *vì sao*.

---

## 1. Nguyên tắc trung tâm — một vòng lặp duy nhất

Mọi module đều làm cùng một hình dạng việc:

```
module  ->  đề xuất  ->  hàng đợi  ->  người bấm Yes/No  ->  thực thi  ->  ghi kết quả
```

Module tìm việc đẻ ra đề xuất. Module CV đẻ ra đề xuất. Module gửi mail đẻ ra đề xuất.
**Tất cả cùng một kiểu object: `Proposal`.**

Hệ quả:

- Dashboard chỉ cần biết vẽ **một** thứ.
- Cổng Yes/No chỉ viết **một** lần.
- Thống kê chỉ đếm **một** kiểu.
- **Thêm module mới thì phần lõi không phải sửa gì.**

Đây là lý do kiến trúc này sạch. Nó rút về một vòng lặp.

> **Luật:** module không được tự ý gây tác động ra ngoài. Module chỉ được *đề xuất*.
> Thực thi là việc của lõi, sau khi có Yes.

## 2. Trục an toàn — auto vs. Yes/No

Không phải module nào cũng bình đẳng. Ranh giới đi theo **tính đảo ngược được**:

| Loại | Module | Vì sao |
|---|---|---|
| **Chạy tự do 24/7** | store, ingest, dedup, scoring, stats, dashboard | Chỉ đọc và tính. Sai thì xóa, chạy lại. |
| **Bắt buộc Yes/No** | cv (xuất bản), mail (gửi), outreach (đăng bài, kết nối) | Gửi ra ngoài. Không rút lại được. |

Đây không phải tính năng phụ — **nó là trục an toàn của cả hệ thống.**
Mọi hành động không đảo ngược được đều phải đi qua một lần bấm của người.

## 3. Nhịp chạy — 24/7 đặt ở đâu

Chạy chậm nhưng liên tục thì vẫn xong việc. Nhưng đặt sai chỗ thì hỏng:

- **24/7 thoải mái:** API job board public, đọc mail, chấm điểm, thống kê, sinh nội dung.
- **Không 24/7:** site không có API công khai (LinkedIn là ví dụ). Không người thật nào online 3 giờ sáng mỗi đêm, 7 ngày một tuần — *chính nhịp đó là dấu hiệu bị phát hiện*, chậm hay nhanh không cứu được.

Cách xử lý: chạy trong vài cửa sổ ngắn giống người, có nghỉ, có ngày trống. Phần nặng vốn không nằm ở đó.

### Nguồn dữ liệu — thị trường UK + global

Người dùng ở **UK**, nhắm **UK + global**. Đã kiểm chứng thật:

| Nguồn | Cần key | Ghi chú |
|---|---|---|
| `arbeitnow.com` | Không | **59/175 tin trang đầu là UK.** Phủ EU tốt. Dùng ngay được. |
| `boards-api.greenhouse.io` | Không | Theo từng công ty. Đã thử: `monzo`, `wise` OK. |
| `api.lever.co` | Không | Theo từng công ty. |
| `api.ashbyhq.com` | Không | Theo từng công ty. |
| `remotive.com` | Không | Remote toàn cầu. |
| `api.adzuna.com/.../gb/` | **Có** (miễn phí) | Nhà UK, phủ thị trường UK rộng nhất. Cần `app_id` + `app_key`. |
| `reed.co.uk/api` | **Có** (miễn phí) | Board lớn ở UK. Trả 401 nếu thiếu key. |
| `jobs.service.gov.uk` | — | Board của chính phủ UK (findAJob đã chuyển sang đây). |

Nguồn không có API công khai (LinkedIn, Otta, Indeed): qua extension Chrome, chạy
trong cửa sổ giống người — không 24/7.

## 4. Kiến trúc dữ liệu

```
raw_posting   nguyên văn + body gốc     KHÔNG BAO GIỜ sửa
      ↓  derive()  — một giao dịch, chỉ tính lại cái đã cũ
posting       chuẩn hoá + phán quyết    tính lại được hoàn toàn từ raw
```

Ba tính chất bắt buộc:

**Tính lại được.** `scripts/rebuild.py` dựng lại toàn bộ tầng suy diễn từ raw.
Không có nó thì một lỗi trong `strip_html` là hỏng vĩnh viễn — mà nó đã sai
hai lần, và tin LinkedIn hết hạn thì không fetch lại được.

**Gắn phiên bản.** Mỗi phán quyết ghi rõ sinh ra từ hồ sơ phiên bản nào
(`judged_profile`) và luật phiên bản nào (`judged_rules`, `scored_rules`).
Đổi hồ sơ hay sửa `core/versions.py` -> tin cũ tự thành "cần tính lại".

**Một giao dịch.** Lọc + gộp + chấm nằm trong một `derive()`. Web đọc giữa
chừng thấy trạng thái CŨ trọn vẹn, không thấy trạng thái dở dang.

**Một định nghĩa.** `core/postings.FIELD_MAP` là nơi duy nhất nối kiểu `Posting`
với cột trong bảng. Có test gãy nếu hai bên lệch nhau.

**Nguồn hỏng phải trông khác nguồn tốt.** Mỗi lần đọc trả về `Health(attempted,
failed)`; hỏng quá 30% thì đánh dấu nguồn hỏng kể cả khi vẫn lấy được ít tin.

## 5. Dữ liệu & cache

Bốn tầng, tách bạch, **không trộn**:

| Tầng | Chứa gì | Xóa được không |
|---|---|---|
| `raw` | Nguyên văn đã fetch + nguồn + thời điểm | Được — fetch lại |
| `derived` | Kết quả dedup, điểm số, phân tích | Được — tính lại từ `raw` |
| `state` | Vòng đời ứng tuyển, quyết định Yes/No | **Không.** Đây là dữ liệu thật. |
| `audit` | Đã làm gì, lúc nào, kết quả ra sao | **Không.** Đây là nguồn của mọi thống kê. |

Vì sao cache là bắt buộc, không phải tối ưu:

1. Không fetch lại cùng một tin — nguồn có rate limit.
2. Không chấm điểm lại cùng một JD — tốn tiền và thời gian.
3. Dedup cần lịch sử để so.
4. Tiến trình 24/7 **phải khởi động lại được mà không mất gì**.

## 6. Ngôn ngữ

| Chỗ nào | Ngôn ngữ | Vì sao |
|---|---|---|
| Giao diện app (câu hỏi, nhãn, nút) | **Tiếng Anh** | Thị trường UK/global; CV và JD đều tiếng Anh |
| Chú thích và docstring trong code | Tiếng Việt | Phần giải thích thiết kế, không phải giao diện |
| Tài liệu trong `docs/` | Tiếng Việt | Bàn thiết kế |

> Cần cân nhắc lại nếu repo này thành portfolio: người đọc ở UK sẽ không đọc được
> chú thích tiếng Việt. Chưa quyết — xem §7.

## 7. Hình dạng app

**App macOS thật, không phải tab trình duyệt.** Cùng cách Discord/Slack/VS Code làm:
nội dung là HTML, nhưng nằm trong `NSWindow` + `WKWebView` native.

Một tiến trình, ba phần:

| Luồng | Việc | Ghi chú |
|---|---|---|
| chính | Cocoa event loop + cửa sổ | Bắt buộc phải là luồng chính |
| nền | Web server | Nội dung cho cửa sổ, ở localhost:8765 |
| nền | Scheduler | Tự quét mỗi 60 phút |

`setActivationPolicy(Regular)` -> có icon Dock, cmd-tab được.
Xác nhận: `lsappinfo` báo `ApplicationType="Foreground"`, và `CGWindowListCopyWindowInfo`
thấy cửa sổ `'jobbot' 1180x806 layer=0` cùng status item `'Item-0' layer=25`.

Hành vi kiểu Discord: `windowShouldClose:` trả về `False` và `orderOut:` — đóng cửa sổ
thì ẩn, app chạy tiếp. `applicationShouldTerminateAfterLastWindowClosed:` cũng `False`.
Bấm icon Dock -> `applicationShouldHandleReopen:` hiện lại cửa sổ.

WebKit không có bindings dựng sẵn trong PyObjC của Anaconda, nên nạp động bằng
`objc.loadBundle` -> vẫn không phải cài gì thêm.

launchd giữ cho nó sống: `KeepAlive={SuccessfulExit: false}` — crash thì bật lại,
nhưng bấm Quit thì dừng hẳn. Dùng `KeepAlive=true` là mỗi lần Quit nó lại tự bật.

## 8. Giao diện

Bố cục **app desktop**, không phải trang web:

- **Sidebar trái cố định** (216px), chạy lên tận đỉnh cửa sổ. Chân sidebar hiện
  trạng thái engine — luôn nhìn thấy, không phải mở trang nào.
- Thanh tiêu đề trong suốt + ẩn chữ (`FullSizeContentView`), chỉ còn ba nút
  traffic light nổi trên nền. CSS chừa sẵn `--top: 38px`.
- **Home = tình hình**, không phải bảng số. Thứ tự: *cần bạn làm gì* -> *máy đang
  làm gì* -> *con số* -> *đã làm gì*. Người mở app không hỏi "có bao nhiêu tin",
  họ hỏi "có gì cần tôi không".

Bảng màu — dark theme dứt khoát, **chỉ một tông**, không theo theme hệ thống:

| Biến | Mã | Vai trò |
|---|---|---|
| `--bg` | `#191B1C` | Nền ghi đậm. Không dùng đen tuyệt đối — tương phản quá gắt, mỏi mắt khi nhìn lâu |
| `--panel` | `#212426` | Thẻ |
| `--ink` | `#DDE1DF` | Chữ chính. Không trắng tinh |
| `--acc` | `#55C98D` | Xanh lá dịu — không neon, cũng không xám nhờ |

Toàn bộ CSS chạy bằng biến, nên đổi tông là sửa đúng khối `:root`.
Nền cửa sổ native đặt khớp `--bg` để không nháy trắng lúc mở.

## 9. Stack

| Chọn | Vì sao |
|---|---|
| Python | Việc chính là parse, chấm điểm, gọi API |
| SQLite | Một file. Không cần server. Restart không mất. Một người dùng thì thừa sức. |
| Web dashboard nhỏ | Xem live, bấm Yes/No |

**Không dùng:** Docker, Postgres, message queue, microservice.
Thêm vào chỉ tốn công bảo trì, không giải quyết gì ở quy mô một người.

## 10. Quyết định đã chốt

- [x] Một vòng lặp `Proposal` duy nhất cho mọi module
- [x] Mọi hành động không đảo ngược được đều qua cổng Yes/No
- [x] Python + SQLite + dashboard nhỏ
- [x] Không lấy LinkedIn làm trung tâm — nó chỉ là một nguồn trong nhiều nguồn
- [x] Làm đến đâu test được đến đấy (xem `roadmap.md`)

## 11. Đã bỏ (có lý do)

**Đối chiếu sponsor register gov.uk** — Vin đang có Graduate visa nên không cần lọc
theo công ty được phép bảo lãnh. Bỏ khỏi bước 1.

Dữ liệu vẫn có sẵn nếu cần bật lại: `gov.uk/government/publications/register-of-licensed-sponsors-workers`,
CSV 143.082 tổ chức, cập nhật hàng ngày. Đáng bật lại khi Graduate visa còn ~9 tháng —
lúc đó công ty không bảo lãnh được là công ty không giữ được Vin.

## 12. Chưa quyết

- [ ] Engine chấm điểm: keyword/BM25 thuần, embedding, hay LLM — quyết sau khi có dữ liệu thật ở M5
- [ ] Framework dashboard cụ thể
- [ ] Gửi mail qua đâu
- [ ] Có dịch chú thích code sang tiếng Anh không (cần nếu repo thành portfolio — xem §5)
