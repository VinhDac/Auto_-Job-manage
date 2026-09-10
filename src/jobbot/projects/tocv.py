"""Project làm XONG -> mấy dòng cho CV. Chỗ vá cuối cùng của vòng lặp.

Trước chỗ này, bảng `project` chỉ có hai nơi đọc: tab Projects và
`existing_work`. Vin bỏ 2-3 ngày, bấm Xong, ô chuyển xanh — rồi thôi. Điểm
không đổi, CV không đổi. Kho tích vào một cái hộp kín.

LUẬT GỐC KHÔNG ĐỔI (xem cv/build.py): máy CHỌN và SẮP XẾP, không viết mới.
Ở đây máy có vẻ như đang viết — nhưng nó chỉ CHÉP LẠI thứ chính mã của Vin vừa
in ra: `result.json` do analyse.py ghi, sau khi chạy trên dữ liệu thật. Mọi con
số trong dòng đề xuất đều mở tệp ra là thấy.

Và nó ĐỀ XUẤT, không tự dán vào. Vin đọc, sửa, rồi mới đồng ý — vì thứ lên CV
là thứ Vin phải bảo vệ được trong phòng phỏng vấn, không phải thứ máy tự tin.
"""

from __future__ import annotations

import json
from pathlib import Path

MIN_KEEP = 0.5      # dưới ngần này thì con số là lời cảnh báo, không phải lời khoe


def facts(link: str) -> dict:
    """Đọc result.json trong repo. Chưa chạy `make run` thì chưa có gì để nói."""
    if not link:
        return {}
    found = Path(link) / "result.json"
    if not found.exists():
        return {}
    try:
        return json.loads(found.read_text())
    except (ValueError, OSError):
        return {}


def title(row: dict, data: dict) -> str:
    """Dòng đầu khối, theo đúng định dạng CV Vin đang dùng: `Tên — mô tả`.

    KHÔNG dùng gạch đầu dòng cho phần thân: cv/blocks.py bóc theo định dạng
    của chính CV này, và CV này không có gạch đầu dòng — thêm vào thì dấu `·`
    lọt nguyên vào chữ.
    """
    skill = (row.get("skills") or ["project"])[0]
    if data.get("shape") == "signal":
        return (f"{skill.title()} — a cross-sectional alpha signal on equity "
                f"index data, backtested walk-forward and costed")
    return (f"{skill.title()} — abnormal-change detection on market data, "
            f"attributed back to the series that caused it")


def lines(row: dict, data: dict) -> list[str]:
    """Ba dòng: LÀM GÌ · KỶ LUẬT · CHỖ YẾU.

    KHÔNG dùng dấu gạch dài có khoảng trắng (` — `) trong thân: cv/blocks.py
    coi mọi dòng chứa nó là một TIÊU ĐỀ khối mới, nên một dòng thân có dấu đó
    sẽ tự tách khối project làm đôi. Đã xảy ra ở bản đầu.

    Dòng thứ ba là dòng hay bị bỏ nhất và là dòng quan trọng nhất. Một project
    không có vết xước đọc ra là project chưa từng chạy — cùng lý do cv/rules.py
    giữ lại câu thất bại cho phần write-up.

    Dùng ĐÚNG TỪ thị trường dùng (`out-of-sample`, `equity`, `market data`,
    `walk-forward`) chứ không phải từ đồng nghĩa. Không phải để lách: bộ chấm
    và bộ dựng CV đều khớp theo từ vựng trong scoring/vocab.py, nên viết
    "never used to choose anything" thay vì "out-of-sample" là dòng đó KHÔNG
    mang được kỹ năng nào — đo được: khối đầu tiên mất cả `equities`,
    `market data` lẫn `validation`.
    """
    if not data:
        return []
    span = f"{data.get('from', '?')} to {data.get('to', '?')}"
    parts = data.get("parts", "?")
    total = data.get("days", 0) + data.get("dropped", 0)

    if data.get("shape") == "signal":
        keep = data.get("number", 0)
        verdict = "held up" if keep >= MIN_KEEP else "lost more than half its edge"
        return [
            f"Built an alpha signal ({data.get('signal', 'a cross-sectional rule')}) "
            f"across {parts} equity industry portfolios of daily market data, "
            f"{span}, then asked how much of the backtest survived contact with "
            f"reality: it {verdict}. Sharpe {data.get('in_sample_sharpe')} in "
            f"sample against {data.get('held_out_sharpe')} out-of-sample net of "
            f"{data.get('cost_bps')} bps, {keep:.0%} of the original.",
            f"Walk-forward by construction: the last third of history "
            f"({data.get('held_out_from')} onward) is a strict out-of-sample "
            f"holdout, weights formed on one day earn the next so there is no "
            f"look-ahead, and costs come out of realised turnover "
            f"({data.get('turnover')}x/day). Each of those is held by a test, "
            f"not by discipline; data pull, tests and the matplotlib "
            f"visualisation all run from one make command.",
            f"Dropped {data.get('dropped'):,} of {total:,} rows for missing cells "
            f"rather than filling them, {data.get('dropped', 0) / max(total, 1):.0%} "
            f"of the history, and the reason the early sample is thin. Filling "
            f"them would have invented the very moves the study is measuring.",
        ]

    return [
        f"Measured the rate of change across {parts} series of daily market data, "
        f"{span}, and asked what drove the largest abnormal move: "
        f"{data.get('headline', '')}. {data.get('events')} days crossed the "
        f"threshold; the biggest was {data.get('biggest')}, carried by "
        f"{data.get('driver')}.",
        f"Detection is {data.get('detector', 'a rolling threshold')}, fitted "
        f"out-of-sample: only on data before each day it scores, with no "
        f"look-ahead. A test plants a huge shock at the end of the series to "
        f"prove earlier events are not masked by it; data pull, tests and the "
        f"matplotlib visualisation all run from one make command.",
        f"Attribution holds one series still at a time, so contributions do not "
        f"sum to the total and the figure reported is a share, not a sum. "
        f"{data.get('dropped'):,} rows with any missing cell were dropped rather "
        f"than filled.",
    ]


def block(row: dict, data: dict, repo_url: str = "") -> str:
    """Khối đúng định dạng cv/blocks.py bóc được: một dòng tiêu đề, rồi thân
    KHÔNG gạch đầu dòng — giống hệt các khối project Vin tự viết.

    Link repo nằm ở DÒNG TIÊU ĐỀ, không phải một câu trong thân. Câu trong
    thân bị cv/build.py tách nhỏ và xếp lại theo độ liên quan, nên "Code:
    https://…" trồi lên thành một gạch đầu dòng chen giữa hai câu số liệu.
    """
    if not data:
        return ""
    head = title(row, data)
    if repo_url:
        head += f" ({repo_url})"
    return head + "\n" + "\n".join(lines(row, data)) + "\n"
