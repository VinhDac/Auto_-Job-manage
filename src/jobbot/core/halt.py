"""Cờ DỪNG — một chỗ, một cờ cho mỗi khúc.

Vì sao cần: `stop()` của lịch trình chỉ chặn lần chạy SAU. Một vòng quét đang
chạy mất 8–16 phút vì phải mở Chrome đọc từng tin; bấm Dừng mà nó vẫn chạy tiếp
là một nút nói dối — đúng loại nút đã phải giết ba lần trong dự án này.

Vì sao theo TỪNG KHÚC chứ không một cờ chung: dừng vòng quét không được dừng
luôn việc quét thư đang chạy song song. Mỗi chức năng có nút dừng riêng thì
phải có cờ riêng.

Việc đang chạy tự kiểm `wanted(khúc)` ở những chỗ ngắt được — giữa hai nguồn,
giữa hai trang — rồi dừng sạch và nói ra là đã dừng. KHÔNG giết luồng giữa
chừng: nửa giao dịch ghi vào DB còn tệ hơn chạy nốt.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_flags: dict[str, threading.Event] = {}


def _flag(stage: str) -> threading.Event:
    with _lock:
        return _flags.setdefault(stage, threading.Event())


def ask(stage: str) -> None:
    """Xin khúc này dừng ở điểm ngắt gần nhất."""
    _flag(stage).set()


def clear(stage: str) -> None:
    """Bắt đầu một lượt mới — xoá cờ cũ, nếu không lượt này dừng ngay."""
    _flag(stage).clear()


def wanted(stage: str) -> bool:
    return _flag(stage).is_set()
