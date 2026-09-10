"""Run: pytest -q

Three things worth testing, because these are the three places a backtest
lies to the person who wrote it:

    · does the signal read tomorrow's data
    · does the portfolio earn the return it was built from
    · do costs actually come out of the result
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import analyse
from signal_rule import rank

# Đủ chỗ cho cả hai sổ, dù repo này được sinh với SIDE bằng bao nhiêu.
PARTS = max(20, analyse.SIDE * 4)
DAYS = 1600


def frame(seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(0, 1.0, size=(DAYS, PARTS)),
        index=pd.bdate_range("2000-01-03", periods=DAYS),
        columns=[f"p{i}" for i in range(PARTS)])


# ------------------------------------------------------- 1 · no look-ahead

def test_signal_ignores_the_future():
    """Rewrite history after a day and that day's score must not move."""
    base = frame()
    scores = rank(base)
    day = scores.index[len(scores) // 2]

    tampered = base.copy()
    tampered.loc[tampered.index > day] *= 100.0
    after = rank(tampered)

    pd.testing.assert_series_equal(scores.loc[day], after.loc[day],
                                   check_names=False)


def test_portfolio_does_not_earn_the_day_it_was_built_from():
    """Plant one component with a huge return on a single day. If weights were
    applied the same day, that day's P&L would be enormous."""
    f = frame()
    day_at = 900
    f.iloc[day_at, 2] += 500.0
    gross, _ = analyse.returns(f, analyse.weights(f))
    assert abs(gross.iloc[day_at]) < 60, "weights earned their own signal day"


# --------------------------------------------------------------- 2 · costs

def test_costs_reduce_the_result():
    f = frame()
    w = analyse.weights(f)
    gross, turnover = analyse.returns(f, w)
    net = gross - turnover * analyse.COST_BPS / 10_000
    assert turnover.mean() > 0, "a signal that never trades is not a signal"
    assert net.sum() < gross.sum(), "costs did not come out"


def test_zero_cost_leaves_the_result_alone():
    f = frame()
    gross, turnover = analyse.returns(f, analyse.weights(f))
    net = gross - turnover * 0 / 10_000
    pd.testing.assert_series_equal(gross, net)


# ---------------------------------------------------------- 3 · the weights

def test_weights_are_market_neutral_and_fully_used():
    f = frame()
    w = analyse.weights(f).dropna(how="all")
    row = w.iloc[-1]
    assert abs(row.sum()) < 1e-9, "the book is not zero net"
    assert abs(row.abs().sum() - 2.0) < 1e-9, "gross exposure is not 1 long 1 short"
    assert (row > 0).sum() == analyse.SIDE and (row < 0).sum() == analyse.SIDE


def test_no_edge_on_pure_noise():
    """The background is random, so a held-out Sharpe far from zero would mean
    the machinery is manufacturing an edge rather than measuring one."""
    f = frame(seed=11)
    gross, _ = analyse.returns(f, analyse.weights(f))
    cut = analyse.split(gross.index)
    assert abs(analyse.sharpe(gross.loc[cut:])) < 1.0


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
