"""
Aggregate parsed Barchart CSV rows into compact, LLM-friendly summaries.

Two CSV shapes are supported:

- **Flow** (`options-flow-*.csv`, `etf-flow-*.csv`): one row per executed trade.
  Has Premium, Side, *, Code columns. Aggregated by ticker into a rollup
  table (total / call / put premium, sentiment counts, opening-flag counts,
  weighted-avg DTE & IV, biggest single trade) plus the top-N largest single
  trades raw.

- **Unusual** (`unusual-stock-*.csv`, `unusual-etf-*.csv`): one row per
  strike-day with elevated Vol/OI. No Premium / Side / Code. Aggregated by
  ticker (trade count, total volume, max Vol/OI, calls/puts, DTE range,
  biggest single Vol/OI) plus the top-N rows by Vol/OI raw.

The functions return strings of markdown so they drop straight into the
existing `prepare_analysis.py` stdout-to-LLM pipeline.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Iterable


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _to_float(x: str | float | int | None) -> float:
    """Parse a Barchart numeric cell to float. Returns 0.0 on failure.

    Handles bare numbers, percent strings ('331.14%'), and comma-separated
    thousands ('1,234.56'). Empty / 'unch' / None → 0.0.
    """
    if x is None or x == "":
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "").rstrip("%")
    if not s or s.lower() in {"unch", "n/a", "na"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_int(x: str | float | int | None) -> int:
    return int(_to_float(x))


def _classify_sentiment(opt_type: str, side: str) -> str:
    """Apply Barchart's bullish/bearish rules (see config/barchart-reference.md).

    - Call on ask  → bullish
    - Put  on bid  → bullish
    - Call on bid  → bearish
    - Put  on ask  → bearish
    - anything on mid → neutral
    """
    t = (opt_type or "").strip().lower()
    s = (side or "").strip().lower()
    if t == "call" and s == "ask":
        return "bullish"
    if t == "put" and s == "bid":
        return "bullish"
    if t == "call" and s == "bid":
        return "bearish"
    if t == "put" and s == "ask":
        return "bearish"
    return "neutral"


def _fmt_money(x: float) -> str:
    """Compact dollar formatter: 10300100 → '$10.3M', 850000 → '$850K'."""
    if x is None:
        return "$0"
    ax = abs(x)
    sign = "-" if x < 0 else ""
    if ax >= 1_000_000_000:
        return f"{sign}${ax / 1_000_000_000:.2f}B"
    if ax >= 1_000_000:
        return f"{sign}${ax / 1_000_000:.2f}M"
    if ax >= 1_000:
        return f"{sign}${ax / 1_000:.0f}K"
    return f"{sign}${ax:.0f}"


def _fmt_ratio(num: float, den: float) -> str:
    if den <= 0:
        return "∞" if num > 0 else "—"
    return f"{num / den:.2f}"


# ---------------------------------------------------------------------------
# Flow aggregation
# ---------------------------------------------------------------------------

# Column names as they appear in Barchart flow CSV headers.
_FLOW_SYMBOL    = "Symbol"
_FLOW_UPRICE    = "Price~"   # underlying price at trade time
_FLOW_TYPE      = "Type"
_FLOW_STRIKE    = "Strike"
_FLOW_DTE       = "DTE"
_FLOW_SIDE      = "Side"
_FLOW_PREMIUM   = "Premium"
_FLOW_SIZE      = "Size"
_FLOW_IV        = "IV"
_FLOW_DELTA     = "Delta"
_FLOW_OPENFLAG  = "*"
_FLOW_CODE      = "Code"
_FLOW_TIME      = "Time"

# |delta| at or above this is treated as a stock substitute (financing /
# conversion / replacement) — premium there is mostly intrinsic, not a bet on a
# move. Used for the per-ticker financing share, not to discard the direction.
_FINANCING_DELTA = 0.85

# DTE maturity buckets (label, inclusive upper bound). Mirrors the method files'
# interpretive table: event/gamma, tactical, medium-term, strategic/LEAP.
_DTE_BUCKETS = (("event", 14), ("tact", 60), ("med", 180), ("strat", None))


def _dte_bucket(dte: float) -> str:
    for label, hi in _DTE_BUCKETS:
        if hi is None or dte <= hi:
            return label
    return _DTE_BUCKETS[-1][0]


def _trade_extrinsic(prem: float, opt_type: str, spot: float, strike: float, size: int) -> float:
    """Extrinsic (time-value) share of a trade's premium, floored at 0.

    Deep-ITM premium is mostly intrinsic — stock exposure, not optionality — so
    ranking on raw premium lets financing/conversion flow pose as conviction.
    When spot or strike is missing the trade is NOT discounted (extrinsic =
    full premium): absence of data is never treated as evidence of financing.
    """
    t = (opt_type or "").strip().lower()
    if spot <= 0 or strike <= 0 or size <= 0 or t not in ("call", "put"):
        return prem
    intrinsic_per_share = max(spot - strike, 0.0) if t == "call" else max(strike - spot, 0.0)
    return max(prem - intrinsic_per_share * size * 100, 0.0)


def _flow_ticker_rows(rows: Iterable[dict]) -> list[dict]:
    """Group flow rows by symbol and compute per-ticker aggregates."""
    by_sym: dict[str, dict] = defaultdict(lambda: {
        "symbol": "",
        "trades": 0,
        "premium_total": 0.0,
        "premium_call": 0.0,
        "premium_put": 0.0,
        "ext_total": 0.0,
        "ext_call": 0.0,
        "ext_put": 0.0,
        "delta_notional": 0.0,
        "fin_premium": 0.0,
        "size_total": 0,
        "bullish": 0,
        "bearish": 0,
        "neutral": 0,
        "to_open": 0,
        "buy_to_open": 0,
        "sell_to_open": 0,
        "_dte_premium_sum": 0.0,
        "_iv_premium_sum": 0.0,
        "_ext_by_bucket": defaultdict(float),
        "biggest": None,  # (premium, type, strike, side, dte, time)
    })

    for r in rows:
        sym = (r.get(_FLOW_SYMBOL) or "").strip()
        if not sym:
            continue
        prem = _to_float(r.get(_FLOW_PREMIUM))
        opt_type = (r.get(_FLOW_TYPE) or "").strip()
        side = (r.get(_FLOW_SIDE) or "").strip()
        dte = _to_float(r.get(_FLOW_DTE))
        iv = _to_float(r.get(_FLOW_IV))  # IV is "331.14%" → 331.14
        flag = (r.get(_FLOW_OPENFLAG) or "").strip()
        size = _to_int(r.get(_FLOW_SIZE))
        spot = _to_float(r.get(_FLOW_UPRICE))
        strike = _to_float(r.get(_FLOW_STRIKE))
        delta = _to_float(r.get(_FLOW_DELTA))
        ext = _trade_extrinsic(prem, opt_type, spot, strike, size)

        agg = by_sym[sym]
        agg["symbol"] = sym
        agg["trades"] += 1
        agg["premium_total"] += prem
        agg["size_total"] += size
        agg["ext_total"] += ext
        # Share-equivalent dollar exposure (delta × contracts × 100 × spot),
        # signed — the conviction-size axis for deep-ITM/stock-substitute flow.
        agg["delta_notional"] += delta * size * 100 * spot
        if abs(delta) >= _FINANCING_DELTA:
            agg["fin_premium"] += prem
        agg["_ext_by_bucket"][_dte_bucket(dte)] += ext
        if opt_type.lower() == "call":
            agg["premium_call"] += prem
            agg["ext_call"] += ext
        elif opt_type.lower() == "put":
            agg["premium_put"] += prem
            agg["ext_put"] += ext

        sent = _classify_sentiment(opt_type, side)
        agg[sent] += 1

        # Opening-flag values in real data are CamelCase no spaces.
        f = flag.replace(" ", "").lower()
        if f == "toopen":
            agg["to_open"] += 1
        elif f == "buytoopen":
            agg["buy_to_open"] += 1
        elif f == "selltoopen":
            agg["sell_to_open"] += 1

        agg["_dte_premium_sum"] += dte * prem
        agg["_iv_premium_sum"]  += iv * prem

        big = agg["biggest"]
        if big is None or prem > big[0]:
            agg["biggest"] = (prem, opt_type, r.get(_FLOW_STRIKE, ""), side, dte, r.get(_FLOW_TIME, ""))

    out = []
    for sym, a in by_sym.items():
        pt = a["premium_total"]
        dte_w = a["_dte_premium_sum"] / pt if pt > 0 else 0.0
        iv_w  = a["_iv_premium_sum"]  / pt if pt > 0 else 0.0
        # Dominant DTE bucket by extrinsic premium — where the real (time-value)
        # money sits on the maturity axis, e.g. "strat 71%".
        buckets = a["_ext_by_bucket"]
        ext_sum = sum(buckets.values())
        if ext_sum > 0:
            top_label, top_val = max(buckets.items(), key=lambda kv: kv[1])
            horizon = f"{top_label} {top_val / ext_sum * 100:.0f}%"
        else:
            horizon = "—"
        out.append({
            "symbol": sym,
            "trades": a["trades"],
            "premium_total": pt,
            "premium_call": a["premium_call"],
            "premium_put": a["premium_put"],
            "ext_total": a["ext_total"],
            "ext_call": a["ext_call"],
            "ext_put": a["ext_put"],
            "delta_notional": a["delta_notional"],
            # Share of premium from |delta| ≥ 0.85 trades — the stock-substitute
            # (financing/conversion/replacement) fraction of the headline number.
            "fin_share": (a["fin_premium"] / pt) if pt > 0 else 0.0,
            "horizon": horizon,
            "size_total": a["size_total"],
            # Avg $ per contract — high = expensive/high-IV/deep-ITM options, i.e.
            # premium driven by price not by positioning size.
            "prem_per_ct": (pt / a["size_total"]) if a["size_total"] else 0.0,
            "cp_ratio": _fmt_ratio(a["premium_call"], a["premium_put"]),
            "bullish": a["bullish"],
            "bearish": a["bearish"],
            "neutral": a["neutral"],
            "to_open": a["to_open"],
            "buy_to_open": a["buy_to_open"],
            "sell_to_open": a["sell_to_open"],
            "dte_w": dte_w,
            "iv_w": iv_w,
            "biggest": a["biggest"],
        })

    out.sort(key=lambda r: r["ext_total"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Conviction scoring (direction-agnostic)
# ---------------------------------------------------------------------------
#
# The score answers "how much should this name be looked at today", NOT
# "is it bullish or bearish". It is built only from NORMALIZED inputs so an
# expensive underlying cannot buy its way up the list with raw premium:
#
#   flow    EXTRINSIC-premium rank WITHIN the day, GUARDED by size rank   0–3
#   rep     repetition — number of trades clustering on the name         0–2
#   cross   cross-section — also appears in the unusual-activity dataset  0 / 2
#   voloi   strength of the name's unusual Vol/OI print, if any           0–2
#   open    ≥1 BuyToOpen / SellToOpen / ToOpen label present              0 / 1
#   persist extra days the name recurs across the window (multi-day)     0–3
#
# The `flow` component = min(ext_rank, size_rank + 1). Extrinsic premium
# (premium minus intrinsic value) leads: deep-ITM financing/conversion/
# stock-replacement premium is mostly intrinsic — stock exposure, not a bet on
# a move — so ranking raw premium let it pose as conviction. Contract size can
# only *cap* the rank, never lift it: a name big on extrinsic but thin on
# contracts is vol-/price-inflated and gets discounted, while cheap high-volume
# lottery flow (big size, tiny premium) is never boosted. Premium already
# embeds IV (price ∝ vega), so IV is deliberately NOT a separate term — see
# config/analysis-roadmap.md. When the Size column is absent the size cap never
# binds; when Price~/Strike are absent extrinsic falls back to full premium.
#
# A missing opening label scores 0, never negative — Barchart frequently omits
# the flag, and absence of the label is not evidence the trade was closing.
# Direction (bull/bear) lives in the separate sentiment columns; it never feeds
# this number. Single-day ceiling is 10; persistence can push it to 13.

_SCORE_BUCKETS = (  # (min_score, label), highest first
    (9, "high-conv"),
    (6, "candidate"),
    (3, "watch"),
    (0, "ignore"),
)


def score_label(score: float) -> str:
    for threshold, label in _SCORE_BUCKETS:
        if score >= threshold:
            return label
    return "ignore"


def _voloi_by_symbol(unusual_rows: Iterable[dict] | None) -> dict[str, float]:
    """Max Vol/OI per symbol from an unusual section — premium-independent."""
    out: dict[str, float] = {}
    for r in unusual_rows or []:
        sym = (r.get(_UN_SYMBOL) or "").strip()
        if not sym:
            continue
        out[sym] = max(out.get(sym, 0.0), _to_float(r.get(_UN_VOLOI)))
    return out


def score_flow_rollup(
    rollup: list[dict],
    unusual_syms: set[str] | None = None,
    voloi_by_sym: dict[str, float] | None = None,
    persist_days_by_sym: dict[str, int] | None = None,
) -> list[dict]:
    """Attach a direction-agnostic conviction score to each rollup row.

    Adds keys ``score`` (int), ``score_label`` (str), ``score_parts`` (dict).
    Mutates and returns the same list. Every input other than the rollup is
    optional — absent corroboration simply scores 0 for that component, it is
    never a penalty.
    """
    unusual_syms = unusual_syms or set()
    voloi_by_sym = voloi_by_sym or {}
    persist_days_by_sym = persist_days_by_sym or {}

    # Rank on extrinsic premium (falls back to raw premium for rows built
    # without Price~/Strike, where no intrinsic discount is computable).
    exts = [r.get("ext_total", r["premium_total"]) for r in rollup]
    sizes = [r.get("size_total", 0) for r in rollup]
    n = len(exts)

    def _rank_bucket(value: float, population: list[float]) -> int:
        """3/2/1/0 by where `value` ranks within the day (0 = top). Fraction of
        names strictly larger; ties share a bucket, so when a measure is missing
        for everyone (all equal) nobody is penalised."""
        pct = (sum(1 for v in population if v > value) / n) if n else 1.0
        if pct <= 0.05:
            return 3
        if pct <= 0.15:
            return 2
        if pct <= 0.35:
            return 1
        return 0

    for r in rollup:
        sym = r["symbol"]
        # Extrinsic premium leads but contract size can only cap it, never lift
        # it:
        #   flow = min(ext_rank, size_rank + 1)
        # discounts vol-/price-inflated premium (thin size), without boosting
        # cheap high-volume lottery flow (thin premium). Absent Size → size_rank
        # is 3 for all → cap never binds → flow falls back to extrinsic rank.
        ext_rank = _rank_bucket(r.get("ext_total", r["premium_total"]), exts)
        size_rank = _rank_bucket(r.get("size_total", 0), sizes)
        flow = min(ext_rank, size_rank + 1)

        trades = r["trades"]
        rep = 2 if trades >= 8 else 1 if trades >= 3 else 0

        cross = 2 if sym in unusual_syms else 0

        voloi = voloi_by_sym.get(sym, 0.0)
        voloi_pts = 2 if voloi >= 25 else 1 if voloi >= 10 else 0

        opening = 1 if (r["buy_to_open"] + r["sell_to_open"] + r["to_open"]) > 0 else 0

        persist = min(max(persist_days_by_sym.get(sym, 0), 0), 3)

        parts = {
            "flow": flow, "rep": rep, "cross": cross,
            "voloi": voloi_pts, "open": opening, "persist": persist,
        }
        total = sum(parts.values())
        r["score"] = total
        r["score_parts"] = parts
        r["score_label"] = score_label(total)

    return rollup


def _flow_rollup_md(rollup: list[dict], title: str) -> str:
    if not rollup:
        return f"### {title} — ticker rollup\n\n_No data._\n"
    headers = [
        "Symbol", "Score", "Trades", "Total$", "Ext$", "Fin%", "ΔNot$",
        "Ctts", "$/ct", "Call$", "Put$", "C/P",
        "Bull", "Bear", "Mid",
        "BTO", "STO", "ToOpen",
        "wDTE", "Hzn", "wIV%",
        "Biggest trade",
    ]
    sep = " | ".join(["---"] * len(headers))
    lines = []
    for r in rollup:
        big = r["biggest"]
        if big is None:
            big_str = "—"
        else:
            prem, opt_type, strike, side, dte, _ = big
            big_str = f"{_fmt_money(prem)} {opt_type} ${strike} {side} {int(dte)}d"
        score = r.get("score")
        score_str = f"{score} {r.get('score_label', '')}".strip() if score is not None else "—"
        lines.append(" | ".join([
            r["symbol"],
            score_str,
            str(r["trades"]),
            _fmt_money(r["premium_total"]),
            _fmt_money(r.get("ext_total", 0.0)),
            f"{r.get('fin_share', 0.0) * 100:.0f}%",
            _fmt_money(r.get("delta_notional", 0.0)),
            f"{r.get('size_total', 0):,}",
            _fmt_money(r.get("prem_per_ct", 0.0)),
            _fmt_money(r["premium_call"]),
            _fmt_money(r["premium_put"]),
            r["cp_ratio"],
            str(r["bullish"]),
            str(r["bearish"]),
            str(r["neutral"]),
            str(r["buy_to_open"]),
            str(r["sell_to_open"]),
            str(r["to_open"]),
            f"{r['dte_w']:.0f}",
            r.get("horizon", "—"),
            f"{r['iv_w']:.0f}",
            big_str,
        ]))
    body = "\n".join(lines)
    return f"### {title} — ticker rollup ({len(rollup)} symbols, ranked by score)\n\n{' | '.join(headers)}\n{sep}\n{body}\n"


def _flow_top_trades_md(rows: list[dict], top_n: int, title: str) -> str:
    """Emit the top-N trades by Premium with full columns preserved."""
    sortable = [(r, _to_float(r.get(_FLOW_PREMIUM))) for r in rows]
    sortable.sort(key=lambda t: t[1], reverse=True)
    top = [r for r, _ in sortable[:top_n]]
    if not top:
        return f"### {title} — top trades\n\n_No data._\n"
    headers = list(top[0].keys())
    sep = " | ".join(["---"] * len(headers))
    body = "\n".join(" | ".join(str(r.get(h, "")) for h in headers) for r in top)
    return f"### {title} — top {len(top)} trades by premium\n\n{' | '.join(headers)}\n{sep}\n{body}\n"


def build_scored_flow_rollup(
    rows: list[dict],
    unusual_rows: list[dict] | None = None,
) -> list[dict]:
    """Per-ticker flow rollup with conviction scores attached, sorted best-first.

    When ``unusual_rows`` (the matching unusual-activity section) is supplied the
    conviction score also credits cross-section overlap and Vol/OI strength.
    Shared by the markdown summary and the CSV export so both see identical
    scoring and ordering.
    """
    rollup = _flow_ticker_rows(rows)
    unusual_syms = {(r.get(_UN_SYMBOL) or "").strip() for r in (unusual_rows or [])}
    unusual_syms.discard("")
    score_flow_rollup(rollup, unusual_syms, _voloi_by_symbol(unusual_rows))
    rollup.sort(key=lambda r: (r["score"], r.get("ext_total", r["premium_total"])), reverse=True)
    return rollup


def summarize_flow(
    rows: list[dict],
    title: str,
    top_n: int = 75,
    unusual_rows: list[dict] | None = None,
) -> str:
    """Compact flow-section summary: scored ticker rollup + top-N raw trades.

    When ``unusual_rows`` (the matching unusual-activity section) is supplied the
    conviction score also credits cross-section overlap and Vol/OI strength; the
    rollup is sorted high-to-low by score so the names worth reading lead.
    """
    if not rows:
        return f"## {title}\n\n_No data available._\n"
    rollup = build_scored_flow_rollup(rows, unusual_rows)
    return (
        f"## {title}\n\n"
        f"_{len(rows)} trades across {len(rollup)} symbols._\n\n"
        + _flow_rollup_md(rollup, title)
        + "\n"
        + _flow_top_trades_md(rows, top_n, title)
    )


# Machine-readable CSV column order for the scored flow rollup. Money columns are
# emitted as raw rounded numbers (not "$10.3M") so the file sorts/sums in a
# spreadsheet; the score breakdown is split into its component columns.
FLOW_CSV_COLUMNS = [
    "Section", "Symbol", "Score", "ScoreLabel",
    "Flow", "Rep", "Cross", "VolOI", "Open", "Persist",
    "Trades", "TotalPremium", "ExtPremium", "ExtCallPremium", "ExtPutPremium",
    "DeltaNotional", "FinancingShare", "Horizon",
    "Contracts", "PremPerContract",
    "CallPremium", "PutPremium", "CallPutRatio",
    "Bull", "Bear", "Mid", "BTO", "STO", "ToOpen",
    "wDTE", "wIV", "BiggestTrade",
]


def _biggest_trade_str(big) -> str:
    if not big:
        return ""
    prem, opt_type, strike, side, dte, _ = big
    return f"{_fmt_money(prem)} {opt_type} ${strike} {side} {int(dte)}d"


def flow_rollup_csv(sections: list[tuple[str, list[dict]]]) -> str:
    """Render one or more scored flow rollups as a single CSV string.

    ``sections`` is ``[(section_label, scored_rollup), ...]`` where each rollup
    comes from :func:`build_scored_flow_rollup`. Rows are tagged with their
    section so stock and ETF flow can share one file.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FLOW_CSV_COLUMNS)
    writer.writeheader()
    for section_label, rollup in sections:
        for r in rollup:
            parts = r.get("score_parts", {})
            writer.writerow({
                "Section": section_label,
                "Symbol": r["symbol"],
                "Score": r.get("score", ""),
                "ScoreLabel": r.get("score_label", ""),
                "Flow": parts.get("flow", ""),
                "Rep": parts.get("rep", ""),
                "Cross": parts.get("cross", ""),
                "VolOI": parts.get("voloi", ""),
                "Open": parts.get("open", ""),
                "Persist": parts.get("persist", ""),
                "Trades": r["trades"],
                "TotalPremium": round(r["premium_total"]),
                "ExtPremium": round(r.get("ext_total", 0.0)),
                "ExtCallPremium": round(r.get("ext_call", 0.0)),
                "ExtPutPremium": round(r.get("ext_put", 0.0)),
                "DeltaNotional": round(r.get("delta_notional", 0.0)),
                "FinancingShare": round(r.get("fin_share", 0.0), 3),
                "Horizon": r.get("horizon", ""),
                "Contracts": r.get("size_total", 0),
                "PremPerContract": round(r.get("prem_per_ct", 0.0)),
                "CallPremium": round(r["premium_call"]),
                "PutPremium": round(r["premium_put"]),
                "CallPutRatio": r["cp_ratio"],
                "Bull": r["bullish"],
                "Bear": r["bearish"],
                "Mid": r["neutral"],
                "BTO": r["buy_to_open"],
                "STO": r["sell_to_open"],
                "ToOpen": r["to_open"],
                "wDTE": round(r["dte_w"]),
                "wIV": round(r["iv_w"]),
                "BiggestTrade": _biggest_trade_str(r["biggest"]),
            })
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unusual aggregation
# ---------------------------------------------------------------------------

_UN_SYMBOL = "Symbol"
_UN_TYPE   = "Type"
_UN_STRIKE = "Strike"
_UN_DTE    = "DTE"
_UN_VOLUME = "Volume"
_UN_VOLOI  = "Vol/OI"
_UN_MONEY  = "Moneyness"


def _unusual_ticker_rows(rows: Iterable[dict]) -> list[dict]:
    by_sym: dict[str, dict] = defaultdict(lambda: {
        "symbol": "",
        "rows": 0,
        "calls": 0,
        "puts": 0,
        "total_volume": 0,
        "max_voloi": 0.0,
        "dte_min": None,
        "dte_max": None,
        "biggest": None,  # (voloi, type, strike, dte, moneyness)
    })

    for r in rows:
        sym = (r.get(_UN_SYMBOL) or "").strip()
        if not sym:
            continue
        opt_type = (r.get(_UN_TYPE) or "").strip()
        voloi = _to_float(r.get(_UN_VOLOI))
        vol = _to_int(r.get(_UN_VOLUME))
        dte = _to_int(r.get(_UN_DTE))

        agg = by_sym[sym]
        agg["symbol"] = sym
        agg["rows"] += 1
        if opt_type.lower() == "call":
            agg["calls"] += 1
        elif opt_type.lower() == "put":
            agg["puts"] += 1
        agg["total_volume"] += vol
        agg["max_voloi"] = max(agg["max_voloi"], voloi)
        agg["dte_min"] = dte if agg["dte_min"] is None else min(agg["dte_min"], dte)
        agg["dte_max"] = dte if agg["dte_max"] is None else max(agg["dte_max"], dte)

        big = agg["biggest"]
        if big is None or voloi > big[0]:
            agg["biggest"] = (voloi, opt_type, r.get(_UN_STRIKE, ""), dte, r.get(_UN_MONEY, ""))

    out = list(by_sym.values())
    out.sort(key=lambda r: r["max_voloi"], reverse=True)
    return out


def _unusual_rollup_md(rollup: list[dict], title: str) -> str:
    if not rollup:
        return f"### {title} — ticker rollup\n\n_No data._\n"
    headers = ["Symbol", "Rows", "Calls", "Puts", "TotalVol", "MaxVol/OI", "DTE", "Biggest"]
    sep = " | ".join(["---"] * len(headers))
    lines = []
    for r in rollup:
        big = r["biggest"]
        if big is None:
            big_str = "—"
        else:
            voloi, opt_type, strike, dte, money = big
            big_str = f"{voloi:.1f}x {opt_type} ${strike} {dte}d {money}"
        dte_range = f"{r['dte_min']}–{r['dte_max']}"
        lines.append(" | ".join([
            r["symbol"], str(r["rows"]), str(r["calls"]), str(r["puts"]),
            f"{r['total_volume']:,}", f"{r['max_voloi']:.1f}", dte_range, big_str,
        ]))
    body = "\n".join(lines)
    return f"### {title} — ticker rollup ({len(rollup)} symbols)\n\n{' | '.join(headers)}\n{sep}\n{body}\n"


def _unusual_top_rows_md(rows: list[dict], top_n: int, title: str) -> str:
    sortable = [(r, _to_float(r.get(_UN_VOLOI))) for r in rows]
    sortable.sort(key=lambda t: t[1], reverse=True)
    top = [r for r, _ in sortable[:top_n]]
    if not top:
        return f"### {title} — top rows\n\n_No data._\n"
    headers = list(top[0].keys())
    sep = " | ".join(["---"] * len(headers))
    body = "\n".join(" | ".join(str(r.get(h, "")) for h in headers) for r in top)
    return f"### {title} — top {len(top)} rows by Vol/OI\n\n{' | '.join(headers)}\n{sep}\n{body}\n"


def summarize_unusual(rows: list[dict], title: str, top_n: int = 50) -> str:
    if not rows:
        return f"## {title}\n\n_No data available._\n"
    rollup = _unusual_ticker_rows(rows)
    return (
        f"## {title}\n\n"
        f"_{len(rows)} strikes across {len(rollup)} symbols._\n\n"
        + _unusual_rollup_md(rollup, title)
        + "\n"
        + _unusual_top_rows_md(rows, top_n, title)
    )


# ---------------------------------------------------------------------------
# Cross-section
# ---------------------------------------------------------------------------

def cross_section_tickers(flow_rows: Iterable[dict], unusual_rows: Iterable[dict]) -> list[str]:
    """Tickers that appear in BOTH the flow and unusual sections — high signal."""
    flow_syms    = {(r.get(_FLOW_SYMBOL) or "").strip() for r in flow_rows}
    unusual_syms = {(r.get(_UN_SYMBOL)   or "").strip() for r in unusual_rows}
    return sorted(s for s in (flow_syms & unusual_syms) if s)


def cross_section_md(flow_rows: list[dict], unusual_rows: list[dict]) -> str:
    tickers = cross_section_tickers(flow_rows, unusual_rows)
    if not tickers:
        return "## Cross-section (flow ∩ unusual)\n\n_No overlapping tickers._\n"
    return (
        "## Cross-section (flow ∩ unusual)\n\n"
        f"_{len(tickers)} tickers appear in both stock flow and stock unusual — high-signal candidates:_\n\n"
        + ", ".join(tickers) + "\n"
    )


# ---------------------------------------------------------------------------
# Hedge pressure (market-level, first-class)
# ---------------------------------------------------------------------------
#
# "Hedge pressure" — broad protection bought on indexes/credit/sector ETFs while
# single-stock demand stays bullish — used to be rediscovered qualitatively
# every run. This makes it a precomputed 0–100 metric:
#
#   score = 100 × hedge_put_ext / (hedge_put_ext + stock_call_ext)
#
# where hedge_put_ext is EXTRINSIC put premium on the hedge-vehicle ETFs (deep-
# ITM financing puts are excluded by construction) and stock_call_ext is total
# extrinsic call premium across single stocks (the bullish-demand offset).

# Index / credit / core-sector vehicles institutions use to hedge books.
HEDGE_TICKERS = frozenset({"SPY", "QQQ", "IWM", "DIA", "RSP", "HYG", "LQD", "SMH", "SOXX"})

_HEDGE_PRESSURE_BUCKETS = (  # (min_score, label), highest first
    (80, "panic"),
    (60, "risk-off"),
    (40, "hedge-pressure"),
    (20, "neutral"),
    (0, "risk-on"),
)


def hedge_pressure(stock_flow_rows: list[dict], etf_flow_rows: list[dict]) -> dict | None:
    """Compute the hedge-pressure score for one day's flow. None when no data.

    Returns ``{"score", "label", "hedge_put_ext", "stock_call_ext", "by_ticker"}``
    where ``by_ticker`` is the extrinsic put premium per hedge vehicle (largest
    first) so the read stays auditable.
    """
    etf_rollup = _flow_ticker_rows(etf_flow_rows or [])
    stock_rollup = _flow_ticker_rows(stock_flow_rows or [])

    by_ticker = {
        r["symbol"]: r["ext_put"]
        for r in etf_rollup
        if r["symbol"] in HEDGE_TICKERS and r["ext_put"] > 0
    }
    hedge_put_ext = sum(by_ticker.values())
    stock_call_ext = sum(r["ext_call"] for r in stock_rollup)

    denom = hedge_put_ext + stock_call_ext
    if denom <= 0:
        return None
    score = round(100 * hedge_put_ext / denom)
    label = next(lbl for mn, lbl in _HEDGE_PRESSURE_BUCKETS if score >= mn)
    return {
        "score": score,
        "label": label,
        "hedge_put_ext": hedge_put_ext,
        "stock_call_ext": stock_call_ext,
        "by_ticker": dict(sorted(by_ticker.items(), key=lambda kv: kv[1], reverse=True)),
    }


def hedge_pressure_md(stock_flow_rows: list[dict], etf_flow_rows: list[dict]) -> str:
    """The `## Hedge pressure` markdown section for the prepared analysis."""
    hp = hedge_pressure(stock_flow_rows, etf_flow_rows)
    if hp is None:
        return "## Hedge pressure\n\n_No flow data to compute._\n"
    breakdown = ", ".join(f"{sym} {_fmt_money(v)}" for sym, v in hp["by_ticker"].items()) or "—"
    scale = " · ".join(
        f"{mn}–{hi}={lbl}"
        for (mn, lbl), hi in zip(reversed(_HEDGE_PRESSURE_BUCKETS),
                                 (20, 40, 60, 80, 100))
    )
    return (
        "## Hedge pressure\n\n"
        f"**Score: {hp['score']}/100 — {hp['label'].upper()}** "
        f"(scale: {scale})\n\n"
        f"- Hedge-vehicle extrinsic put premium: {_fmt_money(hp['hedge_put_ext'])} "
        f"({breakdown})\n"
        f"- Single-stock extrinsic call premium (bullish offset): "
        f"{_fmt_money(hp['stock_call_ext'])}\n\n"
        "_Extrinsic-only by construction: deep-ITM financing/conversion puts do "
        "not count as hedge demand. The buckets are static heuristics — read the "
        "score through the Baseline context percentiles before letting it set "
        "the regime, and treat hedge-pressure as protection on longs being kept, "
        "not a directional price-down forecast._\n"
    )


# ---------------------------------------------------------------------------
# Persistence (multi-day)
# ---------------------------------------------------------------------------

def _persistence_lean(row: dict) -> str:
    """Direction tilt for the persistence view, kept SEPARATE from the score.

    Uses call vs put premium with a 20% deadband so balanced names read 'Mix'.
    """
    call, put = row.get("premium_call", 0.0), row.get("premium_put", 0.0)
    if call > put * 1.2:
        return "Bull"
    if put > call * 1.2:
        return "Bear"
    return "Mix"


def summarize_persistence(days: list[dict], title: str, top_n: int = 30) -> str:
    """Track per-ticker flow across several trading days.

    ``days`` is ordered **oldest → newest**; each entry is
    ``{"date": "YYYY-MM-DD", "flow_rows": [...], "unusual_rows": [...]}``.

    The strongest signals are not single-day prints — they recur. This emits one
    row per ticker that appears on **two or more** days, showing its premium and
    conviction-score trajectory across the window plus a persistence-adjusted
    score (latest-day base score + 1 per recurring day, capped +3). Recomputed
    from the raw daily data each run, so no score state is stored anywhere.
    """
    if not days:
        return f"## {title} — persistence\n\n_No data._\n"

    dates = [d.get("date", "?") for d in days]
    # Score each day independently, indexed by symbol.
    per_day: list[dict[str, dict]] = []
    all_syms: set[str] = set()
    for d in days:
        rollup = _flow_ticker_rows(d.get("flow_rows") or [])
        un_rows = d.get("unusual_rows") or []
        un_syms = {(r.get(_UN_SYMBOL) or "").strip() for r in un_rows}
        un_syms.discard("")
        score_flow_rollup(rollup, un_syms, _voloi_by_symbol(un_rows))
        by_sym = {r["symbol"]: r for r in rollup}
        per_day.append(by_sym)
        all_syms.update(by_sym)

    records = []
    for sym in all_syms:
        present = [i for i, bs in enumerate(per_day) if sym in bs]
        days_present = len(present)
        if days_present < 2:  # persistence view = recurring names only
            continue
        latest_i = present[-1]
        latest_row = per_day[latest_i][sym]
        base = latest_row["score"]
        bonus = min(days_present - 1, 3)
        adjusted = base + bonus

        prem_traj = "·".join(
            _fmt_money(per_day[i][sym]["premium_total"]) if sym in per_day[i] else "—"
            for i in range(len(per_day))
        )
        score_traj = "·".join(
            str(per_day[i][sym]["score"]) if sym in per_day[i] else "—"
            for i in range(len(per_day))
        )
        records.append({
            "symbol": sym,
            "days": days_present,
            "prem_traj": prem_traj,
            "score_traj": score_traj,
            "bonus": bonus,
            "adjusted": adjusted,
            "label": score_label(adjusted),
            "lean": _persistence_lean(latest_row),
            "_latest_prem": latest_row["premium_total"],
        })

    if not records:
        return (
            f"## {title} — persistence ({len(days)} days: {dates[0]} → {dates[-1]})\n\n"
            "_No ticker appears on two or more days in this window._\n"
        )

    records.sort(key=lambda r: (r["adjusted"], r["days"], r["_latest_prem"]), reverse=True)
    records = records[:top_n]

    # Names recurring ≥3 days lead the section explicitly — a name showing up
    # session after session usually outweighs any single-day print.
    persistent = [r for r in records if r["days"] >= 3]
    callout = (
        "**Persistent names (≥3 days):** "
        + " · ".join(f"{r['symbol']} {r['days']}/{len(days)} ({r['lean']})" for r in persistent)
        + "\n\n"
    ) if persistent else ""

    headers = ["Symbol", "Days", "Premium/day", "Score/day", "Persist+", "Adj", "Label", "Lean"]
    sep = " | ".join(["---"] * len(headers))
    body = "\n".join(
        " | ".join([
            r["symbol"],
            f"{r['days']}/{len(days)}",
            r["prem_traj"],
            r["score_traj"],
            f"+{r['bonus']}",
            str(r["adjusted"]),
            r["label"],
            r["lean"],
        ])
        for r in records
    )
    return (
        f"## {title} — persistence ({len(days)} days: {dates[0]} → {dates[-1]})\n\n"
        f"{callout}"
        f"_Trajectories run oldest→newest ({' · '.join(dates)}). "
        f"Names on ≥2 days; 'Adj' = latest score + recurrence bonus. "
        f"'Lean' is a separate call/put tilt, not part of the score._\n\n"
        f"{' | '.join(headers)}\n{sep}\n{body}\n"
    )


# ---------------------------------------------------------------------------
# Raw / ticker-filter passthrough (used by --raw and --ticker)
# ---------------------------------------------------------------------------

def rows_to_markdown_raw(rows: list[dict], title: str) -> str:
    """Verbatim per-row markdown — the old default behavior of prepare_analysis."""
    if not rows:
        return f"## {title}\n\n_No data available._\n"
    headers = list(rows[0].keys())
    sep = " | ".join(["---"] * len(headers))
    body = "\n".join(" | ".join(str(r.get(h, "")) for h in headers) for r in rows)
    return f"## {title}\n\n{' | '.join(headers)}\n{sep}\n{body}\n"


def filter_by_ticker(rows: list[dict], ticker: str) -> list[dict]:
    t = ticker.strip().upper()
    return [r for r in rows if (r.get("Symbol") or "").strip().upper() == t]
