"""{{question}}

Three steps, no more:

    1 DETECT     measure the RATE OF CHANGE of {{watch}}, flag days outside normal
    2 CHECK      walk forward — the threshold only ever learns from earlier data
    3 ATTRIBUTE  hold each {{unit}} still in turn, see how much of the move goes away

Run: python3 analyse.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from detect import HOW, flag

DATA = Path(__file__).parent / "data" / "raw.csv"
FIGURE = Path(__file__).parent / "change.png"

# Codes this source uses for a missing cell. NOT filled in: filling means
# inventing a number, and this whole study hunts for unusual numbers — one
# invented cell is one fake event.
MISSING = [-99.99, -999.0]


def load(path: Path = DATA) -> tuple[pd.DataFrame, int]:
    """-> (usable table, rows dropped).

    Returns the drop count so it reaches the screen instead of vanishing:
    dropping incomplete rows is a decision with a price, and the reader is
    entitled to see the price.
    """
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    clean = frame.replace(MISSING, np.nan).dropna(how="any")
    return clean, len(frame) - len(clean)


def watch(frame: pd.DataFrame) -> pd.Series:
    """{{watch}}, one value per day."""
    return frame.std(axis=1, ddof=0)


def attribute(frame: pd.DataFrame, day: pd.Timestamp) -> pd.Series:
    """Step 3: hold each {{unit}} at its previous value, one at a time.

    A {{unit}}'s contribution = the real move minus the move that would have
    happened had it stayed still. These do NOT sum to the total, because a
    standard deviation is not additive. That trade is deliberate: this version
    can be explained in one sentence and checked by a test. The headline figure
    is a SHARE, not a sum.
    """
    where = frame.index.get_loc(day)
    before, after = frame.iloc[where - 1], frame.iloc[where]
    real = after.std(ddof=0) - before.std(ddof=0)
    out = {}
    for name in frame.columns:
        held = after.copy()
        held[name] = before[name]
        out[name] = real - (held.std(ddof=0) - before.std(ddof=0))
    return pd.Series(out).sort_values(key=np.abs, ascending=False)


def chart(series: pd.Series, hits: pd.DatetimeIndex, biggest: pd.Timestamp,
          parts: pd.Series) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7),
                                      gridspec_kw={"height_ratios": [2, 1]})
    top.plot(series.index, series.values, lw=.6, color="#3B4143")
    top.scatter(hits, series.loc[hits], s=14, color="#D9736C", zorder=3,
                label=f"{len(hits)} abnormal days")
    top.axvline(biggest, color="#55C98D", lw=1.2,
                label=f"largest · {biggest:%Y-%m-%d}")
    top.set_title("{{watch}}".capitalize())
    top.legend(loc="upper left", fontsize=9)

    head = parts.head(8)[::-1]
    bottom.barh(head.index.astype(str), head.values,
                color=["#55C98D" if v > 0 else "#D9736C" for v in head.values])
    bottom.set_title(f"What drove {biggest:%Y-%m-%d} — top 8 {{units}}")
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=130)
    print(f"figure: {FIGURE.name}")


def main() -> None:
    frame, dropped = load()
    series = watch(frame)
    change = series.diff().dropna()

    hits = flag(change)
    if len(hits) == 0:
        raise SystemExit("nothing crossed the threshold — loosen detect.py")

    biggest = change.loc[hits].abs().idxmax()
    parts = attribute(frame, biggest)
    share = parts.abs().iloc[0] / parts.abs().sum()

    print(f"{len(frame):,} usable days · {frame.shape[1]} {{units}} "
          f"· {frame.index.min():%Y-%m-%d} → {frame.index.max():%Y-%m-%d}")
    if dropped:
        print(f"dropped {dropped:,} rows ({dropped / (len(frame) + dropped):.0%}) "
              f"missing at least one cell — NOT filled in, because this study "
              f"hunts for unusual numbers and a filled cell is a fake event")
    print(f"detector: {HOW}")
    print(f"{len(hits)} abnormal days · largest {biggest:%Y-%m-%d} "
          f"(change={change.loc[biggest]:+.4f})")
    print()
    print(f"HEADLINE: {share:.1%} of that move came from ONE {{unit}} — "
          f"{parts.index[0]}")
    print()
    for name, value in parts.head(5).items():
        print(f"   {name:<18} {value:+.4f}   {abs(value)/parts.abs().sum():>6.1%}")
    chart(series, hits, biggest, parts)


if __name__ == "__main__":
    main()
