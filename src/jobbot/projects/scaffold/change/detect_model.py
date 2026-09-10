"""Step 1 — DETECT with a MODEL that learns what a normal day looks like.

Different from the plain threshold in one way that matters: a threshold sees
one dimension (is the move big?), while a model sees shape — a middling move
arriving in an unusually quiet market is still abnormal.

WALK FORWARD, one year at a time. Never fit once and score the whole series:

    learn on [t-WINDOW, t)   ->   score [t, t+STEP)

The model never sees the day it is scoring. Refitting daily would be stricter
still, but it takes hours and does not change the conclusion; refitting yearly
is what a real desk does.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

WINDOW = 750          # three years to learn from
STEP = 250            # score one year, then relearn
RATE = 0.004          # share of days treated as abnormal
SEED = 0              # fixed so anyone re-running gets this exact number

HOW = (f"isolation forest, learning on {WINDOW} days then scoring the next "
       f"{STEP}, walked forward (contamination={RATE})")


def features(change: pd.Series) -> pd.DataFrame:
    """Three features, all causal — each uses only data up to that day."""
    return pd.DataFrame({
        "change": change,
        "size": change.abs(),
        "vs_calm": change.abs() / change.rolling(20, closed="left").std(ddof=0),
    }).replace([np.inf, -np.inf], np.nan).dropna()


def flag(change: pd.Series, window: int = WINDOW, step: int = STEP,
         rate: float = RATE) -> pd.DatetimeIndex:
    table = features(change)
    hits: list[pd.Timestamp] = []
    for start in range(window, len(table), step):
        learn = table.iloc[start - window:start]
        judge = table.iloc[start:start + step]
        if len(judge) == 0:
            break
        model = IsolationForest(n_estimators=200, contamination=rate,
                                random_state=SEED)
        model.fit(learn.values)
        hits += list(judge.index[model.predict(judge.values) == -1])
    return pd.DatetimeIndex(hits)
