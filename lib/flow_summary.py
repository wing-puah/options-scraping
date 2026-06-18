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


def _fmt_iv_pts(x: float | None) -> str:
    """Signed IV points for the IVspr / IVskew columns: 12.3 → '+12', None → '—'."""
    if x is None:
        return "—"
    return f"{x:+.0f}"


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

# Columns dropped from raw trade rows — low signal for LLM analysis.
# Price~ is in the rollup context; Expiration Date duplicates DTE;
# Bid/Ask x Size and Trade price add noise; Time is not useful at this level.
_RAW_DROP_COLUMNS = frozenset({
    "Price~", "Expiration Date", "Bid x Size", "Ask x Size", "Trade", "Time",
    # Enriched columns: hide from raw trade tables; OI signal is shown as
    # normalized per-ticker aggregates in the breakdown section instead.
    "oi_d", "oi_prev", "oi_change", "vol_d",
    "eod_iv", "eod_delta", "eod_gamma", "eod_vega", "oi_enriched_on",
})

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


_MONEYNESS_BANDS = ("deep-OTM", "OTM", "ATM", "ITM", "deep-ITM")


def _otm_pct(strike: float, spot: float, opt_type: str) -> float | None:
    """Signed % from at-the-money: positive = OTM, negative = ITM."""
    if not (strike and spot):
        return None
    if opt_type.lower() == "call":
        return (strike - spot) / spot * 100
    return (spot - strike) / spot * 100


def _moneyness_band(otm_pct: float | None) -> str:
    if otm_pct is None:
        return "?"
    if otm_pct > 10:
        return "deep-OTM"
    if otm_pct > 2:
        return "OTM"
    if otm_pct > -2:
        return "ATM"
    if otm_pct > -10:
        return "ITM"
    return "deep-ITM"


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
        # OTM-probability-weighted extrinsic premium: Σ extrinsic × (1−|delta|).
        # Operationalizes the informed-trading measure of Hilliard et al. (2025)
        # — monetary size of the bet × risk-neutral probability of expiring OTM
        # — using |delta| as the P(ITM) proxy so P(OTM) ≈ 1−|delta|. Only trades
        # carrying a Delta cell contribute (absence of data is never credited).
        "otm_ext": 0.0,
        "delta_notional": 0.0,
        "fin_premium": 0.0,
        # Premium-weighted IV split by side, plus skew bands (Lin/Lu/Driessen
        # 2013): IV spread = call−put IV (positive → bullish), IV skew =
        # OTM-put − ATM-call IV (steeper → bearish). Directional context only —
        # never fed into the direction-agnostic conviction score.
        "_iv_call_prem_sum": 0.0,
        "_iv_put_prem_sum": 0.0,
        "_iv_otmput_sum": 0.0,
        "_iv_otmput_w": 0.0,
        "_iv_atmcall_sum": 0.0,
        "_iv_atmcall_w": 0.0,
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
        # OI enrichment accumulators (populated when oi_change is present)
        "_oi_by_bucket": defaultdict(int),   # (dte_label, moneyness_band) → net oi_change
        "_oi_confirm_n": 0,
        "_oi_total_n": 0,
        "_oi_call_sum": 0,
        "_oi_put_sum": 0,
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
        delta_cell = r.get(_FLOW_DELTA)
        has_delta = delta_cell not in (None, "")
        delta = _to_float(delta_cell)
        ext = _trade_extrinsic(prem, opt_type, spot, strike, size)
        t_lower = opt_type.lower()

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
        # OTM-probability weight: only when a Delta cell is present, so a missing
        # delta is never read as "deep OTM" and credited. P(OTM) ≈ 1−|delta|,
        # clamped to [0, 1]. Weights the *extrinsic* (already-financing-stripped)
        # premium toward economically-sized, low-delta (OTM) informed flow.
        if has_delta:
            p_otm = min(max(1.0 - abs(delta), 0.0), 1.0)
            agg["otm_ext"] += ext * p_otm
        agg["_ext_by_bucket"][_dte_bucket(dte)] += ext
        if t_lower == "call":
            agg["premium_call"] += prem
            agg["ext_call"] += ext
            agg["_iv_call_prem_sum"] += iv * prem
            # ATM call band for skew: 0.40 ≤ |delta| ≤ 0.60.
            if has_delta and 0.40 <= abs(delta) <= 0.60:
                agg["_iv_atmcall_sum"] += iv * prem
                agg["_iv_atmcall_w"] += prem
        elif t_lower == "put":
            agg["premium_put"] += prem
            agg["ext_put"] += ext
            agg["_iv_put_prem_sum"] += iv * prem
            # OTM put band for skew: |delta| ≤ 0.40.
            if has_delta and abs(delta) <= 0.40:
                agg["_iv_otmput_sum"] += iv * prem
                agg["_iv_otmput_w"] += prem

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

        oi_chg_raw = r.get("oi_change", "")
        if oi_chg_raw not in (None, ""):
            try:
                oi_chg = int(float(oi_chg_raw))
            except (ValueError, TypeError):
                oi_chg = None
            if oi_chg is not None:
                dte_label = _dte_bucket(dte) if dte else "?"
                m_band = _moneyness_band(_otm_pct(strike, spot, opt_type))
                agg["_oi_by_bucket"][(dte_label, m_band)] += oi_chg
                agg["_oi_total_n"] += 1
                if oi_chg > 0:
                    agg["_oi_confirm_n"] += 1
                if t_lower == "call":
                    agg["_oi_call_sum"] += oi_chg
                elif t_lower == "put":
                    agg["_oi_put_sum"] += oi_chg

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
        # Premium-weighted IV by side and the two directional vol reads. Each is
        # None when the requisite side / delta-band has no premium, so the table
        # shows "—" rather than a misleading 0.
        iv_call_w = (a["_iv_call_prem_sum"] / a["premium_call"]) if a["premium_call"] > 0 else None
        iv_put_w = (a["_iv_put_prem_sum"] / a["premium_put"]) if a["premium_put"] > 0 else None
        iv_spread = (iv_call_w - iv_put_w) if (iv_call_w is not None and iv_put_w is not None) else None
        otmput_iv = (a["_iv_otmput_sum"] / a["_iv_otmput_w"]) if a["_iv_otmput_w"] > 0 else None
        atmcall_iv = (a["_iv_atmcall_sum"] / a["_iv_atmcall_w"]) if a["_iv_atmcall_w"] > 0 else None
        iv_skew = (otmput_iv - atmcall_iv) if (otmput_iv is not None and atmcall_iv is not None) else None
        out.append({
            "symbol": sym,
            "trades": a["trades"],
            "premium_total": pt,
            "premium_call": a["premium_call"],
            "premium_put": a["premium_put"],
            "ext_total": a["ext_total"],
            "ext_call": a["ext_call"],
            "ext_put": a["ext_put"],
            "otm_ext": a["otm_ext"],
            "iv_call_w": iv_call_w,
            "iv_put_w": iv_put_w,
            "iv_spread": iv_spread,
            "iv_skew": iv_skew,
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
            # OI enrichment fields (None when no enriched data for this ticker)
            "oi_confirm_pct": round(a["_oi_confirm_n"] / a["_oi_total_n"] * 100)
                              if a["_oi_total_n"] > 0 else None,
            "cpir": round(a["_oi_call_sum"] / (a["_oi_call_sum"] + a["_oi_put_sum"]), 2)
                    if (a["_oi_call_sum"] + a["_oi_put_sum"]) != 0 else None,
            "oi_by_bucket": dict(a["_oi_by_bucket"]),
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
#   otm     OTM-prob-weighted extrinsic rank — informed OTM tell          0–2
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
# The `otm` component ranks otm_ext = Σ extrinsic × (1−|delta|) within the day,
# capped at 2. It rewards economically-sized flow concentrated in OTM contracts
# — the informed-trading tell of Hilliard et al. (2025) — and is 0 for any name
# whose trades carry no Delta cell (absence of data is never credited). It is
# moneyness/probability, not IV, so it does not violate the "no separate IV
# term" rule above. IV-augmentation (×IV, the paper's OIFCA variant) is left off
# deliberately to keep IV out of the score.
#
# A missing opening label scores 0, never negative — Barchart frequently omits
# the flag, and absence of the label is not evidence the trade was closing.
# Direction (bull/bear) lives in the separate sentiment columns; it never feeds
# this number. Single-day ceiling is 12; persistence can push it to 15.

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
    otm_exts = [r.get("otm_ext", 0.0) for r in rollup]
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

        # OTM-prob-weighted extrinsic rank, capped at 2. A name with no
        # delta-bearing trades (otm_ext == 0) scores 0 outright — _rank_bucket
        # would otherwise hand everyone the top bucket when the whole column is
        # zero, which would credit absent data.
        otm = 0 if r.get("otm_ext", 0.0) <= 0 else min(_rank_bucket(r["otm_ext"], otm_exts), 2)

        opening = 1 if (r["buy_to_open"] + r["sell_to_open"] + r["to_open"]) > 0 else 0

        persist = min(max(persist_days_by_sym.get(sym, 0), 0), 3)

        parts = {
            "flow": flow, "rep": rep, "cross": cross,
            "voloi": voloi_pts, "otm": otm, "open": opening, "persist": persist,
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
        "Symbol", "Score", "Trades", "Total$", "Ext$", "OTM$", "Fin%", "ΔNot$",
        "Ctts", "$/ct", "Call$", "Put$", "C/P",
        "Bull", "Bear", "Mid",
        "BTO", "STO", "ToOpen",
        "wDTE", "Hzn", "wIV%", "IVspr", "IVskew",
        "OIConf%", "CPIR",
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
            _fmt_money(r.get("otm_ext", 0.0)),
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
            _fmt_iv_pts(r.get("iv_spread")),
            _fmt_iv_pts(r.get("iv_skew")),
            f"{r['oi_confirm_pct']}%" if r.get("oi_confirm_pct") is not None else "—",
            f"{r['cpir']:.2f}"        if r.get("cpir")            is not None else "—",
            big_str,
        ]))
    body = "\n".join(lines)
    header_line = ' | '.join(headers)
    return f"### {title} — ticker rollup ({len(rollup)} symbols, ranked by score)\n\n{header_line}\n{sep}\n{body}\n"


def _flow_top_trades_md(
    rows: list[dict], top_tickers: list[str], raw_n: int, title: str
) -> str:
    """For each ticker in top_tickers (score order), emit top raw_n trades by premium."""
    by_ticker: dict[str, list[dict]] = {}
    for r in rows:
        sym = (r.get(_FLOW_SYMBOL) or "").strip()
        if sym in top_tickers:
            by_ticker.setdefault(sym, []).append(r)

    sections = []
    for sym in top_tickers:
        ticker_rows = by_ticker.get(sym, [])
        if not ticker_rows:
            continue
        ticker_rows.sort(key=lambda r: _to_float(r.get(_FLOW_PREMIUM)), reverse=True)
        top = ticker_rows[:raw_n]
        headers = [h for h in top[0].keys() if h not in _RAW_DROP_COLUMNS]
        sep = " | ".join(["---"] * len(headers))
        body = "\n".join(" | ".join(str(r.get(h, "")) for h in headers) for r in top)
        sections.append(f"#### {sym}\n\n{' | '.join(headers)}\n{sep}\n{body}\n")

    if not sections:
        return ""
    return f"### {title} — top {raw_n} trades per ticker (top {len(top_tickers)} by score)\n\n" + "\n".join(sections)


def _oi_breakdown_section(rollup: list[dict], top_n: int, title: str) -> str:
    """Per-ticker OI change breakdown by DTE bucket × moneyness band.

    Only emitted when at least one ticker in the rollup has enriched OI data.
    Tickers with no enrichment are silently skipped.
    """
    _DTE_ORDER = [b[0] for b in _DTE_BUCKETS]

    sections = []
    for r in rollup[:top_n]:
        bucket = r.get("oi_by_bucket", {})
        if not bucket:
            continue
        sym = r["symbol"]
        conf = r.get("oi_confirm_pct")
        cpir = r.get("cpir")
        meta = []
        if conf is not None:
            meta.append(f"Conf: {conf}%")
        if cpir is not None:
            meta.append(f"CPIR: {cpir:.2f}")
        meta_str = f"  ({' | '.join(meta)})" if meta else ""

        # Collect which moneyness bands actually appear for this ticker.
        present_bands = [b for b in _MONEYNESS_BANDS if any(
            b == m for (_, m) in bucket
        )]
        if not present_bands:
            continue

        header = "| DTE | " + " | ".join(present_bands) + " |"
        sep = "|-----|" + "|".join(["-----"] * len(present_bands)) + "|"
        rows_md = []
        for dte_label in _DTE_ORDER:
            cells = [bucket.get((dte_label, m), None) for m in present_bands]
            if all(v is None or v == 0 for v in cells):
                continue
            def _fmt_cell(v):
                if v is None or v == 0:
                    return "—"
                return f"+{v:,}" if v > 0 else f"{v:,}"
            row = f"| {dte_label} | " + " | ".join(_fmt_cell(v) for v in cells) + " |"
            rows_md.append(row)

        if not rows_md:
            continue
        sections.append(f"#### {sym}{meta_str}\n\n{header}\n{sep}\n" + "\n".join(rows_md))

    if not sections:
        return ""
    return (
        f"### {title} — OI change by DTE × Moneyness\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


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
    top_n: int = 20,
    raw_n: int = 5,
    unusual_rows: list[dict] | None = None,
    focus: set[str] | None = None,
) -> str:
    """Full rollup (all tickers) + top raw_n raw trades for each of the top_n tickers by score.

    Unusual rows are used only for scoring — no separate unusual table is emitted.
    Set raw_n=0 to omit raw trades entirely.

    ``focus`` (a set of upper-cased symbols) narrows the DISPLAYED rollup, raw
    trades, and OI breakdown to those tickers — scoring still runs over the full
    population so percentile ranks stay meaningful. The trade/symbol count line
    keeps the full-population figures as market context.
    """
    if not rows:
        return f"## {title}\n\n_No data available._\n"
    rollup = build_scored_flow_rollup(rows, unusual_rows)
    count_line = f"_{len(rows)} trades across {len(rollup)} symbols._"
    display = rollup
    if focus is not None:
        display = [r for r in rollup if r["symbol"].upper() in focus]
        if not display:
            return (
                f"## {title}\n\n{count_line}\n\n"
                f"_None of the focus tickers had flow in {title}._\n"
            )
    top_tickers = [r["symbol"] for r in display[:top_n]] if top_n > 0 else []
    out = (
        f"## {title}\n\n"
        f"{count_line}\n\n"
        + _flow_rollup_md(display, title)
    )
    if raw_n > 0 and top_tickers:
        out += "\n" + _flow_top_trades_md(rows, top_tickers, raw_n, title)
    oi_section = _oi_breakdown_section(display, top_n, title)
    if oi_section:
        out += "\n" + oi_section
    return out


# Machine-readable CSV column order for the scored flow rollup. Money columns are
# emitted as raw rounded numbers (not "$10.3M") so the file sorts/sums in a
# spreadsheet; the score breakdown is split into its component columns.
FLOW_CSV_COLUMNS = [
    "Section", "Symbol", "Score", "ScoreLabel",
    "Flow", "Rep", "Cross", "VolOI", "Otm", "Open", "Persist",
    "Trades", "TotalPremium", "ExtPremium", "ExtCallPremium", "ExtPutPremium",
    "OTMExtPremium", "DeltaNotional", "FinancingShare", "Horizon",
    "Contracts", "PremPerContract",
    "CallPremium", "PutPremium", "CallPutRatio",
    "Bull", "Bear", "Mid", "BTO", "STO", "ToOpen",
    "wDTE", "wIV", "IVSpread", "IVSkew", "BiggestTrade",
    "OIConfirmPct", "CPIR",
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
                "Otm": parts.get("otm", ""),
                "Open": parts.get("open", ""),
                "Persist": parts.get("persist", ""),
                "Trades": r["trades"],
                "TotalPremium": round(r["premium_total"]),
                "ExtPremium": round(r.get("ext_total", 0.0)),
                "ExtCallPremium": round(r.get("ext_call", 0.0)),
                "ExtPutPremium": round(r.get("ext_put", 0.0)),
                "OTMExtPremium": round(r.get("otm_ext", 0.0)),
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
                "IVSpread": round(r["iv_spread"], 1) if r.get("iv_spread") is not None else "",
                "IVSkew": round(r["iv_skew"], 1) if r.get("iv_skew") is not None else "",
                "BiggestTrade": _biggest_trade_str(r["biggest"]),
                "OIConfirmPct": r.get("oi_confirm_pct", ""),
                "CPIR": r.get("cpir", ""),
            })
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unusual aggregation
# ---------------------------------------------------------------------------

_UN_SYMBOL = "Symbol"
_UN_VOLOI  = "Vol/OI"




# ---------------------------------------------------------------------------
# Cross-section
# ---------------------------------------------------------------------------

def cross_section_tickers(flow_rows: Iterable[dict], unusual_rows: Iterable[dict]) -> list[str]:
    """Tickers that appear in BOTH the flow and unusual sections — high signal."""
    flow_syms    = {(r.get(_FLOW_SYMBOL) or "").strip() for r in flow_rows}
    unusual_syms = {(r.get(_UN_SYMBOL) or "").strip() for r in unusual_rows}
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

def persistence_callout_md(days: list[dict], title: str) -> str:
    """One-line callout of names recurring ≥3 days across the window.

    Same per-day scoring as summarize_persistence but emits only the
    '**Persistent names (≥3 days):**' line — no trajectory table.
    Returns an empty string when nothing qualifies.
    """
    if not days:
        return ""

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

    n = len(days)
    persistent = []
    for sym in all_syms:
        present = [i for i, bs in enumerate(per_day) if sym in bs]
        if len(present) < 3:
            continue
        latest_row = per_day[present[-1]][sym]
        persistent.append((sym, len(present), latest_row["score"], _persistence_lean(latest_row)))

    if not persistent:
        return ""

    persistent.sort(key=lambda r: (r[2], r[1]), reverse=True)
    names = " · ".join(f"{sym} {days_}/{n} ({lean})" for sym, days_, _, lean in persistent)
    return f"**{title} — persistent names (≥3 days):** {names}"


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
