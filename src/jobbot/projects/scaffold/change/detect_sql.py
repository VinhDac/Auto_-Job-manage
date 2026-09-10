"""Step 1 — DETECT in SQL rather than in pandas.

The same computation as the plain threshold, written with SQL window
functions. The line worth looking at is
`ROWS BETWEEN {window} PRECEDING AND 1 PRECEDING`: that `AND 1 PRECEDING` is
the no-look-ahead rule stated in the query itself, rather than living in the
head of whoever wrote it.

SQLite has no STDDEV, so the standard deviation is built from E[x²] − E[x]² —
which is worth writing by hand once, to see how it loses precision when the
two terms are close.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

WINDOW = 250
K = 4.0

HOW = f"SQL window function, {K:g}-sigma over the {WINDOW} preceding rows"

QUERY = """
WITH stat AS (
    SELECT
        day,
        d,
        AVG(d)     OVER w AS mu,
        AVG(d * d) OVER w AS mu2,
        COUNT(*)   OVER w AS n
    FROM change
    WINDOW w AS (ORDER BY day ROWS BETWEEN {window} PRECEDING AND 1 PRECEDING)
)
SELECT day
FROM stat
WHERE n = {window}
  AND mu2 - mu * mu > 0
  AND ABS(d - mu) > {k} * SQRT(mu2 - mu * mu)
ORDER BY day
"""


def flag(change: pd.Series, window: int = WINDOW, k: float = K) -> pd.DatetimeIndex:
    conn = sqlite3.connect(":memory:")
    change.rename("d").rename_axis("day").reset_index().assign(
        day=lambda f: f["day"].dt.strftime("%Y-%m-%d")
    ).to_sql("change", conn, index=False)
    rows = conn.execute(QUERY.format(window=window, k=k)).fetchall()
    conn.close()
    return pd.DatetimeIndex([r[0] for r in rows])
