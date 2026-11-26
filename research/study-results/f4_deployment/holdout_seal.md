# holdout_seal — the one registered read

**Question.** On the sealed v4 window (signal dates from 2026-09-23), do Tier A and Tier B of the
deployed set each earn a positive mean R? See the
[registration](../../pre-registrations/f4_deployment/holdout_seal.md).

Append-only. The read runs once and is never re-cut.

## era v4 — recorded 2026-11-26

**Verdict: `UNDERPOWERED` on both tiers.** Tier A has 38 deployed positions and Tier B has 26,
both below the floor of 40. Each tier therefore prints a census only. Per the registration, the
seal does not re-close and the window is not extended. The seal lifts with this record
(`era.SEAL_LIFTED = "2026-11-26"`).

**Disclosed before the read.** Two earlier reads touched sealed dates: a descriptive pass on
2026-10-22 and the bear-strategies peek on 2026-11-21. Neither printed a per-tier figure on the
deployed set, which is the only thing this read reserves.

**Note on the census.** The census counts priced dates on the exports, so it reaches 44. The
deployed set counts only rows that are closed or past their path window, so it reaches 33 dates.
The 195 pending rows are excluded, per the loader's default.

Report, verbatim:

```
HOLDOUT SEAL — the one registered read (holdout_seal.md)
  run at       2026-11-26 14:36:46
  era          v4
  census       {'seal_start': '2026-09-23', 'lifted': None, 'need': 40, 'exports': {'results': {'rows': 243, 'dates': 40, 'exists': True}, 'proxy': {'rows': 226, 'dates': 44, 'exists': True}, 'analysis': {'rows': 514, 'dates': 45, 'exists': True}}, 'priced_dates': 44, 'condition_met': True}
  window       signal dates >= 2026-09-23: 170 rows on 37 dates
  deployed set 64 positions on 33 dates (top_k=3, tiers A+B)

  Tier A: n=38 on 22 dates  -> UNDERPOWERED (census only)
  Tier B: n=26 on 12 dates  -> UNDERPOWERED (census only)

>>> holdout_seal: UNDERPOWERED (per tier above) <<<
```

Loader stderr, verbatim:

```
pending: 195 open_at_data_end rows still inside their path window at the export as-of 2026-11-25 excluded; 63 closed-window open rows kept as cap_open outcomes
SEAL: withheld 0 rows on 0 signal dates >= 2026-09-23 (reader holdout_seal) — holdout_seal.md
book outcomes: 2041 rows; 63 open_at_data_end (cap_open marks at the data end, not closes), 185 carried, 55 deferred exit fills (calibration skipped), 18 no_two_sided
```

The read was run by this one-off script, which is kept here because the registration builds no
module:

```python
"""The ONE registered read of holdout_seal.md, section "The read, fixed now".

Deployed set = protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible),
era-scoped, include_bs=False (real + tweak only), book loaded with
load_book(sealed_read="holdout_seal") and cut to signal dates >= SEAL_START.
Prints exactly: Tier A and Tier B meanR, its 95% date-clustered CI, PF, its
95% date-clustered CI. Plus the census the seal permits (counts only).
"""
import sys
from datetime import datetime

sys.path[:0] = [".", "scripts"]
from scripts.backtest_study.lib import era, protocol  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

book, diag = load_book(include_bs=False, sealed_read="holdout_seal")
window = [r for r in book if str(r["date"])[:10] >= era.SEAL_START]
picked = protocol.top_k_per_day(window, protocol.ladder_rank, k=3,
                                eligible_fn=protocol.ladder_eligible)

print("HOLDOUT SEAL — the one registered read (holdout_seal.md)")
print(f"  run at       {datetime.now():%Y-%m-%d %H:%M:%S}")
print(f"  era          {diag.get('era')}")
print(f"  census       {era.seal_census()}")
print(f"  window       signal dates >= {era.SEAL_START}: "
      f"{len(window)} rows on {len({str(r['date'])[:10] for r in window})} dates")
print(f"  deployed set {len(picked)} positions on "
      f"{len({str(r['date'])[:10] for r in picked})} dates (top_k=3, tiers A+B)")
print()
verdict_parts = {}
for tier in ("A", "B"):
    rows = [r for r in picked if r.get("tier") == tier]
    n = len([r for r in rows if r.get("R") is not None])
    dates = len({str(r["date"])[:10] for r in rows})
    if n < 40:
        print(f"  Tier {tier}: n={n} on {dates} dates  -> UNDERPOWERED (census only)")
        verdict_parts[tier] = "UNDERPOWERED"
        continue
    mean_r = sum(float(r["R"]) for r in rows if r.get("R") is not None) / n
    lo, hi = protocol.boot_ci_by_date(rows, key="R")
    pf_pt, pf_lo, pf_hi = protocol.pf_ci_by_date(rows, key="R")
    print(f"  Tier {tier}: n={n} on {dates} dates")
    print(f"    meanR {mean_r:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    pf_s = "undefined" if pf_pt is None else f"{pf_pt:.3f}"
    print(f"    PF    {pf_s}  95% CI [{pf_lo:.3f}, {pf_hi:.3f}]")
    verdict_parts[tier] = (mean_r, lo, hi)
print()

def clears(v):
    return isinstance(v, tuple) and v[0] > 0 and v[1] > 0

def contrary(v):
    return isinstance(v, tuple) and v[0] < 0 and v[2] < 0

a, b = verdict_parts["A"], verdict_parts["B"]
if contrary(a) or contrary(b):
    token = "CONTRARY"
elif "UNDERPOWERED" in (a, b):
    token = "UNDERPOWERED (per tier above)"
elif clears(a) and clears(b) and a[0] >= b[0]:
    token = "CONFIRMED"
elif clears(a) or clears(b):
    token = "PARTIAL"
else:
    token = "NULL"
print(f">>> holdout_seal: {token} <<<")
```
