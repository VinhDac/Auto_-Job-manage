"""Run: pytest -q

Three things worth testing, because these are the three places the study could
fool itself:

    · does the detector find a change that is really there
    · does the threshold peek at the future
    · does attribution point at the {{unit}} that actually caused the move
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import analyse
from detect import flag

PARTS = 12
DAYS = 1500
SHOCK_AT = 1200
SHOCK_COL = 3


def frame(shock: float = 0.0, at: int = SHOCK_AT, col: int = SHOCK_COL,
          days: int = DAYS) -> pd.DataFrame:
    """A quiet, reproducible background with one shock planted in one column."""
    rng = np.random.default_rng(7)
    data = rng.normal(0, 1.0, size=(days, PARTS))
    if shock:
        data[at, col] += shock
    return pd.DataFrame(
        data,
        index=pd.bdate_range("2000-01-03", periods=days),
        columns=[f"p{i}" for i in range(PARTS)])


def change_of(f: pd.DataFrame) -> pd.Series:
    return analyse.watch(f).diff().dropna()


# --------------------------------------------------------------- 1 · detect

def test_finds_a_real_shock():
    hits = flag(change_of(frame(shock=40.0)))
    day = frame().index[SHOCK_AT]
    assert any(abs((h - day).days) <= 4 for h in hits), "missed the planted shock"


def test_stays_quiet_on_a_quiet_series():
    hits = flag(change_of(frame()))
    assert len(hits) <= len(frame()) * 0.01, f"{len(hits)} flags on a quiet series"


# ------------------------------------------- 2 · the threshold must not peek

def test_a_huge_shock_at_the_end_does_not_hide_the_one_in_the_middle():
    """Learn the threshold over the WHOLE series and a huge late shock drags it
    up, erasing the earlier one. This test is what catches that."""
    f = frame(shock=40.0)
    f.iloc[-30, 7] += 4000.0
    day = f.index[SHOCK_AT]
    hits = flag(analyse.watch(f).diff().dropna())
    assert any(abs((h - day).days) <= 4 for h in hits)


def test_scores_nothing_before_the_window_is_full():
    change = change_of(frame(shock=40.0))
    hits = flag(change)
    assert all(h >= change.index[100] for h in hits), "scored before it had data"


# ------------------------------------------------------------ 3 · attribute

def test_points_at_the_component_that_moved():
    f = frame(shock=40.0)
    parts = analyse.attribute(f, f.index[SHOCK_AT])
    assert parts.index[0] == f"p{SHOCK_COL}"


def test_that_component_carries_most_of_the_move():
    f = frame(shock=40.0)
    parts = analyse.attribute(f, f.index[SHOCK_AT])
    assert parts.abs().iloc[0] / parts.abs().sum() > 0.5


def test_components_that_did_not_move_contribute_almost_nothing():
    f = frame(shock=40.0)
    parts = analyse.attribute(f, f.index[SHOCK_AT]).drop(f"p{SHOCK_COL}")
    assert parts.abs().max() < 1.0


# ------------------------------------------------------------------- input

def test_incomplete_rows_are_dropped_not_filled(tmp_path):
    f = frame().head(20)
    f.iloc[5, 0] = -99.99
    path = tmp_path / "raw.csv"
    f.to_csv(path)
    clean, dropped = analyse.load(path)
    assert len(clean) == 19 and dropped == 1, "a missing cell was filled in"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
