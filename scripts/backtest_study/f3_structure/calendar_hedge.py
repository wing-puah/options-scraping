"""Calendar hedge: the one vol_sleeve survivor, re-derived under a pre-registered pick rule.

Pre-registered in `research/current.md` §2026-08-13 "`calendar_hedge`:
PRE-REGISTRATION", written BEFORE this file was built or run. The pick rules, the
gates, the criteria, the power floor and the two baselines are fixed there;
nothing here may be reworded after seeing a table.

WHAT THIS RE-DERIVES, AND WHY IT WILL BE A DIFFERENT NUMBER
-----------------------------------------------------------
The 2026-08-12 `vol_sleeve` run left exactly one candidate: the calendar is
uncorrelated with the deployed book (+0.088, CI spans zero) and returns +0.336
CI [+0.124, +0.486] on its worst decile. That number is a PER-STRUCTURE
SUBGROUP of a POOLED gate, n=13 rows over 7 dates, with no pick rule and with
the LOOSE (<= 5 day) entry-lag fill rule. This study fixes all three: one hedge
per day chosen by a pre-registered rule (P1 nearest-ATM), a universe restricted
to dates the ladder actually deployed, and a STRICT fill definition — both legs
cached on the ladder's own entry session, because you cannot decide to hedge on
Monday and be filled on Friday. A smaller n and a different number are the
expected outcome, not a failure of the study.

THE RECONSTRUCTION GATES COME FIRST, AND R4 IS THE CRITICAL ONE
---------------------------------------------------------------
R1 quotes the book calibration. R2 re-prices every source row. R3 PRINTS the
deployed ladder line this book produces. **R4** builds `vol_sleeve`'s calendar
cell TWICE in this run, from the same strike index and the same book — once
through this study's `build_universe`/`evaluate`, once through
`vol_sleeve.synthesize` itself — and requires the two equal row for row.
Without R4 the gap between vol_sleeve's +0.336 and whatever H2 prints cannot be
attributed to the pick rule rather than to re-implementation drift, so R4
failing is a hard non-zero exit and the H arm does not run.

AMENDMENT 2026-08-15 (labelled): R3 was a PASS/FAIL comparison against
`R3_EXPECT = dict(n=220, dates=90, dollars=63553.0)` — a checksum of ONE export
snapshot. Those three numbers fingerprint the population, not the code, so every
legitimate data refresh broke the gate: when the bare exports were refreshed that
day and the book went from ~1,900 rows / 142 dates to 74 rows / 10 dates, R3
failed and stopped a study whose logic had not changed. R3 now PRINTS the
deployed line — that is genuinely informative, it is the base the hedge is
measured against — and gates nothing. R4 keeps its constants deliberately: R4 is
a RE-IMPLEMENTATION check (does this code reproduce a cell another study built
from the same cache?), and re-implementation drift is exactly what a fixed
expectation should catch. What replaces R3-as-gate is the thin-era refusal in
main(): a population too small to conclude from is now said in one line with the
numbers, rather than discovered as a snapshot mismatch three gates in.

THE FROZEN HARNESS IS NOT EDITED
--------------------------------
`harness.py` prices nothing — it replays a mark series. Synthesis and pricing
are `vol_sleeve.build_legs`/`_strike_index` and `bear_rewrap.{entry_date_for,
net_entry, net_marks, size_contracts, reconstructs}` IMPORTED UNCHANGED, and
exits are the frozen `replay` under `DEBIT_PROD`. Two copies of the entry rule
would eventually disagree, and R4 is precisely the test that they have not.

CHECKPOINTING
-------------
Every synthesized+replayed candidate is appended to
`backtests/sweep_cache/synth_results.csv`, keyed
`(structure, ticker, date, expiry, profile_hash)`; an interrupted run resumes
instead of restarting, and the report is computed FROM the store. `--redo`
drops the keys this invocation would write before recomputing them.

AMENDMENT 2026-08-13, SUPERSEDED 2026-08-19 (labelled): R4 was re-keyed to a
pre-scrape cache snapshot via the sweep manifest. That held the cache still by
SUBTRACTING the sweep's own additions — a valid inverse only while every LATER
addition is manifested too, which stopped being true within a day (6,240 cache
files postdate the keyed run; the manifest covers 1,452) and can never be true
for a rescrape that overwrites a contract in place. R4 now CANCELS the cache
instead of subtracting it: both sides read the same index in the same process,
so growth moves them together and drift is the only thing left that can differ.
The snapshot machinery is deleted with it, and the checkpoint store is keyed on
its input so a cached row can never be compared against a freshly built one.

Read-only with respect to the project: touches no config, writes no tab. Run:

    python -m scripts.backtest_study run calendar_hedge --gates-only
    python -m scripts.backtest_study run calendar_hedge
    python -m scripts.backtest_study run calendar_hedge --arm S   # after a leg scrape
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.f3_structure import vol_sleeve as VS  # noqa: E402
from scripts.backtest_study.f4_deployment.bear_deploy import max_drawdown  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, cell_stats, fmt_row, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.lib.book import DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade, replay  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal rather than a failure:
# 2 = the era is too thin to conclude from (the `era.require_dates` call in
# main()), 3 = `load_book`'s era guard refusing an export set that is not the era
# asked for. `run.py` reads this by AST parse and never imports the module, so it
# MUST stay a literal module-level assignment — an alias to
# `era.DESIGNED_REFUSAL_EXIT_CODES` would be invisible to it and a correct
# refusal would be reported as FAILED (and its report deleted). Note that R2/R4
# failing is still exit 1: those are real reconstruction failures, not refusals.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── pre-registered constants (do not tune) ───────────────────────────────────

WORST_DECILE = 0.10
WORST_QUARTILE = 0.25
HEDGE_SIZE = 0.5                     # <= 1/2 position, the shipped sleeve convention
SIZE_FRACTIONS = (0.0, 0.25, 0.50, 1.0)
H0_FILL_MIN = 0.60                   # both denominators
MIN_N_TO_READ = 10                # H2(b) is NOT EVALUABLE below this
FRESH_STALE_MAX = 3                  # H0b
FRESH_REAL_MIN = 0.5                 # H0b

# NO R3_EXPECT and NO R4_EXPECT. Both were checksums transcribed from one past
# run — R3's `dict(n=220, dates=90, dollars=63553.0)` off an export, R4's
# `dict(n=183, mean_r=0.158, dollars=28059.0, exits={...})` off
# vol_sleeve-latest.txt (2026-08-12, git 470b95f) — and both broke on data that
# had every right to move. R3 became a print on 2026-08-15; R4 became a same-run
# comparison on 2026-08-19 (see `r4_calendar_cell`). The rule the two failures
# teach: a gate compares two things computed THIS run from the SAME input, or it
# is a fingerprint of one snapshot wearing a gate's clothes. A code-behaviour
# claim that needs a fixed expectation belongs in `tests/` against a committed
# fixture, where the input is version-controlled beside the code.

# The ETF list for pick rule P6, fixed here and printed in the report.
ETF_UNDERLYINGS = (
    "SPY", "QQQ", "IWM", "DIA", "XLE", "XLF", "XLK", "XLI", "XLV", "XLY",
    "XLP", "XLU", "XLB", "XLRE", "XBI", "SMH", "GLD", "SLV", "USO", "TLT",
    "HYG", "EEM", "EFA", "FXI", "KWEB", "ARKK", "VXX", "UVXY", "SQQQ", "TQQQ",
)

# Exit profiles. DEBIT_PROD is the pre-registered one; HOLD is the LABELLED
# SENSITIVITY (hold to near-leg expiry / path cap) and may not change a verdict.
PROFILES = {
    "DEBIT_PROD": dict(DEBIT_PROD),
    "HOLD": dict(pt=None, sl=None, trig=None, trail=None, tef=None),
}

SWEEP_CACHE = ROOT / "backtests" / "sweep_cache"
STORE_PATH = SWEEP_CACHE / "synth_results.csv"
FLUSH_EVERY = 25

STORE_FIELDS = [
    "structure", "ticker", "date", "expiry", "profile_hash",
    "status", "profile", "far_exp",
    "entry_net", "contracts", "exit_reason", "days_held", "pnl_pct",
    "E", "mfe", "mae", "dte", "moneyness", "coverage",
    "pct_real", "stale_at_cap", "entry_lag_days", "fillable_strict",
    "cache_sig",
]

FAIL_HASH = "FAIL"          # a build/pricing failure is not profile-specific


def profile_hash(prof: dict) -> str:
    s = ";".join(f"{k}={prof[k]!r}" for k in sorted(prof))
    return hashlib.md5(s.encode()).hexdigest()[:8]


def cache_fingerprint() -> tuple[int, str]:
    """`(n_contracts, newest_mtime)` of the option-history cache.

    PROVENANCE ONLY — no gate keys to it any more. It still has to be on the
    page, because `vol_sleeve` picks K* as "the cached strike nearest spot" and
    the far leg as "the next cached expiry": the same code on a grown cache
    chooses different legs and prints a different number, so a replication
    cannot interpret any figure here without knowing which cache produced it.
    That property is also why R4 compares two same-run builds instead of a
    stored one (`r4_calendar_cell`) and why the checkpoint store carries
    `ticker_cache_sig`.
    """
    newest, n = 0.0, 0
    for p in HISTORY_CACHE.glob("*.csv"):
        n += 1
        newest = max(newest, p.stat().st_mtime)
    stamp = (datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M:%S")
             if newest else "—")
    return n, stamp


def ticker_cache_sig() -> dict[str, str]:
    """`{ticker: "<n files>@<newest mtime>"}` over the option-history cache.

    Stamped onto every checkpoint row and part of its key, so a row built
    against one cache generation is never REUSED as, or COMPARED against, a row
    built against another. Without this the checkpoint store reintroduces the
    exact defect R4 was converted to remove: `evaluate` would skip a cached row
    while `vol_sleeve.synthesize` recomputed a fresh one, and R4 would fail on
    the next scrape for a reason that has nothing to do with drift.

    Per TICKER, not whole-cache: a scrape touches some tickers, and invalidating
    the other ~1,100 would empty the store without making one number more
    correct. Files are named `{TICKER}_{...}.csv`.

    Rows written before this column existed carry `""`, which matches no live
    signature — they are recomputed rather than trusted, which is the intended
    reading of a row whose input generation is unknown.
    """
    agg: dict[str, tuple[int, int]] = {}
    for p in HISTORY_CACHE.glob("*.csv"):
        tk = p.stem.split("_")[0].upper()
        n, newest = agg.get(tk, (0, 0))
        agg[tk] = (n + 1, max(newest, int(p.stat().st_mtime)))
    return {tk: f"{n}@{m}" for tk, (n, m) in agg.items()}


# ── checkpoint store ─────────────────────────────────────────────────────────

class Store:
    """Append-only CSV of synthesized+replayed candidates, resumable.

    The key is `(structure, ticker, date, expiry, profile_hash)`. A candidate
    that could not be built or priced is written ONCE under `profile_hash =
    "FAIL"` with its reason in `status`, so a resumed run reproduces the same
    unpriceable census instead of re-deriving it (and the census is part of the
    report: which calendars cannot be filled IS the fill-rate question).
    """

    def __init__(self, path: Path = STORE_PATH, sigs: dict[str, str] | None = None):
        self.path = path
        self.sigs = ticker_cache_sig() if sigs is None else sigs
        self.rows: dict[tuple, dict] = {}
        self._pending: list[dict] = []
        self.load()

    def sig_for(self, ticker: str) -> str:
        return self.sigs.get(str(ticker).upper(), "")

    @staticmethod
    def key_of(row: dict) -> tuple:
        return (row["structure"], row["ticker"], row["date"], row["expiry"],
                row["profile_hash"], row.get("cache_sig", ""))

    def key(self, structure: str, ticker: str, d: str, expiry: str,
            prof_hash: str) -> tuple:
        """The key a row built THIS run would have — signature included.

        Callers must go through this rather than assembling the tuple, or they
        would look up a key with no `cache_sig` and hit rows from an older
        cache generation.
        """
        return (structure, ticker, d, expiry, prof_hash, self.sig_for(ticker))

    def load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open() as fh:
            for row in csv.DictReader(fh):
                self.rows[self.key_of(row)] = row

    def has(self, key: tuple) -> bool:
        return key in self.rows

    def failed(self, structure: str, ticker: str, d: str, expiry: str) -> str | None:
        row = self.rows.get(self.key(structure, ticker, d, expiry, FAIL_HASH))
        return row["status"] if row else None

    def put(self, row: dict) -> None:
        row.setdefault("cache_sig", self.sig_for(row["ticker"]))
        self.rows[self.key_of(row)] = row
        self._pending.append(row)
        if len(self._pending) >= FLUSH_EVERY:
            self.flush()

    def flush(self) -> None:
        if not self._pending:
            return
        SWEEP_CACHE.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists()
        with self.path.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=STORE_FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            for r in self._pending:
                w.writerow(r)
        self._pending = []

    def drop(self, pred) -> int:
        """Remove every row matching `pred` and REWRITE the file. Used by --redo."""
        keep = {k: v for k, v in self.rows.items() if not pred(v)}
        dropped = len(self.rows) - len(keep)
        self.rows = keep
        self._pending = []
        SWEEP_CACHE.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=STORE_FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in self.rows.values():
                w.writerow(r)
        return dropped

    def select(self, structure: str, prof_hash: str) -> list[dict]:
        """Rows of one cell — CURRENT cache generation only.

        The signature is in the key, so a stale row cannot be overwritten by a
        fresh one; it has to be filtered out here as well, or `select` would
        return both generations of the same candidate.
        """
        return [_typed(r) for r in self.rows.values()
                if r["structure"] == structure and r["profile_hash"] == prof_hash
                and r["status"] == "ok"
                and r.get("cache_sig", "") == self.sig_for(r["ticker"])]

    def describe(self) -> str:
        if not self.path.exists():
            return f"{self.path.relative_to(ROOT)} — absent (built this run)"
        mt = datetime.fromtimestamp(self.path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return (f"{self.path.relative_to(ROOT)} — {len(self.rows):,} rows, "
                f"mtime {mt}")


def _num(v, cast=float):
    if v is None or v == "":
        return None
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def _typed(row: dict) -> dict:
    """Store row -> report row, with the numerics cast and `R`/`R_dol` derived."""
    out = dict(row)
    for f, cast in (("entry_net", float), ("contracts", int), ("days_held", int),
                    ("pnl_pct", float), ("E", float), ("mfe", float), ("mae", float),
                    ("dte", int), ("moneyness", float), ("coverage", float),
                    ("pct_real", float), ("stale_at_cap", int),
                    ("entry_lag_days", int)):
        out[f] = _num(row.get(f), cast)
    out["fillable_strict"] = str(row.get("fillable_strict", "")).lower() == "true"
    out["R"] = out["pnl_pct"]
    denom = abs(out["entry_net"]) if out["entry_net"] else 0.0
    # FULL-SIZE dollars, the unit vol_sleeve reported and R4 checks against.
    out["R_dol"] = (out["R"] * denom * 100 * out["contracts"]
                    if out["R"] is not None and out["contracts"] else None)
    out["E_dol"] = (out["E"] * denom * 100 * out["contracts"]
                    if out["E"] is not None and out["contracts"] else None)
    # HALF-SIZE dollars: the pre-registered hedge sizing (<= 1/2 a position).
    # The REPLAY is left at full size on purpose — `harness.replay`'s dollar_stop
    # is an absolute $1,000 cap, so re-replaying at half size would change which
    # exit fired and the row would no longer be the one R4 validated. The
    # halving is applied to dollars only, exactly as `bear_deploy` applies its
    # sleeve fraction.
    #
    # 2026-08-13 recorded follow-up (closed 2026-08-14): at contracts == 1,
    # `int(HEDGE_SIZE * 1) == 0` used to be floored back UP to 1 — a FULL-size
    # hedge where the arm specifies half-size. The floor now SKIPS the
    # position instead of rounding up: `hedge_contracts` / `H_dol` are None
    # when half-size rounds under one contract.
    #
    # This is a SIZING fact only, not a fill fact — the candidate stays in
    # every fillable/universe count (`strict`, `keep`, H0's fill gate) exactly
    # as before; a None `H_dol` must be coalesced to $0 wherever a caller sums
    # or correlates it (ARM H does not take the position, so it contributes
    # $0 — same treatment as "no pick that day"). Do NOT filter these rows out
    # of the candidate universe: that flips H0 (a recorded gate) by conflating
    # "fillable but unsizable" with "unfillable". The whole ARM H programme is
    # UNDERPOWERED on this book (next-steps.md §2.3), so this changes no
    # conclusion — only which $0 rows disclose as unsizable in the census.
    raw_ct = int(HEDGE_SIZE * out["contracts"]) if out["contracts"] else None
    hedge_ct = raw_ct if raw_ct and raw_ct >= 1 else None
    out["hedge_contracts"] = hedge_ct
    out["H_dol"] = (out["R"] * denom * 100 * hedge_ct
                    if out["R"] is not None and hedge_ct else None)
    return out


# ── universe: vol_sleeve's construction, restated so it can be gated ─────────

def build_universe(book: list[dict]) -> tuple[dict, Counter]:
    """`{(date, ticker): {expiry: {spot, rec}}}` — `vol_sleeve.synthesize`'s loop.

    Reproduced here (not imported) because `synthesize` fuses universe
    construction, leg building, pricing and replay in one pass, and this study
    needs the universe separately: R2 reports on it, R4 replays all of it, and
    the H arm restricts it to deployed dates. The iteration order and the
    `setdefault` are kept identical — the first book row on a (date, ticker,
    expiry) supplies the spot, and changing that would change K*.
    """
    diag = Counter()
    seen_recon: dict[tuple, bool] = {}
    universe: dict[tuple[str, str], dict[date, dict]] = defaultdict(dict)
    for rec in book:
        t: Trade = rec["t"]
        key = (rec["date"], rec["ticker"])
        if key not in seen_recon:
            ok, why = BR.reconstructs(rec)
            seen_recon[key] = ok
            diag["recon_pass" if ok else "recon_fail"] += 1
            if not ok:
                diag[f"recon_why_{why}"] += 1
        if not seen_recon[key]:
            continue
        spot = VS._f(t.row.get("entry_underlying"))
        if spot is None or spot <= 0:
            diag["no_spot"] += 1
            continue
        for leg in t.legs:
            universe[key].setdefault(leg.expiration, dict(spot=spot, rec=rec))
    diag["ticker_dates"] = len(universe)
    return universe, diag


# ── candidate builders ───────────────────────────────────────────────────────

def _expiries(idx, ticker: str, strike: float, cp: str) -> list[date]:
    """Every cached expiry at one (ticker, strike, call/put), ascending."""
    return sorted(exp for (tk, exp), strikes in idx.items()
                  if tk == ticker and cp in strikes.get(strike, set()))


def build_calendar(idx, ticker: str, expiry: date, spot: float) -> list[Leg] | None:
    """THE structure under test — delegated to `vol_sleeve.build_legs` verbatim.

    Short near-expiry call + long next-cached-expiry call, both at K* = the
    cached strike nearest spot. Not re-implemented: R4 compares this study's
    output to vol_sleeve's row-for-row, and a second copy of the builder is
    exactly the drift R4 exists to catch.
    """
    return VS.build_legs("calendar", idx, ticker, expiry, spot)


def build_put_calendar(idx, ticker: str, expiry: date, spot: float) -> list[Leg] | None:
    """ARM S1 — the put mirror of the calendar."""
    grid = VS.paired_strikes(idx, ticker, expiry)
    if not grid:
        return None
    k = min(grid, key=lambda s: abs(s - spot))
    later = [e for e in _expiries(idx, ticker, k, "P") if e > expiry]
    if not later:
        return None
    return [Leg(-1, ticker, expiry, k, "Put"), Leg(+1, ticker, later[0], k, "Put")]


def build_put_diagonal(idx, ticker: str, expiry: date, spot: float) -> list[Leg] | None:
    """ARM S2 — short near put at K*, long next-expiry put at the strike BELOW."""
    grid = VS.paired_strikes(idx, ticker, expiry)
    if not grid:
        return None
    k = min(grid, key=lambda s: abs(s - spot))
    below = [s for s in grid if s < k]
    if not below:
        return None
    k_long = below[-1]
    later = [e for e in _expiries(idx, ticker, k_long, "P") if e > expiry]
    if not later:
        return None
    return [Leg(-1, ticker, expiry, k, "Put"),
            Leg(+1, ticker, later[0], k_long, "Put")]


def build_iron_condor(idx, ticker: str, expiry: date, spot: float) -> list[Leg] | None:
    """ARM S6 — bull-put + bear-call wings at the nearest cached strikes around K*.

    Four legs on ONE expiry: short put below spot, long put one cached strike
    lower, short call above spot, long call one cached strike higher.
    """
    grid = VS.paired_strikes(idx, ticker, expiry)
    below = [k for k in grid if k < spot]
    above = [k for k in grid if k > spot]
    if len(below) < 2 or len(above) < 2:
        return None
    sp, lp = below[-1], below[-2]
    sc, lc = above[0], above[1]
    return [Leg(-1, ticker, expiry, sp, "Put"), Leg(+1, ticker, expiry, lp, "Put"),
            Leg(-1, ticker, expiry, sc, "Call"), Leg(+1, ticker, expiry, lc, "Call")]


def sub_narrower(rec: dict) -> list[Leg] | None:
    """ARM S3 — bear vertical with the SHORT pulled UP to the highest cached
    strike strictly below the long. The mirror of `bear_rewrap.sub_wider`."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    shorts = [l for l in legs if l.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    short, long_leg = shorts[0], longs[0]
    if short.opt_type != "Put":
        return None
    between = [k for k in BR.cached_puts(short.ticker, short.expiration)
               if short.strike < k < long_leg.strike]
    if not between:
        return None
    new_short = Leg(qty=short.qty, ticker=short.ticker, expiration=short.expiration,
                    strike=max(between), opt_type=short.opt_type)
    if not BR.leg_details(new_short):
        return None
    return [long_leg, new_short]


# Structures built from (idx, ticker, expiry, spot) — the synthesizer arm.
GRID_BUILDERS = {
    "calendar": build_calendar,
    "put_calendar": build_put_calendar,
    "put_diagonal": build_put_diagonal,
    "iron_condor": build_iron_condor,
}
# Structures built from a book ROW — the bear_rewrap controls (ARM S internal
# plumbing checks with known answers: wider -0.056, long_put +0.002).
REC_BUILDERS = {
    "narrower": sub_narrower,
    "wider": BR.BUILDERS["wider"],
    "long_put": BR.BUILDERS["long_put"],
}

ARM_S_STRUCTURES = ("put_calendar", "put_diagonal", "narrower", "wider",
                    "long_put", "iron_condor")


# ── synthesis + replay, checkpointed ─────────────────────────────────────────

def _fill_facts(signal_date: date, legs: list[Leg]) -> tuple[date | None, int | None, bool]:
    """`(entry_date, entry_lag_days, fillable_strict)` for one candidate.

    Computed independently of the loose gate inside `vol_sleeve.synth_trade` so
    the report can print the lag distribution as the pre-registered sensitivity.
    STRICT means the entry lands on `grid[0]` — the ladder's own entry session,
    the first weekday after the signal.
    """
    nearest = min((l.expiration - signal_date).days for l in legs)
    if nearest <= 0:
        return None, None, False
    end = signal_date + timedelta(days=min(nearest, PATH_CAP_DAYS))
    grid = _weekday_grid(signal_date, end)
    if not grid:
        return None, None, False
    ed = BR.entry_date_for(legs, grid)
    if ed is None:
        return None, None, False
    return ed, (ed - signal_date).days, ed == grid[0]


def evaluate(universe: dict, idx, structures: tuple[str, ...], profiles: dict,
             store: Store, quiet: bool = False) -> Counter:
    """Synthesize + replay every candidate not already in the store."""
    diag = Counter()
    groups = 0
    for (d, ticker), by_exp in sorted(universe.items()):
        signal_date = date.fromisoformat(d)
        for expiry in sorted(by_exp):
            info = by_exp[expiry]
            spot, src = info["spot"], info["rec"]
            exp_s = expiry.isoformat()
            for structure in structures:
                groups += 1
                done = all(store.has(store.key(structure, ticker, d, exp_s,
                                               profile_hash(p)))
                           for p in profiles.values())
                if done or store.failed(structure, ticker, d, exp_s):
                    diag["cached"] += 1
                    continue

                if structure not in GRID_BUILDERS:
                    # rec-based substitutions go through `rec_substitutions`, which
                    # uses bear_rewrap's base-row grid and shipped per-row exit.
                    # Routing them here would price them on a rebuilt grid under
                    # flat DEBIT_PROD and break the published controls.
                    raise ValueError(
                        f"{structure!r} is a rec-based substitution — build it with "
                        "rec_substitutions(), not evaluate()")
                legs = GRID_BUILDERS[structure](idx, ticker, expiry, spot)
                base = dict(structure=structure, ticker=ticker, date=d, expiry=exp_s)
                if legs is None:
                    # For a calendar this is "no paired strike grid" OR "no later
                    # cached expiry" — the far_exp <= near_exp exclusion, in effect.
                    diag[f"{structure}_no_grid"] += 1
                    store.put(dict(base, profile_hash=FAIL_HASH, status="no_grid"))
                    continue

                far = max(l.expiration for l in legs)
                ed, lag, strict = _fill_facts(signal_date, legs)
                if lag is not None:
                    diag[f"lag_{lag}"] += 1

                t, why = VS.synth_trade(signal_date, ticker, legs, structure)
                if t is None:
                    diag[f"{structure}_unpriceable"] += 1
                    diag[f"{structure}_why_{why}"] += 1
                    store.put(dict(base, profile_hash=FAIL_HASH, status=why,
                                   far_exp=far.isoformat(),
                                   entry_lag_days="" if lag is None else lag,
                                   fillable_strict=strict))
                    continue
                E, mfe, mae, n_priced = VS.path_stats(t)
                if E is None:
                    diag[f"{structure}_unpriceable"] += 1
                    diag[f"{structure}_why_no_priced_marks"] += 1
                    store.put(dict(base, profile_hash=FAIL_HASH,
                                   status="no_priced_marks", far_exp=far.isoformat()))
                    continue

                pct_real, stale = VS.mark_quality(legs, t.grid)
                k = legs[0].strike
                common = dict(
                    base, status="ok", far_exp=far.isoformat(),
                    entry_net=f"{t.entry_net:.6f}", contracts=t.contracts,
                    E=f"{E:.8f}", mfe=f"{mfe:.8f}", mae=f"{mae:.8f}",
                    dte=t.dte_entry, moneyness=f"{abs(k - spot) / spot:.8f}",
                    coverage=f"{n_priced / len(t.grid):.6f}" if t.grid else "",
                    pct_real=f"{pct_real:.6f}", stale_at_cap=stale,
                    entry_lag_days="" if lag is None else lag,
                    fillable_strict=strict)
                for pname, prof in profiles.items():
                    rp = replay(t, **prof)
                    store.put(dict(common, profile=pname, profile_hash=profile_hash(prof),
                                   exit_reason=rp["exit_reason"],
                                   days_held=rp["days_held"],
                                   pnl_pct=f"{rp['pnl_pct']:.10f}"))
                diag[f"{structure}_built"] += 1
    store.flush()
    diag["groups"] = groups
    if not quiet:
        print(f"  candidate groups walked {groups}  (cached {diag['cached']})")
    return diag


# ── small stats helpers ──────────────────────────────────────────────────────

def fmt_ci(ci) -> str:
    lo, hi = ci
    if lo != lo:
        return "        (thin)   "
    return f"[{lo:>+6.3f}, {hi:>+6.3f}]"


def mean(vals) -> float:
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def daily_dollars(rows: list[dict], key: str) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.get(key) is not None:
            out[str(r["date"])] += float(r[key])
    return dict(out)


# ══════════════════════════════════════════════════════════════════════════════
# GATES R1-R4
# ══════════════════════════════════════════════════════════════════════════════

def r1_book(book: list[dict], diag: dict) -> bool:
    hdr("R1 — book calibration, quoted before anything is built on it")
    dc = diag["debit_calib"]
    print(f"  pooled book (real+tweak, bs excluded)   {len(book):>6} rows over "
          f"{diag['n_dates']} dates  {diag['date_range'][0]} .. {diag['date_range'][1]}")
    print("  by source: " + "  ".join(f"{k}={v}" for k, v in
                                      sorted(Counter(r["source"] for r in book).items())))
    print(f"  debit_calib      n={dc['n']}  exact={dc['exact']}  "
          f"near-rounding-tie={dc['near']}  superseded-basis={dc.get('superseded', 0)}  "
          f"hard={dc['hard']}")
    print(f"  n_credit_ungated {diag['n_credit_ungated']}   "
          f"(admitted WITHOUT the exact-replay gate — see book.py docstring)")
    print(f"  proxy debit rows excluded (non-exact) {diag['n_proxy_excluded_non_exact']}")
    if diag.get("mech_table_warning"):
        print(f"  WARNING: {diag['mech_table_warning']}")
    return True


def r2_recon(diag: Counter) -> bool:
    hdr("R2 — reconstruction gate on every source row feeding the universe")
    print("  A (date, ticker) is used only if THIS code, re-pricing the ORIGINAL")
    print("  book row from the same cache, reproduces its stored entry and marks.")
    ok, bad = diag.get("recon_pass", 0), diag.get("recon_fail", 0)
    tot = ok + bad
    print(f"\n  reconstructs: {ok} / {tot}"
          + (f"  ({ok / tot:.1%})" if tot else ""))
    for k, v in sorted(diag.items()):
        if str(k).startswith("recon_why_"):
            print(f"    failed: {str(k)[10:]:<24} {v}")
    print(f"  signal ticker-dates usable: {diag.get('ticker_dates', 0)}   "
          f"(vol_sleeve 2026-08-12: 786 / 786)")
    passed = bad == 0 and ok > 0
    print(f"  R2 {'PASS' if passed else 'FAIL'}")
    return passed


def r3_deployed(book: list[dict]) -> list[dict]:
    """The deployed ladder line THIS book produces — printed, not gated.

    Returns the picked rows; the H arm's universe is restricted to these dates
    and every hedge number is read against this base, so the line has to be on
    the page. It used to be compared against a stored 220/90/$63,553 and the
    study exited 1 on any difference — a checksum of one export, which failed on
    the 2026-08-15 refresh for no reason but the data being newer. Thin
    populations are refused in main() with a date count instead.
    """
    hdr("R3 — the deployed ladder line this book produces (printed, NOT a gate)")
    picked = P.top_k_per_day(book, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    st = P.replay_stats(picked)
    print(f"  deployed: {st['n']} positions over {st['dates']} dates, "
          f"${st['dollars']:,.0f}   meanR {st['mean_R']:+.3f}  win {st['win']:.0%}")
    print("  (for orientation, the 2026-08-12 vol_sleeve print on the then-current "
          "export was\n   220 positions / 90 dates / $63,553 — a different "
          "population, not a target)")
    return picked


R4_COMPARE_FIELDS = ("entry_net", "contracts", "exit_reason", "days_held", "R")


def _r(v, n):
    return None if v is None or v == "" else round(float(v), n)


def _i(v):
    return None if v is None or v == "" else int(v)


def cell_fingerprint(rows: list[dict]) -> dict[tuple[str, str, str], tuple]:
    """`{(ticker, date, expiry): (entry_net, contracts, exit_reason, days_held, R)}`.

    The comparable form of a calendar cell, so a stored row and an in-memory
    `vol_sleeve` row can be put side by side. Rounded to the precision the
    checkpoint store ROUND-TRIPS (`entry_net` at 6dp and `R` at 10dp, the
    formats `evaluate` writes) — that is the store's own precision, not a
    tolerance chosen to make the gate pass, and widening it would hide the drift
    R4 exists to catch.
    """
    out: dict[tuple[str, str, str], tuple] = {}
    for r in rows:
        key = (str(r["ticker"]), str(r["date"]), str(r["expiry"]))
        out[key] = (_r(r.get("entry_net"), 6), _i(r.get("contracts")),
                    r.get("exit_reason"), _i(r.get("days_held")),
                    _r(r.get("R"), 10))
    return out


def cell_diff(mine: dict, theirs: dict) -> tuple[list, list, list]:
    """`(only_mine, only_theirs, disagreed)` between two cell fingerprints."""
    only_mine = sorted(set(mine) - set(theirs))
    only_theirs = sorted(set(theirs) - set(mine))
    disagreed = sorted(k for k in set(mine) & set(theirs) if mine[k] != theirs[k])
    return only_mine, only_theirs, disagreed


def r4_calendar_cell(store: Store, book: list[dict], idx) -> bool:
    """`vol_sleeve`'s calendar cell, built TWICE this run, required equal.

    R4 asks one question — has `build_universe`/`evaluate` drifted from the
    construction `vol_sleeve.synthesize` performs inline? — and it now asks it
    with both sides built in THIS process from the SAME book and the SAME strike
    index, so the cache cancels instead of standing there as a second free
    variable.

    It used to compare against `R4_EXPECT = dict(n=183, mean_r=0.158, ...)`,
    transcribed from vol_sleeve's 2026-08-12 report. That comparison had two
    unknowns and one equation: `vol_sleeve` picks K* as "the cached strike
    nearest spot" and the far leg as "the next cached expiry", so ADDING
    contracts re-picks legs and moves the cell with no code change, and a
    mismatch could not be read as drift rather than as cache growth — which is
    why the FAIL path needed a whole `_r4_attribute` bisect to guess which had
    happened. The 2026-08-13 amendment tried to hold the cache still by
    SUBTRACTING the sweep scrape's own additions; see the module docstring for
    why that inverse could not survive. Cancelling the variable is what
    subtracting it was reaching for. Recorded in `research/current.md`
    §2026-08-19.
    """
    hdr("R4 — the calendar cell built TWICE this run, required equal (the gate)")
    print("  Pick rule DISABLED, LOOSE fill (entry lag <= U.MAX_ENTRY_LAG_DAYS ="
          f" {U.MAX_ENTRY_LAG_DAYS}), full size,")
    print("  DEBIT_PROD — the construction vol_sleeve reports. Side A is this")
    print("  study's build_universe + evaluate; side B is vol_sleeve.synthesize")
    print("  itself. Both read the same book and the same strike index in this")
    print("  process, so cache growth moves them together and the only thing a")
    print("  mismatch can mean is that this study has drifted from the")
    print("  construction it claims to reproduce.")
    print("  NO stored expectation: nothing here is keyed to a past run.")

    mine_rows = store.select("calendar", profile_hash(PROFILES["DEBIT_PROD"]))
    theirs_rows, _ = VS.synthesize(book, idx, structures=("calendar",))

    mine, theirs = cell_fingerprint(mine_rows), cell_fingerprint(theirs_rows)
    only_mine, only_theirs, disagreed = cell_diff(mine, theirs)

    def dol(rows):
        return sum(r["R_dol"] for r in rows if r.get("R_dol") is not None)

    print(f"\n  {'':<18} {'this study':>14} {'vol_sleeve':>14}")
    print(f"  {'rows':<18} {len(mine):>14} {len(theirs):>14}")
    print(f"  {'meanR':<18} {mean([r['R'] for r in mine_rows]):>+14.3f} "
          f"{mean([r['R'] for r in theirs_rows]):>+14.3f}")
    print(f"  {'$R':<18} {dol(mine_rows):>14,.0f} {dol(theirs_rows):>14,.0f}")
    a_ex = Counter(r["exit_reason"] for r in mine_rows)
    b_ex = Counter(r["exit_reason"] for r in theirs_rows)
    print(f"  {'exit mix':<18}")
    for k in sorted(set(a_ex) | set(b_ex)):
        ae, be = a_ex.get(k, 0), b_ex.get(k, 0)
        print(f"    {str(k):<16} {ae:>14} {be:>14}   "
              f"{'OK' if ae == be else '*** MISMATCH ***'}")

    print(f"\n  keys only in this study {len(only_mine)}   "
          f"only in vol_sleeve {len(only_theirs)}   "
          f"present in both but disagreeing {len(disagreed)}")
    for label, keys in (("only here     ", only_mine),
                        ("only vol_sleeve", only_theirs)):
        for k in keys[:10]:
            print(f"    {label}: {k[0]} {k[1]} exp {k[2]}")
        if len(keys) > 10:
            print(f"    ... and {len(keys) - 10} more")
    for k in disagreed[:10]:
        print(f"    disagree: {k[0]} {k[1]} exp {k[2]}")
        for f, av, bv in zip(R4_COMPARE_FIELDS, mine[k], theirs[k]):
            if av != bv:
                print(f"        {f:<12} here {av!r}   vol_sleeve {bv!r}")
    if len(disagreed) > 10:
        print(f"    ... and {len(disagreed) - 10} more disagreeing")

    ok = not (only_mine or only_theirs or disagreed)
    print(f"\n  R4 {'PASS — the two constructions agree row for row' if ok else 'FAIL'}")
    if not ok:
        print("  STOPPING: the H arm does not run on an unverified rebuild.")
        print("""
  This is re-implementation drift and nothing else. Both sides were built in
  this process from the same book and the same strike index, and the checkpoint
  store is keyed on its cache generation, so the cache, the era and the export
  cannot account for a difference. The divergence is between `build_universe` /
  `evaluate` here and the inline construction in `vol_sleeve.synthesize`; the
  per-key lines above name where. Do NOT reconcile by widening a tolerance or by
  storing whatever this run printed — that is how R4 got into its previous
  state.""")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# H ARM
# ══════════════════════════════════════════════════════════════════════════════

def pick_rules(top_ticker_by_date: dict[str, str]) -> dict:
    """The CLOSED list of decision-time pick rules from the pre-registration.

    Each returns a sort key (LOWER is picked) or None when the row is not a
    candidate for that rule. Every key ends with (ticker, expiry) so the pick is
    deterministic under ties.
    """
    def p1(r):
        return (r["moneyness"], r["ticker"], r["expiry"])

    def p2(r):
        return (-r["dte"], r["ticker"], r["expiry"])

    def p3(r):
        return (r["dte"], r["ticker"], r["expiry"])

    def p4(r):
        gap = (date.fromisoformat(r["far_exp"]) - date.fromisoformat(r["expiry"])).days
        return (-gap, r["ticker"], r["expiry"])

    def p5(r):
        want = top_ticker_by_date.get(str(r["date"]))
        if want is None or r["ticker"] != want:
            return None
        return p1(r)

    def p6(r):
        if r["ticker"].upper() not in ETF_UNDERLYINGS:
            return None
        return p1(r)

    return {"P1 nearest-ATM": p1, "P2 longest near DTE": p2,
            "P3 shortest near DTE": p3, "P4 widest expiry gap": p4,
            "P5 top-pick ticker": p5, "P6 ETF only": p6}


def apply_pick(rows_by_date: dict[str, list[dict]], rule) -> dict[str, dict]:
    out = {}
    for d, rs in rows_by_date.items():
        keyed = [(rule(r), r) for r in rs]
        keyed = [(k, r) for k, r in keyed if k is not None]
        if keyed:
            out[d] = min(keyed, key=lambda kr: kr[0])[1]
    return out


def h0_fill(fillable_by_date: dict[str, list[dict]], dep_dates: list[str],
            worst_dates: list[str], picks: dict[str, dict]) -> bool:
    hdr("H0 — FILL gate: is the hedge available when it is needed?")
    print("  A hedge unavailable exactly when needed is not a hedge. The gate is")
    print("  >= 60% of deployed dates AND >= 60% of the deployed book's worst")
    print("  decile; it fails on either. Unfillable days are carried at 0 in every")
    print("  portfolio line below, never dropped from a denominator.")
    all_n = sum(1 for d in dep_dates if d in picks)
    worst_n = sum(1 for d in worst_dates if d in picks)
    all_r = all_n / len(dep_dates) if dep_dates else 0.0
    worst_r = worst_n / len(worst_dates) if worst_dates else 0.0
    print(f"\n  P1 fillable on deployed dates        {all_n:>4} / {len(dep_dates):<4} "
          f"= {all_r:>6.1%}   {'PASS' if all_r >= H0_FILL_MIN else 'FAIL'}")
    print(f"  P1 fillable on worst-decile dates    {worst_n:>4} / {len(worst_dates):<4} "
          f"= {worst_r:>6.1%}   {'PASS' if worst_r >= H0_FILL_MIN else 'FAIL'}")
    any_n = sum(1 for d in dep_dates if fillable_by_date.get(d))
    print(f"  (any strict-fillable calendar exists on {any_n} / {len(dep_dates)} "
          f"deployed dates — P1 always picks when one does)")
    met = all_r >= H0_FILL_MIN and worst_r >= H0_FILL_MIN
    print(f"\n  H0 {'MET' if met else 'NOT MET'}")
    return met


def h1_standalone(sleeve: list[dict], label: str = "P1") -> None:
    hdr(f"H1 — STANDALONE expectancy of the {label} sleeve (CONTEXT, not a gate)")
    print("  A hedge is allowed to lose money standalone; the shipped bear sleeve")
    print("  does. This is here so the write-up can say what it costs.")
    if not sleeve:
        print("\n  no sleeve rows.")
        return
    ci_r = P.boot_ci_by_date(sleeve, key="R")
    ci_e = P.boot_ci_by_date(sleeve, key="E")
    _, pos, means = P.sign_stable(sleeve, key="R")
    _, pos_e, means_e = P.sign_stable(sleeve, key="E")
    print(f"\n  n={len(sleeve)} positions over {len({r['date'] for r in sleeve})} dates")
    print(f"  meanR {mean([r['R'] for r in sleeve]):+.3f}  CI {fmt_ci(ci_r)}   "
          f"win {sum(1 for r in sleeve if r['R'] > 0) / len(sleeve):.0%}   "
          f"$ (1/2 size) {sum(r['H_dol'] for r in sleeve if r['H_dol'] is not None):+,.0f}")
    print(f"  meanE {mean([r['E'] for r in sleeve]):+.3f}  CI {fmt_ci(ci_e)}")
    print("  years R: " + "  ".join(f"{y} {v:+.3f}" for y, v in means.items())
          + f"   ({pos}/{len(means)} positive)")
    print("  years E: " + "  ".join(f"{y} {v:+.3f}" for y, v in means_e.items())
          + f"   ({pos_e}/{len(means_e)} positive)")
    mix = Counter(r["exit_reason"] for r in sleeve)
    print("  exits: " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))
    print(fmt_row(label, cell_stats(sleeve, key="R")))


def h2_contribution(sleeve: list[dict], picks: dict[str, dict], dep: dict,
                    dep_dates: list[str], worst_dates: list[str],
                    label: str = "P1") -> dict:
    hdr(f"H2 — HEDGE CONTRIBUTION ({label}) — THE PRIMARY GATE")
    print("  D2's rule verbatim: (a) date-level correlation < 0, (b) mean sleeve R")
    print("  on the deployed book's worst-decile dates > 0 with a date-clustered CI")
    print("  excluding zero, (c) worst-quartile tail positive in >= 2 evaluable")
    print("  years. All three. UNDERPOWERED: fewer than 10 positions in the")
    print("  worst-decile cell and (b) is NOT EVALUABLE — not 'failed'.")

    # (a) correlation of the two DAILY DOLLAR series over every deployed date,
    #     unfillable days carried at 0 — and so is a day whose pick IS
    #     fillable but unsizable at the ARM H half-size floor (H_dol is None
    #     there; see `_typed`, 2026-08-14): ARM H does not take that
    #     position, so it contributes $0, same as no pick that day.
    sleeve_dol = {d: (picks[d]["H_dol"]
                      if d in picks and picks[d]["H_dol"] is not None else 0.0)
                  for d in dep_dates}
    pairs = [(dep[d]["dollars"], sleeve_dol[d]) for d in dep_dates]
    r_dol = VS.pearson([a for a, _ in pairs], [b for _, b in pairs])
    ci_dol = VS.corr_ci(pairs)
    sleeve_r = {d: (picks[d]["R"] if d in picks else 0.0) for d in dep_dates}
    pairs_r = [(dep[d]["mean_R"], sleeve_r[d]) for d in dep_dates]
    r_mean = VS.pearson([a for a, _ in pairs_r], [b for _, b in pairs_r])
    ci_mean = VS.corr_ci(pairs_r)
    sub("(a) date-level correlation with the deployed book")
    print(f"  corr(daily $)       {r_dol:>+6.3f}  CI95 {fmt_ci(ci_dol)}   "
          f"over {len(pairs)} deployed dates (unfillable carried at 0)")
    print(f"  corr(daily mean R)  {r_mean:>+6.3f}  CI95 {fmt_ci(ci_mean)}   (context)")
    a_met = r_dol is not None and r_dol < 0
    print(f"  needs < 0: {'YES' if a_met else 'NO'}")

    # (b) worst-decile tail.
    sub("(b) the sleeve on the deployed book's worst-decile dates")
    tail = [picks[d] for d in worst_dates if d in picks]
    dep_tail = sum(dep[d]["dollars"] for d in worst_dates)
    print(f"  worst decile = {len(worst_dates)} dates, deployed ${dep_tail:,.0f}")
    b_met = None
    if len(tail) < MIN_N_TO_READ:
        print(f"  sleeve positions on those dates: n={len(tail)}  "
              f"meanR {mean([r['R'] for r in tail]):+.3f}  "
              f"$ (1/2) {sum(r['H_dol'] for r in tail if r['H_dol'] is not None):+,.0f}")
        print(f"  UNDERPOWERED — n < {MIN_N_TO_READ}. The CI is NOT read and (b) is")
        print("  recorded NOT EVALUABLE, not failed. This was the pre-registered")
        print("  expectation for a 1/day rule; the honest conclusion is 'needs new dates'.")
    else:
        ci = P.boot_ci_by_date(tail, key="R")
        m = mean([r["R"] for r in tail])
        b_met = ci[0] == ci[0] and ci[0] > 0
        print(f"  n={len(tail)}  meanR {m:+.3f}  CI {fmt_ci(ci)}  "
              f"$ (1/2) {sum(r['H_dol'] for r in tail if r['H_dol'] is not None):+,.0f}")
        print(f"  needs > 0 with CI excluding zero: {'YES' if b_met else 'NO'}")

    # (c) worst-quartile tail by year.
    sub("(c) worst-quartile tail, by year")
    ok_years, tot_years = 0, 0
    for y in sorted({d[:4] for d in dep_dates}):
        ys = [d for d in dep_dates if d[:4] == y]
        if len(ys) < 6:
            print(f"  {y}: only {len(ys)} deployed dates — not evaluated")
            continue
        order = sorted(ys, key=lambda d: dep[d]["dollars"])
        ytail = order[:max(2, len(ys) // 4)]
        yrows = [picks[d] for d in ytail if d in picks]
        tot_years += 1
        m = mean([r["R"] for r in yrows]) if yrows else float("nan")
        good = m == m and m > 0
        ok_years += 1 if good else 0
        print(f"  {y}: worst-quartile dates {len(ytail):>3}  deployed "
              f"{mean([dep[d]['dollars'] for d in ytail]):>+10,.0f}  sleeve n={len(yrows):>3} "
              f"meanR {m:+.3f}  -> {'positive' if good else 'not positive'}")
    c_met = ok_years >= 2
    print(f"  tail positive in {ok_years}/{tot_years} evaluable years — needs >= 2: "
          f"{'YES' if c_met else 'NO'}")

    sub("H2 verdict")
    if b_met is None:
        verdict = "NOT EVALUABLE"
        print(f"  (a) {'MET' if a_met else 'not met'}   (b) NOT EVALUABLE (power floor)"
              f"   (c) {'MET' if c_met else 'not met'}")
        print("  H2 = NOT EVALUABLE — the primary gate cannot be read on this window.")
    else:
        met = bool(a_met and b_met and c_met)
        verdict = "MET" if met else "NOT MET"
        print(f"  (a) {'MET' if a_met else 'not met'}   (b) {'MET' if b_met else 'not met'}"
              f"   (c) {'MET' if c_met else 'not met'}")
        print(f"  H2 = {verdict}")
    return dict(verdict=verdict, a=a_met, b=b_met, c=c_met, tail_n=len(tail))


def h0b_freshness(fillable_by_date: dict, rule, dep: dict, dep_dates: list[str],
                  worst_dates: list[str]) -> None:
    hdr("H0b — FRESHNESS: does the headline survive a fresh-marks cut?")
    print(f"  Long premium is the one structure a carried-forward mark flatters.")
    print(f"  Cut to stale_at_cap <= {FRESH_STALE_MAX} AND pct_real >= {FRESH_REAL_MIN},")
    print("  then RE-PICK (the cut can change which calendar P1 selects) and")
    print("  recompute the headline.")
    fresh_by_date = {d: [r for r in rs if r["stale_at_cap"] is not None
                         and r["stale_at_cap"] <= FRESH_STALE_MAX
                         and r["pct_real"] is not None
                         and r["pct_real"] >= FRESH_REAL_MIN]
                     for d, rs in fillable_by_date.items()}
    fresh_by_date = {d: rs for d, rs in fresh_by_date.items() if rs}
    picks = apply_pick(fresh_by_date, rule)
    sleeve = [picks[d] for d in dep_dates if d in picks]
    n_all = sum(1 for d in dep_dates if d in picks)
    n_worst = sum(1 for d in worst_dates if d in picks)
    print(f"\n  fill after the cut: {n_all}/{len(dep_dates)} deployed dates "
          f"({n_all / len(dep_dates):.1%}), {n_worst}/{len(worst_dates)} worst-decile")
    if not sleeve:
        print("  nothing survives the cut.")
        return
    ci = P.boot_ci_by_date(sleeve, key="R")
    tail = [picks[d] for d in worst_dates if d in picks]
    print(f"  meanR {mean([r['R'] for r in sleeve]):+.3f}  CI {fmt_ci(ci)}  n={len(sleeve)}"
          f"   meanE {mean([r['E'] for r in sleeve]):+.3f}")
    print(f"  worst-decile cell: n={len(tail)}  meanR {mean([r['R'] for r in tail]):+.3f}"
          + ("   (below the power floor — no CI read)" if len(tail) < MIN_N_TO_READ else
             f"   CI {fmt_ci(P.boot_ci_by_date(tail, key='R'))}"))


def bear_sleeve_dollars(book: list[dict], dates: list[str]) -> dict[str, float]:
    """The SHIPPED bear hedge sleeve: 1/day, |delta| DESCENDING, <= 1/2 size.

    `docs/deployment-rules.md` §4. Dollars follow `bear_deploy._sleeve_dollars`'
    convention — the day's single best-ranked bear candidate, its realized
    dollars — replayed on the SHIPPED merge (`bear_giveback.prod_profile_for`,
    i.e. base -> structure_exit bear_debit be_after 0.50 -> regime_exit BEAR_HE),
    then halved for the sleeve's <= 1/2 size.
    """
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in book:
        if r["structure"] in BEAR_DEBIT and not r["credit"] and r.get("delta") is not None:
            by_day[str(r["date"])].append(r)
    out = {}
    for d in dates:
        rs = by_day.get(d) or []
        if not rs:
            continue
        pick = max(rs, key=lambda r: abs(float(r["delta"])))
        rp = replay(pick["t"], **prod_profile_for(pick, 0.50, True))
        out[d] = HEDGE_SIZE * pick["t"].dollars(rp["pnl_pct"])
    return out


def _sweep(base_daily: dict[str, float], sleeve: dict[str, float],
           dates: list[str], label: str) -> None:
    print(f"\n  baseline: {label}")
    print(f"  {'f':>5s} {'total $':>12s} {'max DD $':>12s} {'worst date $':>13s} "
          f"{'neg dates':>10s}")
    out, base = [], None
    for f in SIZE_FRACTIONS:
        daily = [base_daily.get(d, 0.0) + f * sleeve.get(d, 0.0) for d in dates]
        tot, mdd, worst = sum(daily), max_drawdown(daily), min(daily)
        neg = sum(1 for v in daily if v < 0)
        print(f"  {f:5.2f} {tot:>12,.0f} {mdd:>12,.0f} {worst:>13,.0f} {neg:>10d}")
        if f == 0.0:
            base = (tot, mdd, worst)
        out.append(dict(f=f, total=tot, mdd=mdd, worst=worst))
    ok = [o for o in out if o["f"] > 0 and o["mdd"] >= base[1] - 1e-9
          and o["worst"] >= base[2] - 1e-9]
    if ok:
        best = max(ok, key=lambda o: o["f"])
        print(f"  -> DEPLOYABLE at f = {best['f']:.2f}: DD {base[1]:,.0f} -> "
              f"{best['mdd']:,.0f}, total ${base[0]:,.0f} -> ${best['total']:,.0f} "
              f"({best['total'] - base[0]:+,.0f})")
    else:
        print("  -> NOT MET at any size — no fraction leaves both drawdown and "
              "worst-date unharmed.")
        # Which of the two conditions bound is decision-relevant and is NOT a
        # relaxation of the rule: the rule is unchanged, this only says why.
        dd_ok = [o for o in out if o["f"] > 0 and o["mdd"] >= base[1] - 1e-9]
        w_ok = [o for o in out if o["f"] > 0 and o["worst"] >= base[2] - 1e-9]
        print(f"     bound by: drawdown {'ok at every f' if len(dd_ok) == len(out) - 1 else 'fails'}"
              f"; worst-date {'ok at every f' if len(w_ok) == len(out) - 1 else 'fails'}"
              f"  (f=1.00 moves DD {out[-1]['mdd'] - base[1]:+,.0f}, "
              f"worst date {out[-1]['worst'] - base[2]:+,.0f}, "
              f"total {out[-1]['total'] - base[0]:+,.0f})")


def h3_sizing(picks: dict[str, dict], dep: dict, dep_dates: list[str],
              book: list[dict]) -> None:
    hdr("H3 — SIZING: the largest f that harms neither drawdown nor the worst date")
    print("  Two baselines, a deliberate change from vol_sleeve: the calendar must")
    print("  beat the hedge the operator ALREADY HAS, not just the empty seat.")
    print("  (i) the deployed ladder alone; (ii) ladder + the SHIPPED bear sleeve")
    print("  (|delta| descending, 1/day, <= 1/2 size, docs/deployment-rules.md §4).")
    # A pick that is fillable but unsizable at the ARM H half-size floor
    # (H_dol None; see `_typed`, 2026-08-14) contributes $0 here too — ARM H
    # does not take it, same as no pick that day.
    cal = {d: (picks[d]["H_dol"]
               if d in picks and picks[d]["H_dol"] is not None else 0.0)
           for d in dep_dates}
    ladder = {d: dep[d]["dollars"] for d in dep_dates}
    bear = bear_sleeve_dollars(book, dep_dates)
    print(f"\n  calendar sleeve: {sum(1 for d in dep_dates if d in picks)} positions; "
          f"bear sleeve: {len(bear)} positions; both over {len(dep_dates)} deployed dates")
    _sweep(ladder, cal, dep_dates, "(i) deployed ladder alone")
    ladder_plus_bear = {d: ladder[d] + bear.get(d, 0.0) for d in dep_dates}
    print(f"\n  (shipped bear sleeve alone contributes "
          f"${sum(bear.values()):+,.0f} over {len(bear)} dates)")
    _sweep(ladder_plus_bear, cal, dep_dates, "(ii) ladder + SHIPPED bear sleeve")


def h4_pick(fillable_by_date: dict, rules: dict, dep_dates: list[str]) -> None:
    hdr("H4 — CONDITIONAL PICK: is P1 the right rule, within the day?")
    print("  Same-date pairing throughout, so the day is its own control and the")
    print("  level problem that sinks every cross-sectional comparison does not")
    print("  apply. A P2-P6 pass with P1 failing is a candidate for a future")
    print("  window, never a ship — the pre-registration fixes P1 as THE rule.")

    day_rows = {d: rs for d, rs in fillable_by_date.items() if d in set(dep_dates)}
    all_picks = {name: apply_pick(day_rows, rule) for name, rule in rules.items()}
    p1 = all_picks["P1 nearest-ATM"]

    sub("coverage and standalone mean of each rule")
    print(f"  {'rule':<24} {'dates':>6} {'meanR':>8} {'$ (1/2)':>12}")
    for name, picks in all_picks.items():
        rows = [picks[d] for d in dep_dates if d in picks]
        if not rows:
            print(f"  {name:<24} {0:>6}       —            —")
            continue
        print(f"  {name:<24} {len(rows):>6} {mean([r['R'] for r in rows]):>+8.3f} "
              f"{sum(r['H_dol'] for r in rows if r['H_dol'] is not None):>12,.0f}")

    sub("P1 vs the day's MEAN fillable calendar (paired by date)")
    paired = []
    for d in dep_dates:
        if d not in p1:
            continue
        rs = day_rows.get(d) or []
        paired.append(dict(date=d, a=p1[d]["R"], b=mean([r["R"] for r in rs])))
    if len(paired) >= 5:
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        print(f"  n={len(paired)} dates  dR {mean([p['a'] - p['b'] for p in paired]):+.3f}"
              f"  CI [{lo:+.3f}, {hi:+.3f}]")
        print(f"  (mean day carries {mean([len(day_rows[p['date']]) for p in paired]):.1f} "
              f"fillable calendars)")
    else:
        print(f"  too few paired dates ({len(paired)}) to read")

    for name, picks in all_picks.items():
        if name.startswith("P1"):
            continue
        sub(f"P1 vs {name} (same-date pairs only)")
        paired = [dict(date=d, a=p1[d]["R"], b=picks[d]["R"])
                  for d in dep_dates if d in p1 and d in picks]
        if len(paired) < 5:
            print(f"  too few paired dates ({len(paired)}) to read")
            continue
        same = sum(1 for d in dep_dates if d in p1 and d in picks
                   and p1[d]["ticker"] == picks[d]["ticker"]
                   and p1[d]["expiry"] == picks[d]["expiry"])
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        print(f"  n={len(paired)} dates ({same} identical picks)  "
              f"dR {mean([p['a'] - p['b'] for p in paired]):+.3f}  CI [{lo:+.3f}, {hi:+.3f}]")


def h5_timing(sleeve: list[dict], ctx: dict) -> None:
    hdr("H5 — TIMING (POST-HOC, labelled): when is the calendar worth carrying?")
    print("  NOT pre-registered as a gate. Every cell here was chosen AFTER seeing")
    print("  vol_sleeve, including the one CI-clearing conditional it found")
    print("  (calendar x earnings-inside-DTE, +0.356 vs -0.035, n=42). Read as a")
    print("  CANDIDATE for an independent window; nothing here can ship.")
    if not sleeve:
        print("\n  no sleeve rows.")
        return
    for r in sleeve:
        c = ctx.get((str(r["date"]), r["ticker"]), {})
        r["mech_cell"] = c.get("mech_cell")
        r["mech_vol"] = c.get("mech_vol")
        r["model_dir"] = c.get("model_dir")
        r["model_vol"] = c.get("model_vol")
        r["days_to_earnings"] = c.get("days_to_earnings")

    print(f"\n  {'condition':<30} {'n':>4}  {'meanR':>7}  {'vs rest':>8}  "
          f"{'diff CI95 (date-clustered)':>26}")

    def show(label, sel):
        got = [r for r in sleeve if sel(r)]
        rest = [r for r in sleeve if not sel(r)]
        if not got or not rest:
            print(f"  {label:<30} (one side empty: {len(got)}/{len(rest)})")
            return
        d_ci = VS.boot_ci_diff_by_date(sleeve, sel, key="R")
        flag = "" if (d_ci[0] != d_ci[0] or d_ci[0] <= 0 <= d_ci[1]) else "  <- excludes 0"
        print(f"  {label:<30} {len(got):>4}  {mean([r['R'] for r in got]):>+7.3f}  "
              f"{mean([r['R'] for r in rest]):>+8.3f}  {fmt_ci(d_ci):>26}{flag}")

    show("mech_cell == BEAR_HE", lambda r: r.get("mech_cell") == "BEAR_HE")
    show("mech_vol H-VOL", lambda r: r.get("mech_vol") == "H-VOL")
    show("model RANGE + C/L-VOL",
         lambda r: r.get("model_dir") == "RANGE" and r.get("model_vol") in ("C-VOL", "L-VOL"))
    show("earnings inside DTE",
         lambda r: r.get("days_to_earnings") is not None
         and r["days_to_earnings"] == r["days_to_earnings"]
         and 0 <= r["days_to_earnings"] <= (r["dte"] or 0))


# ══════════════════════════════════════════════════════════════════════════════
# ARM S — the structure sweep. CODE ONLY on this run; needs the leg scrape.
# ══════════════════════════════════════════════════════════════════════════════

# bear_rewrap's published cell means (backtests/study_output/bear_rewrap-latest.txt,
# 2026-08-12) — the known answers S4/S5 must reproduce, or the plumbing is wrong.
REWRAP_CONTROLS = {"wider": -0.056, "long_put": +0.002, "baseline": -0.093}
CONTROL_TOL = 0.0005


def rec_substitutions(bear: list[dict], labels: list[str]):
    """S3/S4/S5 built on bear debit rows through `bear_rewrap`'s OWN path.

    NOT routed through this module's `evaluate`: `bear_rewrap` prices a
    substitution on the BASE ROW's grid and exits it on the shipped per-row
    merge (`replay_rec` -> `prod_profile_for`), while `evaluate` rebuilds the
    grid from the legs and exits on flat `DEBIT_PROD`. Only the former can
    reproduce the published control means, and a control that cannot reproduce
    its known answer is not a control.

    They are also kept OUT of the checkpoint store on purpose: the store key is
    (structure, ticker, date, expiry), and two bear rows on one ticker-date can
    share an expiry at different strikes — they would collide and silently
    overwrite each other.

    Returns `(rows_by_label, availability_diag, control_cells)`.
    """
    out: dict[str, list[dict]] = defaultdict(list)
    diag = Counter()
    controls: dict[str, list[dict]] = defaultdict(list)
    for rec in bear:
        ok, _ = BR.reconstructs(rec)
        if not ok:
            diag["recon_fail"] += 1
            continue
        base_out = BR.replay_rec(rec, rec["t"])
        controls["baseline"].append(dict(date=rec["date"], **base_out))
        spot = VS._f(rec["t"].row.get("entry_underlying"))
        for label in labels:
            legs = REC_BUILDERS[label](rec)
            if legs is None:
                diag[f"skip_{label}"] += 1
                continue
            t = BR.synth_trade(rec, legs, label)
            if t is None:
                diag[f"unpriced_{label}"] += 1
                continue
            res = BR.replay_rec(rec, t)
            controls[label].append(dict(date=rec["date"], **res))
            longs = [l for l in legs if l.qty > 0]
            k = (longs[0] if longs else legs[0]).strike
            near = min(l.expiration for l in legs)
            far = max(l.expiration for l in legs)
            # ARM H half-size floor, same skip-don't-round-up rule as
            # `_typed` (2026-08-14): at t.contracts == 1 the floor SKIPS
            # (hedge_ct None, H_dol None) rather than rounding up to a
            # full-size hedge. This is a sizing fact only — the row still
            # goes into `out[label]` so R-based comparisons are unaffected.
            raw_ct = int(HEDGE_SIZE * t.contracts)
            hedge_ct = raw_ct if raw_ct >= 1 else None
            out[label].append(dict(
                date=rec["date"], ticker=rec["ticker"],
                expiry=near.isoformat(), far_exp=far.isoformat(),
                moneyness=(abs(k - spot) / spot) if spot else float("inf"),
                dte=t.dte_entry, R=res["R"], E=None,
                entry_net=t.entry_net, contracts=t.contracts,
                exit_reason=res["exit_reason"],
                H_dol=(res["R"] * abs(t.entry_net) * 100 * hedge_ct
                       if hedge_ct is not None else None)))
            diag[f"built_{label}"] += 1
    return dict(out), dict(diag), dict(controls)


def arm_s_controls(controls: dict[str, list[dict]]) -> None:
    """S4/S5 are internal plumbing checks with KNOWN answers — verify them.

    `wider` selects the lowest cached put strike below the short, so the sweep
    scrape (895 new puts) can legitimately move it; `long_put` only DROPS the
    short leg and touches no grid, so it must reproduce exactly. Printing both
    against their published values is what separates "the cache grew" from
    "this study's plumbing is wrong".
    """
    sub("S4 / S5 CONTROLS — reproduction against bear_rewrap's published cells")
    print("  Known answers (bear_rewrap-latest.txt, 2026-08-12): baseline -0.093,")
    print("  long_put +0.002, wider -0.056. long_put touches no strike grid and")
    print("  MUST reproduce; wider re-selects from the grid and may legitimately")
    print("  move now that the sweep scrape added 895 puts.")
    print(f"\n  {'cell':<12} {'n':>5} {'meanR':>9} {'published':>11} {'delta':>9}   verdict")
    for label in ("baseline", "long_put", "wider"):
        rows = controls.get(label) or []
        if not rows:
            print(f"  {label:<12} {'—':>5}   (not built)")
            continue
        m = mean([r["R"] for r in rows])
        pub = REWRAP_CONTROLS[label]
        delta = m - pub
        if abs(delta) <= CONTROL_TOL:
            verdict = "REPRODUCES"
        elif label == "wider":
            verdict = "MOVED (grid-selecting — expected on a grown cache)"
        else:
            verdict = "*** MISMATCH — plumbing suspect ***"
        print(f"  {label:<12} {len(rows):>5} {m:>+9.3f} {pub:>+11.3f} "
              f"{delta:>+9.3f}   {verdict}")


def arm_s(universe: dict, idx, store: Store, book: list[dict], dep: dict,
          dep_dates: list[str], worst_dates: list[str],
          top_ticker_by_date: dict) -> int:
    """The bounded sweep of untried wrappers. Refuses to run before the H arm.

    MULTIPLICITY is the whole point of the arm being separate: a cell is a
    CANDIDATE only if its worst-decile CI excludes zero at Bonferroni
    alpha = 0.05 / (n_structures x n_pick_rules), is right-signed in every year
    present, and clears H0. Nothing in here can ship from this run; the maximum
    verdict is carry-to-next-window.
    """
    # "Has the H arm printed?" — asked across EVERY report this study has
    # written, not just `-latest.txt`. A `--gates-only` run overwrites latest,
    # so keying the gate on that one file makes the runner's own bookkeeping
    # look like a missing H arm. The marker is the H2 verdict line, so a
    # gates-only report still cannot unlock the sweep.
    out_dir = ROOT / "backtests" / "study_output"
    h_reports = sorted(p for p in out_dir.glob("calendar_hedge-*.txt")
                       if "H2 (primary)" in p.read_text())
    if not h_reports:
        print(f"ARM S REFUSED: no H-arm report in {out_dir.relative_to(ROOT)} "
              "carries an")
        print("H2 verdict. ARM S runs only AFTER the H arm has printed, in a")
        print("separate invocation, per the pre-registration.")
        return 2
    print(f"  H-arm precondition satisfied by {h_reports[-1].name}")

    hdr("ARM S — structure sweep (separate invocation, separate report)")
    print("  Synthesis here runs on the FULL GROWN cache — that was the point of the")
    print("  sweep-leg scrape. Only R4's snapshot cell withholds the scraped legs.")
    structures = list(ARM_S_STRUCTURES)

    # ---- S6 gate: four-leg coverage, printed either way ----
    ic_ok, ic_tot = 0, 0
    for (d, ticker), by_exp in universe.items():
        for expiry, info in by_exp.items():
            ic_tot += 1
            if build_iron_condor(idx, ticker, expiry, info["spot"]) is not None:
                ic_ok += 1
    cov = ic_ok / ic_tot if ic_tot else 0.0
    sub("S6 four-leg coverage gate")
    print(f"  iron_condor buildable on {ic_ok}/{ic_tot} groups = {cov:.1%}"
          f"   (gate {H0_FILL_MIN:.0%}; plan-time cache-only was 214/786 = 27.2%)")
    if cov < H0_FILL_MIN:
        print("  S6 = NOT EVALUABLE — excluded from the sweep AND from the")
        print("  multiplicity count (it cannot spend alpha it never tested).")
        structures.remove("iron_condor")
    else:
        print("  S6 = EVALUABLE — included in the sweep and the multiplicity count.")

    # ---- synthesize the grid-based structures on the grown cache ----
    grid_structures = [s for s in structures if s in GRID_BUILDERS]
    rec_structures = [s for s in structures if s in REC_BUILDERS]
    sub("synthesis")
    evaluate(universe, idx, tuple(grid_structures), PROFILES, store)

    # ---- the rec-based substitutions, through bear_rewrap's OWN path ----
    bear = [r for r in book if r["structure"] in BEAR_DEBIT and not r["credit"]]
    rec_rows, rec_diag, controls = rec_substitutions(bear, rec_structures)

    ph = profile_hash(PROFILES["DEBIT_PROD"])
    dep_set = set(dep_dates)

    sub("per-structure coverage (candidates available before any pick rule)")
    print(f"  {'structure':<14} {'path':<12} {'built':>7} {'on dep dates':>13} "
          f"{'dep dates covered':>18}")
    pool: dict[str, list[dict]] = {}
    for s in grid_structures:
        rows = [r for r in store.select(s, ph)
                if r["fillable_strict"] and r["entry_net"] is not None
                and r["entry_net"] > 0]
        on_dep = [r for r in rows if str(r["date"]) in dep_set]
        pool[s] = on_dep
        print(f"  {s:<14} {'synth grid':<12} {len(rows):>7} {len(on_dep):>13} "
              f"{len({str(r['date']) for r in on_dep}):>10} / {len(dep_dates)}")
    for s in rec_structures:
        rows = rec_rows.get(s) or []
        on_dep = [r for r in rows if str(r["date"]) in dep_set]
        pool[s] = on_dep
        print(f"  {s:<14} {'bear_rewrap':<12} {len(rows):>7} {len(on_dep):>13} "
              f"{len({str(r['date']) for r in on_dep}):>10} / {len(dep_dates)}")
    print("  (grid structures are STRICT-filled and entry_net > 0, as the H arm;")
    print("   bear_rewrap rows are real book positions re-wrapped on their own entry)")
    if rec_diag:
        print("  bear_rewrap availability: " + "  ".join(
            f"{k}={v}" for k, v in sorted(rec_diag.items())))

    # ---- S4/S5 controls: known answers, or the plumbing is wrong ----
    arm_s_controls(controls)

    # ---- the sweep ----
    rules = pick_rules(top_ticker_by_date)
    alpha = 0.05 / (len(structures) * len(rules))
    sub("MULTIPLICITY")
    print(f"  structures {len(structures)} x pick rules {len(rules)} = "
          f"{len(structures) * len(rules)} cells  ->  Bonferroni alpha = "
          f"{alpha:.5f}")
    print(f"  every worst-decile CI below is a {(1 - alpha) * 100:.3f}% interval, not 95%.")

    sub("the sweep — worst-decile CI at the corrected alpha")
    print(f"  {'structure':<14} {'rule':<24} {'fill':>6} {'n':>4} {'meanR':>8} "
          f"{'tail n':>7} {'tail R':>8}  {'tail CI (Bonferroni)':>26}  verdict")
    candidates, n_power, n_cells = [], 0, 0
    for structure in structures:
        by_date: dict[str, list[dict]] = defaultdict(list)
        for r in pool.get(structure) or []:
            by_date[str(r["date"])].append(r)
        for rname, rule in rules.items():
            picks = apply_pick(by_date, rule)
            sleeve = [picks[d] for d in dep_dates if d in picks]
            fill = len(sleeve) / len(dep_dates) if dep_dates else 0.0
            tail = [picks[d] for d in worst_dates if d in picks]
            n_cells += 1
            if len(tail) < MIN_N_TO_READ:
                n_power += 1
                verdict = "NOT EVALUABLE (power)"
                ci_s = "     not read (power floor)"
            else:
                ci = P.boot_ci_by_date(tail, key="R", alpha=alpha)
                ci_s = f"{fmt_ci(ci):>26}"
                _, _, means = P.sign_stable(tail, key="R")
                right_signed = bool(means) and all(v > 0 for v in means.values())
                ok = (ci[0] == ci[0] and ci[0] > 0 and right_signed
                      and fill >= H0_FILL_MIN)
                verdict = "CANDIDATE" if ok else "no"
                if ok:
                    candidates.append((structure, rname, len(tail),
                                       mean([r["R"] for r in tail]), ci, fill))
            tail_r = mean([r["R"] for r in tail]) if tail else float("nan")
            print(f"  {structure:<14} {rname:<24} {fill:>5.0%} {len(sleeve):>4} "
                  f"{mean([r['R'] for r in sleeve]):>+8.3f} {len(tail):>7} "
                  f"{tail_r:>+8.3f}  {ci_s}  {verdict}")

    sub("ARM S verdict")
    if candidates:
        print(f"  {len(candidates)} cell(s) clear the corrected bar:")
        for s, rname, n, m, ci, fill in candidates:
            print(f"    {s} x {rname}: tail n={n} meanR {m:+.3f} CI {fmt_ci(ci)} "
                  f"fill {fill:.0%}")
        print("  Status: CARRY-TO-NEXT-WINDOW. Not a finding, not a ship.")
    else:
        print(f"  NO cell clears the corrected bar. {n_power} of {n_cells} cells")
        print("  are UNDERPOWERED on the worst-decile cell (n < "
              f"{MIN_N_TO_READ}) — the same")
        print("  stop that made the H arm's H2 NOT EVALUABLE, and for the same")
        print("  reason: a 1/day rule over 9 worst-decile dates cannot fill a cell")
        print("  large enough to read. This is a POWER outcome, not evidence")
        print("  against any structure.")
    print("\n  Nothing in ARM S can ship from this run. Maximum verdict:")
    print("  carry-to-next-window, per the pre-registration.")
    return 0


# ══════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gates-only", action="store_true",
                    help="run R1-R4 and stop (non-zero exit if a gate fails; R3 "
                         "prints and never fails)")
    ap.add_argument("--arm", default="H", choices=("H", "S"),
                    help="H = the study proper (default); S = the structure sweep, "
                         "which refuses to run before the H-arm report exists")
    ap.add_argument("--redo", action="store_true",
                    help="drop this invocation's keys from the checkpoint store "
                         "before recomputing them")
    a = ap.parse_args(argv)

    structures = ("calendar",) if a.arm == "H" else ARM_S_STRUCTURES

    store = Store()
    if a.redo:
        # R4's cell is always redone with the arm: it is the gate, and a stale
        # stored row is the one thing that could hide a real drift.
        drop_set = set(structures) | {"calendar"}
        n = store.drop(lambda r: r["structure"] in drop_set)
        print(f"--redo: dropped {n} store rows for {', '.join(sorted(drop_set))}")

    hdr("PROVENANCE — inputs, store, and the frozen pieces this rests on")
    n_cache, newest = cache_fingerprint()
    print(f"  option cache       {n_cache:,} contracts, newest {newest}")
    print("                     (provenance only — no gate is keyed to it)")
    print(f"  checkpoint store   {store.describe()}")
    print(f"  exit profiles      " + "   ".join(
        f"{k}={profile_hash(v)} {v}" for k, v in PROFILES.items()))
    print(f"  pre-registration   research/current.md "
          f"§2026-08-13 calendar_hedge")
    print(f"  P6 ETF list ({len(ETF_UNDERLYINGS)}): " + " ".join(ETF_UNDERLYINGS))

    book, bdiag = load_book(include_bs=False)
    # Refuse a thin era HERE — before `_strike_index()` and `build_universe()`,
    # which are the expensive parts, and before any gate can mistake "there was
    # nothing to test" for "the test failed". This study has no larger date floor
    # of its own (MIN_N_TO_READ is a ROW count, applied to H2 downstream), so
    # it takes the shared power floor.
    era.require_dates(bdiag["n_dates"], bdiag["era"],
                      what="the deployed-date universe and its worst decile")
    idx = VS._strike_index()

    # ---- gates ----
    r1_book(book, bdiag)
    universe, udiag = build_universe(book)
    if not r2_recon(udiag):
        return 1
    deployed = r3_deployed(book)

    hdr("SYNTHESIS — building every candidate the universe can carry")
    print("  Results are checkpointed to the store keyed (structure, ticker, date,")
    print("  expiry, profile_hash); an interrupted run resumes.")

    # R4's side A, on the LIVE index — the same one vol_sleeve's side B reads.
    # ARM S does not otherwise build "calendar", so this is load-bearing there;
    # under ARM H the store dedups it against the full evaluate just below.
    print("\n  R4 side A: building the calendar cell on the live strike index")
    evaluate(universe, idx, ("calendar",),
             {"DEBIT_PROD": PROFILES["DEBIT_PROD"]}, store)

    if a.arm == "H":
        print()
        sdiag = evaluate(universe, idx, ("calendar",), PROFILES, store)
        for k in sorted(sdiag):
            if str(k).startswith("calendar_"):
                print(f"  {k:<34} {sdiag[k]}")

    if not r4_calendar_cell(store, book, idx):
        return 1
    if a.gates_only:
        hdr("GATES ONLY — R2 and R4 pass (R1/R3 print); the H arm was not run")
        return 0

    # ---- the deployed book, its dates, and its worst decile ----
    dep = VS.daily(deployed)
    dep_dates = sorted(dep)
    order = sorted(dep_dates, key=lambda d: dep[d]["dollars"])
    n_dec = max(1, int(len(order) * WORST_DECILE))
    worst_dates = order[:n_dec]
    top_ticker_by_date = {}
    for r in deployed:
        top_ticker_by_date.setdefault(str(r["date"]), r["ticker"])

    if a.arm == "S":
        return arm_s(universe, idx, store, book, dep, dep_dates, worst_dates,
                     top_ticker_by_date)

    hdr("H ARM UNIVERSE — deployed dates only, STRICT fill")
    print("  FILLABLE means both legs cached on the ladder's OWN entry session")
    print("  (entry_date == grid[0]) — you cannot decide to hedge on Monday and be")
    print("  filled on Friday. The loose <= 5-day rule vol_sleeve used prints below")
    print("  as the pre-registered sensitivity.")
    dep_set = set(dep_dates)
    cal_rows = store.select("calendar", profile_hash(PROFILES["DEBIT_PROD"]))
    on_dep = [r for r in cal_rows if str(r["date"]) in dep_set]
    strict = [r for r in on_dep if r["fillable_strict"]]
    excl_credit = [r for r in strict if r["entry_net"] is not None and r["entry_net"] <= 0]
    excl_exp = [r for r in strict
                if r["far_exp"] and r["expiry"] and r["far_exp"] <= r["expiry"]]
    keep = [r for r in strict if r["entry_net"] is not None and r["entry_net"] > 0
            and not (r["far_exp"] and r["far_exp"] <= r["expiry"])]
    print(f"\n  deployed dates                         {len(dep_dates):>5}")
    print(f"  worst-decile deployed dates            {len(worst_dates):>5}  "
          f"(by deployed daily dollars; deployed ${sum(dep[d]['dollars'] for d in worst_dates):,.0f})")
    print(f"  loose-priced calendars on those dates  {len(on_dep):>5}")
    print(f"  ... STRICT-fillable (entry on grid[0]) {len(strict):>5}")
    print(f"  ... excluded, entry_net <= 0           {len(excl_credit):>5}")
    print(f"  ... excluded, far_exp <= near_exp      {len(excl_exp):>5}")
    print(f"  candidate calendars retained           {len(keep):>5}  over "
          f"{len({str(r['date']) for r in keep})} dates, "
          f"{len({r['ticker'] for r in keep})} tickers")
    # 2026-08-14: the ARM H half-size floor (`_typed`'s `hedge_contracts`,
    # None when HEDGE_SIZE * contracts rounds under one contract) is a
    # SIZING fact, not a fill fact — "fillable but too small to half-size"
    # is not "unfillable". It must NOT move `keep`/`strict`/H0's fill
    # gate (a recorded gate: 75.6% deployed / 66.7% worst-decile MET), so
    # unsizable candidates stay IN the universe here and are only skipped
    # where ARM H actually sizes and sums dollars (h2_contribution's
    # `sleeve_dol`, h3_sizing's `cal`, etc. — those coalesce a None hedge to
    # $0, same as "no pick that day"). Disclosed, not excluded:
    n_unsizable = sum(1 for r in keep if r["hedge_contracts"] is None)
    if n_unsizable:
        print(f"  ... of which unsizable at half-size    {n_unsizable:>5}  "
              f"contribute $0 (ARM H sizing floor, 2026-08-14)")

    sub("entry-lag distribution under the LOOSE rule (sensitivity, not the universe)")
    print("  STRICT is not a single lag bucket: grid[0] is the first WEEKDAY after")
    print("  the signal, so a Mon-Thu signal fills strict at lag 1 and a Friday")
    print("  signal fills strict at lag 3. The split is printed per bucket.")
    lag = Counter(r["entry_lag_days"] for r in on_dep if r["entry_lag_days"] is not None)
    lag_strict = Counter(r["entry_lag_days"] for r in on_dep
                         if r["entry_lag_days"] is not None and r["fillable_strict"])
    tot = sum(lag.values())
    print(f"\n  {'lag':>6}  {'rows':>5}  {'share':>6}  {'of which STRICT':>16}")
    for k in sorted(lag):
        print(f"  {k:>4}d  {lag[k]:>5}  {lag[k] / tot:>6.1%}  {lag_strict.get(k, 0):>16}")
    if on_dep:
        print(f"  strict share of loose-priced rows: {len(strict)}/{len(on_dep)} "
              f"= {len(strict) / len(on_dep):.1%}")

    fillable_by_date: dict[str, list[dict]] = defaultdict(list)
    for r in keep:
        fillable_by_date[str(r["date"])].append(r)
    rules = pick_rules(top_ticker_by_date)
    p1_rule = rules["P1 nearest-ATM"]
    picks = apply_pick(fillable_by_date, p1_rule)
    sleeve = [picks[d] for d in dep_dates if d in picks]

    h0_met = h0_fill(fillable_by_date, dep_dates, worst_dates, picks)
    h1_standalone(sleeve)
    h2 = h2_contribution(sleeve, picks, dep, dep_dates, worst_dates)
    h0b_freshness(fillable_by_date, p1_rule, dep, dep_dates, worst_dates)
    h3_sizing(picks, dep, dep_dates, book)
    h4_pick(fillable_by_date, rules, dep_dates)

    ctx = {}
    for (d, ticker), by_exp in universe.items():
        rec = next(iter(by_exp.values()))["rec"]
        ctx[(d, ticker)] = rec
    h5_timing(sleeve, ctx)

    # ---- labelled exit sensitivity ----
    hdr("EXIT SENSITIVITY (LABELLED) — the same tables held to near-leg expiry")
    print("  pt / sl / tef all None. It MAY NOT change the verdict; it exists so the")
    print("  write-up can say whether the verdict is exit-shape-dependent.")
    hold_rows = store.select("calendar", profile_hash(PROFILES["HOLD"]))
    hold_keep = {(str(r["date"]), r["ticker"], r["expiry"]): r for r in hold_rows}
    hold_by_date: dict[str, list[dict]] = defaultdict(list)
    for r in keep:
        h = hold_keep.get((str(r["date"]), r["ticker"], r["expiry"]))
        if h is not None:
            hold_by_date[str(r["date"])].append(h)
    hold_picks = apply_pick(hold_by_date, p1_rule)
    hold_sleeve = [hold_picks[d] for d in dep_dates if d in hold_picks]
    h1_standalone(hold_sleeve, label="P1 (hold to near expiry)")
    h2_hold = h2_contribution(hold_sleeve, hold_picks, dep, dep_dates, worst_dates,
                              label="P1 hold-to-expiry")

    hdr("VERDICT")
    print(f"  H0 FILL           {'MET' if h0_met else 'NOT MET'}")
    print(f"  H2 (primary)      {h2['verdict']}")
    print(f"  H2 under hold     {h2_hold['verdict']}   (sensitivity — may not change "
          f"the verdict)")
    print("\n  Ship ceiling per the pre-registration: an optional second hedge sleeve")
    print("  in docs/deployment-rules.md §4, requiring H0 MET and H0b not flipping")
    print("  the verdict and H2 MET and H3 deployable at f >= 0.25. Anything less is")
    print("  a candidate. Nothing here changes config/backtest.yml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
