#!/bin/bash
# Bấm đúp để chạy Auto Job Manage.  (macOS)
# File này tự tìm thư mục dự án, nên di chuyển cả thư mục đi đâu vẫn chạy.

cd "$(dirname "$0")" || exit 1
printf '\033]0;Auto Job Manage\007'          # đặt tên cửa sổ Terminal

PORT=8765

# Đang chạy sẵn thì chỉ mở trình duyệt, không dựng thêm một server nữa.
if curl -sf -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/"; then
  echo "  Already running — opening browser."
  open "http://127.0.0.1:$PORT/"
  sleep 1
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "  python3 not found."
  echo "  Install with:  xcode-select --install"
  echo
  read -n 1 -s -r -p "  Press any key to close..."
  exit 1
fi

echo "  Starting…  (Ctrl+C to stop; closing this window also stops it)"
echo
python3 run.py
status=$?

if [ $status -ne 0 ]; then
  echo
  echo "  Exited with error (code $status). See the message above."
  read -n 1 -s -r -p "  Press any key to close..."
fi
