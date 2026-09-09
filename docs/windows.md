# Chạy trên Windows

## Cần gì

| | |
|---|---|
| **Python 3.11+** | bắt buộc — app dùng `tomllib`, chỉ có từ 3.11. Tải ở python.org, **nhớ tick "Add python.exe to PATH"** lúc cài. |
| **Google Chrome** | bắt buộc — vừa là vỏ cửa sổ, vừa là thứ đi đọc LinkedIn. Edge/Brave cũng chạy được (đều là Chromium). |

Không cài gói Python nào. Không venv. Không `pip install`.

## Chạy

Bấm đúp **`run.bat`** — mở cửa sổ app riêng, không thanh địa chỉ.

Muốn thấy log và dừng bằng Ctrl+C thì bấm **`run-console.bat`**.

Hoặc trong terminal:

```
py -3 run.py             cửa sổ app
py -3 run.py --window    chạy trong terminal, mở trình duyệt
py -3 run.py --scan      quét một lần rồi thoát
```

## Chuyển từ máy Mac sang

Chép **cả thư mục dự án**, trừ hai chỗ:

```
data/jobbot.db        ← PHẢI chép. 61 MB. Toàn bộ tin, điểm, hồ sơ, nhật ký.
data/chrome-profile/  ← ĐỪNG chép. 311 MB, tự sinh lại. Chép sang còn dễ hỏng.
data/chrome-ui/       ← ĐỪNG chép. Tự sinh lại.
```

`data/` nằm trong `.gitignore` nên `git clone` sẽ **không** mang DB theo — phải
chép tay `data/jobbot.db`.

Không có gì phụ thuộc đường dẫn tuyệt đối: mọi chỗ dùng `pathlib`, và thư mục
dữ liệu tính từ vị trí repo. Đặt thư mục ở đâu cũng chạy.

Đổi chỗ chứa dữ liệu (ví dụ để lên ổ khác):

```
set JOBBOT_DATA_DIR=D:\jobbot-data
py -3 run.py
```

## Khác gì bản macOS

| | macOS | Windows |
|---|---|---|
| Cửa sổ app | `NSWindow` + `WKWebView`, có icon Dock, icon thanh menu | cửa sổ **Chrome `--app`** — không tab, không thanh địa chỉ, có icon riêng trên taskbar |
| Thông báo | `osascript` | PowerShell toast (WinRT) — **chưa thử trên máy Windows thật** |
| Đọc CV dạng PDF | PDFKit của hệ — đọc được cả font nhúng | bóc bằng thư viện chuẩn — **chỉ đọc được PDF chữ thường** |
| Tự chạy khi bật máy | `scripts/install_agent.py` (launchd) | **chưa làm** |

### PDF: chỗ yếu thật

Bộ bóc PDF bằng thư viện chuẩn không đọc nổi PDF dùng **font nhúng có bảng mã
riêng** — LaTeX, Canva, InDesign hay xuất kiểu này. Gặp loại đó, app **báo lỗi
và bảo bạn dán chữ**, chứ không nhét ký tự rác vào hồ sơ.

Đường vòng: mở PDF, `Ctrl+A`, `Ctrl+C`, dán vào ô "paste" ở trang Import CV.
Kết quả y hệt.

## Vỏ Chrome `--app` — nó là gì

Chrome mở ở chế độ `--app=<url>`: một cửa sổ đứng riêng, **không tab, không
thanh địa chỉ**, có mục riêng trên taskbar và Alt+Tab. Không phải cửa sổ native
thật, nhưng là thứ gần nhất mà không phải cài gói nào — mà nguyên tắc của app
này là không cài gì.

Cửa sổ giao diện dùng **profile Chrome riêng** (`data/chrome-ui`), tách khỏi
profile đi cào (`data/chrome-profile`). Chung profile thì đóng cửa sổ đang xem
là giết luôn tab máy đang lái.

## Hỏng thì xem đâu

```
py -3 run.py --window
```

Log hiện thẳng ra terminal. Dòng `vỏ ->` cho biết đang chạy vỏ nào.

Trong app, mọi việc chạy nền đều ghi vào **Nhật ký** (tab Search / Score /
Projects, và Home gộp tất cả). Nguồn hỏng hiện thành cảnh báo ngay trong tab
của nó.

Chrome không tìm thấy → lỗi ghi rõ đã dò bao nhiêu chỗ. Cài Chrome vào chỗ mặc
định, hoặc thêm `chrome.exe` vào `PATH`.

## Chưa làm

- **Tự chạy khi bật máy.** Trên macOS có `scripts/install_agent.py` (launchd).
  Trên Windows sẽ là Task Scheduler hoặc shortcut trong thư mục Startup —
  chưa viết.
- **Đóng gói thành `.exe`.** `scripts/make_app.py` chỉ dựng `.app` cho macOS.
- **Thông báo Windows chưa chạy thử trên máy thật.** Viết theo tài liệu WinRT.
  Hỏng thì `send()` trả `False` và scheduler ghi `notify_failed` vào nhật ký —
  không im lặng, nhưng cũng chưa chắc đúng.
