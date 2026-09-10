# {{title}}

**{{headline}}**

> {{question}}

This mirrors what the postings say the job is:

{{duties}}

Data: [{{dataset}}]({{url}}) — {{parts}} {{units}}, from {{since}}.

```bash
make setup   # pandas · numpy · scikit-learn · matplotlib · pytest
make data    # fetch the data (NOT committed)
make test    # check for look-ahead, and that costs come out
make run     # print the number, write signal.png
```

## Three steps

| step | what it does | where |
|---|---|---|
| 1 · build | {{how}} | `signal_rule.py` |
| 2 · test | the last third of history is held out and never used to choose anything | `analyse.split` |
| 3 · cost | {{cost}} bps round trip charged on realised turnover | `analyse.main` |

## Where a backtest lies, and what stops it here

- **Reading tomorrow.** The signal is shifted so every score on day *t* is
  built from data ending before *t*, and `test_signal_ignores_the_future`
  rewrites history after a day to confirm that day's score does not move.
- **Earning the day it was built from.** Weights formed on day *t* earn day
  *t+1*. Without that shift every backtest looks brilliant and the number is
  one nobody could have traded — `test_portfolio_does_not_earn_the_day_it_was_built_from`
  plants a huge single-day return to catch it.
- **Costs quietly not applied.** Charged on realised turnover, and the mean
  turnover is printed so the charge can be checked by hand.
- **An edge manufactured out of noise.** `test_no_edge_on_pure_noise` runs the
  whole machine on random data and requires the held-out Sharpe to stay near zero.

## Not done yet

- [ ] a second signal on the same data, to see whether the result is about the
      signal or about the period
- [ ] cost sensitivity: at what level of costs does the edge disappear entirely
- [ ] write `WRITEUP.md`; the "what I got wrong" section is what decides whether
      a reader believes the rest
