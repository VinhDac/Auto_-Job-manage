"""{{question}}

Mirrors what the postings say the job is:
{{duties}}

Three steps, no more:

    1 BUILD   score the {{parts}} {{units}} against each other, every day
    2 TEST    hold out the last third of history; the signal never sees it while forming
    3 COST    charge {{cost}} bps of round-trip cost on realised turnover

Run: python3 analyse.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from signal_rule import HOW, rank

DATA = Path(__file__).parent / "data" / "raw.csv"
FIGURE = Path(__file__).parent / "signal.png"

MISSING = [-99.99, -999.0]
SIDE = {{side}}          # how many {{units}} long, and how many short
COST_BPS = {{cost}}      # round-trip cost charged on turnover
HOLDOUT = 1 / 3          # last third of history is never used to choose anything


def load(path: Path = DATA) -> tuple[pd.DataFrame, int]:
    """-> (usable table, rows dropped). The drop count reaches the screen: it
    is a decision with a price, and the reader is entitled to see the price."""
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    clean = frame.replace(MISSING, np.nan).dropna(how="any")
    return clean, len(frame) - len(clean)


def weights(frame: pd.DataFrame, side: int = SIDE) -> pd.DataFrame:
    """Long the top `side`, short the bottom `side`, equal weight, zero net.

    Ranks come from `signal_rule.rank`, which only ever looks backwards — that
    is the whole discipline here, and it has its own test.
    """
    scores = rank(frame)
    if 2 * side > scores.shape[1]:
        # Long `side` và short `side` trên ít hơn 2*side cột thì hai sổ chồng
        # lên nhau và mọi con số phía sau là rác. Dừng, đừng chạy tiếp.
        raise ValueError(f"side={side} too large for {scores.shape[1]} columns")
    order = scores.rank(axis=1, method="first")
    n = scores.notna().sum(axis=1)
    long = order.gt(n.values[:, None] - side)
    short = order.le(side) & scores.notna()
    w = long.astype(float) / side - short.astype(float) / side
    return w[scores.notna().any(axis=1)]


def returns(frame: pd.DataFrame, w: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """-> (gross daily return, turnover). Weights formed on day t earn day t+1.

    Shifting by one day is not a detail. Without it the portfolio earns the
    return it was built from, every backtest looks brilliant, and the number
    is one nobody could have traded.
    """
    aligned = w.reindex(frame.index).ffill()
    gross = (aligned.shift(1) * frame).sum(axis=1).loc[aligned.index]
    turnover = aligned.diff().abs().sum(axis=1)
    return gross.dropna(), turnover.reindex(gross.index).fillna(0.0)


def sharpe(daily: pd.Series) -> float:
    sd = daily.std(ddof=0)
    return float(np.sqrt(252) * daily.mean() / sd) if sd > 0 else 0.0


def split(index: pd.DatetimeIndex, holdout: float = HOLDOUT) -> pd.Timestamp:
    return index[int(len(index) * (1 - holdout))]


def chart(gross: pd.Series, net: pd.Series, cut: pd.Timestamp) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(gross.index, gross.cumsum(), lw=1.0, color="#3B4143", label="gross")
    ax.plot(net.index, net.cumsum(), lw=1.2, color="#55C98D", label=f"net of {COST_BPS} bps")
    ax.axvline(cut, color="#D9736C", lw=1.0, ls="--", label="held out from here")
    ax.set_title("Cumulative return · {{title}}")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=130)
    print(f"figure: {FIGURE.name}")


def main() -> None:
    frame, dropped = load()
    gross, turnover = returns(frame, weights(frame))
    net = gross - turnover * COST_BPS / 10_000

    cut = split(gross.index)
    inside, outside = gross.loc[:cut], net.loc[cut:]
    promise, delivered = sharpe(inside), sharpe(outside)
    survives = delivered / promise if promise > 0 else 0.0

    print(f"{len(frame):,} usable days · {frame.shape[1]} {{units}} "
          f"· {frame.index.min():%Y-%m-%d} → {frame.index.max():%Y-%m-%d}")
    if dropped:
        print(f"dropped {dropped:,} rows ({dropped / (len(frame) + dropped):.0%}) "
              f"missing at least one cell — not filled in")
    print(f"signal: {HOW}")
    print(f"long {SIDE} / short {SIDE} · {COST_BPS} bps round trip "
          f"· mean turnover {turnover.mean():.2f}x/day")
    print()
    print(f"  in-sample gross Sharpe   {promise:6.2f}   (to {cut:%Y-%m-%d})")
    print(f"  held-out net Sharpe      {delivered:6.2f}   (from {cut:%Y-%m-%d})")
    print()
    print(f"HEADLINE: {survives:.0%} of the backtest's promise survived "
          f"being held out and paying costs")
    chart(gross, net, cut)
    save({
        "shape": "signal",
        "headline": f"{survives:.0%} of a {{short}} signal's backtested Sharpe "
                    f"survived being held out and paying {COST_BPS} bps",
        "number": round(float(survives), 4),
        "unit_of_number": "held-out net Sharpe as a share of in-sample gross",
        "days": len(frame), "dropped": dropped, "parts": frame.shape[1],
        "from": str(frame.index.min().date()), "to": str(frame.index.max().date()),
        "in_sample_sharpe": round(promise, 3),
        "held_out_sharpe": round(delivered, 3),
        "cost_bps": COST_BPS, "turnover": round(float(turnover.mean()), 3),
        "held_out_from": str(cut.date()), "signal": HOW,
    })


def save(facts: dict) -> None:
    """Write the numbers to result.json as well as the screen.

    A number that only ever reaches stdout cannot be cited later. This file is
    what the CV line is built from — so every claim about this project points
    back at a value this script actually produced.
    """
    import json
    out = Path(__file__).parent / "result.json"
    out.write_text(json.dumps(facts, indent=2, default=str))
    print(f"facts: {out.name}")


if __name__ == "__main__":
    main()
