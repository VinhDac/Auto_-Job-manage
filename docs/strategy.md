# Chiến lược — bản chất bài toán xin việc

> Tài liệu này là *lý do* tồn tại của hệ thống. Đọc file này trước khi đọc `design.md`.
> Mọi quyết định kỹ thuật phải truy ngược được về một mục ở đây. Không truy ngược được thì không làm.

---

## 1. Tiền đề

Công ty tuyển người **làm được việc ngay**. Họ không nuôi người có tiềm năng.

Hệ quả trực tiếp: hồ sơ phải khớp JD. Không phải khớp "đại khái" — khớp theo đúng ngôn ngữ họ viết trong JD.

## 2. Sai lầm đã nhận ra

Apply vượt tầm, mong người ta nhận ra tài năng.

Cái này hỏng vì nó bị loại ở vòng lọc, **trước khi** có ai đọc đến phần đáng đọc. Bị loại không phải vì kém — mà vì bộ lọc đang làm đúng việc của nó.

Nhưng phản xạ ngược lại cũng sai: hạ tầm xuống thì bị loại vì overqualified, hoặc vào được rồi mắc kẹt.

**Đích đúng:** apply đúng băng tần của mình, nhưng là hồ sơ có bằng chứng mạnh nhất trong băng tần đó.

## 3. Hai cơ chế, đừng gộp làm một

Một hồ sơ đi qua ba cửa:

| Cửa | Ai đọc | Tiêu chí thật |
|-----|--------|---------------|
| 1. ATS / lọc từ khóa | Máy | Trùng chữ |
| 2. Recruiter quét vài giây | Người, không đọc kỹ | *Nhận dạng*: người này có đúng làm nghề này không |
| 3. Hiring manager đọc thật | Người, đọc kỹ | Bằng chứng làm được việc |

> **Matching là bộ lọc. Bằng chứng là thứ tạo khác biệt.**

Matching đưa bạn từ 200 người xuống nhóm 40. Từ 40 xuống 5 người được gọi thì matching vô dụng — cả 40 đều khớp. Thứ quyết định là **personal project**.

Hệ thống phải phục vụ **cả hai**, và không nhầm lẫn giữa chúng.

## 4. Vì sao link GitHub vô giá trị

- **Không ai bấm.** Người đọc CV không clone repo. Không bao giờ.
- **Chi phí đánh giá quá cao.** Đọc code người lạ để phán xét mất 20–30 phút. Không ai trả giá đó cho ứng viên chưa quyết định thích.
- **Không phân biệt.** Ai cũng có GitHub, ai cũng có scraper / todo app / chatbot. Thứ ai cũng có thì không mang thông tin.
- **Là lời tuyên bố, không phải bằng chứng.** "Đây là code tôi viết" — rồi sao? Có chạy không? Giải quyết được gì?

| | |
|---|---|
| **Project** | "Tôi đã xây X" — một hiện vật |
| **Bằng chứng** | "Gặp vấn đề P, làm X, số đo từ A xuống B, đo bằng cách này, chỗ này tôi làm sai" |

Phần **"chỗ này tôi làm sai"** là phần ai cũng bỏ, và là phần người có kinh nghiệm tin nhất. Công việc thật luôn có đánh đổi. Một project toàn thắng, không vết xước — đọc là biết chưa chạy thật.

## 5. Hình dạng của bằng chứng

Không phải repo. Là **một trang kết quả**, đọc hết trong 90 giây:

```
Vấn đề       — một câu, bằng đúng ngôn ngữ trong JD
Cách làm     — 3-5 dòng, cơ chế thật, không buzzword
Số đo        — trước -> sau, kèm CÁCH ĐO (thiếu cách đo thì số vô nghĩa)
Đánh đổi     — cái đã hy sinh, và vì sao
Link code    — cuối trang, cho 5% muốn xem
```

Vừa một màn hình. Không tô hồng. Người có kinh nghiệm đọc xong biết ngay có làm thật hay không.

## 6. Phương án tổng quát cho personal project

Bài toán khó:
- Không thể làm project riêng cho từng JD — không scale, kể cả chạy 24/7.
- Không thể một project generic rải cho tất cả — quay lại vấn đề link GitHub.

Lời giải:

> **Một hệ thống thật + nhiều lát cắt theo JD.**

Xây **một** thứ duy nhất, thật, đang chạy. Chọn thứ chạm nhiều chiều, để cắt ra nhiều lát mà **lát nào cũng thật** — không bịa câu nào.

| JD thuộc mảng | Cắt lát nào |
|---|---|
| Data engineering | ingest đa nguồn, dedup / entity resolution |
| Backend | API, state machine vòng đời, scheduling |
| Reliability | xử lý hỏng, retry, nguồn chết |
| ML / IR | engine chấm điểm CV↔JD, phân tích false positive |
| Analytics | đo tỉ lệ phản hồi theo nguồn và theo điểm |

Ba trang khác nhau, ba ngôn ngữ khác nhau, không câu nào nói dối.

## 7. Chính hệ thống này là project đó

Nhìn lại về mặt kỹ thuật, nó có: ingest đa nguồn dị thể · dedup / entity resolution · engine chấm điểm · scheduling & rate limit · state machine · xử lý hỏng · đo lường thật.

Và nó có thứ gần như không portfolio nào có: **kết quả thật, số thật, hệ quả thật.**

> "1.240 tin trong 8 tuần → dedup còn 890 tin duy nhất → apply 60 tin match >75% → 9 phản hồi → 3 phỏng vấn. Ngưỡng 75% là kết quả sau khi thử 60% và 85%."

Vòng lặp tự chứng minh: **thứ giúp có việc chính là lý lẽ để tuyển.**

## 8. Bẫy trình bày — nghiêm trọng

- ❌ "Bot tự động apply việc hàng loạt" → hiring manager đọc ra: *người này rải spam*. Lùi lại ngay.
- ✅ "Hệ thống dedup và chấm điểm tin tuyển dụng đa nguồn — và vì sao 80% match điểm cao lại là false positive"

Kể **bài toán kỹ thuật khó**, không kể phần automation.

Hệ quả kèm theo: **volume kèm match cao thì tốt; volume không match là spam**, và nó phá chính mình. Hệ thống phải chặn điều này bằng thiết kế, không bằng kỷ luật cá nhân.

---

## Câu hỏi còn mở

- [ ] **Băng tần thật:** mảng gì, bao nhiêu năm làm thật?
- [ ] **2–3 JD thật** thấy "cái này tôi làm được thật" (không phải "cố thì được") — để ngược từ JD ra project, thay vì xây trước rồi tìm chỗ nhét vào.
