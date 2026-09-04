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

## 4. Dữ liệu & cache

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

## 5. Ngôn ngữ

| Chỗ nào | Ngôn ngữ | Vì sao |
|---|---|---|
| Giao diện app (câu hỏi, nhãn, nút) | **Tiếng Anh** | Thị trường UK/global; CV và JD đều tiếng Anh |
| Chú thích và docstring trong code | Tiếng Việt | Phần giải thích thiết kế, không phải giao diện |
| Tài liệu trong `docs/` | Tiếng Việt | Bàn thiết kế |

> Cần cân nhắc lại nếu repo này thành portfolio: người đọc ở UK sẽ không đọc được
> chú thích tiếng Việt. Chưa quyết — xem §7.

## 6. Stack

| Chọn | Vì sao |
|---|---|
| Python | Việc chính là parse, chấm điểm, gọi API |
| SQLite | Một file. Không cần server. Restart không mất. Một người dùng thì thừa sức. |
| Web dashboard nhỏ | Xem live, bấm Yes/No |

**Không dùng:** Docker, Postgres, message queue, microservice.
Thêm vào chỉ tốn công bảo trì, không giải quyết gì ở quy mô một người.

## 7. Quyết định đã chốt

- [x] Một vòng lặp `Proposal` duy nhất cho mọi module
- [x] Mọi hành động không đảo ngược được đều qua cổng Yes/No
- [x] Python + SQLite + dashboard nhỏ
- [x] Không lấy LinkedIn làm trung tâm — nó chỉ là một nguồn trong nhiều nguồn
- [x] Làm đến đâu test được đến đấy (xem `roadmap.md`)

## 8. Chưa quyết

- [ ] Engine chấm điểm: keyword/BM25 thuần, embedding, hay LLM — quyết sau khi có dữ liệu thật ở M5
- [ ] Framework dashboard cụ thể
- [ ] Gửi mail qua đâu
- [ ] Có dịch chú thích code sang tiếng Anh không (cần nếu repo thành portfolio — xem §5)
