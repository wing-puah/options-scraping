"""
Step 6 — "what is the best position to take from the analysis?"

PRODUCTION TIER. Three parts, deliberately separated so the deterministic work
never depends on the model and the model can never see more than the rules
already cleared:

    rank()    PART A — the deterministic ranker. Reads one date's analysis
              plays plus the open book and applies `config/deployment-rules.md`
              §0-§4 via `scripts/live_loop/mapping.ladder_tier` (the ONE
              encoding of §1-§3 — this module never reimplements a tier rule).
              Does all the real work; a `--no-llm` run is this function plus
              `render()` and nothing else.
    judge()   PART B — the ONE judgment call. Sees ONLY the survivors `rank()`
              returns (never a rejected/vetoed play) and is asked exactly three
              questions (see `prompt.py`). Structurally cannot promote, re-tier,
              or resurrect anything — see the module-level note above
              `judge()` for exactly how that is enforced.
    render()  PART C — a markdown deploy card. Stands on its own with the
              judgment section marked "not run" when `judge()` was never
              called; the AI is an annotation layer, not a dependency.

WHY `score_total` NEVER MOVES A PLAY BETWEEN TIERS. §6 of the rules is
explicit that it is a within-tier tie-break only and otherwise
decision-irrelevant. `rank()` computes tier from `mapping.ladder_tier()` alone
and only ever uses `score_total` as a `sort()` key WITHIN an already-decided
tier bucket — it is never part of the tier decision itself, and the hedge
sleeve (§4) never reads it at all.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field, replace

import pandas as pd

from . import analysis, prompt
from . import risk as risk_mod
from .config import (JUDGMENT_MAX_ATTEMPTS, JUDGMENT_MODEL, JUDGMENT_TIMEOUT_S,
                     RECOMMENDATION_MAX_AGE_DAYS)

try:
    from scripts.live_loop import mapping
except ImportError:  # pragma: no cover - alternate sys.path layout (tests/conftest.py)
    from live_loop import mapping

log = logging.getLogger(__name__)

# deployment-rules.md §0: "Budget: the analysis emits ~10 plays/day. Deploy 1-3."
DEPLOY_BUDGET = 3

# deployment-rules.md §1.4: bear debit is a hedge, never a selection play. It
# stays emitted/visible and is eligible for the §4 hedge sleeve, but is NEVER a
# `rank()` deploy candidate no matter how thin the day's A/B supply — ladder_tier()
# itself has no opinion on "selection vs hedge" (it is tier-neutral, shared with
# the fortnightly audit), so that split is this module's job, not mapping.py's.
_HEDGE_ONLY_STRUCTURES = ("bear_put_spread", "long_put")

# The caveat block PART C prints verbatim near the top of every card — see
# `render()`. Quoted from config/deployment-rules.md's own top-of-file
# blockquote plus its §6 v3/v4 note, not paraphrased, so the two documents
# cannot silently drift apart.
_V3_V4_CAVEAT = (
    "> **Derived on v3 rows; v4 transfer is not yet validated.** The "
    "pre-registered composition bridge has not fired. Until it does, deploy "
    "under these rules unchanged and expect them to be re-confirmed, not "
    "re-derived. — `config/deployment-rules.md`\n"
    ">\n"
    "> **v3 and v4 `score_total` are not comparable** (§6): v3 ran 0-100, v4 "
    "runs 0-50 (0-55 for VOLATILITY-intent plays). Every `score_total` on this "
    "card is a within-tier tie-break only and carries no other signal."
)


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------
@dataclass
class Candidate:
    """One play that survived §1's vetoes — either a deploy candidate (Tier A/B,
    `role="deploy"`) or a §4 hedge-sleeve candidate (`role="hedge"`).

    Every field through `headroom_note` is set by `rank()` and is never
    touched again. Everything from `trigger_verdict` on down starts blank and
    is filled in ONLY by `judge()`'s annotation pass (see the guard note
    there) — `render()` treats a blank verdict as "judgment not run/not
    applicable", never as a "no".
    """

    ticker: str
    play: str
    structure: str
    market_regime: str
    tier: str                 # ladder_tier()'s own label: "A", "B", or "C"
    tier_partial: bool
    tier_reason: str
    score_total: float | None
    horizon: str
    trigger: str
    invalidation: str
    alternative_interpretation: str
    role: str                 # "deploy" | "hedge"
    reasons: list[str] = field(default_factory=list)
    duplicate_exposure: bool = False
    delta: float | None = None
    headroom_ok: bool | None = None
    headroom_note: str = ""
    deploy: bool = False      # top-DEPLOY_BUDGET flag, role="deploy" only

    # --- judgment annotations (judge() only; rank() never sets these) -----
    trigger_verdict: str | None = None
    trigger_note: str | None = None
    alt_verdict: str | None = None
    alt_note: str | None = None
    demoted: bool = False
    demote_reasons: list[str] = field(default_factory=list)
    hedge_pick: bool = False

    def to_prompt_dict(self) -> dict:
        """The subset of fields `judge()` shows the model — see `prompt.py`."""
        return {
            "ticker": self.ticker, "tier": self.tier, "structure": self.structure,
            "play": self.play, "trigger": self.trigger,
            "invalidation": self.invalidation,
            "alternative_interpretation": self.alternative_interpretation,
            "delta": self.delta,
        }


@dataclass
class Rejected:
    """A play that did NOT survive §1-§4 as a deploy candidate: VETO (§1) or
    Tier C (capital-constrained). Kept visible in the card either way — a VETO
    is never hidden, and a thin day's Tier C plays are exactly what an operator
    would otherwise wonder about."""

    ticker: str
    play: str
    structure: str
    market_regime: str
    tier: str                 # "VETO" | "C"
    reason: str
    score_total: float | None = None


# --------------------------------------------------------------------------
# PART 0 — the time bound
# --------------------------------------------------------------------------
class StaleAnalysis(RuntimeError):
    """The chosen analysis session cannot support a deploy card: either too old
    to still be actionable, or — the unconditional case — dated AFTER the day
    the card is being built for."""


def check_freshness(session, as_of, *,
                    max_age_days: int = RECOMMENDATION_MAX_AGE_DAYS,
                    allow_stale: bool = False) -> tuple[int, str]:
    """`(staleness_days, note)` for a card. Raises `StaleAnalysis` if unusable.

    TWO REFUSALS, AND ONLY ONE OF THEM IS OVERRIDABLE. Keeping them apart is the
    whole point of this function:

      * `staleness > max_age_days` — the analysis is too cold to act on. A
        judgement call about actionability, so `allow_stale` may override it;
        an operator rebuilding a historical card, or coming back to a genuine
        11-day gap, has a real reason to look. The override is recorded on the
        card and on every persisted row, never silent.

      * `session > as_of` — the analysis did not EXIST yet. That is not
        staleness, it is lookahead, and there is no version of it that is a
        legitimate request. `allow_stale` does not reach it and must never be
        made to: a card ranked off plays published after the session it plans
        would look like foresight and be nothing of the kind.
    """
    days = analysis.staleness_days(session, as_of)
    if days is None:
        raise StaleAnalysis(
            f"Cannot date the analysis session ({session!r}) against as-of "
            f"({as_of!r}) — refusing to build a card whose age is unknown")

    if days < 0:
        raise StaleAnalysis(
            f"Analysis session {session} is AFTER the as-of date {as_of} "
            f"({-days} day(s) in the future). That is lookahead, not staleness: "
            "the card would rank plays that had not been published yet. "
            "--allow-stale does not override this.")

    if days > max_age_days:
        if not allow_stale:
            raise StaleAnalysis(
                f"Analysis session {session} is {days} days before the as-of "
                f"date {as_of}, past the {max_age_days}-day bound. Re-run the "
                "analysis pipeline, or pass --allow-stale to build the card "
                "anyway (it will be marked as stale).")
        return days, (f"**--allow-stale**: this card ranks analysis from {session}, "
                      f"{days} days before {as_of} and past the "
                      f"{max_age_days}-day bound. Treat it as a reconstruction, "
                      "not a read of today's tape.")

    return days, ""


# --------------------------------------------------------------------------
# PART A — the deterministic ranker
# --------------------------------------------------------------------------
def _optional_float(row, col: str) -> float | None:
    """Read an optional numeric column off an analysis row.

    Every analysis row today has none of the optional columns this looks for
    (`score_total` is the one exception, always present via
    `analysis._normalise`) — `delta` / `delta_notional` / `short_leg_delta` are
    not part of `config.ROW_COLUMNS`; deployment-rules.md §3 is explicit that
    delta and DTE are read at IBKR order entry, not off the analysis row. This
    helper exists so that IF a caller ever backfills one of those columns (or a
    test constructs a `ac_df` that has one), it is used; when the column is
    absent or blank, `None` comes back and nothing downstream pretends
    otherwise — see the "do not invent a delta" constraint in the module intro.
    """
    val = row.get(col) if hasattr(row, "get") else None
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _extract_alt(play_text: str) -> str:
    """Pull the 'Alt: ...' alternative-interpretation line back out of the play
    cell. `core.py::analysis_to_rows` folds `alternative_interpretation` into
    the play text as its own line (there is no dedicated sheet column) and
    `scripts/backtest/classify.py::_primary_text` already strips it the other
    way — this is that operation's inverse."""
    m = re.search(r"\n\s*Alt:\s*(.*)", str(play_text or ""), re.DOTALL)
    return m.group(1).strip() if m else ""


def _score_sort_key(score: float | None) -> float:
    """Higher score_total sorts first WITHIN a tier; a missing score sorts
    last within its tier rather than being treated as a strong or weak score."""
    return float("inf") if score is None else -score


def _delta_sort_key(delta: float | None) -> float:
    """Larger |delta| sorts first; a missing delta sorts LAST — never assumed
    to be the closest-to-money pick just because it is unknown. Never a
    function of score_total (deployment-rules.md §4)."""
    return float("inf") if delta is None else -abs(delta)


def _ensure_caps(book: risk_mod.BookRisk, net_liq: float | None) -> risk_mod.BookRisk:
    """If `book` was built without caps, bind `config/account-sim.yml`'s caps to
    `net_liq` so headroom can still be checked. Leaves an already-capped book
    untouched — `book.caps` is the book builder's call, this only fills a gap."""
    if book.caps is not None or not net_liq:
        return book
    try:
        caps = risk_mod.load_caps(net_liq)
    except ValueError as exc:
        log.warning("Could not load caps for headroom check: %s", exc)
        return book
    return replace(book, caps=caps)


def _headroom(book: risk_mod.BookRisk, dn: float | None,
              ticker: str | None = None) -> tuple[bool | None, str]:
    """`(ok, note)` for one candidate's estimated delta-notional.

    `ok` is `None` — not False — whenever headroom cannot be evaluated at all
    (no delta-notional estimate, or no caps loaded), so a caller can never read
    "unknown" as "fits".

    `ticker` nets the candidate against that ticker's existing exposure, so this
    advisory line uses the same cap definition `risk.assess` flags breaches on.
    """
    if dn is None:
        return None, ("delta-notional not estimable from the analysis row — "
                      "verify cap headroom in IBKR at order entry (§3)")
    if book.caps is None:
        return None, "no caps loaded (net_liq unavailable) — cap headroom not checked"
    ok, binding = risk_mod.headroom_for(book, dn, ticker)
    if ok:
        return True, f"fits under caps (est. delta-notional ${dn:,.0f})"
    return False, f"would breach the {binding} cap (est. delta-notional ${dn:,.0f})"


def rank(ac_df: pd.DataFrame, date: str, book: risk_mod.BookRisk,
         net_liq: float | None) -> tuple[list[Candidate], list[Rejected]]:
    """Rank one date's analysis plays into deploy/hedge candidates + rejects.

    Returns `(candidates, rejected)`. `candidates` holds BOTH roles in one
    list — deploy-role entries first (Tier A before Tier B, `score_total`
    tie-break only, top `DEPLOY_BUDGET` flagged `deploy=True`), then
    hedge-role entries (§4 bear candidates, ordered by |delta| descending).
    Filter on `.role` to split them back apart; `render()` and `judge()` both
    do exactly that rather than assuming list order.
    """
    book = _ensure_caps(book, net_liq)
    open_tickers = {p.ticker for p in book.positions} | {p.ticker for p in book.unpriced}

    plays = analysis.plays_for_date(ac_df, date)
    market_regime = analysis.market_regime_by_date(ac_df).get(str(date), "")

    deploy_candidates: list[Candidate] = []
    hedge_candidates: list[Candidate] = []
    rejected: list[Rejected] = []

    for _, row in plays.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        play_text = row.get("play", "")
        structure = mapping.play_structure(play_text)
        dte_proxy = mapping.play_dte(play_text, row.get("horizon"))
        short_delta = _optional_float(row, "short_leg_delta")
        tier, partial, tier_reason = mapping.ladder_tier(
            structure, market_regime, dte_proxy, short_delta)
        score_total = _optional_float(row, "score_total")
        trigger = str(row.get("trigger", "")).strip()
        invalidation = str(row.get("invalidation", "")).strip()
        horizon = str(row.get("horizon", "")).strip()
        alt = _extract_alt(play_text)
        delta = _optional_float(row, "delta")
        dn_estimate = _optional_float(row, "delta_notional")

        reasons = [
            f"structure={structure}",
            # The LABEL only. The full market-regime cell is a paragraph of
            # justification and is identical on every play of the date, so
            # repeating it per candidate buries the reason chain it is part of.
            # The card prints it once, in the header. `ladder_tier()` above still
            # receives the untruncated string — this is display, not logic.
            f"market regime={_regime_label(market_regime)}",
            f"ladder_tier={tier} ({tier_reason})",
        ]

        # §1 vetoes (bear_call_spread intake veto, BEAR+H-VOL, credit in
        # RANGE+L-VOL) are absolute -- ladder_tier() already folds all three
        # in, including for a would-be hedge candidate: §1.2's "any play" and
        # §1's other two vetoes carry no hedge-sleeve carve-out in the rules
        # text (only §1.4 names one explicitly), so a VETO tier here means
        # excluded from BOTH the deploy set and the hedge sleeve.
        if tier == "VETO":
            rejected.append(Rejected(ticker, str(play_text), structure, market_regime,
                                     "VETO", tier_reason, score_total))
            continue

        if structure in _HEDGE_ONLY_STRUCTURES:
            # §1.4 card veto: never a selection play, however thin the day's
            # A/B supply -- but explicitly still eligible for the §4 sleeve,
            # since ladder_tier() cleared it (no §1-3 veto fired above).
            reasons.append(
                "§1.4 card veto: bear debit is hedge-only, never a selection play "
                f"(ladder_tier said {tier}, overridden here)")
            dup = ticker in open_tickers
            if dup:
                reasons.append(f"DUPLICATE EXPOSURE: {ticker} already open in book")
            headroom_ok, headroom_note = _headroom(book, dn_estimate, ticker)
            reasons.append(headroom_note)
            hedge_candidates.append(Candidate(
                ticker=ticker, play=str(play_text), structure=structure,
                market_regime=market_regime, tier=tier, tier_partial=partial,
                tier_reason=tier_reason, score_total=score_total, horizon=horizon,
                trigger=trigger, invalidation=invalidation,
                alternative_interpretation=alt, role="hedge", reasons=reasons,
                duplicate_exposure=dup, delta=delta,
                headroom_ok=headroom_ok, headroom_note=headroom_note))
            continue

        if tier == "C":
            rejected.append(Rejected(
                ticker, str(play_text), structure, market_regime, "C",
                f"capital-constrained: {tier_reason}", score_total))
            continue

        # Tier A or B survives as a deploy candidate.
        dup = ticker in open_tickers
        if dup:
            reasons.append(f"DUPLICATE EXPOSURE: {ticker} already open in book")
        headroom_ok, headroom_note = _headroom(book, dn_estimate, ticker)
        reasons.append(headroom_note)
        deploy_candidates.append(Candidate(
            ticker=ticker, play=str(play_text), structure=structure,
            market_regime=market_regime, tier=tier, tier_partial=partial,
            tier_reason=tier_reason, score_total=score_total, horizon=horizon,
            trigger=trigger, invalidation=invalidation,
            alternative_interpretation=alt, role="deploy", reasons=reasons,
            duplicate_exposure=dup, delta=delta,
            headroom_ok=headroom_ok, headroom_note=headroom_note))

    # Tier A before Tier B; score_total is a tie-break WITHIN a tier only —
    # never part of the sort's first key, so it can never move a play between
    # tiers (see the module docstring).
    deploy_candidates.sort(key=lambda c: (0 if c.tier == "A" else 1,
                                          _score_sort_key(c.score_total)))
    for i, c in enumerate(deploy_candidates):
        c.deploy = i < DEPLOY_BUDGET
        c.reasons.append(f"deploy set (top-{DEPLOY_BUDGET})" if c.deploy
                         else "reserve (budget exceeded)")

    # §4: ranked by |delta| descending, NEVER by score_total.
    hedge_candidates.sort(key=lambda c: _delta_sort_key(c.delta))

    return deploy_candidates + hedge_candidates, rejected


# --------------------------------------------------------------------------
# PART B — the ONE judgment call
# --------------------------------------------------------------------------
def _default_invoke(prompt_text: str) -> str:
    """One `claude -p` call, mirroring `_invoke_claude()` in
    `scripts/analysis_pipeline/core.py`. Run from a throwaway cwd so no
    project CLAUDE.md/skill loads into the judgment session. Only used when
    `judge()` is called with no `invoke` override (i.e. never in tests)."""
    with tempfile.TemporaryDirectory() as cwd:
        proc = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", JUDGMENT_MODEL],
            input=prompt_text, capture_output=True, text=True, cwd=cwd,
            timeout=JUDGMENT_TIMEOUT_S, check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    parsed = json.loads(proc.stdout)
    if isinstance(parsed, list):
        results = [e for e in parsed if isinstance(e, dict) and e.get("type") == "result"]
        wrapper = results[-1] if results else {}
    else:
        wrapper = parsed
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {wrapper.get('result')}")
    return wrapper.get("result", "")


def judge(candidates: list[Candidate], context: str, invoke=None) -> dict:
    """The ONE judgment call. Sees ONLY `rank()`'s survivors, asked exactly
    three questions (see `prompt.py`): has each candidate's trigger fired, is
    its alternative interpretation now more likely, and (hedge sleeve only)
    which to take on a genuine tie.

    `invoke`, when given, is `Callable[[str], str]` — takes the assembled
    prompt, returns the model's raw text — so tests never spawn a process.
    Defaults to a real `claude -p` call.

    STRUCTURAL GUARDS (both tested in `tests/test_journal_recommend.py`):

    1. A ticker in the parsed response that is not one of `candidates`'
       tickers is dropped and a warning is recorded — this covers both an
       outright fabricated ticker AND a real ticker the model tries to
       resurrect from outside the survivor set (a vetoed play was never put
       in `candidates` to begin with, so it can never match here either).
    2. The response is applied as ANNOTATIONS onto the existing `candidates`
       list, in place, by ticker lookup — this function never sorts, filters,
       or rebuilds that list, and never sets `.tier` or `.deploy`. A verdict
       can only set `.trigger_verdict` / `.alt_verdict` / `.demoted` /
       `.demote_reasons` / `.hedge_pick`, so the worst it can do is flag a
       survivor for a human to reconsider — it cannot move anything, and it
       cannot promote a play `rank()` did not already clear.
    """
    deploy = [c for c in candidates if c.role == "deploy"]
    hedge = [c for c in candidates if c.role == "hedge"]
    survivor_tickers = {c.ticker for c in deploy} | {c.ticker for c in hedge}

    result: dict = {
        "ran": False, "warnings": [], "dropped_tickers": [],
        "raw": None, "hedge_pick": None, "hedge_pick_note": "",
    }

    if not survivor_tickers:
        result["warnings"].append("no surviving candidates to judge")
        return result

    prompt_text = prompt.build_prompt(
        [c.to_prompt_dict() for c in deploy],
        [c.to_prompt_dict() for c in hedge],
        context)

    invoke_fn = invoke or _default_invoke
    parsed = None
    last_err: Exception | None = None
    for attempt in range(1, JUDGMENT_MAX_ATTEMPTS + 1):
        try:
            text = invoke_fn(prompt_text)
            parsed = prompt.parse_response(text)
            break
        except Exception as exc:  # noqa: BLE001 - retry loop, reported at the end
            last_err = exc
            log.warning("judgment attempt %d/%d failed: %s",
                        attempt, JUDGMENT_MAX_ATTEMPTS, exc)
    if parsed is None:
        result["warnings"].append(
            f"judgment call failed after {JUDGMENT_MAX_ATTEMPTS} attempt(s): {last_err}")
        return result

    result["ran"] = True
    result["raw"] = parsed

    # -- GUARD 1: drop any ticker that is not a Part-A survivor -------------
    def _filter(verdicts) -> dict:
        kept = {}
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            t = str(v.get("ticker", "")).strip().upper()
            if t not in survivor_tickers:
                result["dropped_tickers"].append(t)
                result["warnings"].append(
                    f"model returned ticker {t!r}, which is not a Part-A survivor "
                    "-- dropped, never trusted")
                continue
            kept[t] = v
        return kept

    verdicts_by_ticker = _filter(parsed.get("candidates", []))
    verdicts_by_ticker.update(_filter(parsed.get("hedge", [])))

    # -- GUARD 2: annotate the EXISTING candidates list in place ------------
    for c in candidates:
        v = verdicts_by_ticker.get(c.ticker)
        if v is None:
            continue
        c.trigger_verdict = v.get("trigger_fired")
        c.trigger_note = v.get("trigger_note")
        c.alt_verdict = v.get("alt_more_likely")
        c.alt_note = v.get("alt_note")
        demote_reasons = []
        if c.trigger_verdict == "no":
            demote_reasons.append("trigger has not fired")
        if c.alt_verdict == "yes":
            demote_reasons.append("alternative interpretation now more likely than the thesis")
        if demote_reasons:
            c.demoted = True
            c.demote_reasons = demote_reasons

    hedge_pick = parsed.get("hedge_pick")
    if hedge_pick:
        hedge_pick = str(hedge_pick).strip().upper()
        hedge_tickers = {c.ticker for c in hedge}
        if hedge_pick in hedge_tickers:
            for c in hedge:
                c.hedge_pick = c.ticker == hedge_pick
            result["hedge_pick"] = hedge_pick
            result["hedge_pick_note"] = parsed.get("hedge_pick_note", "") or ""
        else:
            result["warnings"].append(
                f"model picked hedge ticker {hedge_pick!r}, which is not a hedge-sleeve "
                "survivor -- ignored")

    return result


# --------------------------------------------------------------------------
# PART C — the markdown deploy card
# --------------------------------------------------------------------------
def _fmt_score(score: float | None) -> str:
    return "—" if score is None else f"{score:g}"


def _fmt_bool(b: bool | None, yes: str = "yes", no: str = "no", unknown: str = "unknown") -> str:
    if b is None:
        return unknown
    return yes if b else no


def _regime_label(regime: str | None) -> str:
    """The regime LABEL — 'BULL + L-VOL + RISK-ON' — without its justification.

    The analysis writes the label, an em-dash, then a paragraph explaining it.
    Only the label is decision-relevant (it is what `ladder_tier()` matches on),
    and it is the same on every play of the date.
    """
    if not regime:
        return "(none)"
    label = str(regime).split("—", maxsplit=1)[0].split(" - ", maxsplit=1)[0].strip()
    return label or str(regime)[:60].strip()


def _play_headline(play: str | None, limit: int = 160) -> str:
    """One-line summary of a play cell, minus the `Alt:` block.

    The cell is multi-line and ends with the alternative interpretation, which
    the card already prints under its own heading. Printing the raw cell repeats
    it verbatim and pushes the trigger — the thing you actually check at the
    open — below the fold.
    """
    if not play:
        return "(none given)"
    kept = []
    for line in str(play).splitlines():
        if line.strip().lower().startswith("alt:"):
            break
        if line.strip():
            kept.append(line.strip())
    text = " ".join(kept) or str(play).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _wrap_note(text: str | None, limit: int = 240) -> str:
    if not text:
        return "(none given)"
    t = " ".join(str(text).split())
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _render_reasons(c: Candidate) -> str:
    return "; ".join(c.reasons)


def _render_judgment_line(c: Candidate) -> str:
    if c.trigger_verdict is None and c.alt_verdict is None:
        return "  judgment: not run / no verdict returned"
    parts = [
        f"trigger fired: {c.trigger_verdict or 'unknown'}"
        + (f" ({c.trigger_note})" if c.trigger_note else ""),
        f"alt more likely: {c.alt_verdict or 'unknown'}"
        + (f" ({c.alt_note})" if c.alt_note else ""),
    ]
    line = "  judgment: " + " | ".join(parts)
    if c.demoted:
        line += "\n  ⚠ DEMOTED (annotation only, ordering unchanged): " + "; ".join(
            c.demote_reasons)
    return line


def _render_deploy_candidate(i: int, c: Candidate) -> str:
    tag = "[DEPLOY]" if c.deploy else "[RESERVE]"
    lines = [
        f"{i}. {tag} **{c.ticker}** — {c.structure} — Tier {c.tier}"
        + (" (partial: tier gate unverified)" if c.tier_partial else ""),
        f"  play: {_play_headline(c.play)}",
        f"  trigger: {_wrap_note(c.trigger)}",
        f"  invalidation: {_wrap_note(c.invalidation)}",
        f"  alternative interpretation: {_wrap_note(c.alternative_interpretation)}",
        f"  score_total: {_fmt_score(c.score_total)} (tie-break only, §6 — never a promotion signal)",
        f"  duplicate exposure: {_fmt_bool(c.duplicate_exposure)}",
        f"  cap headroom: {_fmt_bool(c.headroom_ok)} — {c.headroom_note}",
        f"  reasons: {_render_reasons(c)}",
        _render_judgment_line(c),
    ]
    return "\n".join(lines)


def _render_hedge_candidate(i: int, c: Candidate) -> str:
    pick = " ← MODEL PICK (tie-break only)" if c.hedge_pick else ""
    delta_str = "—" if c.delta is None else f"{abs(c.delta):.3f}"
    lines = [
        f"{i}. **{c.ticker}** — {c.structure} — |delta| {delta_str}{pick}",
        f"  play: {_play_headline(c.play)}",
        f"  trigger: {_wrap_note(c.trigger)}",
        f"  alternative interpretation: {_wrap_note(c.alternative_interpretation)}",
        f"  duplicate exposure: {_fmt_bool(c.duplicate_exposure)}",
        f"  cap headroom: {_fmt_bool(c.headroom_ok)} — {c.headroom_note}",
        "  size: ≤ ½ a normal position (§4) — insurance, not a trade",
        _render_judgment_line(c),
    ]
    return "\n".join(lines)


def _render_rejected(r: Rejected) -> str:
    return (f"- **{r.ticker}** ({r.tier}) — {r.structure} — {r.reason} "
            f"[score_total: {_fmt_score(r.score_total)}]")


def render(candidates: list[Candidate], rejected: list[Rejected], judgment: dict | None,
           *, date: str, source: str = "", net_liq: float | None = None,
           as_of: str = "", staleness_days: int | None = None,
           stale_note: str = "", book_evaluable: bool = True,
           book_note: str = "") -> str:
    """Render the full markdown deploy card.

    Stands on its own with `judgment=None` (the `--no-llm` path) — the
    judgment section is present and clearly says "not run" rather than being
    omitted, so the deterministic card is always complete on its own.

    Every provenance argument is keyword-only WITH A DEFAULT that reproduces the
    pre-existing card byte-for-byte. `scripts/backtest_study/live_select.py`
    imports this module directly (the one sanctioned research->production
    import), so a required parameter here would break the research tier.
    """
    deploy = [c for c in candidates if c.role == "deploy"]
    hedge = [c for c in candidates if c.role == "hedge"]
    veto = [r for r in rejected if r.tier == "VETO"]
    tier_c = [r for r in rejected if r.tier == "C"]

    lines: list[str] = []
    lines.append(f"# Deploy card — {date}")
    lines.append("")
    lines.append(_V3_V4_CAVEAT)
    lines.append("")

    # --- provenance: WHEN this card stands, and what it could not see -----
    if as_of:
        age = ("age unknown" if staleness_days is None else
               "same day" if staleness_days == 0 else
               f"{staleness_days} day{'s' if staleness_days != 1 else ''} old")
        lines.append(f"_Session {date} · as of {as_of} · analysis {age}._")
        lines.append("")
    if stale_note:
        lines.append(f"> {stale_note}")
        lines.append("")
    if not book_evaluable:
        # The empty-book case. `rank()` computes duplicate exposure from the
        # open book, so with no book it stamps False on everything -- which
        # reads as "checked, and clear". Say plainly that it was not checked;
        # an unevaluated cap must never be mistaken for a satisfied one.
        lines.append("> **Cap headroom and duplicate exposure were NOT evaluated.** "
                     + (book_note or "No broker pull dated on or before this session "
                                     "was available.")
                     + " Every \"duplicate exposure: no\" below means UNKNOWN, not "
                       "clear, and every \"cap headroom\" line means unchecked. "
                       "Verify both in IBKR at order entry (§3).")
        lines.append("")

    if source:
        lines.append(f"_Analysis source: {source}. Net liq: "
                     f"{'—' if net_liq is None else f'${net_liq:,.0f}'}._")
        lines.append("")

    # The market regime is a market-level read: identical on every play of the
    # date, and the input to §2 tiering. It belongs here once, not on each row.
    regimes = {c.market_regime for c in candidates if c.market_regime}
    regimes |= {r.market_regime for r in rejected if r.market_regime}
    if len(regimes) == 1:
        full = next(iter(regimes))
        lines.append(f"**Model regime (§2 tiering input):** `{_regime_label(full)}`")
        lines.append("")
        lines.append(f"<details><summary>full regime read</summary>\n\n{full}\n\n</details>")
        lines.append("")
    elif len(regimes) > 1:
        # Should not happen for a single date — the MARKET row is one per date.
        # If it does, say so rather than silently picking one.
        lines.append(f"**Model regime:** ⚠ {len(regimes)} different regime reads found for "
                     "this date; the ladder was applied per-row. Check the analysis book.")
        lines.append("")

    lines.append("## Deploy set (§0 budget: 1-3/day, Tier A before Tier B)")
    lines.append("")
    if not deploy:
        lines.append("_No Tier A/B candidates survived §1 today._")
    else:
        for i, c in enumerate(deploy, 1):
            lines.append(_render_deploy_candidate(i, c))
            lines.append("")

    lines.append("## Hedge sleeve (§4, optional — ranked by |delta| desc, never score_total)")
    lines.append("")
    if not hedge:
        lines.append("_No bear candidates cleared §1 today._")
    else:
        for i, c in enumerate(hedge, 1):
            lines.append(_render_hedge_candidate(i, c))
            lines.append("")

    lines.append("## Rejected — visible, not deployed")
    lines.append("")
    lines.append(f"### VETO (§1) — {len(veto)}")
    if not veto:
        lines.append("_None._")
    else:
        lines.extend(_render_rejected(r) for r in veto)
    lines.append("")
    lines.append(f"### Tier C — capital-constrained — {len(tier_c)}")
    if not tier_c:
        lines.append("_None._")
    else:
        lines.extend(_render_rejected(r) for r in tier_c)
    lines.append("")

    lines.append("## Judgment call")
    lines.append("")
    if judgment is None:
        lines.append("**Not run** (`--no-llm`). This card is the complete deterministic "
                     "ranking — the judgment pass is an annotation layer only, never a "
                     "dependency of the card above.")
    elif not judgment.get("ran"):
        warn_text = "; ".join(judgment.get("warnings", [])) or "no warnings recorded"
        lines.append(f"**Attempted, did not complete.** {warn_text}")
    else:
        lines.append("Ran. Annotations are already applied to the candidates above; "
                     "summary below.")
        if judgment.get("dropped_tickers"):
            lines.append("")
            lines.append("Dropped (not a Part-A survivor, never trusted): "
                         + ", ".join(judgment["dropped_tickers"]))
        if judgment.get("hedge_pick"):
            lines.append("")
            lines.append(f"Hedge-sleeve pick: **{judgment['hedge_pick']}** "
                         f"({judgment.get('hedge_pick_note', '')})")
        other_warnings = [w for w in judgment.get("warnings", [])
                          if "not a Part-A survivor" not in w]
        if other_warnings:
            lines.append("")
            lines.append("Warnings: " + "; ".join(other_warnings))

    return "\n".join(lines) + "\n"
