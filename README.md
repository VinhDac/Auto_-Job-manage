# Auto Job Manage

Hệ thống tìm việc chạy liên tục — **máy đề xuất, người quyết định.**

Trạng thái: **warmup — mới dựng khung, chưa có logic.**

---

## Đọc theo thứ tự

| | File | Nội dung |
|---|---|---|
| 1 | [docs/strategy.md](docs/strategy.md) | *Vì sao.* Bản chất bài toán xin việc. Đọc trước tiên. |
| 2 | [docs/design.md](docs/design.md) | *Làm thế nào.* Vòng lặp đề xuất, trục an toàn, cache, stack. |
| 3 | [docs/roadmap.md](docs/roadmap.md) | *Theo thứ tự nào.* 11 module, mỗi cái có tiêu chí "Xong khi". |

## Ý tưởng trong một khung

```
module  ->  đề xuất  ->  hàng đợi  ->  bạn bấm Yes/No  ->  thực thi  ->  ghi kết quả
```

Mọi module đều đẻ ra cùng một kiểu object. Vì vậy dashboard chỉ vẽ một thứ,
cổng duyệt chỉ viết một lần, và thêm module mới thì lõi không phải sửa.

**Hai luật không được phá:**

1. Module chỉ **đề xuất**. Lõi mới **thực thi**.
2. Mọi hành động **không đảo ngược được** đều phải qua một lần bấm của người.

## Bản đồ thư mục

```
docs/                 Tài liệu. Quyết định nằm ở đây, không nằm trong đầu.
config/               config.example.toml -> copy thành config.toml (đã gitignore)
src/jobbot/
  core/         M0,M5  Kiểu dữ liệu, store, cache, hàng đợi, cổng Yes/No, thực thi
  ingest/       M1     Kéo tin về. Một file một nguồn.
  dedup/        M2     Gộp tin trùng
  dashboard/    M3     Xem live, bấm Yes/No
  scoring/      M4     Chấm điểm CV <-> JD
  cv/           M6     Dựng CV theo JD  [Yes/No]
  mail/         M7     Gửi hồ sơ, đọc phản hồi  [Yes/No khi gửi]
  notify/       M8     Báo ra ngoài
  stats/        M9     Đếm, đo, tỉ lệ phản hồi
  outreach/     M10    Profile, bài đăng, kết nối  [Yes/No — rủi ro cao nhất]
tests/                Test theo module
scripts/              Lệnh chạy tay, việc một lần
data/                 DB + cache. KHÔNG commit.
```

Mỗi thư mục con trong `src/jobbot/` có `__init__.py` ghi rõ **cái gì thuộc về nó và cái gì không**.
Đọc dòng đó trước khi thêm file. Không biết file mới nên nằm đâu → nghĩa là chưa rõ nó làm gì.

## Luật giữ sạch

- Một nguồn dữ liệu = một file trong `ingest/`. Không nhồi hai nguồn vào một file.
- Không có logic nghiệp vụ trong `dashboard/`. Nó chỉ vẽ.
- `core/` không được biết Greenhouse hay LinkedIn là gì.
- Thử nghiệm, việc chạy một lần → `scripts/`. Không để rơi ở thư mục gốc.
- Quyết định gì thì ghi vào `docs/`, không để trong chat.
- Xong một module thì tick vào `roadmap.md` — nhưng chỉ khi đạt đúng "Xong khi".

## Việc tiếp theo

Lát 1 — xương sống: **M0 → M1 → M2 → M3**

Kéo tin thật từ ≥3 nguồn → cache vào SQLite → dedup → dashboard hiện số live.
Chưa chấm điểm, chưa CV, chưa gửi gì. Mục tiêu là chứng minh xương sống chạy được.

## Còn thiếu để đi tiếp

Xem cuối [docs/strategy.md](docs/strategy.md): cần **băng tần thật** và **2–3 JD thật**
để ngược từ JD ra project, thay vì xây trước rồi tìm chỗ nhét vào.
