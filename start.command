#!/bin/bash
# Bấm đúp để mở jobbot.  (macOS)
# Đang chạy   -> chỉ mở dashboard
# Chưa chạy   -> khởi động ngầm (icon ◆ trên thanh menu) rồi mở dashboard

cd "$(dirname "$0")" || exit 1
PORT=8765
URL="http://127.0.0.1:$PORT/"

if curl -sf -o /dev/null --max-time 1 "$URL"; then
  open "$URL"; exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "jobbot" message "Không tìm thấy python3.

Cài bằng: xcode-select --install"'
  exit 1
fi

# Chạy tách hẳn khỏi Terminal — không để lại cửa sổ lơ lửng.
nohup python3 run.py > data/app.log 2>&1 &

for _ in $(seq 1 20); do
  curl -sf -o /dev/null --max-time 1 "$URL" && break
  sleep 0.4
done

if curl -sf -o /dev/null --max-time 1 "$URL"; then
  open "$URL"
else
  osascript -e 'display alert "jobbot" message "Khởi động không thành công. Xem data/app.log"'
fi
