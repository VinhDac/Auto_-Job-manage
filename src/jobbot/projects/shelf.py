"""Kệ dữ liệu — nguồn ĐÃ TẢI THẬT và mở ra đọc được.

Khuôn dựng project cần đúng hai thứ ở một bộ dữ liệu:

    trục thời gian   để thấy có gì vừa đổi
    nhiều thành phần để truy cú đổi đó về đâu

Trùng khít với hai thứ feasible.inspect() đang đo: has_date và numeric_cols.
Không phải trùng hợp — đó là cùng một điều kiện, nhìn từ hai phía.

Mỗi dòng ở đây đã chạy qua feasible.inspect() thật, ngày 10/09/2026. Không
thêm nguồn nào vào kệ mà chưa chạy — một URL chết trong kệ là một project chết.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="


@dataclass
class Source:
    key: str
    name: str
    url: str
    unit: str                 # một THÀNH PHẦN gọi là gì (để viết đề bài)
    units: str                # ... và số nhiều của nó. Ghi thẳng ra, không
                              # đặt luật thêm "s": ra "5 maturitys".
    watch: str                # thứ đem ra theo dõi
    parts: int                # bao nhiêu thành phần truy về được
    since: str                # dữ liệu bắt đầu từ đâu
    skills: list[str] = field(default_factory=list)   # ô nào trên lưới nó phục vụ
    note: str = ""


SHELF: list[Source] = [
    Source("ff49", "Ken French 49 Industry Portfolios, daily returns",
           FF + "49_Industry_Portfolios_daily_CSV.zip",
           unit="industry", units="industries", watch="cross-sectional dispersion of daily returns",
           parts=49, since="1926",
           skills=["equities", "alpha research", "backtesting", "portfolio",
                   "machine learning", "visualisation", "probability",
                   "market data", "data pipeline", "sql"],
           note="ô trống mã -99.99 — chính nó là bài tập chất lượng dữ liệu"),

    Source("ff5", "Fama-French five research factors, daily",
           FF + "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
           unit="factor", units="factors", watch="cross-sectional dispersion of factor returns",
           parts=5, since="1963",
           skills=["risk", "alpha research", "backtesting", "probability",
                   "machine learning", "optimisation"]),

    Source("ff25", "Ken French 25 portfolios formed on size and book-to-market, daily",
           FF + "25_Portfolios_5x5_daily_CSV.zip",
           unit="size-value bucket", units="size-value buckets", watch="cross-sectional dispersion of returns",
           parts=25, since="1926",
           skills=["equities", "portfolio", "optimisation", "visualisation"]),

    Source("curve", "US Treasury constant-maturity yields, daily (FRED)",
           FRED + "DGS1,DGS2,DGS5,DGS10,DGS30",
           unit="maturity", units="maturities", watch="cross-sectional dispersion of yields",
           parts=5, since="1962",
           skills=["fixed income", "derivatives", "risk", "market data",
                   "probability"]),
]

BY_KEY = {s.key: s for s in SHELF}


def for_skill(skill: str) -> Source | None:
    """Nguồn phục vụ kỹ năng này, nhiều thành phần nhất lên trước.

    Nhiều thành phần = truy xuất có chỗ để nói. Một chuỗi đơn (VIX, một lãi
    suất) không lên kệ được: bước 3 của khuôn không có gì để chia.
    """
    fits = [s for s in SHELF if skill in s.skills]
    return max(fits, key=lambda s: s.parts) if fits else None


def uncovered() -> list[str]:
    """Kỹ năng chưa nguồn nào phục vụ — để nói THẲNG chứ không dựng bừa."""
    from ..scoring.vocab import SKILLS
    served = {k for s in SHELF for k in s.skills}
    return sorted(set(SKILLS) - served)
