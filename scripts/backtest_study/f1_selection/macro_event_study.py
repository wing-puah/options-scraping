"""Do scheduled macro events (FOMC, minutes, CPI, NFP, PCE) show up in the book?

PRE-REGISTERED 2026-08-19 in research/pre-registrations/f1_selection/macro_event_study.md
BEFORE this file was written. Read that file first; nothing here may drift
from it. In brief:

  H1 (PRIMARY, ARM I)  entry `vrp` runs up before a scheduled event and
       crushes after, vs a control of "no event of that type within +/-5
       calendar days". Secondary: ticker-demeaned iv_entry, iv_spread, iv_pct.
       Every headline re-cut within mech_vol (events cluster with vol regime).
  H2 (ARM P)   R and E by entry-proximity bucket, WITHIN STRUCTURE from the
       first look; the pooled table prints but carries no conclusion.
  H3 (ARM V)   VIX level / 1-day change by event-relative session over EVERY
       session in the span — index vol, CONTEXT ONLY, no verdict rests on it.
  H4 (ARM X)   exit census — ENDOGENOUS by construction, no verdict; its only
       output is the pre-declared macro_event_exit trigger.

Event distance keys off the ENTRY SESSION (t.grid[0]), never the signal date:
the book fills at the next session's open, so a signal-date event is already
in the entry price. Day 0 on the entry session splits by clock: a pre-open
print (08:30 CPI/NFP/PCE) buckets AFTER (it is in the fill); a post-open
release (14:00 FOMC/minutes, the two 10:00 PCE deviations) buckets BEFORE
(the position sits in front of it).

Gates: G0 power+coverage census FIRST (exit 4 = calendar does not cover the
book; a cell under MIN_EVENT_DATES affected dates prints its n and is not
read), G1 coverage-before-numbers, G2 date-clustered CIs + window/year/tier
cuts, G3 iv units stay decimal fractions, G4 no annualised figures. The
proximity windows {0,1,2,3,5} and the +/-5 control are FROZEN. n_*_in_dte is
census-only (near-constant on this book) — pre-declared non-readable.
Nothing ships from this study under any outcome.
"""
from __future__ import annotations

import random
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import macro_calendar as MC  # noqa: E402
from scripts.backtest_study.lib import underlying_features as UF  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.underlying import load_bars  # noqa: E402

# The runner promotes -latest.txt on these codes instead of deleting it. It
# finds this by AST parse, so it must stay a PLAIN SET LITERAL — a
# frozenset(...) call is invisible to ast.literal_eval and the refusal would
# be misfiled as a failure (found the hard way on the first exit-4 test).
DESIGNED_REFUSAL_EXIT_CODES = {4}  # calendar does not cover the book

# The repo's standing date-level power floor (selection_order.MIN_AFFECTED_DATES,
# declared there 2026-08-13 before any macro count was knowable). Kept as a
# local constant so importing an f4 study module is not a dependency of an f1
# study; the pre-registration names the provenance.
MIN_EVENT_DATES = 25

# FROZEN by the pre-registration. May not grow after any result is seen.
PROXIMITY_WINDOWS = (0, 1, 2, 3, 5)
CONTROL_WINDOW = 5
IV_SECONDARY = ("iv_entry_dm", "iv_spread", "iv_pct")
DEMEAN_MIN_APPEARANCES = 5
BOOT_SEED = 20260819
REL_SESSIONS = 5          # ARM V: event-relative sessions t-5..t+5
TRIGGER_BUCKETS = ("EARLY", "MID", "LATE")   # ARM X hold-position terciles
# Amendment 2: one trading month — long enough that EARLY/MID/LATE are all
# mechanically reachable inside the hold. May not move after results are seen.
SURVIVAL_MIN_HOLD = 20


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


# ── event enrichment ─────────────────────────────────────────────────────────

def enrich(recs: list[dict], cal: MC.MacroCalendar) -> None:
    """Attach event proximity (as of the ENTRY session) + window censuses."""
    for r in recs:
        t = r["t"]
        entry = t.grid[0]
        expiry = min(leg.expiration for leg in t.legs)
        hold_end = None
        if r.get("days_held"):
            hold_end = t.grid[min(int(r["days_held"]), len(t.grid)) - 1]
        r["entry_session"] = entry
        r.update(MC.event_read(cal, entry))
        r.update(MC.window_read(cal, entry, expiry, hold_end))


def signed_prox(r: dict, etype: str):
    """('BEFORE'|'AFTER', k) | ('CONTROL', None) | ('UNKNOWN', None).

    BEFORE k: the next event of `etype` is k calendar days ahead of the entry
    session (k=0 = a post-open release on the entry session itself).
    AFTER k: the last event was k days ago (k=0 = a pre-open print that
    morning, already in the fill). Nearer side wins; a tie goes to BEFORE
    (sitting in front of an event dominates a stale one). CONTROL requires
    KNOWING there is no event within +/-CONTROL_WINDOW — an uncovered forward
    schedule is UNKNOWN, never CONTROL.
    """
    on = r.get(f"on_asof_{etype}")
    if on == "post_open":
        return "BEFORE", 0
    if on == "pre_open":
        return "AFTER", 0
    dn, ds = r.get(f"days_to_next_{etype}"), r.get(f"days_since_last_{etype}")
    if dn is None and not r["_covered"][etype]:
        return "UNKNOWN", None
    before = dn if dn is not None and dn <= CONTROL_WINDOW else None
    after = ds if ds is not None and ds <= CONTROL_WINDOW else None
    if before is None and after is None:
        return "CONTROL", None
    if after is None or (before is not None and before <= after):
        return "BEFORE", before
    return "AFTER", after


def cell_rows(recs, etype, side, w):
    return [r for r in recs
            if r["_prox"][etype][0] == side
            and (side == "CONTROL" or r["_prox"][etype][1] <= w)]


def n_dates(rows):
    return len({r["date"] for r in rows})


# ── date-clustered two-group bootstrap (study-local; protocol has the
#    one-sample and paired variants, not the independent-groups contrast) ────

def boot_diff_by_date(rows_a, rows_b, key, n=2000, seed=BOOT_SEED):
    """Mean(a) - mean(b), CI by resampling DATES within each group."""
    by_a, by_b = {}, {}
    for rows, by in ((rows_a, by_a), (rows_b, by_b)):
        for r in rows:
            v = r.get(key)
            # NaN != NaN: iv_spread/iv_pct are pandas-sourced and carry NaN,
            # not None — the same trap underlying_features.terciles() fixed on
            # 2026-08-12. `is not None` alone lets NaN poison every mean.
            if v is not None and v == v:
                by.setdefault(r["date"], []).append(v)
    if not by_a or not by_b:
        return None
    da, db = sorted(by_a), sorted(by_b)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        sa = [v for d in (rng.choice(da) for _ in da) for v in by_a[d]]
        sb = [v for d in (rng.choice(db) for _ in db) for v in by_b[d]]
        if sa and sb:
            diffs.append(statistics.fmean(sa) - statistics.fmean(sb))
    diffs.sort()
    point = (statistics.fmean(v for vs in by_a.values() for v in vs)
             - statistics.fmean(v for vs in by_b.values() for v in vs))
    return point, diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def print_contrast(label, rows, control, key):
    got = boot_diff_by_date(rows, control, key)
    if got is None:
        print(f"    {label:<28} (no usable {key} values)")
        return None
    d, lo, hi = got
    star = " *" if lo > 0 or hi < 0 else ""
    print(f"    {label:<28} n={len(rows):>4}/{n_dates(rows):>3}d  "
          f"diff {d:+.3f}  CI[{lo:+.3f},{hi:+.3f}]{star}")
    return got


# ── G0: power + coverage census ──────────────────────────────────────────────

def g0(cal: MC.MacroCalendar, recs: list[dict], diag: dict) -> dict:
    hdr("G0 — CALENDAR COVERAGE + POWER CENSUS (blocks every read below)")
    print(f"  calendar: {cal.path}  compiled {cal.compiled}")
    cov = cal.coverage()
    for t in MC.EVENT_TYPES:
        c = cov[t]
        print(f"    {t:<13} n={c['n']:>3}  {c['first']} .. {c['last']}  "
              f"verified_through {c['verified_through']}")
    lo = min(r["entry_session"] for r in recs)
    hi = max(r["entry_session"] for r in recs)
    print(f"  book: {len(recs)} rows / {n_dates(recs)} dates  "
          f"entry sessions {lo} .. {hi}  "
          f"counts_by_source={diag['counts_by_source']} (bs excluded)")
    bad = [t for t in MC.EVENT_TYPES
           if cov[t]["first"] is None or cov[t]["first"] > lo
           or cov[t]["verified_through"] < hi]
    if bad:
        print(f"\n  *** G0 REFUSAL: calendar does not cover the book span for "
              f"{bad} — extend config/macro-events.yml, do not narrow the book. ***")
        sys.exit(4)

    print(f"\n  power floor: {MIN_EVENT_DATES} affected DATES "
          f"(selection_order.MIN_AFFECTED_DATES; pre-registered)")
    print(f"  {'type':<13}{'side':<9}"
          + "".join(f"  w<={w}: dates/rows" for w in PROXIMITY_WINDOWS))
    powered = {}
    for t in MC.EVENT_TYPES:
        for side in ("BEFORE", "AFTER"):
            cells = []
            for w in PROXIMITY_WINDOWS:
                rows = cell_rows(recs, t, side, w)
                nd = n_dates(rows)
                powered[(t, side, w)] = nd >= MIN_EVENT_DATES
                mark = "" if powered[(t, side, w)] else "!"
                cells.append(f"  {nd:>4}/{len(rows):>4}{mark:<1}")
            print(f"  {t:<13}{side:<9}" + "".join(f"{c:>18}" for c in cells))
        ctrl = cell_rows(recs, t, "CONTROL", None)
        unk = [r for r in recs if r["_prox"][t][0] == "UNKNOWN"]
        print(f"  {t:<13}{'CONTROL':<9}  {n_dates(ctrl):>4}/{len(ctrl):>4}"
              f"   UNKNOWN {len(unk)}")
    print("  (! = under the floor: census only, no mean, no CI, no verdict)")

    sub("day-0 audit (the pre_open assignment rule, made checkable)")
    for t in MC.EVENT_TYPES:
        pre = sum(1 for r in recs if r.get(f"on_asof_{t}") == "pre_open")
        post = sum(1 for r in recs if r.get(f"on_asof_{t}") == "post_open")
        print(f"  {t:<13} entry-session events: {pre:>3} pre-open (bucket AFTER)"
              f"  {post:>3} post-open (bucket BEFORE)")

    sub("census, PRE-DECLARED NON-READABLE (near-constant / endogenous)")
    n_dte = sum(1 for r in recs if (r.get("n_macro_in_dte") or 0) >= 1)
    with_hold = [r for r in recs if r.get("n_macro_in_hold") is not None]
    n_hold = sum(1 for r in with_hold if r["n_macro_in_hold"] >= 1)
    print(f"  rows with >=1 macro event inside DTE window : {n_dte}/{len(recs)}")
    print(f"  rows with >=1 macro event inside realized hold: "
          f"{n_hold}/{len(with_hold)}")
    return powered


# ── G1: coverage before numbers ──────────────────────────────────────────────

def gate_coverage(recs: list[dict], diag: dict) -> None:
    hdr("G1 — COVERAGE (denominators for every number below)")
    print(f"  book debit calibration: {diag['debit_calib']}   "
          f"credit rows ungated: {diag['n_credit_ungated']}")
    src = Counter(r["source"] for r in recs)
    print(f"  pricing tiers: {dict(src)}")
    have_vrp = sum(1 for r in recs if r.get("vrp") is not None)
    have_dm = sum(1 for r in recs if r.get("iv_entry_dm") is not None)
    print(f"  vrp computable        : {have_vrp}/{len(recs)} "
          "(needs real bars + iv_entry; OHLC denominator)")
    print(f"  iv_entry ticker-demean: {have_dm}/{len(recs)} "
          f"(tickers with >={DEMEAN_MIN_APPEARANCES} book rows)")
    print("  G3 units note: iv_entry_pct is a DECIMAL FRACTION (0.3295 = 33% "
          "IV); nothing here converts it.")


def enrich_iv(recs: list[dict]) -> None:
    """vrp as of the SIGNAL date (iv_entry is a signal-EOD mark; using the
    entry session would fold in a close the fill never saw), plus
    ticker-demeaned iv_entry."""
    for r in recs:
        r["vrp"] = None
        if r.get("iv_entry") is not None:
            bars = load_bars(r["ticker"])
            r["vrp"] = UF.vrp(bars, r["t"].signal_date, r["iv_entry"])
    med = {}
    for tick in {r["ticker"] for r in recs}:
        vals = [r["iv_entry"] for r in recs
                if r["ticker"] == tick and r.get("iv_entry") is not None]
        if len(vals) >= DEMEAN_MIN_APPEARANCES:
            med[tick] = statistics.median(vals)
    for r in recs:
        m = med.get(r["ticker"])
        r["iv_entry_dm"] = (r["iv_entry"] - m
                            if m is not None and r.get("iv_entry") is not None
                            else None)


# ── ARM V: market context (VIX event study) ──────────────────────────────────

def arm_v(cal: MC.MacroCalendar) -> None:
    hdr("ARM V — VIX and SPY by event-relative session (H3 + amendment 1: "
        "CONTEXT ONLY — index level, not the book; no verdict may rest here)")
    vix, spy = {}, {}
    import csv as _csv
    with UF.MARKET_SERIES.open() as fh:
        for row in _csv.DictReader(fh):
            # a session counts only when BOTH closes parse — the series has
            # holiday rows carrying one leg (e.g. 2026-05-25: VIX, no SPY),
            # and a one-legged session would poison the return chain.
            try:
                d = date.fromisoformat(str(row["date"])[:10])
                v, sp = float(row["vix_close"]), float(row["spy_close"])
            except (ValueError, KeyError, TypeError):
                continue
            if v > 0 and sp > 0:
                vix[d], spy[d] = v, sp
    sessions = sorted(vix)
    if not sessions:
        print("  (no SPY/VIX series on disk — run make mech-regime)")
        return
    idx = {d: i for i, d in enumerate(sessions)}
    print(f"  series: {len(sessions)} sessions {sessions[0]} .. {sessions[-1]}")

    def spy_ret(i, j):  # close[i] -> close[j], in %
        return (spy[sessions[j]] / spy[sessions[i]] - 1.0) * 100.0

    for t in MC.EVENT_TYPES:
        evs = cal.events((t,), sessions[0], sessions[-1])
        # session 0 = the session the release lands on (or first after);
        # both 08:30 and 14:00 prints are inside that session's close.
        anchors = []
        for e in evs:
            d = e.date
            while d not in idx and d <= sessions[-1]:
                d = date.fromordinal(d.toordinal() + 1)
            if d in idx and REL_SESSIONS <= idx[d] < len(sessions) - REL_SESSIONS:
                anchors.append(idx[d])
        if not anchors:
            continue
        print(f"\n  {t}  (n={len(anchors)} events in span)")
        print(f"    {'rel':>4} {'mean VIX':>9} {'mean dVIX':>10}  "
              f"{'CI(dVIX)':>17}  {'SPY ret%':>9}  {'CI(SPY ret%)':>17}")
        for rel in range(-REL_SESSIONS, REL_SESSIONS + 1):
            lv = [vix[sessions[i + rel]] for i in anchors]
            dv = [vix[sessions[i + rel]] - vix[sessions[i + rel - 1]]
                  for i in anchors]
            sr = [spy_ret(i + rel - 1, i + rel) for i in anchors]
            vlo, vhi = _boot_mean_ci(dv)
            slo, shi = _boot_mean_ci(sr)
            vstar = "*" if vlo > 0 or vhi < 0 else " "
            sstar = "*" if slo > 0 or shi < 0 else " "
            print(f"    {rel:>+4} {statistics.fmean(lv):>9.2f} "
                  f"{statistics.fmean(dv):>+10.3f}  "
                  f"[{vlo:+.3f},{vhi:+.3f}]{vstar} "
                  f"{statistics.fmean(sr):>+9.3f}  [{slo:+.3f},{shi:+.3f}]{sstar}")
        # amendment 1: the two pre-declared cumulative drift windows
        pre = [spy_ret(i - 3, i) for i in anchors]
        post = [spy_ret(i, i + 3) for i in anchors]
        for label, vals in (("PRE  drift t-3 -> t0 ", pre),
                            ("POST drift t0 -> t+3", post)):
            lo, hi = _boot_mean_ci(vals)
            star = " *" if lo > 0 or hi < 0 else ""
            print(f"    {label}  mean {statistics.fmean(vals):+.3f}%  "
                  f"CI[{lo:+.3f},{hi:+.3f}]{star}")


def _boot_mean_ci(vals, n=2000, seed=BOOT_SEED):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(vals, k=len(vals)))
                   for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


# ── ARM I / ARM P: proximity contrasts ───────────────────────────────────────

def arm_contrasts(recs, powered, key, title, within_structure=False):
    hdr(title)
    read_any = False
    for t in MC.EVENT_TYPES:
        control = cell_rows(recs, t, "CONTROL", None)
        printed_type = False
        for side in ("BEFORE", "AFTER"):
            for w in PROXIMITY_WINDOWS:
                if not powered[(t, side, w)]:
                    continue
                if n_dates(control) < MIN_EVENT_DATES:
                    continue
                rows = cell_rows(recs, t, side, w)
                if not printed_type:
                    print(f"\n  {t}  (control: no {t} within +/-{CONTROL_WINDOW}: "
                          f"{len(control)} rows / {n_dates(control)} dates)")
                    printed_type = True
                print_contrast(f"{side} w<={w} vs CONTROL", rows, control, key)
                read_any = True
                if within_structure:
                    for s, cnt in Counter(
                            r["structure"] for r in rows).most_common(4):
                        srows = [r for r in rows if r["structure"] == s]
                        sctrl = [r for r in control if r["structure"] == s]
                        if (n_dates(srows) >= MIN_EVENT_DATES
                                and n_dates(sctrl) >= MIN_EVENT_DATES):
                            print_contrast(f"  {s} {side} w<={w}", srows,
                                           sctrl, key)
                        else:
                            print(f"      {s:<26} n={len(srows):>4}/"
                                  f"{n_dates(srows):>3}d  UNDERPOWERED")
        if not printed_type:
            print(f"\n  {t}: every proximity cell UNDERPOWERED "
                  "(census in G0; not read)")
    if not read_any:
        print("\n  ARM VERDICT INPUT: UNDERPOWERED — no cell cleared the floor.")
    return read_any


def mech_vol_recut(recs, powered, key):
    sub(f"mech_vol re-cut of every powered {key} contrast (REGIME-PROXY check)")
    for t in MC.EVENT_TYPES:
        control = cell_rows(recs, t, "CONTROL", None)
        for side in ("BEFORE", "AFTER"):
            for w in PROXIMITY_WINDOWS:
                if not powered[(t, side, w)]:
                    continue
                rows = cell_rows(recs, t, side, w)
                for mv in sorted({r["mech_vol"] for r in recs if r.get("mech_vol")}):
                    mrows = [r for r in rows if r.get("mech_vol") == mv]
                    mctrl = [r for r in control if r.get("mech_vol") == mv]
                    if (n_dates(mrows) >= MIN_EVENT_DATES
                            and n_dates(mctrl) >= MIN_EVENT_DATES):
                        print_contrast(f"{t} {side} w<={w} | {mv}",
                                       mrows, mctrl, key)
                    else:
                        print(f"    {t} {side} w<={w} | {mv:<6} "
                              f"n={len(mrows)}/{n_dates(mrows)}d UNDERPOWERED")


def cuts_on_headlines(recs, powered, key):
    sub(f"G2 cuts on powered {key} contrasts (windows / years / pricing tier)")
    for t in MC.EVENT_TYPES:
        control = cell_rows(recs, t, "CONTROL", None)
        for side in ("BEFORE", "AFTER"):
            w = CONTROL_WINDOW
            if not powered.get((t, side, w)):
                continue
            rows = cell_rows(recs, t, side, w)
            print(f"\n  {t} {side} w<={w}:")
            both = rows + control
            wins = Counter(r["month"] for r in both)
            dom = [m for m, _ in wins.most_common(2)]
            for label, keep in (
                    (f"ex-{dom[0]}", lambda r, m=dom[0]: r["month"] != m),
                    (f"ex-{dom[1]}", lambda r, m=dom[1]: r["month"] != m),
                    ("ex-BOTH", lambda r: r["month"] not in dom)):
                print_contrast(f"{label}", [r for r in rows if keep(r)],
                               [r for r in control if keep(r)], key)
            for yr in sorted({r["date"][:4] for r in both}):
                print_contrast(f"year {yr}",
                               [r for r in rows if r["date"][:4] == yr],
                               [r for r in control if r["date"][:4] == yr],
                               key)
            for srcv in ("real", "tweak"):
                print_contrast(f"tier {srcv}",
                               [r for r in rows if r["source"] == srcv],
                               [r for r in control if r["source"] == srcv], key)


# ── ARM X: exit census ───────────────────────────────────────────────────────

def arm_x(recs: list[dict], cal: MC.MacroCalendar) -> None:
    hdr("ARM X — EXIT CENSUS (H4: ENDOGENOUS — a fast exit is why some holds "
        "contain no event. Census only; no verdict)")
    pop = [r for r in recs if r.get("n_macro_in_hold") is not None
           and r.get("R") is not None and r.get("days_held")]
    spans = [r for r in pop if r["n_macro_in_hold"] >= 1]
    clean = [r for r in pop if r["n_macro_in_hold"] == 0]
    for label, rows in (("hold spans >=1 macro event", spans),
                        ("hold spans none", clean)):
        if not rows:
            continue
        mr = statistics.fmean(r["R"] for r in rows)
        print(f"\n  {label}: {len(rows)} rows / {n_dates(rows)} dates  "
              f"mean R {mr:+.3f}  mean days_held "
              f"{statistics.fmean(r['days_held'] for r in rows):.1f}")
        for reason, cnt in Counter(r["exit_reason"] for r in rows).most_common():
            print(f"    {str(reason):<22} {cnt:>4}")

    sub("exit position relative to the NEAREST event (H4's literal census)")
    exit_prox = {"<= -6": [], "-5..-1": [], "0": [], "+1..+5": [], ">= +6": []}
    for r in pop:
        t = r["t"]
        exit_d = t.grid[min(int(r["days_held"]), len(t.grid)) - 1]
        lo = date.fromordinal(exit_d.toordinal() - 45)
        hi = date.fromordinal(exit_d.toordinal() + 45)
        evs = cal.events_between(lo, hi)
        if not evs:
            continue
        signed = min(((exit_d - e.date).days for e in evs), key=abs)
        b = ("0" if signed == 0 else
             "-5..-1" if -5 <= signed <= -1 else
             "+1..+5" if 1 <= signed <= 5 else
             "<= -6" if signed < 0 else ">= +6")
        exit_prox[b].append(r)
    print("  signed days = exit session minus nearest event (any type); "
          "negative = exited BEFORE the event. Census only.")
    for b, rows in exit_prox.items():
        if rows:
            print(f"  exit {b:<7} {len(rows):>4} rows / {n_dates(rows):>3} dates  "
                  f"mean R {statistics.fmean(r['R'] for r in rows):+.3f}")

    sub("hold-position terciles (feeds the pre-declared macro_event_exit trigger)")
    positioned = []          # (rec, position fraction of the FIRST event)
    for r in spans:
        t = r["t"]
        exit_d = t.grid[min(int(r["days_held"]), len(t.grid)) - 1]
        evs = cal.events_between(r["entry_session"], exit_d)
        if not evs:
            continue
        f = ((evs[0].date - r["entry_session"]).days
             / max(1, (exit_d - r["entry_session"]).days))
        positioned.append((r, f))

    def position_table(pairs, indent="  "):
        """EARLY/MID/LATE mean-R rows; returns (means, affected dates)."""
        bkt = {b: [] for b in TRIGGER_BUCKETS}
        for r, f in pairs:
            bkt["EARLY" if f < 1 / 3 else "MID" if f < 2 / 3 else "LATE"].append(r)
        means = {}
        for b in TRIGGER_BUCKETS:
            if bkt[b]:
                means[b] = statistics.fmean(r["R"] for r in bkt[b])
                print(f"{indent}first event {b:<6} in hold: {len(bkt[b]):>4} rows"
                      f" / {n_dates(bkt[b]):>3} dates  mean R {means[b]:+.3f}")
        return means, n_dates([r for rows in bkt.values() for r in rows])

    means, affected = position_table(positioned)
    mono = (len(means) == 3
            and (means["EARLY"] <= means["MID"] <= means["LATE"]
                 or means["EARLY"] >= means["MID"] >= means["LATE"]))
    fired = mono and affected >= MIN_EVENT_DATES
    msg = ("FIRED — see the amendment-2 survival control below"
           if fired else "not fired")
    print(f"\n  RAW TRIGGER (monotone R across hold-position terciles AND >= "
          f"{MIN_EVENT_DATES} affected dates [{affected}]): {msg}")

    sub("X-C1 — survival control: same table, holds >= "
        f"{SURVIVAL_MIN_HOLD} sessions only (amendment 2)")
    long_pairs = [(r, f) for r, f in positioned
                  if int(r["days_held"]) >= SURVIVAL_MIN_HOLD]
    print(f"  subset: {len(long_pairs)} of {len(positioned)} spanning rows "
          "(event position is mechanically coupled to hold length; a real "
          "effect must survive fixing the length)")
    c1_means, c1_affected = position_table(long_pairs)
    c1_mono = (len(c1_means) == 3
               and (c1_means["EARLY"] <= c1_means["MID"] <= c1_means["LATE"]
                    or c1_means["EARLY"] >= c1_means["MID"] >= c1_means["LATE"]))
    same_dir = (c1_mono and len(means) == 3
                and ((c1_means["LATE"] - c1_means["EARLY"])
                     * (means["LATE"] - means["EARLY"])) > 0)
    if c1_affected < MIN_EVENT_DATES:
        verdict = ("UNDERPOWERED — control unreadable; macro_event_exit stays "
                   "queued but BLOCKED on data")
    elif fired and same_dir:
        verdict = "TRIGGER STANDS — macro_event_exit stays queued"
    else:
        verdict = ("SURVIVAL-ARTIFACT — macro_event_exit DE-QUEUED; re-arms "
                   "only on a future CONTROLLED trigger")
    print(f"\n  X-C1 verdict ({c1_affected} affected dates vs floor "
          f"{MIN_EVENT_DATES}): {verdict}")

    sub("X-C2 — position x hold-length terciles (census; boundaries in-sample)")
    dhs = sorted(int(r["days_held"]) for r, _ in positioned)
    t1, t2 = dhs[len(dhs) // 3], dhs[2 * len(dhs) // 3]
    print(f"  days_held tercile boundaries: <= {t1} < mid <= {t2} < long")
    for label, keep in (
            (f"SHORT (<= {t1}d)", lambda d: d <= t1),
            (f"MID   ({t1}-{t2}d)", lambda d: t1 < d <= t2),
            (f"LONG  (> {t2}d)", lambda d: d > t2)):
        sel = [(r, f) for r, f in positioned if keep(int(r["days_held"]))]
        print(f"  {label}: {len(sel)} rows")
        if sel:
            position_table(sel, indent="    ")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    cal = MC.MacroCalendar.from_yaml()
    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"date_range={diag['date_range']}  (bs excluded)")

    enrich(recs, cal)
    for r in recs:
        r["_covered"] = {t: cal.covers(r["entry_session"], t)
                         for t in MC.EVENT_TYPES}
        r["_prox"] = {t: signed_prox(r, t) for t in MC.EVENT_TYPES}

    powered = g0(cal, recs, diag)
    enrich_iv(recs)
    gate_coverage(recs, diag)

    arm_v(cal)

    read_i = arm_contrasts(
        recs, powered, "vrp",
        "ARM I — IV BEHAVIOUR (H1 PRIMARY: vrp, entry-proximity vs control)")
    if read_i:
        mech_vol_recut(recs, powered, "vrp")
        cuts_on_headlines(recs, powered, "vrp")
        for key in IV_SECONDARY:
            arm_contrasts(recs, powered, key,
                          f"ARM I secondary — {key} (same cells, no new windows)")
            cuts_on_headlines(recs, powered, key)

    read_p = arm_contrasts(
        recs, powered, "R",
        "ARM P — PLAY OUTCOMES (H2: R by proximity; pooled table carries no "
        "conclusion — read the within-structure lines)", within_structure=True)
    if read_p:
        arm_contrasts(recs, powered, "E",
                      "ARM P — E basis (same cells)", within_structure=True)
        mech_vol_recut(recs, powered, "R")
        cuts_on_headlines(recs, powered, "R")

    arm_x(recs, cal)

    print("\nG4 note: no annualised return, Sharpe, or time-to-recover is "
          "printed anywhere above, by design. iv units: decimal fractions "
          "throughout (G3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
