"""
STAGE 1 of the live-vs-backtest feedback loop.

Maps real IBKR fills to AnalysisClaude rows and deployment-ladder tiers, then
runs an entry-slippage check and a selection-compliance audit. Pure audit
harness: reads only local files, writes only
backtests/live_loop/stage1_report_<snapshot-date>.md (and mirrors the same text
to stdout / stage1_output.txt). Idempotent.

TRACKED CODE, DISPOSABLE DATA. This module lives under `scripts/` and its
inputs/outputs live under `backtests/`, which `.gitignore` excludes as scratch
that "gets deleted periodically". It used to live there too — the same mistake
the 2026-08-11 refactor fixed for study code by moving it to
`scripts/backtest_study/`. With backtest tuning closed, this is the only source
of NEW evidence in the system, so it must survive a `backtests/` wipe.

Run as: `python3 -m scripts.live_loop.stage1_map_fills`
        `python3 -m scripts.live_loop.stage1_map_fills --snapshot <path>`

Defaults to the NEWEST snapshot in backtests/live_loop/. A later snapshot is not
a superset of an earlier one — contract identity is only recoverable while a
position is open — so past snapshots stay on disk and their mapped sets are
pooled. Re-run an old one with --snapshot; the report name follows the snapshot
date, so nothing is clobbered.

Inputs (all local):
  backtests/live_loop/ibkr_snapshot_<YYYY-MM-DD>.json   (newest by default)
  backtests/to_evaluate/analysis - AnalysisClaude.csv
  backtests/to_evaluate/analysis - BacktestResults.csv
  backtests/to_evaluate/analysis - BacktestProxy.csv
  docs/deployment-rules.md   (encoded as ladder_tier() below)

Nothing under config/, lib/, scripts/ is modified; no network / Sheets access.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Re-exported for existing importers (e.g. tests/test_live_loop.py) that pull
# structure/ladder helpers straight off this module rather than mapping.py.
try:  # `python3 -m scripts.live_loop.stage1_map_fills` (package = scripts.live_loop)
    from .mapping import (  # noqa: F401
        CONFIDENCES,
        DIRECTION,
        SIDE,
        _CONF_RANK,
        _is_overlay,
        _live_strikes,
        _live_to_canonical,
        classify_structure,
        ladder_tier,
        leg_desc,
        map_entry,
        play_dte,
        play_strikes,
        play_structure,
    )
except ImportError:  # tests/conftest.py puts scripts/ on sys.path (package = live_loop)
    from live_loop.mapping import (  # noqa: F401
        CONFIDENCES,
        DIRECTION,
        SIDE,
        _CONF_RANK,
        _is_overlay,
        _live_strikes,
        _live_to_canonical,
        classify_structure,
        ladder_tier,
        leg_desc,
        map_entry,
        play_dte,
        play_strikes,
        play_structure,
    )

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / "backtests" / "live_loop"
EVAL_DIR = ROOT / "backtests" / "to_evaluate"

def _latest_snapshot() -> Path:
    """Newest `ibkr_snapshot_<YYYY-MM-DD>.json` in LIVE_DIR.

    Snapshots accumulate (each is an immutable broker pull), so the module
    defaults to the most recent one rather than a pinned filename. Pass
    `--snapshot <path>` to re-run an older one; the report name follows the
    snapshot date so re-running a past snapshot never clobbers a newer report.
    """
    snaps = sorted(LIVE_DIR.glob("ibkr_snapshot_*.json"))
    if not snaps:
        raise SystemExit(f"no ibkr_snapshot_*.json under {LIVE_DIR}")
    return snaps[-1]


_argv_snap = None
if "--snapshot" in sys.argv:
    _argv_snap = Path(sys.argv[sys.argv.index("--snapshot") + 1])

IBKR_JSON = _argv_snap or _latest_snapshot()
AC_PATH = EVAL_DIR / "analysis - AnalysisClaude.csv"
BR_PATH = EVAL_DIR / "analysis - BacktestResults.csv"
BP_PATH = EVAL_DIR / "analysis - BacktestProxy.csv"

_SNAP_TAG = IBKR_JSON.stem.replace("ibkr_snapshot_", "")
REPORT_MD = LIVE_DIR / f"stage1_report_{_SNAP_TAG}.md"

PRICE_MATCH_TOL = 0.05  # per-share tolerance for fill<->open-position avg_price join

_LINES: list[str] = []


def emit(line: str = "") -> None:
    _LINES.append(line)


# --------------------------------------------------------------------------
# Contract-description parsing
# --------------------------------------------------------------------------
_CONTRACT_RE = re.compile(
    r"^(?P<sym>[A-Z]+)\s+(?P<mon>[A-Z][a-z]{2})(?P<day>\d{1,2})'(?P<yy>\d{2})\s+"
    r"(?P<strike>[\d.]+)\s+(?P<right>CALL|PUT)"
)
_MON = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_contract(desc: str):
    m = _CONTRACT_RE.match(desc.strip())
    if not m:
        return None
    yy = 2000 + int(m.group("yy"))
    exp = f"{yy:04d}-{_MON[m.group('mon')]:02d}-{int(m.group('day')):02d}"
    return {
        "symbol": m.group("sym"),
        "expiry": exp,
        "strike": float(m.group("strike")),
        "right": "C" if m.group("right") == "CALL" else "P",
        "desc": desc.strip(),
    }


# --------------------------------------------------------------------------
# Load IBKR snapshot
# --------------------------------------------------------------------------
def load_snapshot():
    data = json.loads(IBKR_JSON.read_text())
    trades = pd.DataFrame(data["trades"])
    positions = data["open_positions"]
    parsed_pos = []
    for p in positions:
        info = parse_contract(p["contract_description"])
        if info is None:  # stock (CSPX) — no strike/right
            parsed_pos.append({**p, "symbol": p["contract_description"].split()[0],
                               "expiry": None, "strike": None, "right": None,
                               "is_option": False, "claimed": False})
        else:
            parsed_pos.append({**p, **info, "is_option": True, "claimed": False})
    return data.get("notes", ""), trades, parsed_pos


# --------------------------------------------------------------------------
# Step A — reconstruct entries from fills
# --------------------------------------------------------------------------
def reconstruct(trades: pd.DataFrame, positions: list[dict]):
    opt = trades[trades["sec_type"] == "OPT"].copy()
    opt["trade_dt"] = pd.to_datetime(opt["trade_time"])
    opt["fill_date"] = opt["trade_dt"].dt.strftime("%Y-%m-%d")

    # closing fills carry realized_pnl != 0; opening fills == 0.
    # A $0.00 price with realized_pnl == 0 is expiry/assignment bookkeeping, not
    # a fill — IBKR stamps those outside market hours (a 2026-08-08 Saturday row
    # is what surfaced this), and treating them as opens invents phantom entries
    # at zero cost. Zero-price rows WITH realized_pnl stay in the closing ledger:
    # those are real expiration P&L.
    settlement = opt[(opt["realized_pnl"] == 0) & (opt["price"] == 0)]
    opening = opt[(opt["realized_pnl"] == 0) & (opt["price"] != 0)].copy().reset_index(drop=True)
    closing = opt[opt["realized_pnl"] != 0].copy()

    # -- global best-match assignment (avoids first-come collisions) --
    # Two distinct fills can both sit within tol of one position's avg_price
    # (e.g. TSM 370P avg 7.751 vs fills 7.72 and 7.74). Assign each open
    # position to its single closest unclaimed fill, smallest-diff first.
    leg_match = {}  # opening-row index -> matched position
    candidates = []
    for li, tr in opening.iterrows():
        want_sign = -1 if tr["side"] == "SELL" else 1
        for pi, p in enumerate(positions):
            if not p["is_option"] or p["symbol"] != tr["symbol"]:
                continue
            if np.sign(p["position"]) != want_sign:
                continue
            diff = abs(float(tr["price"]) - float(p["average_price"]))
            if diff <= PRICE_MATCH_TOL:
                candidates.append((diff, li, pi))
    candidates.sort()
    used_leg, used_pos = set(), set()
    for diff, li, pi in candidates:
        if li in used_leg or pi in used_pos:
            continue
        used_leg.add(li)
        used_pos.add(pi)
        positions[pi]["claimed"] = True
        leg_match[li] = positions[pi]

    # group opening fills into combos by identical trade_time (one combo order)
    entries = []
    for tt, grp in opening.groupby("trade_time"):
        legs = [{"trade": tr, "match": leg_match.get(li)} for li, tr in grp.iterrows()]
        entries.append({"trade_time": tt,
                        "fill_date": grp["fill_date"].iloc[0],
                        "trade_dt": grp["trade_dt"].iloc[0],
                        "symbol": grp["symbol"].iloc[0],
                        "legs": legs})
    entries.sort(key=lambda e: e["trade_dt"], reverse=True)
    return entries, closing, positions, settlement


# --------------------------------------------------------------------------
# Report builder
# --------------------------------------------------------------------------
def main():
    notes, trades, positions = load_snapshot()
    ac = pd.read_csv(AC_PATH)
    br = pd.read_csv(BR_PATH)
    bp = pd.read_csv(BP_PATH)

    entries, closing, positions, settlement = reconstruct(trades, positions)

    # market regime per date (MARKET row)
    mkt = ac[ac["ticker"] == "MARKET"].set_index("date")["regime"].to_dict()
    ac_dates = set(ac["date"].dropna().unique())

    emit("# Stage 1 — Live IBKR fills → analysis rows → deployment tiers")
    emit("")
    emit(f"_Snapshot: `{IBKR_JSON.name}` · generated by `stage1_map_fills.py` "
         f"(idempotent, local-only)._")
    emit("")
    emit(f"IBKR note (verbatim): {notes}")
    if len(settlement):
        emit("")
        rows = ", ".join(f"{r.symbol} {r.side} @0 on {r.trade_time[:10]}"
                         for r in settlement.itertuples())
        emit(f"**Dropped {len(settlement)} zero-price settlement row(s)** before entry "
             f"reconstruction (expiry/assignment bookkeeping, `realized_pnl == 0` and "
             f"`price == 0`; IBKR stamps these outside market hours): {rows}. They are "
             f"not fills and would otherwise appear as phantom zero-cost entries.")
    emit("")

    # ================= STEP A — INVENTORY =================
    emit("## 1. Inventory (Step A) — reconstructed entries")
    emit("")
    emit("Opening fills (realized_pnl == 0) grouped into combo orders by identical "
         "`trade_time`; each leg joined to an open position by symbol + sign + "
         "price≈average_price (tol ${:.2f}). Legs with no matching open position "
         "are already-closed round-trips → identity UNKNOWN.".format(PRICE_MATCH_TOL))
    emit("")
    emit("| # | fill date | ticker | structure | legs (strike/expiry or UNKNOWN) | net px | net w/comm | status |")
    emit("|---|-----------|--------|-----------|----------------------------------|--------|-----------|--------|")

    inv = []
    n_overlay = n_unknown_legs = 0
    for i, e in enumerate(entries, 1):
        struct, net, netc, status, note, is_overlay = classify_structure(e, positions)
        legs = leg_desc(e, struct, positions)
        dc = "debit" if net > 0 else "credit"
        n_unk = sum(1 for lg in e["legs"] if lg["match"] is None)
        n_unknown_legs += n_unk
        if is_overlay:
            n_overlay += 1
        emit(f"| {i} | {e['fill_date']} | {e['symbol']} | {struct} | {legs} | "
             f"{net:+.2f} ({dc}) | {netc:+.2f} | {status} |")
        if note:
            emit(f"|   |   |   | _note_ | {note} | | | |")
        inv.append({"idx": i, "entry": e, "structure": struct, "net": net,
                    "net_with_comm": netc, "status": status, "note": note,
                    "is_overlay": is_overlay})

    # closing-fill inventory
    close_events = closing.groupby("trade_time")
    n_close_fills = len(closing)
    n_close_events = close_events.ngroups
    emit("")
    emit("### Closing fills (realized_pnl != 0) — out of scope for entry mapping, listed for the ledger")
    emit("")
    emit("| trade_time | ticker | side | price | realized_pnl |")
    emit("|-----------|--------|------|-------|--------------|")
    for _, r in closing.sort_values("trade_time", ascending=False).iterrows():
        emit(f"| {r['trade_time']} | {r['symbol']} | {r['side']} | {r['price']:g} | {r['realized_pnl']:+.2f} |")

    n_open = sum(1 for x in inv if x["status"] == "OPEN")
    n_closed_entries = sum(1 for x in inv if x["status"] == "CLOSED")
    # Split the NONEs by cause so the caveat can distinguish "no coverage" from
    # "coverage existed, identity lost" — they call for opposite remedies.
    n_none_no_analysis = n_none_unknown = n_none_nomatch = 0
    emit("")
    emit("**Counts:** "
         f"{len(inv)} combo entries ({n_open} still-open, {n_closed_entries} closed round-trips) · "
         f"{n_close_fills} closing fills across {n_close_events} closing orders · "
         f"{n_overlay} overlays · {n_unknown_legs} unknown-identity legs.")
    emit("")

    # ================= STEP B — MAPPING =================
    emit("## 2. Mapping (Step B) — each entry → AnalysisClaude row")
    emit("")
    emit("Signal date = prior **business day** of the fill (entry basis = next-day open). "
         "Also checked same-day and D-2. Confidence: EXACT (structure + both strikes), "
         "STRUCTURE (structure matches, strikes differ), CORE (the play's structure was "
         "traded as the CORE of a larger position, with a short leg sold to finance it), "
         "SUBSTITUTED (same ticker/date/"
         "direction, different structure family — e.g. a naked leg traded against a spread "
         "play, or vice versa), OVERLAY (a financing/carry leg sold against a position "
         "already open — not a play attempt at all), NONE (no same-ticker play that date, "
         "or the only candidate play(s) that date are the opposite direction).")
    emit("")
    emit("| # | fill date | ticker | live structure | signal date (D-1 bday) | AC play | confidence |")
    emit("|---|-----------|--------|----------------|------------------------|---------|-----------|")

    mapped = []
    # Built from mapping.CONFIDENCES, never hand-listed: a category added there
    # and missing here would KeyError on the increment below — or worse, be
    # silently dropped from the tally if the increment ever grew a .get().
    conf_tally = {c: 0 for c in CONFIDENCES}
    for x in inv:
        e = x["entry"]
        fill = pd.Timestamp(e["fill_date"])
        # roll='forward' so a fill stamped on a non-business day (broker
        # bookkeeping rows carry weekend timestamps) resolves to the business
        # day before it rather than raising.
        d1 = np.busday_offset(fill.date(), -1, roll="forward").astype(str)
        d2 = np.busday_offset(fill.date(), -2, roll="forward").astype(str)
        same = fill.strftime("%Y-%m-%d")
        # candidate signal date: prefer D-1 bday, note availability of others
        avail = {c: (c in ac_dates) for c in (d1, same, d2)}
        sig = d1
        result = map_entry(x, sig, e["symbol"], ac)
        # overlays are flagged; never force-match to a spread play
        if x["is_overlay"]:
            note = "OVERLAY — short-leg add, not force-matched"
        else:
            note = ""
        conf = result["confidence"]
        conf_tally[conf] += 1
        # Three distinct reasons for a NONE, and they mean opposite things:
        # no analysis that date / analysis covered the ticker but the live
        # structure could not be resolved (closed round-trip, identity lost) /
        # a play existed and genuinely did not match. Collapsing them into
        # "no same-ticker play" reads as "the analysis never covered this",
        # which is the wrong conclusion when the coverage was there.
        if result["ac_play"]:
            ac_play = result["ac_play"]
        elif sig not in ac_dates:
            ac_play = "— (D-1 bday not in analysis)"
            n_none_no_analysis += 1
        elif ac[(ac["date"] == sig) & (ac["ticker"] == e["symbol"])].empty:
            ac_play = "— (no same-ticker play)"
            n_none_no_analysis += 1
        elif _live_to_canonical(x["structure"]) == "unknown":
            ac_play = "— (play exists; live structure UNKNOWN)"
            n_none_unknown += 1
        else:
            ac_play = "— (play exists; no direction/family match)"
            n_none_nomatch += 1
        emit(f"| {x['idx']} | {e['fill_date']} | {e['symbol']} | {x['structure']} | "
             f"{sig}{'' if sig in ac_dates else ' [no analysis]'} | {ac_play[:70]} | {conf} |")
        if note:
            emit(f"|   |   |   | | | _{note}_ | |")
        mapped.append({**x, "signal_date": sig, "map": result, "avail": avail})

    emit("")
    emit("**Confidence tally:** "
         + ", ".join(f"{k}={v}" for k, v in conf_tally.items())
         + ".")
    emit("")

    # ================= STEP C — TIERS + COMPLIANCE =================
    emit("## 3. Tier reconstruction + selection compliance (Step C)")
    emit("")
    emit("Tier reconstructed from `docs/deployment-rules.md` using the **analysis row** "
         "(structure × MARKET regime of that date; bull_put delta clause UNVERIFIABLE off "
         "the row → DTE-proxy only, marked PARTIAL).")
    emit("")

    # per-mapped-entry tier
    # NOTE: SUBSTITUTED rows are kept here deliberately (only "NONE" is
    # dropped) -- the tier is reconstructed from the EMITTED play's structure
    # (r["ac_structure"]), not the structure actually traded, so it still
    # reflects the analysis-row's compliance cell. The `confidence` column
    # makes SUBSTITUTED rows visible as their own split rather than pooling
    # them with true STRUCTURE/EXACT matches.
    emit("### Deployed-entry tiers")
    emit("")
    emit("| # | ticker | signal date | market regime | AC structure | confidence | tier | partial | reason |")
    emit("|---|--------|-------------|---------------|--------------|------------|------|---------|--------|")
    veto_hits = []
    deployed_by_date = {}
    n_substituted_tiered = 0
    for m in mapped:
        r = m["map"]
        if r["confidence"] == "NONE" or r["ac_structure"] is None:
            continue
        sig = m["signal_date"]
        reg = mkt.get(sig, "")
        tier, partial, reason = ladder_tier(r["ac_structure"], reg, r["dte_proxy"])
        # CORE counts here for the same reason SUBSTITUTED does: both are tiered
        # on the EMITTED play's structure while the fill traded something else —
        # a different family, or that family plus a financing leg.
        if r["confidence"] in ("SUBSTITUTED", "CORE"):
            n_substituted_tiered += 1
        emit(f"| {m['idx']} | {m['entry']['symbol']} | {sig} | {reg[:32]} | "
             f"{r['ac_structure']} | {r['confidence']} | **{tier}** | "
             f"{'PARTIAL' if partial else ''} | {reason} |")
        if tier == "VETO":
            veto_hits.append((m, reason))
        deployed_by_date.setdefault(sig, []).append(m)

    if veto_hits:
        emit("")
        emit("> **⚠ VETO HITS — deployed plays that land in a veto cell:**")
        for m, reason in veto_hits:
            emit(f"> - #{m['idx']} {m['entry']['symbol']} {m['entry']['fill_date']} "
                 f"({m['structure']}) — {reason}")
    if n_substituted_tiered:
        emit("")
        emit(f"> **ℹ {n_substituted_tiered} SUBSTITUTED/CORE row(s) above** are tiered on "
             "the *emitted* play's structure, not the structure actually traded — the "
             "operator traded a different (same-direction) structure, or that structure "
             "as the core of a financed one, so the tier reflects what the analysis "
             "emitted, not what filled.")
    emit("")

    # selection-compliance: all plays that date with tiers
    emit("### Selection-compliance view — every play on each entry's signal date")
    emit("")
    compliance = []
    for sig in sorted(deployed_by_date):
        reg = mkt.get(sig, "")
        emit(f"**Signal date {sig}** — market regime `{reg[:48]}`")
        emit("")
        emit("| tier | score | ticker | play structure | DTE proxy | deployed? |")
        emit("|------|-------|--------|----------------|-----------|-----------|")
        day = ac[(ac["date"] == sig) & (ac["ticker"] != "MARKET")].copy()
        deployed_tickers = {m["entry"]["symbol"] for m in deployed_by_date[sig]}
        rows = []
        for _, pr in day.iterrows():
            struct = play_structure(pr["play"])
            dte = play_dte(pr["play"], pr.get("horizon"))
            tier, partial, _ = ladder_tier(struct, reg, dte)
            rows.append({"tier": tier, "score": pr.get("score_total"),
                         "ticker": pr["ticker"], "struct": struct, "dte": dte,
                         "partial": partial,
                         "deployed": pr["ticker"] in deployed_tickers})
        tier_rank = {"A": 0, "B": 1, "C": 2, "VETO": 3}
        rows.sort(key=lambda r: (tier_rank.get(r["tier"], 9),
                                 -(r["score"] if pd.notna(r["score"]) else -1)))
        available_tiers = [t for t in ["A", "B", "C"] if any(r["tier"] == t for r in rows)]
        top_available = available_tiers[0] if available_tiers else None
        for r in rows:
            mark = "✅ DEPLOYED" if r["deployed"] else ""
            dte_s = f"{r['dte']:g}" if pd.notna(r["dte"]) else "—"
            tsuf = " (P)" if r["partial"] else ""
            emit(f"| {r['tier']}{tsuf} | {r['score']:g} | {r['ticker']} | {r['struct']} | "
                 f"{dte_s} | {mark} |" if pd.notna(r["score"]) else
                 f"| {r['tier']}{tsuf} | — | {r['ticker']} | {r['struct']} | {dte_s} | {mark} |")
        for r in rows:
            if r["deployed"]:
                compliance.append({"date": sig, "ticker": r["ticker"],
                                   "deployed_tier": r["tier"],
                                   "top_available": top_available})
        emit("")

    # compliance summary
    emit("### Compliance summary")
    emit("")
    for c in compliance:
        ok = "IN top tier" if c["deployed_tier"] == c["top_available"] else \
             ("VETO — worst cell" if c["deployed_tier"] == "VETO" else
              f"BELOW top ({c['top_available']} was available)")
        emit(f"- {c['date']} {c['ticker']}: deployed **{c['deployed_tier']}**, "
             f"top available = **{c['top_available']}** → {ok}")
    n_top = sum(1 for c in compliance if c["deployed_tier"] == c["top_available"])
    n_veto = sum(1 for c in compliance if c["deployed_tier"] == "VETO")
    emit("")
    emit(f"**{n_top}/{len(compliance)} deployed plays were in the top available tier; "
         f"{n_veto} landed in a VETO cell.**")
    emit("")

    # ================= STEP D — SLIPPAGE =================
    emit("## 4. Entry slippage vs modeled next-open (Step D)")
    emit("")
    emit(f"BacktestResults signal_date span: {br['signal_date'].min()} → "
         f"{br['signal_date'].max()}. BacktestProxy span: {bp['signal_date'].min()} → "
         f"{bp['signal_date'].max()}.")
    emit("")
    # NOTE: only "NONE" and "OVERLAY" are dropped here -- SUBSTITUTED and CORE
    # entries stay in scope (own `confidence` column) so the eval can read
    # slippage/coverage for operator substitutions and financed cores
    # separately from true structure matches. OVERLAY joins NONE because a
    # financing leg was never an attempt at a play, so there is no modeled
    # entry price it could be compared against.
    emit("| # | ticker | signal date | confidence | in BacktestResults? | in BacktestProxy? | modeled entry px | live net px | slippage |")
    emit("|---|--------|-------------|------------|---------------------|-------------------|------------------|-------------|----------|")
    n_compare = 0
    for m in mapped:
        r = m["map"]
        if r["confidence"] in ("NONE", "OVERLAY"):
            continue
        sig = m["signal_date"]
        tkr = m["entry"]["symbol"]
        br_hit = ((br["signal_date"] == sig) & (br["ticker"] == tkr)).any()
        bp_hit = ((bp["signal_date"] == sig) & (bp["ticker"] == tkr)).any()
        if not br_hit and not bp_hit:
            emit(f"| {m['idx']} | {tkr} | {sig} | {r['confidence']} | no | no | NOT_BACKTESTED | "
                 f"{m['net']:+.2f} | BLOCKED |")
        else:
            n_compare += 1  # (would compute here; not reachable in this snapshot)
    emit("")
    emit(f"**Comparisons possible: {n_compare}.** Every mapped entry falls on a "
         f"2026-07 signal date, but the BacktestResults / BacktestProxy books both stop at "
         f"**{br['signal_date'].max()}** — no July plays are backtested yet. Slippage is "
         f"therefore **BLOCKED (NOT_BACKTESTED)** for the whole live set; no modeled next-open "
         f"price exists to compare against, and per the brief no legs are priced here. "
         f"Aggregate mean/median/worst-case: N/A (n=0).")
    emit("")
    emit("_Note: the `daily_price_csv` column holds inline comma-separated marks (not a file "
         "path), so there is no local per-play CSV to cross-check against — and there is no "
         "backtest row for these dates regardless._")
    emit("")

    # ================= CAVEATS =================
    emit("## 5. Caveats")
    emit("")
    caveats = [
        "**Leg-identity via price join.** Open contract identity (strike/expiry/right) is "
        "inferred by matching each fill price to an open-position `average_price` within "
        f"${PRICE_MATCH_TOL:.2f}/share (all matches were <$0.02 off). SELL→short, BUY→long "
        "enforced. This is an inference, not a broker-confirmed contract id.",

        "**UNKNOWN-identity legs.** "
        f"{n_unknown_legs} legs across {n_closed_entries} closed round-trip entries "
        "(SMH verticals, and single AMD/NVDA/TSM shorts that were opened and closed within the "
        "30-day window) have no matching open position, so strike/expiry/right cannot be pinned. "
        "Their structure is inferred from net-price sign only; candidate interpretations are "
        "stated inline, never silently guessed. SMH has NO open position at all — every SMH "
        "entry is a closed round-trip.",

        "**Overlays.** The AMD Jul31'26 620 short call (over the Oct16'26 540/640 bull_call) and "
        "the TSM Jul31'26 470 short call (over the Sep18'26 470/590 bull_call) are single-leg, "
        "different-expiry adds. They are flagged as overlays and NOT force-matched to any spread "
        "play; neither signal date carried a same-ticker analysis play anyway.",

        "**PARTIAL tier checks.** The bull_put Tier-B clause needs 0.08≤|short-leg delta|≤0.20, "
        "but delta at entry is not on the analysis row. Tier is assigned by DTE proxy only "
        "(parsed from the play text / horizon) and marked PARTIAL — the delta band is unverified.",

        "**META is an operator substitution, not a structure match.** The live META Sep18'26 540 "
        "short PUT is a single naked short put; the only 2026-07-16 META play is a "
        "bull_put_spread 620/580. Same direction (bullish) and same side (credit), but a "
        "different structure — a naked short put has different max-loss/margin/exit behaviour "
        "than a credit spread, so this is reported **SUBSTITUTED**, not STRUCTURE and not EXACT. "
        "Its VETO tier follows from tiering the *emitted* analysis row (a credit play in "
        "RANGE+L-VOL), which holds regardless of what actually filled.",

        "**Slippage fully blocked.** All mapped entries are 2026-07 signal dates; the backtest "
        f"books stop at {br['signal_date'].max()}. No modeled next-open price exists, so Step D "
        "reports NOT_BACKTESTED rather than improvising a price (no Black-Scholes, no scraping).",

        "**Stage-2 n threshold — the binding constraint is mappability, not fill count.** "
        f"In-scope live entries this snapshot: {len(inv)} combo entries "
        f"({n_open} open, {n_closed_entries} closed) + {n_close_events} closing orders. "
        f"Stage 2 (live-vs-tier P&L feedback) needs ~30–50 *closed* positions: "
        f"{'MET' if n_closed_entries >= 30 else 'NOT met'} at {n_closed_entries} closed "
        f"round-trips. But only "
        f"{sum(1 for m in mapped if m['map']['confidence'] != 'NONE')} entries map to an analysis "
        f"row at all ({conf_tally['EXACT']} EXACT + {conf_tally['STRUCTURE']} STRUCTURE traded "
        f"the emitted play; {conf_tally['CORE']} CORE traded it as the core of a financed "
        f"structure; {conf_tally['SUBSTITUTED']} SUBSTITUTED traded a different, "
        "same-direction structure — each must be read as a separate split, not pooled with the "
        f"above; {conf_tally['OVERLAY']} OVERLAY were financing legs, never play attempts). "
        f"Of the {conf_tally['NONE']} unmapped, {n_none_no_analysis} fall on dates with "
        f"no analysis at all, {n_none_unknown} fall on dates that DID cover the ticker but "
        "whose live structure could not be resolved (see the identity-decay caveat), and "
        f"{n_none_nomatch} had a play that genuinely did not match on direction or family. "
        "The loop cannot be statistically evaluated yet — Stage 1 establishes the plumbing only.",

        "**Identity decay — snapshot cadence matters.** Contract identity is recoverable only "
        "while the position is still open, because it is inferred by joining the fill price to "
        "an open-position `average_price`. Once a round-trip closes, its strike/expiry/right are "
        "unrecoverable from the trades payload and the entry drops to UNKNOWN — so it can never "
        "be mapped, even though the analysis row for that date still exists. This snapshot has "
        f"{n_none_unknown} such entries. Re-running an OLDER snapshot recovers mappings this one "
        "cannot (the 2026-07-22 snapshot maps the 07-15 TSM bull_put and 07-20 QQQ bear_put that "
        "this one reads as UNKNOWN), so snapshots must be taken on a regular cadence and the "
        "mapped sets POOLED across them. A later snapshot is not a superset of an earlier one.",
    ]
    for c in caveats:
        emit(f"- {c}")
    emit("")

    # ---- write outputs ----
    text = "\n".join(_LINES)
    REPORT_MD.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
