"""The SHIPPED selector, run under history — support module for `account_sim --live-select`.

RESEARCH TIER importing PRODUCTION. That is the allowed direction and the whole
point: `account_sim` re-implements the deployment ladder in
`scripts/backtest_study/lib/book.py::ladder_tier`, while the function that actually
decides what gets deployed is `scripts/journal/s06_recommend.py` — `rank()` (the
deterministic ladder, encoded once in `scripts/live_loop/mapping.ladder_tier`)
followed by `judge()` (the one model call, demote-only). The two ladders have
already drifted apart. This module runs the shipped pair over the historical
book so the drift is a measured number rather than an argument, and so the
simulated decision is the live decision.

Nothing here is a second copy of production. `s06_recommend.py` gains no
sim-specific branch: everything the arm needs was already injectable
(`ac_df`, `book`, `net_liq`, `invoke`), and every piece of pricing, sizing,
admission and exit replay is `account_sim`'s own frozen machinery, reached
through the `ranker` hook on `simulate()`.

Four things are worth knowing before reading a number this module prints.

  * **`rank()` annotates on the open book; it does not filter on it.** The book
    is read for duplicate exposure and cap headroom, both recorded on the
    candidate as text, and nothing downstream of that reads them back. So the
    ORDER and MEMBERSHIP `rank()` returns are independent of the book handed to
    it. The synthetic book is still built from the sim's genuinely-open
    positions — that is what makes the printed reasons true — but no reader
    should expect the ledger state to move a pick.

  * **The §3 delta gate cannot be read off an analysis row.** The
    AnalysisClaude export carries no `delta`, `short_leg_delta` or
    `delta_notional`; `docs/deployment-rules.md` §3 is explicit that those are
    read in IBKR at order entry. `entry_check="ibkr_verified"` (the default)
    joins the book row's measured entry-side delta/DTE onto the frame under the
    names `rank()` looks for, which is what the operator would have had in front
    of him and keeps the arm comparable to the frozen book.
    `entry_check="analysis_only"` supplies nothing and shows what the card alone
    can see: every `bull_put_spread` tiers on the DTE proxy with `partial=True`.
    Both counts are printed; neither is the "right" one on its own.

  * **The judgment call is cached, and the cache is the evidence.** Every
    `judge()` prompt is keyed by `sha256(prompt_text)` into
    `backtests/study_output/live-select-judgments.jsonl` — prompt hash, model
    id, session date, raw response, timestamp. A re-run replays from it, so the
    arm is reproducible and what the model actually said is auditable after the
    fact rather than reconstructed from its effects.

  * **`judge()` can see the future and G5 cannot tell.** `JUDGMENT_MODEL` is
    `claude-opus-5`, whose knowledge cutoff overlaps the analysis dates, so it
    may "remember" what a ticker did. G5 blinds RECORD FIELDS; it cannot blind
    model weights, and `journal/lib/prompt.py`'s "do not use any outside knowledge of these
    tickers" is necessary and not sufficient. The arm does not pretend to solve
    this. It BOUNDS it: two ledger walks off one model pass, `demote_policy`
    `skip` against `ignore`, whose difference is the judge layer's entire effect
    on the book and therefore an upper bound on its lookahead exposure. If the
    two books match, the question is moot for this population.

Not a runnable study — `scripts/backtest_study/run.py` lists it as INFRA and
`scripts/study_map/catalog.py` files it the same way. It is driven by
`account_sim.main()` under `--live-select`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import hdr, sub  # noqa: E402
from scripts.backtest_study.lib.book import (  # noqa: E402
    DEFAULT_PROXY_CSV, DEFAULT_RESULTS_CSV, ladder_tier as book_ladder_tier,
)
from scripts.journal.lib import analysis as janalysis  # noqa: E402
from scripts.journal import s06_recommend as recommend  # noqa: E402
from scripts.journal import s03_risk as jrisk  # noqa: E402
from scripts.journal.config import (  # noqa: E402
    DELTA_SOURCE_BARCHART, JUDGMENT_MODEL, PositionRisk,
)
from scripts.live_loop import mapping  # noqa: E402

JUDGMENT_CACHE = ROOT / "backtests" / "study_output" / "live-select-judgments.jsonl"

ENTRY_CHECKS = ("ibkr_verified", "analysis_only")

# Proxy methods that never produce a price path: `scripts/backtest/proxy.py`
# stamps them on a row it declined to price, so a pair whose only evaluation row
# carries one of them is invisible to selection however good the play was.
PROXY_UNPRICED = ("unevaluable", "underlying_trend")


class BudgetDrift(RuntimeError):
    """`recommend.DEPLOY_BUDGET` and `account.max_positions_per_day` disagree."""


class CacheMiss(RuntimeError):
    """A judgment prompt is not in the cache and live model calls are off."""


def assert_budgets_agree(max_per_day: int) -> None:
    """The per-day budget lives in two files and they agree today by coincidence.

    `recommend.DEPLOY_BUDGET` is what the live card deploys; `config/account-sim.yml`'s
    `account.max_positions_per_day` is what the simulation admits. If they ever
    drift, this arm silently stops being a simulation of the live card — the one
    failure it exists to prevent — so it refuses to run rather than reporting a
    book nobody would have traded.
    """
    if int(recommend.DEPLOY_BUDGET) != int(max_per_day):
        raise BudgetDrift(
            f"recommend.DEPLOY_BUDGET={recommend.DEPLOY_BUDGET} but "
            f"account.max_positions_per_day={max_per_day}. The live card and this "
            f"simulation would deploy a different number of positions per session; "
            f"fix the disagreement before reading anything from this arm.")


# ════════════════════════════════════════════════════════════════════════════
# The synthetic book — the sim's open positions in production's own shape
# ════════════════════════════════════════════════════════════════════════════

def synthetic_book(open_positions, equity: float, per_pos_cap: float,
                   net_cap: float) -> jrisk.BookRisk:
    """`risk.BookRisk` over the sim's currently-open `account_sim.Pos` records.

    Deltas come from the backtest export's entry-side `delta`, which is a
    Barchart measurement — so `delta_source` says `barchart` rather than a
    broker name, matching what `risk.delta_source()` would have stamped on a
    Flex-path position. A record with no delta is put in `unpriced` and left out
    of the totals, exactly as a live position with no broker greek would be:
    `signed_dn()` returns 0.0 for such a record, and treating that 0.0 as a real
    zero here would understate the simulated book the same way it would
    understate a live one.
    """
    priced: list[PositionRisk] = []
    unpriced: list[PositionRisk] = []
    for p in open_positions:
        rec = p.rec
        has_delta = rec.get("delta") is not None
        pos = PositionRisk(
            conid_key=f"{rec['date']}|{rec['ticker']}|{rec['structure']}",
            ticker=rec["ticker"], structure=rec["structure"],
            contracts=p.contracts,
            position_delta=rec.get("delta"),
            delta_notional=p.dn if has_delta else None,
            short_leg_delta=rec.get("delta"),
            dte=rec.get("dte"),
            delta_source=DELTA_SOURCE_BARCHART if has_delta else "unavailable",
        )
        (priced if has_delta else unpriced).append(pos)

    caps = jrisk.Caps(per_position=per_pos_cap, net=net_cap, net_liq=float(equity))
    net = sum(p.delta_notional for p in priced)
    gross = sum(abs(p.delta_notional) for p in priced)
    return jrisk.BookRisk(positions=priced, unpriced=unpriced, caps=caps,
                          net_delta_notional=net, gross_delta_notional=gross)


# ════════════════════════════════════════════════════════════════════════════
# Entry check — the §3 fields an analysis row does not carry
# ════════════════════════════════════════════════════════════════════════════

def rec_key(rec) -> tuple:
    return (rec["date"], rec["ticker"], rec["structure"])


def records_by_key(recs) -> dict[tuple, dict]:
    """`(date, ticker, structure) -> record`, real preferred over proxy.

    `load_book` already drops a proxy row whose key exists in the real book, so
    a collision here means two proxy rows for one structure; the first wins and
    the count is reported by the caller rather than resolved silently.
    """
    out: dict[tuple, dict] = {}
    for r in recs:
        k = rec_key(r)
        if k not in out or (r["source"] == "real" and out[k]["source"] != "real"):
            out[k] = r
    return out


def join_entry_check(ac_df: pd.DataFrame, by_key: dict[tuple, dict], mode: str,
                     budget: float) -> tuple[pd.DataFrame, dict]:
    """`(frame, stats)` — the analysis frame with §3's fields joined, or not.

    `ibkr_verified` writes `short_leg_delta`, `delta` and `delta_notional` onto
    each play row from the book record for that (date, ticker, structure), which
    is the measurement the operator would have read at order entry.
    `delta_notional` is estimated at the sizing the study would actually have
    used — `max(1, int(budget / max_loss))` contracts — because a per-contract
    figure would make every headroom check trivially pass and say nothing.

    `analysis_only` returns the frame untouched: `rank()` then sees no delta,
    which is what the deploy card alone can see. NEITHER mode invents a value —
    a pair with no book record gets nothing in either mode.

    The frame is copied, never mutated in place; the caller's `ac_df` is also
    what the coverage census reads.
    """
    if mode not in ENTRY_CHECKS:
        raise ValueError(f"entry_check must be one of {ENTRY_CHECKS}, got {mode!r}")

    # Deferred: account_sim imports this module, so a module-level import here
    # would be circular. Nothing else in this file needs it at import time.
    from scripts.backtest_study.f4_deployment.account_sim import risk_contracts, signed_dn

    out = ac_df.copy()
    stats = {"mode": mode, "rows": 0, "joined": 0, "no_record": 0}
    if mode == "analysis_only":
        stats["rows"] = int((out["ticker"] != janalysis.MARKET_TICKER).sum())
        stats["no_record"] = stats["rows"]
        return out, stats

    deltas: list[float | None] = []
    dns: list[float | None] = []
    for _, row in out.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        if ticker == janalysis.MARKET_TICKER:
            deltas.append(None)
            dns.append(None)
            continue
        stats["rows"] += 1
        structure = mapping.play_structure(row.get("play", ""))
        rec = by_key.get((str(row.get("date", "")), ticker, structure))
        if rec is None or rec.get("delta") is None:
            stats["no_record"] += 1
            deltas.append(None)
            dns.append(None)
            continue
        stats["joined"] += 1
        deltas.append(rec["delta"])
        contracts = risk_contracts(rec.get("max_loss_per_contract"), budget) or 1
        dns.append(signed_dn(rec, contracts))

    out["short_leg_delta"] = deltas
    out["delta"] = deltas
    out["delta_notional"] = dns
    return out, stats


# ════════════════════════════════════════════════════════════════════════════
# The judgment layer — cached, collision-guarded, never promoting
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class JudgmentCache:
    """A `sha256(prompt)` -> raw response store, appended to as a JSONL ledger.

    The file is the arm's evidence, not an optimisation: a run that replays from
    it is reproducible, and a reader can check what the model was asked and what
    it answered without re-running anything. Rows are appended, never rewritten,
    so a changed prompt leaves the old answer visible beside the new one.
    """

    path: Path = JUDGMENT_CACHE
    model: str = JUDGMENT_MODEL
    allow_calls: bool = True
    invoke_fn = None                       # None -> recommend._default_invoke
    hits: int = 0
    misses: int = 0
    _store: dict[str, str] = field(default_factory=dict)
    _session: str = ""

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("prompt_sha256") and row.get("model") == self.model:
                    self._store[row["prompt_sha256"]] = row.get("response", "")

    @staticmethod
    def key(prompt_text: str) -> str:
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    def for_date(self, session: str) -> None:
        """Stamp the session onto the next row written — the cache is keyed by
        prompt, but a reader wants to know which day an answer belongs to."""
        self._session = str(session)

    def invoke(self, prompt_text: str) -> str:
        k = self.key(prompt_text)
        if k in self._store:
            self.hits += 1
            return self._store[k]
        if not self.allow_calls:
            raise CacheMiss(
                f"judgment prompt {k[:12]} for session {self._session} is not in "
                f"{self.path.name} and live model calls are disabled")
        fn = self.invoke_fn or recommend._default_invoke
        response = fn(prompt_text)
        self.misses += 1
        self._store[k] = response
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "prompt_sha256": k,
                "model": self.model,
                "session": self._session,
                "response": response,
                "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }) + "\n")
        return response


def judgment_context(session: str, market_regime: str) -> str:
    """The context block `judge()` is given for a historical session.

    Deliberately thin, and deliberately says so. In live use this is the
    operator's read of the open; here there is no such read, and inventing one
    from anything dated after the session would be the lookahead the whole arm
    is trying to bound. What IS supplied is the analysis's own market-row regime,
    which was written before the session it applies to.
    """
    return (
        f"Session: {session}. This is a historical replay inside a research "
        f"simulation, not a live session.\n"
        f"Market regime read written by the analysis for this session: "
        f"{market_regime or '(none recorded)'}\n"
        "No information from during or after this session is available to you and "
        "none is supplied here. Where this context does not settle a question, "
        "answer \"unknown\" — do not fill the gap from memory of what these "
        "tickers went on to do.")


def ticker_collisions(candidates) -> dict[str, int]:
    """`{ticker: n}` for tickers carrying more than one candidate on one date.

    `judge()` keys its verdicts BY TICKER, so two plays on the same ticker on the
    same date would both receive whichever verdict came back for it — one read of
    one play, silently annotating another. Rare live, present historically.
    """
    counts = Counter(c.ticker for c in candidates)
    return {t: n for t, n in counts.items() if n > 1}


def strip_collided_verdicts(candidates, collided: dict[str, int]) -> None:
    """Undo `judge()`'s annotation on every candidate of a collided ticker.

    The alternative — leaving it — is one play's verdict demoting a different
    play. Blanking both is the same state the card shows for "judgment not run",
    which `render()` already treats as no verdict rather than a "no".
    """
    for c in candidates:
        if c.ticker not in collided:
            continue
        c.trigger_verdict = c.trigger_note = None
        c.alt_verdict = c.alt_note = None
        c.demoted = False
        c.demote_reasons = []


def g6_violations(survivors: set[str], selected) -> list[str]:
    """Tickers in the deploy set that `rank()` never cleared — G6's whole test.

    Structurally this cannot happen in this module (the deploy list is built from
    `rank()`'s own objects, and `judge()` independently drops a non-survivor), but
    an invariant asserted only by reading the code is not enforced. The
    never-promote rule is the one production guarantee this arm could quietly
    break, so it is checked at the sim boundary as well.
    """
    return sorted({t for t in selected if t not in survivors})


# ════════════════════════════════════════════════════════════════════════════
# The ranker — the hook `account_sim.simulate()` calls once per session
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DayTrace:
    """What the selector did on one session, kept for the report."""

    date: str
    survivors: list[str] = field(default_factory=list)      # deploy role, in order
    hedge: list[str] = field(default_factory=list)
    veto: list[str] = field(default_factory=list)
    tier_c: list[str] = field(default_factory=list)
    demoted: list[str] = field(default_factory=list)
    unpriceable: list[tuple] = field(default_factory=list)  # (ticker, structure, why)
    offered: list[tuple] = field(default_factory=list)      # rec keys handed to the ledger
    collisions: dict = field(default_factory=dict)
    judged: bool = False


class LiveRanker:
    """`simulate()`'s per-session ranker, backed by `recommend.rank()`/`judge()`.

    One instance per ledger walk. Two walks off ONE model pass share a
    `JudgmentCache`, so the second walk's prompts hit the cache and the model is
    asked nothing twice — which is also what makes the `skip`-vs-`ignore` delta
    a measurement of the judge layer alone rather than of two model samples.
    """

    def __init__(self, ac_df, by_key, st, *, demote_policy: str,
                 judgment_cache: JudgmentCache | None):
        if demote_policy not in ("skip", "ignore"):
            raise ValueError(f"demote_policy must be skip|ignore, got {demote_policy!r}")
        self.ac_df = ac_df
        self.by_key = by_key
        self.st = st
        self.demote_policy = demote_policy
        self.cache = judgment_cache
        self.market_regime = janalysis.market_regime_by_date(ac_df)
        self.traces: dict[str, DayTrace] = {}
        self.g6: list[tuple[str, list[str]]] = []
        self.dropped_tickers: Counter = Counter()
        self.judge_warnings: list[str] = []

    def __call__(self, session, ranked, open_pos, ledger, net_open, marked):
        d = str(session)
        book = synthetic_book(open_pos, marked, self.st.per_pos_cap, self.st.net_cap)
        candidates, rejected = recommend.rank(self.ac_df, d, book, net_liq=marked)
        deploy = [c for c in candidates if c.role == "deploy"]
        hedge = [c for c in candidates if c.role == "hedge"]

        trace = DayTrace(date=d,
                         survivors=[c.ticker for c in deploy],
                         hedge=[c.ticker for c in hedge],
                         veto=[r.ticker for r in rejected if r.tier == "VETO"],
                         tier_c=[r.ticker for r in rejected if r.tier == "C"])
        trace.collisions = ticker_collisions(candidates)

        if self.cache is not None and (deploy or hedge):
            self.cache.for_date(d)
            result = recommend.judge(
                candidates,
                judgment_context(d, self.market_regime.get(d, "")),
                invoke=self.cache.invoke)
            trace.judged = bool(result.get("ran"))
            for t in result.get("dropped_tickers", []):
                self.dropped_tickers[t] += 1
            for w in result.get("warnings", []):
                if "not a Part-A survivor" not in w:
                    self.judge_warnings.append(f"{d}: {w}")
            # 2e: one verdict must never annotate two plays (see the helper).
            strip_collided_verdicts(candidates, trace.collisions)
            trace.demoted = [c.ticker for c in deploy if c.demoted]

        ordered = deploy
        if self.demote_policy == "skip":
            ordered = [c for c in deploy if not c.demoted]

        offered = []
        for c in ordered:
            rec = self.by_key.get((d, c.ticker, c.structure))
            if rec is None:
                trace.unpriceable.append((c.ticker, c.structure, "no priceable record"))
                continue
            offered.append(rec)
        trace.offered = [rec_key(r) for r in offered]

        # G6, at the boundary: nothing may reach the ledger that `rank()` did not
        # clear as a deploy-role survivor on this date.
        bad = g6_violations(set(trace.survivors), [r["ticker"] for r in offered])
        if bad:
            self.g6.append((d, bad))

        self.traces[d] = trace
        return offered


# ════════════════════════════════════════════════════════════════════════════
# Evaluation coverage — which analysis pairs selection could even see
# ════════════════════════════════════════════════════════════════════════════

def evaluation_index(results_csv=None, proxy_csv=None) -> dict[tuple, dict[str, str]]:
    """`(date, ticker) -> {structure: method}` over BOTH evaluation exports.

    `method` is `"real"` for a BacktestResults row and the row's own
    `proxy_method` for a BacktestProxy row. Read straight off the CSVs rather
    than off `load_book`, because the question this answers is "what evaluation
    exists at all", including the rows the book deliberately drops.
    """
    out: dict[tuple, dict[str, str]] = defaultdict(dict)
    for path, method_of in ((results_csv or DEFAULT_RESULTS_CSV, lambda r: "real"),
                            (proxy_csv or DEFAULT_PROXY_CSV,
                             lambda r: r.get("proxy_method", "") or "unknown")):
        path = Path(path)
        if not path.exists():
            continue
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                key = (str(row.get("signal_date", ""))[:10],
                       str(row.get("ticker", "")).strip().upper())
                structure = str(row.get("structure", "")).strip()
                cell = out[key]
                method = method_of(row)
                # A real row outranks a proxy row for the same structure — that
                # is the same precedence `load_book` applies when it dup-drops.
                if structure not in cell or method == "real":
                    cell[structure] = method
    return dict(out)


def unpriceable_reason(pair_key: tuple, structure: str, evals: dict,
                       by_key: dict) -> str:
    """Why a ranked candidate never reached the ledger, in the arm's vocabulary.

    Ordered from most specific to least, so the bucket names an actual cause
    rather than the first test that happened to fail.
    """
    cell = evals.get(pair_key)
    if not cell:
        return "no_evaluation_row"
    if structure not in cell:
        return "structure_mismatch"
    method = cell[structure]
    if method in PROXY_UNPRICED:
        return method
    if method == "bs_options_hist":
        return "bs_options_hist"
    # It was priced (real, or a strike/expiry tweak) and still is not in the
    # arm's universe — the exact-replay calibration gate withheld it. That is
    # the population `--structure-universe` exists for.
    if (pair_key[0], pair_key[1], structure) not in by_key:
        return "withheld_by_calibration_gate"
    return "priceable"


# ════════════════════════════════════════════════════════════════════════════
# Ladder divergence — mapping.ladder_tier() vs book.ladder_tier()
# ════════════════════════════════════════════════════════════════════════════

CAUSE_CREDIT_VETO = "§1.3 credit veto (RANGE + L-VOL)"
CAUSE_HEDGE = "§1.4 hedge carve-out (bear debit is never a selection play)"
CAUSE_DELTA = "§3 delta/DTE availability"
CAUSE_OTHER = "other"


def divergence_cause(structure: str, map_tier: str, map_reason: str) -> str:
    if map_tier == "VETO" and "credit play in RANGE" in map_reason:
        return CAUSE_CREDIT_VETO
    if structure in recommend._HEDGE_ONLY_STRUCTURES:
        return CAUSE_HEDGE
    if structure == "bull_put_spread":
        return CAUSE_DELTA
    return CAUSE_OTHER


def ladder_divergence(recs, *, entry_check: str) -> list[dict]:
    """One row per record whose two ladders disagree, itemised by cause.

    `mapping.ladder_tier()` is `docs/deployment-rules.md` §1-§3 as production
    encodes it; `book.ladder_tier()` is the research port that has since fallen
    behind it. Under `analysis_only` the delta is withheld from the production
    side too, which is what the card alone would have had — so the §3 bucket
    grows and the §1.3 bucket does not move.
    """
    rows = []
    for r in recs:
        structure = r["structure"]
        regime = r.get("market_regime") or ""
        dte = r["dte"] if r.get("dte") is not None else float("nan")
        delta = r.get("delta") if entry_check == "ibkr_verified" else None
        map_tier, partial, reason = mapping.ladder_tier(structure, regime, dte, delta)
        bt = book_ladder_tier(r)
        hedge_only = structure in recommend._HEDGE_ONLY_STRUCTURES
        if bt == map_tier and not (hedge_only and bt in ("A", "B")):
            continue
        rows.append(dict(date=r["date"], ticker=r["ticker"], structure=structure,
                         source=r["source"], book_tier=bt, map_tier=map_tier,
                         partial=partial, reason=reason,
                         cause=divergence_cause(structure, map_tier, reason)))
    return rows


def credit_veto_population(results_csv=None, proxy_csv=None) -> dict:
    """The §1.3 population counted on the RAW exports, per file.

    Counted here rather than off `load_book` because the claim this checks — "23
    export rows, 8 in BacktestResults and 15 in BacktestProxy" — is about the
    exports themselves, before the book drops duplicates, `bs_options_hist` rows
    and rows that fail the exact-replay gate. A count taken after those drops
    would appear to refute the claim by measuring something else.
    """
    out = {"by_file": {}, "by_structure": Counter(), "total": 0}
    for label, path in (("BacktestResults", results_csv or DEFAULT_RESULTS_CSV),
                        ("BacktestProxy", proxy_csv or DEFAULT_PROXY_CSV)):
        path = Path(path)
        n = 0
        if path.exists():
            with path.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    structure = str(row.get("structure", "")).strip()
                    regime = str(row.get("market_regime") or "")
                    map_tier, _, reason = mapping.ladder_tier(
                        structure, regime, float("nan"), None)
                    if map_tier != "VETO" or "credit play in RANGE" not in reason:
                        continue
                    stub = dict(structure=structure, market_regime=regime,
                                delta=None, dte=None)
                    if book_ladder_tier(stub) == "VETO":
                        continue
                    n += 1
                    out["by_structure"][structure] += 1
        out["by_file"][label] = n
        out["total"] += n
    return out


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def _counter_line(counter: Counter, sep: str = "  ") -> str:
    return sep.join(f"{k}={v}" for k, v in sorted(counter.items())) or "(none)"


def print_preamble(st, entry_check: str, use_llm: bool, cache: JudgmentCache | None) -> None:
    hdr("LIVE SELECT — the SHIPPED selector (recommend.rank + judge) under history")
    judgment_line = ("cached judge() pass, model " + JUDGMENT_MODEL if use_llm
                     else "NOT RUN (--live-select-no-llm) — deterministic rank() only")
    print(f"""  This arm replaces account_sim's own ladder (book.py::ladder_tier) with the
  function that actually decides what gets deployed: scripts/journal/s06_recommend.py's
  rank() — which encodes docs/deployment-rules.md §1-§3 exactly once, via
  scripts/live_loop/mapping.ladder_tier — followed by judge(), the single
  demote-only model call. Pricing, sizing, admission and exit replay are
  account_sim's frozen machinery, unchanged and unreachable from here.

  NOT the frozen basis and not a criterion. A1-A6 were pre-registered against the
  frozen selector and DO NOT TRANSFER to a different candidate set; none of them
  is evaluated here. What this arm reports is coverage, divergence, and the two
  books the selector produces — no verdict, no adoption.

  entry check   {entry_check}
  judgment      {judgment_line}""")
    if use_llm and cache is not None:
        try:
            cache_name = cache.path.relative_to(ROOT)
        except ValueError:      # a stub cache outside the repo — print it whole
            cache_name = cache.path
        print(f"  cache         {cache_name}")
    print(f"""  budget check  recommend.DEPLOY_BUDGET={recommend.DEPLOY_BUDGET} ==
                account.max_positions_per_day={st.max_per_day}  OK""")
    if use_llm:
        print("""
  LOOKAHEAD CAVEAT, printed in full because no gate can replace it. JUDGMENT_MODEL
  is claude-opus-5, whose knowledge cutoff overlaps these analysis dates. judge()
  may therefore "remember" what a ticker went on to do, and G5 CANNOT DETECT THIS
  — G5 blinds record fields, not model weights, and journal/lib/prompt.py's "do not use any
  outside knowledge of these tickers" is necessary and not sufficient. The bound
  this arm can offer is a measurement, not an assurance: the two ledger walks
  below run off ONE model pass with demote_policy skip and ignore, and their
  difference is the judge layer's entire effect on the book — and therefore an
  upper bound on its lookahead exposure. Read that delta before reading anything
  else the judge layer touched.""")


def print_selection_coverage(ac_df, by_key, evals, traces, picked_frozen, st,
                             entry_stats: dict) -> dict:
    """How much of the frozen book is an artifact of what happened to be priceable.

    Every (date, ticker) analysis pair is placed in exactly one bucket and the
    residual is printed. A coverage section that does not add up is not a
    coverage section — it is a subset with an opinion.
    """
    hdr("SELECTION COVERAGE — what the selector saw, and what it could never see")

    plays = ac_df[ac_df["ticker"] != janalysis.MARKET_TICKER]
    pairs = {(str(r["date"]), str(r["ticker"])) for _, r in plays.iterrows()}
    print(f"""  The frozen book only ever ranks rows the backtest could PRICE. This section
  asks the other question: of every play the analysis actually emitted, which
  ones reached selection at all. No P&L, no dollars, no ledger effect — a row
  counted here as unpriceable is never deployed and never assigned an outcome.

  analysis population   {len(pairs):,} (date, ticker) pairs over {plays['date'].nunique()} dates
                        {len(plays):,} play rows ({len(plays) - len(pairs)} extra rows on
                        pairs carrying more than one play)
  entry check           {entry_stats['mode']}: {entry_stats['joined']:,} of {entry_stats['rows']:,} play rows joined a
                        measured entry-side delta; {entry_stats['no_record']:,} got none""")

    # -- bucket every pair, exactly once ------------------------------------
    ranked_deploy: dict[tuple, str] = {}
    ranked_hedge: set[tuple] = set()
    ranked_veto: set[tuple] = set()
    ranked_c: set[tuple] = set()
    deployed: set[tuple] = set()
    for d, tr in traces.items():
        for t in tr.survivors:
            ranked_deploy[(d, t)] = "deploy"
        ranked_hedge |= {(d, t) for t in tr.hedge}
        ranked_veto |= {(d, t) for t in tr.veto}
        ranked_c |= {(d, t) for t in tr.tier_c}
        deployed |= {(k[0], k[1]) for k in tr.offered}

    seen_dates = set(traces)
    buckets: Counter = Counter()
    unpriced_reasons: Counter = Counter()
    unpriced_by_year: Counter = Counter()
    for pair in sorted(pairs):
        d, ticker = pair
        if d not in seen_dates:
            # The ledger walk only visits dates the BOOK has a record for. A
            # date with analysis and no priceable row anywhere is invisible to
            # selection in its entirety, which is exactly the bias being counted.
            buckets["date never reached selection (no priceable row that session)"] += 1
            continue
        if pair in ranked_deploy:
            if pair in deployed:
                buckets["ranked as a deploy candidate, priceable"] += 1
            else:
                buckets["ranked as a deploy candidate, UNPRICEABLE"] += 1
                structure = _structure_of(plays, d, ticker)
                unpriced_reasons[unpriceable_reason(pair, structure, evals, by_key)] += 1
                unpriced_by_year[d[:4]] += 1
        elif pair in ranked_hedge:
            buckets["§4 hedge-sleeve candidate (never a selection play)"] += 1
        elif pair in ranked_veto:
            buckets["§1 VETO"] += 1
        elif pair in ranked_c:
            buckets["Tier C (capital-constrained)"] += 1
        else:
            buckets["not ranked (no play row for this date/ticker in rank())"] += 1

    sub("every analysis pair, in exactly one bucket")
    for name, n in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>6,}  {name}")
    total = sum(buckets.values())
    residual = len(pairs) - total
    print(f"  {total:>6,}  TOTAL          residual against the {len(pairs):,}-pair "
          f"population: {residual}")
    if residual:
        print("  RESIDUAL IS NON-ZERO — the buckets above do not partition the "
              "population and nothing in this section can be trusted.")

    sub("ranked but unpriceable, by cause")
    if not unpriced_reasons:
        print("  (none — every ranked deploy candidate had a priceable record)")
    else:
        for name, n in sorted(unpriced_reasons.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>6,}  {name}")
        print(f"\n  by year: {_counter_line(unpriced_by_year)}")

    # -- displacement: a slot taken by a lower-ranked play ------------------
    sub("displacement — deploy slots filled from below the selector's own top-"
        f"{st.max_per_day}")
    displaced_slots = 0
    displaced_dates = 0
    for d, tr in sorted(traces.items()):
        if not tr.offered:
            continue
        # A pick's rank in the selector's OWN order, unpriceable candidates
        # included. One that sits at or past the day's budget only reached the
        # deploy set because something above it had no priceable record — that,
        # and not "a lower-ranked row was taken", is the displacement.
        order = {t: i for i, t in enumerate(tr.survivors)}
        moved = sum(1 for k in tr.offered[:st.max_per_day]
                    if order.get(k[1], 0) >= st.max_per_day)
        if moved:
            displaced_slots += moved
            displaced_dates += 1
    print(f"""  {displaced_slots} deploy slot(s) across {displaced_dates} session(s) went to a play the selector
  itself ranked BELOW its own top-{st.max_per_day}, purely because a higher-ranked candidate had
  no priceable record. That is the honest size of the pricing bias in the frozen
  book's composition — a book selected on structure would not contain them.""")

    # -- composition diff against the frozen book ---------------------------
    sub("composition against the frozen book's picks")
    frozen_ids = {(r["date"], r["ticker"], r["structure"]) for r in picked_frozen}
    live_ids = {k for tr in traces.values() for k in tr.offered[:st.max_per_day]}
    print(f"  frozen picks {len(frozen_ids)}   live-select offers "
          f"{len(live_ids)}   shared {len(frozen_ids & live_ids)}")
    print(f"  only frozen  {len(frozen_ids - live_ids)}   only live-select "
          f"{len(live_ids - frozen_ids)}")
    print("  by structure, frozen:      "
          + _counter_line(Counter(k[2] for k in frozen_ids)))
    print("  by structure, live-select: "
          + _counter_line(Counter(k[2] for k in live_ids)))
    return dict(pairs=len(pairs), buckets=dict(buckets), residual=residual,
                unpriced_reasons=dict(unpriced_reasons),
                displaced_slots=displaced_slots, displaced_dates=displaced_dates)


def tier_census(frame: pd.DataFrame) -> Counter:
    """`rank()`'s outcome for every play row in `frame`, over every date it has.

    Runs the real `rank()` against an EMPTY book, which is sound because `rank()`
    reads the book only to annotate (see this module's docstring): the tier a play
    receives and the order it comes back in are the same whatever is open. The
    empty book is therefore not a simplification, it is the same answer without
    the ledger.
    """
    census: Counter = Counter()
    empty = jrisk.BookRisk()
    for d in janalysis.analysis_dates(frame):
        candidates, rejected = recommend.rank(frame, d, empty, net_liq=None)
        for c in candidates:
            census[f"{c.role} Tier {c.tier}" + (" (partial)" if c.tier_partial else "")] += 1
        for r in rejected:
            census[f"rejected {r.tier}"] += 1
    return census


def print_entry_check_comparison(ac_df: pd.DataFrame, by_key: dict, budget: float,
                                 active: str) -> None:
    """Both §3 entry-check modes, side by side — neither is "the" answer.

    deployment-rules.md §3 says the short-leg delta and the DTE are read in IBKR
    at order entry, so the analysis row genuinely does not carry them and the
    card genuinely cannot verify the gate. `ibkr_verified` reconstructs what the
    operator would have seen; `analysis_only` shows what he would have had to
    deploy on without looking. The gap between the two columns is the size of
    that unverified region, and it is the reason this knob exists rather than a
    default nobody chose.
    """
    sub("§3 entry check — what the ladder can verify, in both modes")
    frames = {}
    for mode in ENTRY_CHECKS:
        frames[mode], _ = join_entry_check(ac_df, by_key, mode, budget)
    censuses = {mode: tier_census(f) for mode, f in frames.items()}
    keys = sorted(set(censuses[ENTRY_CHECKS[0]]) | set(censuses[ENTRY_CHECKS[1]]))
    print(f"  {'rank() outcome':<34}{'ibkr_verified':>15}{'analysis_only':>15}")
    for k in keys:
        a = censuses["ibkr_verified"].get(k, 0)
        b = censuses["analysis_only"].get(k, 0)
        print(f"  {k:<34}{a:>15,}{b:>15,}")
    print(f"\n  This run selected under: {active}")


def _structure_of(plays: pd.DataFrame, d: str, ticker: str) -> str:
    """The structure `rank()` derived for a (date, ticker) — the first play row's.

    First, not "the" row: a pair with two plays is exactly the collision case
    §2e names, and the report counts those separately rather than pretending the
    pair has one structure.
    """
    hit = plays[(plays["date"] == d) & (plays["ticker"] == ticker)]
    if hit.empty:
        return ""
    return mapping.play_structure(hit.iloc[0].get("play", ""))


def print_ladder_divergence(recs, entry_check: str) -> dict:
    hdr("LADDER DIVERGENCE — the research ladder against the shipped one")
    print("""  book.py::ladder_tier is a 2026-07 port of the deployment ladder; production
  encodes the same rules once, in scripts/live_loop/mapping.ladder_tier. The port
  has since fallen behind. Every disagreement below is a row the simulation and
  the live card would treat differently — itemised by cause, not asserted.""")

    rows = ladder_divergence(recs, entry_check=entry_check)
    sub(f"candidate universe: {len(recs):,} book records")
    if not rows:
        print("  (no disagreement)")
    else:
        by_cause = Counter(r["cause"] for r in rows)
        for cause, n in sorted(by_cause.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>4}  {cause}")
        print(f"  {len(rows):>4}  TOTAL")
        print("\n  by tier transition (book -> shipped): "
              + _counter_line(Counter(f"{r['book_tier']}->{r['map_tier']}" for r in rows)))
        print("  by source:    " + _counter_line(Counter(r["source"] for r in rows)))
        print("  by structure: " + _counter_line(Counter(r["structure"] for r in rows)))

    sub("§1.3 credit veto, counted on the RAW exports")
    pop = credit_veto_population()
    print("""  The clause the port is missing: a CREDIT play in a RANGE + L-VOL market is a
  §1 veto in production and a Tier-B deploy candidate in the port. Counted on the
  export rows themselves, before the book drops duplicates, bs_options_hist rows,
  and rows that fail the exact-replay gate.""")
    for label, n in pop["by_file"].items():
        print(f"  {n:>4}  {label}")
    print(f"  {pop['total']:>4}  TOTAL   by structure: "
          + _counter_line(pop["by_structure"]))
    return dict(rows=rows, credit_veto=pop)


def print_judgment(rankers, cache: JudgmentCache | None, use_llm: bool) -> dict:
    hdr("JUDGMENT LAYER — one model pass, two ledger walks, and what it moved")
    if not use_llm:
        print("""  NOT RUN (--live-select-no-llm). Both ledger walks below are the deterministic
  rank() ordering, so demote_policy skip and ignore are identical BY CONSTRUCTION
  and their agreement says nothing about the judge layer. Re-run without the flag
  to measure it.""")
        return {}

    skip_ranker, _ = rankers
    judged = sum(1 for t in skip_ranker.traces.values() if t.judged)
    collided = {d: t.collisions for d, t in skip_ranker.traces.items() if t.collisions}
    demoted = sum(len(t.demoted) for t in skip_ranker.traces.values())
    print(f"""  sessions judged        {judged}
  cache hits / misses    {cache.hits} / {cache.misses}   ({cache.path.name})
  candidates demoted     {demoted}
  tickers dropped by judge() as non-survivors: """
          + (_counter_line(skip_ranker.dropped_tickers)
             if skip_ranker.dropped_tickers else "(none)"))
    if skip_ranker.judge_warnings:
        print("  warnings:")
        for w in skip_ranker.judge_warnings[:10]:
            print(f"    {w}")

    sub("§2e same-ticker collisions — one verdict must not annotate two plays")
    if not collided:
        print("  (none on any judged session)")
    else:
        print(f"  {len(collided)} session(s) carried a ticker with more than one play. "
              f"judge() keys its\n  verdicts by ticker, so the second play would have "
              f"silently taken the first's\n  verdict; the annotation was blanked on "
              f"both instead, and the sessions are:")
        for d, cell in sorted(collided.items()):
            print(f"    {d}  " + ", ".join(f"{t} x{n}" for t, n in sorted(cell.items())))
    return dict(judged=judged, collisions=collided, demoted=demoted,
                hits=cache.hits, misses=cache.misses)


def print_books(sims: dict, frozen_sim, st, use_llm: bool) -> None:
    """The three books side by side. Descriptive only — no criterion is evaluated."""
    hdr("BOOKS — frozen selector against the shipped selector, both demote policies")
    print("""  Same ledger, same sizing, same frozen exit replay. The only difference is who
  chose.""")
    if use_llm:
        print("""  The skip/ignore pair is the judge layer's entire effect on the book (see the
  LOOKAHEAD CAVEAT above); if those two rows are identical, the model changed
  nothing on this population and its lookahead exposure is bounded at zero.""")
    else:
        print("""  judge() did not run, so the skip/ignore pair is identical by construction and
  bounds nothing. It is printed anyway rather than hidden — a section that
  appears only on some runs is a section a reader stops looking for.""")
    print(f"\n  {'book':<34}{'n':>5}{'dates':>7}{'dollars':>13}{'mean R':>10}{'win':>8}")
    rows = [("frozen ladder (book.py)", frozen_sim)]
    rows += [(f"live-select, demote={k}", s) for k, s in sims.items()]
    for label, sim in rows:
        stats = P.replay_stats(sim.rows())
        win = stats["win"]
        # A book with no priced rows has win == nan; printing "0%" for it would
        # be a claim, so the column says nothing instead.
        win_col = f"{win:>8.0%}" if win == win else f"{'—':>8}"
        mean_r = stats["mean_R"]
        r_col = f"{mean_r:>+10.3f}" if mean_r == mean_r else f"{'—':>10}"
        print(f"  {label:<34}{stats['n']:>5}{stats['dates']:>7}"
              f"{stats['dollars']:>13,.0f}{r_col}{win_col}")

    skip, ignore = sims.get("skip"), sims.get("ignore")
    if skip is not None and ignore is not None:
        a = {(p.rec["date"], p.rec["ticker"], p.rec["structure"], p.contracts)
             for p in skip.signal_pos}
        b = {(p.rec["date"], p.rec["ticker"], p.rec["structure"], p.contracts)
             for p in ignore.signal_pos}
        sub("demote_policy delta — the judge layer's whole effect")
        print(f"  positions only under skip: {len(a - b)}   only under ignore: "
              f"{len(b - a)}   shared: {len(a & b)}")
        print(f"  dollars  skip ${skip.dollars:,.0f}   ignore ${ignore.dollars:,.0f}   "
              f"difference ${skip.dollars - ignore.dollars:+,.0f}")
        if a == b and use_llm:
            print("  The two books are IDENTICAL: judge() demoted nothing that changed "
                  "a deployment,\n  so its lookahead exposure on this population is "
                  "bounded at zero.")


def build_walk(recs, ac_df, st, *, entry_check: str, policy: str,
               replay_cache, judgment_cache, label: str):
    """`(sim, ranker, entry_stats)` — one ledger walk under the shipped selector.

    Factored out because G5 has to run the SAME walk over blinded records: a gate
    that re-implements the thing it checks proves only that two implementations
    agree.
    """
    # Deferred: account_sim imports this module (see join_entry_check).
    from scripts.backtest_study.f4_deployment import account_sim as A

    by_key = records_by_key(recs)
    frame, entry_stats = join_entry_check(ac_df, by_key, entry_check, st.budget)
    # eligible_fn=None on purpose: the shipped selector decides eligibility, so
    # the walk must be handed every record the date has, not the subset the
    # research ladder already called A/B.
    day_lists = P.ordered_by_day(recs, P.ladder_rank, None)
    ranker = LiveRanker(frame, by_key, st, demote_policy=policy,
                        judgment_cache=judgment_cache)
    sim = A.simulate(day_lists, st.cfg(label), cache=replay_cache, ranker=ranker)
    return sim, ranker, entry_stats


def print_gate5_arm(recs, ac_df, st, *, entry_check: str, judgment_cache,
                    sighted: dict) -> bool:
    """G5, re-run with the SHIPPED selector in the loop.

    G2-G4 stay pinned to the frozen basis — G2 is an identity against the profile
    that generated the stored rows and G4 is about the frozen ordering, and
    neither may move because an arm changed who selects. (There is no G1: the
    book-calibration checksum was removed 2026-08-15 and its numbers are now
    printed descriptively — see account_sim's BOOK CALIBRATION section.)
    G5 is different: it is a claim about
    THIS run's decision path, and this run's decision path is `rank()` + `judge()`
    rather than `ladder_rank`. Running it only on the frozen basis would leave
    the arm's own selector unchecked.

    `rank()` reads analysis fields and `judge()` reads a prompt built from them,
    so blinding the book records should be a no-op for both. If it is not, that
    is a real leak — a selector standing on a number that would not exist yet in
    real time — and the run fails.

    NOTE what this gate cannot reach, stated here because it is the arm's central
    weakness: it blinds RECORD FIELDS. `judge()`'s model weights are not a record
    field, and a model whose cutoff overlaps these dates can carry an outcome in
    its head. G5 passing says nothing about that; the skip/ignore delta is the
    only bound this arm has on it.
    """
    # Deferred: account_sim imports this module (see join_entry_check).
    from scripts.backtest_study.f4_deployment import account_sim as A

    sub("G5 (arm) — the SHIPPED selector is BLIND to how a position turned out")
    print("""  Every record is re-wrapped so reading an outcome key raises, AND the outcome
  columns are deleted from the underlying trade row so a read cannot route
  around the wrapper. Both ledger walks must then complete and produce a
  byte-identical book.""")
    blind = A.blind_records(recs)
    ok = True
    for policy, sighted_sim in sighted.items():
        try:
            blind_sim, _ranker, _stats = build_walk(
                blind, ac_df, st, entry_check=entry_check, policy=policy,
                # A FRESH replay memo: a blind result must never be served from a
                # sighted computation. The JUDGMENT cache is deliberately shared —
                # the prompt is built from analysis fields, so a blinded walk asks
                # exactly the same questions and must not be charged for them
                # twice.
                replay_cache=A.new_cache(), judgment_cache=judgment_cache,
                label=f"G5 blind {policy}")
        except A.LookaheadError as exc:
            print(f"  [{policy}] LOOKAHEAD DETECTED: {exc}")
            ok = False
            continue
        a = A.book_signature(sighted_sim)
        b = A.book_signature(blind_sim)
        n_diff = sum(1 for x, y in zip(a, b) if x != y)
        same = len(a) == len(b) and n_diff == 0 and len(a) > 0
        ok = ok and same
        print(f"  [{policy}] positions: sighted {len(a)}  blind {len(b)}  "
              f"differing {n_diff}")
        for x, y in zip(a, b):
            if x != y:
                print(f"    DIVERGED sighted {x}  vs blind {y}")
                break
    print(f"  G5 (arm): {'PASS' if ok else 'FAIL'}")
    return ok


def print_gate6(rankers) -> bool:
    sub("G6 — nothing reaches the ledger that rank() did not clear")
    print("""  The never-promote invariant, enforced at the sim boundary as well as inside
  recommend.judge(). A ticker in the deploy set that was not a Part-A survivor on
  that date is a promotion, and a promotion is the one thing the model layer is
  structurally forbidden to do.""")
    violations = [(d, bad) for r in rankers for d, bad in r.g6]
    for d, bad in violations[:5]:
        print(f"    VIOLATION {d}: {', '.join(bad)}")
    ok = not violations
    sessions = sum(len(r.traces) for r in rankers)
    print(f"  sessions checked: {sessions} ({len(rankers)} ledger walks x "
          f"{sessions // max(1, len(rankers))} sessions)   violations: {len(violations)}")
    print(f"  G6: {'PASS' if ok else 'FAIL'}")
    return ok


# ════════════════════════════════════════════════════════════════════════════
# Driver
# ════════════════════════════════════════════════════════════════════════════

def run_arm(recs, picked, st, cache, *, entry_check: str, use_llm: bool,
            allow_calls: bool = True, invoke_fn=None, cache_path=None) -> int:
    """The whole `--live-select` arm. Returns a process exit code.

    Called from `account_sim.main()` after the gates have passed on the frozen
    basis — G2-G4 are pinned there by design (G2 is an identity against the
    profile that generated the stored rows, G4 is about the frozen selection
    ordering) and G5 has already run on the same records this arm ranks.

    `invoke_fn` / `cache_path` exist so the judgment path can be exercised
    end-to-end against a stub without spending a model call or writing a
    fabricated answer into the real cache — the cache file is the arm's evidence
    of what the model said, and a test's answer has no business in it.
    """
    # Deferred: account_sim imports this module (see join_entry_check).
    from scripts.backtest_study.f4_deployment import account_sim as A

    assert_budgets_agree(st.max_per_day)

    judgment_cache = None
    if use_llm:
        judgment_cache = JudgmentCache(path=cache_path or JUDGMENT_CACHE,
                                       allow_calls=allow_calls)
        if invoke_fn is not None:
            judgment_cache.invoke_fn = invoke_fn

    print_preamble(st, entry_check, use_llm, judgment_cache)

    ac_df, source = janalysis.load(prefer_sheets=False)
    print(f"\n  analysis source: {source}")
    if ac_df.empty:
        print("  EMPTY analysis book — nothing to select from. Exit 1.")
        return 1

    by_key = records_by_key(recs)
    evals = evaluation_index()

    rankers = {}
    sims = {}
    entry_stats = {}
    for policy in ("skip", "ignore"):
        sims[policy], rankers[policy], entry_stats = build_walk(
            recs, ac_df, st, entry_check=entry_check, policy=policy,
            replay_cache=cache, judgment_cache=judgment_cache,
            label=f"live-select {policy}")

    frozen_sim = A.simulate(
        P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible),
        st.cfg("frozen ladder"), cache=cache)

    coverage = print_selection_coverage(ac_df, by_key, evals,
                                        rankers["ignore"].traces, picked, st,
                                        entry_stats)
    print_entry_check_comparison(ac_df, by_key, st.budget, entry_check)
    print_ladder_divergence(recs, entry_check)
    print_judgment((rankers["skip"], rankers["ignore"]), judgment_cache, use_llm)
    print_books(sims, frozen_sim, st, use_llm)

    hdr("GATES — G5 re-run with this arm's selector, plus G6 (G2-G4 stay pinned "
        "to the frozen basis)")
    g5 = print_gate5_arm(recs, ac_df, st, entry_check=entry_check,
                         judgment_cache=judgment_cache, sighted=sims)
    g6 = print_gate6(list(rankers.values()))

    stem, arm_col = A.positions_artifact(compounding=False,
                                         structure_universe=False,
                                         live_select=True)
    path = ROOT / "backtests" / "study_output" / stem
    n_rows = A.write_positions_csv(
        path, {"live_select_skip": sims["skip"], "live_select_ignore": sims["ignore"]},
        arm=arm_col)

    hdr("CLOSE")
    print(f"""  Nothing ships from this arm. It reports coverage and divergence; it evaluates
  no pre-registered criterion, and the frozen book above it is untouched.
  positions CSV: {n_rows} rows -> backtests/study_output/{stem}""")

    if not (g5 and g6):
        return 1
    if coverage["residual"]:
        return 1
    return 0
