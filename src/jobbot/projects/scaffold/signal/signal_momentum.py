"""Step 1 — BUILD the signal from a rule.

Trailing 12-month return, skipping the most recent month. The skip is not
decoration: the last month carries short-term reversal, and leaving it in
mixes two effects that behave in opposite directions.

Nothing here is fitted, so there are no parameters to overfit. That is the
point of starting with a rule: whatever edge shows up later cannot be blamed
on a search over settings.
"""
from __future__ import annotations

import pandas as pd

LOOKBACK = 252        # roughly twelve months of trading days
SKIP = 21             # roughly one month, dropped

HOW = f"trailing {LOOKBACK}-day return skipping the last {SKIP} days, ranked across {{units}}"


def rank(frame: pd.DataFrame) -> pd.DataFrame:
    """One score per {{unit}} per day. Backwards-looking only.

    `.shift(SKIP)` after the rolling sum is what enforces that: every score on
    day t is built from data that ended SKIP days before t.
    """
    total = frame.rolling(LOOKBACK - SKIP).sum().shift(SKIP)
    return total.dropna(how="all")
