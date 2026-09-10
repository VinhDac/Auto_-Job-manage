"""Step 1 — DETECT with a rolling standard-deviation threshold.

The threshold only ever learns from the past. This is the easiest place in the
whole study to fool yourself: fit it over the entire series and the abnormal
day itself drags the threshold upward and hides itself — and worse, the number
you report is one nobody could have produced in real time.
"""
from __future__ import annotations

import pandas as pd

WINDOW = 250          # days used to learn the threshold — one trading year
K = 4.0               # how many standard deviations counts as abnormal

HOW = f"{K:g}-sigma threshold, learnt on the {WINDOW} days before each day"


def flag(change: pd.Series, window: int = WINDOW, k: float = K) -> pd.DatetimeIndex:
    """Which days sit outside normal.

    `closed="left"` is the whole story: the window stops BEFORE the day being
    scored, so that day never helps define its own idea of normal.
    """
    roll = change.rolling(window, closed="left")
    mean, sd = roll.mean(), roll.std(ddof=0)
    out = (sd > 0) & ((change - mean).abs() > k * sd)
    return change.index[out.fillna(False)]
