# {{title}}

**{{headline}}**

> {{question}}

Data: [{{dataset}}]({{url}}) — {{parts}} {{units}}, from {{since}}.

```bash
make setup   # pandas · numpy · scikit-learn · matplotlib · pytest
make data    # fetch the data (NOT committed)
make test    # check the detector and the attribution
make run     # print the number, write change.png
```

## Three steps

| step | what it does | where |
|---|---|---|
| 1 · detect | {{how}} | `detect.py` |
| 2 · check | the threshold only learns from data before the day it scores | `detect.py` |
| 3 · attribute | hold each {{unit}} still in turn, measure how much of the move goes away | `analyse.attribute` |

## Where this could be wrong, and what stops it

- **A threshold that peeks at the future.** Learn it over the whole series and
  the abnormal day drags the threshold up and hides itself. Here the window
  stops before the day being scored, and a test plants a huge shock at the end
  of the series to confirm it does not erase the one in the middle —
  `test_a_huge_shock_at_the_end_does_not_hide_the_one_in_the_middle`.
- **Filling in missing cells.** Filling means inventing a number, and this
  study hunts for unusual numbers — one invented cell is one fake event. Rows
  with any missing cell are dropped, the count is printed, and a test enforces it.
- **Attribution does not add up.** Holding one {{unit}} still at a time does not
  sum to the total move, because a standard deviation is not additive. That
  trade is deliberate: this version can be explained in one sentence and checked
  by a test. The headline figure is a **share**, not a sum.

## Not done yet

- [ ] re-run on a second period to see whether the conclusion holds
- [ ] compare against a different detector — a changepoint test rather than a threshold
- [ ] write `WRITEUP.md`; the "what I got wrong" section is what decides whether
      a reader believes the rest
