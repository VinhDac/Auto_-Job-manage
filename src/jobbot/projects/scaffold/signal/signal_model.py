"""Step 1 — BUILD the signal from a MODEL rather than a rule.

Walk forward, one year at a time:

    fit on [t-WINDOW, t)   ->   predict [t, t+STEP)

The model never sees the day it is predicting. Refitting daily would be
stricter, but it takes hours and does not change the conclusion; refitting
yearly is what a real desk does.

A ridge is deliberate. On noisy cross-sectional return data a flexible model
mostly fits noise, and the honest comparison for a first pass is against a
plain rule — not against a bigger model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

WINDOW = 1000         # about four years to fit on
STEP = 250            # predict one year, then refit
LAGS = (5, 21, 63, 252)
SEED = 0

HOW = (f"ridge regression on trailing {list(LAGS)}-day returns, refit every "
       f"{STEP} days on the previous {WINDOW}")


def features(frame: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Each feature is a trailing sum, shifted so it ends the day before."""
    return {lag: frame.rolling(lag).sum().shift(1) for lag in LAGS}


def rank(frame: pd.DataFrame) -> pd.DataFrame:
    feats = features(frame)
    target = frame.shift(-1)                       # tomorrow's return
    out = pd.DataFrame(index=frame.index, columns=frame.columns, dtype=float)

    stack = pd.concat([f.stack() for f in feats.values()], axis=1).dropna()
    stack.columns = [f"lag{lag}" for lag in LAGS]
    y = target.stack().reindex(stack.index)
    days = stack.index.get_level_values(0).unique()

    for start in range(WINDOW, len(days), STEP):
        learn_days = days[start - WINDOW:start]
        judge_days = days[start:start + STEP]
        if len(judge_days) == 0:
            break
        learn = stack.loc[learn_days].join(y.rename("y")).dropna()
        if learn.empty:
            continue
        model = Ridge(alpha=1.0, random_state=SEED) if "random_state" in \
            Ridge().get_params() else Ridge(alpha=1.0)
        model.fit(learn[stack.columns].values, learn["y"].values)
        judge = stack.loc[judge_days]
        pred = pd.Series(model.predict(judge.values), index=judge.index)
        out.loc[judge_days] = pred.unstack().reindex(columns=frame.columns)
    return out.dropna(how="all")
