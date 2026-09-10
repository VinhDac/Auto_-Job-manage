# Đường nộp của tin LinkedIn — chưa có, và vì sao

Đo ngày 10/09/2026.

## Sự thật

LinkedIn chỉ là **bảng tin**. Nộp vẫn ở website công ty. Nhưng đường dẫn tới
website đó **chỉ hiện ra khi đã đăng nhập**:

    trang khách (guest)   ->  "Sign in to apply", KHÔNG có href nào
    body ta đang lưu      ->  chỉ mô tả công việc
    7/111 tin có link ra ngoài, và đều là link trong phần mô tả, không phải nút Apply

Nên `posting.url` của 111 tin LinkedIn trỏ vào **trang xem tin**, không phải
trang nộp. Bấm Nộp trên chúng thì mở đúng trang đó — đọc được, nộp thì không.

## Bao nhiêu phần cứu được

    111 tin LinkedIn
     24 (22%)  môi giới — không có ATS riêng, nộp qua người tuyển dụng
     14        đã trùng với một tin từ nguồn khác, dedup gộp rồi -> có URL nộp thật
     11        công ty đã có board API ta biết -> tra ra được
    ~62        còn lại: biết tên công ty, chưa biết trang nộp

## Ba đường, chưa chọn

1. **Tra theo công ty.** `ingest/web/careers.py` đã có `resolve_ats()` — cho tên
   công ty, đoán ra board. Rẻ nhất, và nó phục vụ cả vòng quét chứ không riêng
   phần nộp. Không chắc trúng, nhưng sai thì chỉ là mở nhầm trang.

2. **Đăng nhập LinkedIn để đọc nút Apply.** Lấy được đúng URL, nhưng cào bằng
   tài khoản thật là cách bị khoá tài khoản. Mất tài khoản giữa lúc tìm việc
   là mất nhiều hơn thứ tiết kiệm được. KHÔNG làm nếu Vin không nói rõ chấp
   nhận rủi ro đó.

3. **Để nguyên.** Bấm Nộp mở trang LinkedIn, Vin tự bấm Apply ở đó. Vẫn ghi
   được một dòng vào bảng Quản lí — mất phần điền form, không mất phần theo dõi.

Hiện đang là (3).
