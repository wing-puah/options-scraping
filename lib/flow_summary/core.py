"""
Aggregate parsed Barchart CSV rows into compact, LLM-friendly summaries.

Two CSV shapes are supported:

- **Flow** (`options-flow-*.csv`, `etf-flow-*.csv`): one row per executed trade.
  Has Premium, Side, *, Code columns. Aggregated by ticker into a rollup
  table (total / call / put premium, sentiment counts, opening-flag counts,
  weighted-avg DTE & IV, biggest single trade, OI factor measures) plus the
  top-N largest single trades raw.

- **Unusual** (`unusual-stock-*.csv`, `unusual-etf-*.csv`): one row per
  strike-day with elevated Vol/OI. No Premium / Side / Code. Used only to
  corroborate the flow scoring (cross-section overlap + Vol/OI strength).

The functions return strings of markdown so they drop straight into the
analysis-pipeline fetch step. Small parse/format/bucket helpers live in
`_helpers.py`; this module is the aggregation logic.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Iterable

from lib.flow_summary._helpers import (
    DTE_HI,
    DTE_LO,
    IV_MAX_PTS,
    IV_MIN_PTS,
    MIN_OPTION_PRICE,
    MIN_UNDERLYING,
    _FINANCING_DELTA,
    _FLOW_DELTA,
    _FLOW_DTE,
    _FLOW_EXPIRY,
    _FLOW_IV,
    _FLOW_OI,
    _FLOW_OPENFLAG,
    _FLOW_PREMIUM,
    _FLOW_SIDE,
    _FLOW_SIZE,
    _FLOW_STRIKE,
    _FLOW_SYMBOL,
    _FLOW_TIME,
    _FLOW_TRADE,
    _FLOW_TYPE,
    _FLOW_UPRICE,
    _DTE_BUCKETS,
    _MONEYNESS_BANDS,
    _RAW_DROP_COLUMNS,
    _biggest_trade_str,
    _classify_sentiment,
    _dte_bucket,
    _expiry_key,
    _fmt_iv_pts,
    _fmt_money,
    _fmt_ratio,
    _moneyness,
    _moneyness_band,
    _otm_pct,
    _to_float,
    _to_int,
    _trade_extrinsic,
    _wmean,
)


# ---------------------------------------------------------------------------
# Flow aggregation
# ---------------------------------------------------------------------------

def _finalize_oi_factors(contracts: dict) -> dict:
    """Collapse a ticker's per-contract OI store into the ref-03 factor measures.

    ``contracts`` is already deduped to one entry per (type, strike, expiry) —
    enrich_oi writes the same ``oi_change`` onto every trade row of a contract,
    so summing across rows would multiply each ΔOI by its trade count.

    For each OPENING contract (ΔOI > 0) the factor contribution is

        max(ΔOI, 0) × price × P(OTM)

    where ``price`` is the contract's volume-weighted traded price (the
    monetary-size term the paper requires — raw ΔOI "does not capture money")
    and ``P(OTM) ≈ 1−|delta|`` is the risk-neutral expiry-OTM proxy. OIFC/OIFP
    sum these over calls / puts and CPIR = OIFC/(OIFC+OIFP). The IV-augmented
    OIFCA/OIFPA (→ CPIRA) multiply each term by the contract's IV (as a
    fraction). OIConf% (``oi_confirm_pct``) is the share of *moving* contracts
    that opened — ``opens / (opens + closes)`` — with flat contracts (ΔOI == 0)
    EXCLUDED from the denominator: a day where OI did not change is ambiguous,
    not a failed confirmation, and letting flats count against the ratio was
    dragging every percentage down. Returned as a decimal fraction (0.45 = 45%),
    or None when no contract actually moved. ``oi_n`` reports that moving-contract
    sample size so the conviction score can gate on it. Delta/IV prefer the EOD
    settlement greeks, falling back to the size-weighted intraday snapshot.

    Returns the per-ticker scalars (None when no contract carried enriched OI
    data) plus ``oi_by_bucket``: (dte_label, moneyness_band) → {call OIFC
    contribution, put OIFP contribution, signed net ΔOI}. The bucket net ΔOI
    still includes flat contracts — the signed positioning grid is a separate
    view from the confirmation ratio.

    Source: Hilliard, Hilliard & Wu (2025) — see references/references_key_insight
    (ref 03) and config/rollup-reference.md.
    """
    oifc = oifp = oifca = oifpa = 0.0
    oi_any_n = oi_move_n = oi_confirm_n = 0
    by_bucket: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"call": 0.0, "put": 0.0, "doi": 0})

    for c in contracts.values():
        doi = c["oi_change"]
        if doi is None:
            continue
        oi_any_n += 1          # enriched contract (drives has_oi for OIFC/OIFP/CPIR)
        if doi != 0:           # flat OI is ambiguous — excluded from the confirm ratio
            oi_move_n += 1
            if doi > 0:
                oi_confirm_n += 1
        dte_label = _dte_bucket(c["dte"]) if c["dte"] else "?"
        band = _moneyness_band(_otm_pct(c["strike"], c["spot"], c["opt_type"]))
        cell = by_bucket[(dte_label, band)]
        cell["doi"] += doi  # signed net ΔOI — the raw positioning view

        oi_open = max(doi, 0)
        if oi_open == 0:  # closing/rolling flow: counted above, but no factor
            continue
        price = c["prem_sum"] / (c["size_sum"] * 100) if c["size_sum"] > 0 else 0.0
        delta = c["eod_delta"]
        if delta is None:
            delta = _wmean(c["idelta_wsum"], c["idelta_wt"])
        if delta is None or price <= 0:
            continue
        p_otm = min(max(1.0 - abs(delta), 0.0), 1.0)
        base = oi_open * price * p_otm

        iv = c["eod_iv"]
        if iv is None:
            iv = _wmean(c["iiv_wsum"], c["iiv_wt"])
        iv_frac = (iv / 100.0) if iv else 1.0  # IV is in pct points
        aug = base * iv_frac

        if c["opt_type"] == "call":
            oifc += base
            oifca += aug
            cell["call"] += base
        else:
            oifp += base
            oifpa += aug
            cell["put"] += base

    has_oi = oi_any_n > 0
    return {
        # Stored as a DECIMAL FRACTION (0.45 = 45%), not 0–100 — every percentage
        # field in this codebase is decimal so a Google-Sheets cell can be set to
        # percentage format directly. Markdown renders it ×100 for display.
        # Denominator is the MOVING-contract count (opens + closes); flats excluded.
        "oi_confirm_pct": round(oi_confirm_n / oi_move_n, 4) if oi_move_n else None,
        # Sample size behind oi_confirm_pct — the conviction score gates on this so a
        # single opening contract can't earn a name a full confirmation bonus.
        "oi_n": oi_move_n,
        "oifc": oifc if has_oi else None,
        "oifp": oifp if has_oi else None,
        "oifca": oifca if has_oi else None,
        "oifpa": oifpa if has_oi else None,
        "cpir": round(oifc / (oifc + oifp), 2) if (oifc + oifp) > 0 else None,
        "cpira": round(oifca / (oifca + oifpa), 2) if (oifca + oifpa) > 0 else None,
        # The call/put contributions sum to OIFC/OIFP per ticker.
        "oi_by_bucket": {k: dict(v) for k, v in by_bucket.items()},
    }


# IV spread / skew construction bands (Lin/Lu/Driessen 2013, appendix). Both
# measures share the paper's data filters imported from _helpers: the 10–60 DTE
# maturity window (DTE_LO/DTE_HI) plus the IV-bounds / positive-OI / minimum
# underlying- and option-price gates. Skew moneyness (K/S) bands:
# OTM put in [0.80, 0.95] closest to 0.95; ATM call in [0.95, 1.05] closest to 1.0.
_OTMPUT_LO, _OTMPUT_HI, _OTMPUT_TARGET = 0.80, 0.95, 0.95
_ATMCALL_LO, _ATMCALL_HI, _ATMCALL_TARGET = 0.95, 1.05, 1.0


def _settlement_iv(row: dict) -> float | None:
    """Settlement IV (points) for a flow row: EOD ``eod_iv`` if enriched, else the
    intraday snapshot ``IV``.

    Matched pairs / skew compare a traded leg against a backfilled counterpart leg,
    and the counterpart only exists as an end-of-day price-history value — so both
    sides use the settlement IV where available for a like-with-like comparison.
    ``eod_iv`` is stored as a fraction (0.60); the flow feed's intraday IV and this
    module's IV columns are in points (60), so the EOD value is scaled ×100.
    """
    eod = _to_float(row.get("eod_iv"))
    if eod is not None and eod > 0:
        return eod * 100.0
    return _to_float(row.get(_FLOW_IV))


def _new_pair_leg() -> dict:
    return {"call_iv": None, "call_oi": 0.0,
            "put_iv": None, "put_oi": 0.0}


def _update_pair(agg: dict, opt: str, strike_r: float, expiry: str,
                 iv: float, oi: float) -> None:
    """Fold one leg's settlement IV / OI into its (strike, expiry) pair.

    ``iv`` is a single settlement value per contract (first-seen wins — every trade
    row of a contract carries the same EOD IV); ``oi`` takes the max seen. Callers
    gate on positive OI (paper filter v), so every leg arrives weighted. A
    backfilled counterpart never overrides a leg that already traded.
    """
    pair = agg["_pair_contracts"].setdefault((strike_r, expiry), _new_pair_leg())
    if pair[f"{opt}_iv"] is None:
        pair[f"{opt}_iv"] = iv
    pair[f"{opt}_oi"] = max(pair[f"{opt}_oi"], oi)


def _update_skew(agg: dict, opt: str, m: float, iv: float) -> None:
    """Track the closest-moneyness OTM put (→0.95) and ATM call (→1.0) settlement IV."""
    if opt == "put" and _OTMPUT_LO <= m <= _OTMPUT_HI:
        gap = abs(m - _OTMPUT_TARGET)
        if agg["_skew_put_gap"] is None or gap < agg["_skew_put_gap"]:
            agg["_skew_put_gap"] = gap
            agg["_skew_put_iv"] = iv
    elif opt == "call" and _ATMCALL_LO <= m <= _ATMCALL_HI:
        gap = abs(m - _ATMCALL_TARGET)
        if agg["_skew_call_gap"] is None or gap < agg["_skew_call_gap"]:
            agg["_skew_call_gap"] = gap
            agg["_skew_call_iv"] = iv


def _matched_pair_spread(pair_contracts: dict) -> float | None:
    """OI-weighted mean of (IV_call − IV_put) across matched pairs.

    Cremers/Weinbaum (2010) IV spread as used by Lin/Lu/Driessen (2013, A.1): for
    each (strike, expiry) that has BOTH a call and a put settlement IV — traded or
    backfilled — take the leg IV difference, weighted by the pair's average open
    interest (½(OI_call + OI_put)). Every entering leg has positive OI (paper
    filter v, enforced by the callers), so the weight is always positive.
    Returns None when no matched pair exists.
    """
    num = den = 0.0
    for p in pair_contracts.values():
        if p["call_iv"] is None or p["put_iv"] is None:
            continue  # not a matched pair — one leg absent
        w = (p["call_oi"] + p["put_oi"]) / 2.0
        num += w * (p["call_iv"] - p["put_iv"])
        den += w
    return (num / den) if den > 0 else None


def _flow_ticker_rows(rows: Iterable[dict],
                      counterpart_iv: dict[str, list[dict]] | None = None) -> list[dict]:
    """Group flow rows by symbol and compute per-ticker aggregates.

    ``counterpart_iv`` (optional) is ``{UPPER_SYMBOL: [contract, ...]}`` from
    :func:`lib.counterpart_iv.build_iv_lookup` — the settlement IV of counterpart legs
    that did NOT trade, fetched from Barchart price-history (see
    ``scripts/collector/fetch_counterpart_iv.py``). It is folded into the matched-pair and skew
    accumulators so ``iv_spread`` / ``iv_skew`` reflect the fuller chain, not only
    the traded subset. Absent → the metrics fall back to flow-only (frequently
    blank). Pure over its inputs: the caller loads the per-date sidecar and passes
    it, so backtest (historical D) and live (latest D) share one path.
    """
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
        # Premium-weighted IV split by side (for the iv_call_w / iv_put_w display
        # columns only).
        "_iv_call_prem_sum": 0.0,
        "_iv_put_prem_sum": 0.0,
        # Directional vol reads, constructed faithfully to Lin/Lu/Driessen (2013,
        # appendix A.1/A.2) — after Cremers/Weinbaum (2010) and Xing/Zhang/Zhao
        # (2010). Both apply the paper's data filters (10 ≤ DTE ≤ 60, IV within
        # [IV_MIN_PTS, IV_MAX_PTS], positive OI, underlying ≥ MIN_UNDERLYING,
        # option price ≥ MIN_OPTION_PRICE when known) and are built on SETTLEMENT
        # IV (eod_iv) so a traded leg and a backfilled counterpart compare
        # like-with-like. Directional context only — never fed into the
        # conviction score.
        #
        #   IV spread = OI-weighted mean of (IV_call − IV_put) across MATCHED
        #   pairs (same strike + expiry) — a put-call-parity deviation, positive
        #   → bullish. Accumulated per contract in `_pair_contracts` keyed by
        #   (strike, expiry); pairs formed at finalization.
        #
        #   IV skew = IV(OTM put closest to K/S 0.95) − IV(ATM call closest to
        #   K/S 1.0), single contract each — steeper → bearish. Tracked as the
        #   closest-moneyness put/call IV as rows stream in.
        #
        # The paper computes both across the FULL daily option chain; the traded
        # flow rarely carries both legs of a pair, so the missing counterpart legs
        # are BACKFILLED from Barchart price-history (counterpart_iv) — see
        # lib/counterpart_iv.py and config/rollup-reference.md. Still None when even
        # the anchor leg is absent.
        "_pair_contracts": {},          # (strike, expiry) -> per-side settlement IV/OI
        "_spot": None,                  # representative underlying (for backfill moneyness)
        "_skew_put_iv": None,
        "_skew_put_gap": None,          # |K/S − 0.95| of the tracked OTM put
        "_skew_call_iv": None,
        "_skew_call_gap": None,         # |K/S − 1.0| of the tracked ATM call
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
        # OI enrichment: deduped per CONTRACT and finalized by
        # _finalize_oi_factors. Keyed by (opt_type, strike, expiration); each
        # entry captures ΔOI once plus the price / delta / IV inputs the ref-03
        # factor measure needs.
        "_oi_contracts": {},
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
        elif t_lower == "put":
            agg["premium_put"] += prem
            agg["ext_put"] += ext
            agg["_iv_put_prem_sum"] += iv * prem

        if agg["_spot"] is None and spot:
            agg["_spot"] = spot

        # Paper-faithful IV spread / skew (Lin/Lu/Driessen 2013): apply the
        # appendix filters — 10–60 DTE window, settlement IV within bounds,
        # positive OI, underlying ≥ $5, option price ≥ $0.125 (the trade print
        # stands in for the paper's quote mid; unparseable → not dropped) — and
        # require strike + spot for moneyness. SETTLEMENT IV keeps a traded leg
        # and its backfilled counterpart comparable. Counterpart legs (the
        # missing side of a pair) are folded in from counterpart_iv after this
        # loop; build_iv_lookup applies the same filters to them.
        siv = _settlement_iv(r)
        m = _moneyness(strike, spot)
        oi_row = _to_float(r.get(_FLOW_OI))
        trade_px = _to_float(r.get(_FLOW_TRADE))
        if DTE_LO <= dte <= DTE_HI and m is not None \
                and siv is not None and IV_MIN_PTS <= siv <= IV_MAX_PTS \
                and t_lower in ("call", "put") \
                and oi_row > 0 \
                and spot >= MIN_UNDERLYING \
                and not (0 < trade_px < MIN_OPTION_PRICE):
            _update_skew(agg, t_lower, m, siv)
            _update_pair(agg, t_lower, round(strike, 4), _expiry_key(r),
                         siv, oi_row)

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

        _accumulate_oi_contract(agg, r, t_lower, prem, size, dte, strike, spot,
                                delta, has_delta, iv)

        big = agg["biggest"]
        if big is None or prem > big[0]:
            agg["biggest"] = (prem, opt_type, r.get(_FLOW_STRIKE, ""), side, dte, r.get(_FLOW_TIME, ""))

    out = []
    for sym, a in by_sym.items():
        # Fold in backfilled counterpart legs (settlement IV of contracts that did
        # not trade) so single-sided pairs become matched. Selected in-window at
        # fetch time; IV bounds / positive OI / min price already enforced by
        # build_iv_lookup. The underlying-price filter is symbol-level: a known
        # sub-$5 spot drops the name (skew moneyness needs the spot anyway —
        # skipped per leg when absent).
        if not (a["_spot"] and a["_spot"] < MIN_UNDERLYING):
            for cp in (counterpart_iv or {}).get(sym.upper(), []):
                m = _moneyness(cp["strike"], a["_spot"]) if a["_spot"] else None
                if m is not None:
                    _update_skew(a, cp["opt_type"], m, cp["iv"])
                _update_pair(a, cp["opt_type"], round(cp["strike"], 4), cp["expiry"],
                             cp["iv"], cp["oi"])

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
        # IV spread — OI-weighted matched-pair (Cremers/Weinbaum); IV skew —
        # closest-moneyness OTM-put minus ATM-call (Xing/Zhang/Zhao).
        iv_spread = _matched_pair_spread(a["_pair_contracts"])
        iv_skew = (a["_skew_put_iv"] - a["_skew_call_iv"]) \
            if (a["_skew_put_iv"] is not None and a["_skew_call_iv"] is not None) else None

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
            # OI factor measures (ref 03; keys all None when no enriched data).
            **_finalize_oi_factors(a["_oi_contracts"]),
        })

    out.sort(key=lambda r: r["ext_total"], reverse=True)
    return out


def _accumulate_oi_contract(agg, r, t_lower, prem, size, dte, strike, spot,
                            delta, has_delta, iv) -> None:
    """Fold one trade row into its contract's OI accumulator (deduped per
    contract). ``oi_change`` is identical on every row of a contract, so it is
    captured once; price/delta/IV inputs accumulate across the contract's rows
    for _finalize_oi_factors. No-op on rows without an ``oi_change`` cell.
    """
    oi_chg_raw = r.get("oi_change", "")
    if oi_chg_raw in (None, "") or t_lower not in ("call", "put"):
        return
    ckey = (t_lower, str(r.get(_FLOW_STRIKE, "")), _expiry_key(r))
    c = agg["_oi_contracts"].get(ckey)
    if c is None:
        c = {
            "opt_type": t_lower, "oi_change": None,
            "prem_sum": 0.0, "size_sum": 0,
            "eod_delta": None, "eod_iv": None,
            "idelta_wsum": 0.0, "idelta_wt": 0,  # size-weighted intraday |delta|
            "iiv_wsum": 0.0, "iiv_wt": 0,        # size-weighted intraday IV
            "dte": dte, "strike": strike, "spot": spot,
        }
        agg["_oi_contracts"][ckey] = c
    if c["oi_change"] is None:
        try:
            c["oi_change"] = int(float(oi_chg_raw))
        except (ValueError, TypeError):
            c["oi_change"] = None
    c["prem_sum"] += prem
    c["size_sum"] += size
    ed = r.get("eod_delta")
    if ed not in (None, "") and c["eod_delta"] is None:
        c["eod_delta"] = _to_float(ed)
    ei = r.get("eod_iv")
    if ei not in (None, "") and c["eod_iv"] is None:
        c["eod_iv"] = _to_float(ei)
    if has_delta:
        c["idelta_wsum"] += abs(delta) * size
        c["idelta_wt"] += size
    if iv:
        c["iiv_wsum"] += iv * size
        c["iiv_wt"] += size


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
#   oi_confirm  next-day OI open-confirmation share (ref-03)      −2 / −1 / +1 / +2
#   fin_penalty  financing-dominance demotion (direction-agnostic)    −4 / −3 / −2 / 0
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
# The `oi_confirm` term is the one FORWARD-confirmed component: it reads the
# ticker's next-session open-interest change (ref-03 open-confirmation, from
# enrich_oi). oi_confirm_pct = opens / (opens + closes) over the ticker's moving
# contracts (flat ΔOI excluded); a high share means the flow genuinely opened
# positions, a low share means it was closing/rolling and the premium overstated
# conviction. Bands: ≥0.60 → +2, ≥0.40 → +1, ≥0.25 → −1, else −2. It is neutral
# (0) when the data is absent — the enrichment lags one session, so the LATEST
# date a live run scores has no OI-confirm yet — or when the moving-contract
# sample is thin (oi_n < 3), so a single opening print can't earn a full bonus.
# This is the only component besides fin_penalty that can go negative; TODO-P3's
# "OIConfirm<40% underperforms" is what the −1/−2 penalty encodes. Backfilled /
# backtested dates carry it in full.
#
# A missing opening label scores 0, never negative — Barchart frequently omits
# the flag, and absence of the label is not evidence the trade was closing.
#
# The `fin_penalty` term is the ONLY negative component. The flow/otm ranks
# already strip intrinsic, but a name can rank high on absolute extrinsic while
# its premium is DOMINATED by |delta|≥0.85 financing/conversion legs (Fin% high)
# — stock-substitute positioning, not a directional bet. This turns the
# advisory Fin% column into an actual demotion: −2 above 0.60, −3 above 0.75,
# −4 above 0.90. The 0.60 floor was set from the Mar-2025 backtest, where
# fin_share>0.6 names won 33% (avg −28%) vs 86% (avg +57%) below it, while
# borderline real bets (GLD 0.53) stayed in. It is direction-agnostic (a quality
# discount, not a bull/bear call). Total is clamped to ≥0.
#
# Direction (bull/bear) lives in the separate sentiment columns; it never feeds
# this number. Single-day raw ceiling is 14 (before any fin_penalty, incl. a full
# +2 oi_confirm); persistence can push it to 17.

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


_OI_CONFIRM_MIN_N = 3  # min moving contracts before oi_confirm_pct is trusted


def _oi_confirm_points(pct: float | None, n: int | None) -> int:
    """Bonus/penalty for next-day OI open-confirmation (ref-03).

    Neutral (0) when the data is absent (the latest live date has no next-session
    OI yet) or the moving-contract sample is thin (``n < _OI_CONFIRM_MIN_N``) —
    absence is never a penalty. Otherwise rewards a high open share and demotes a
    low one (the TODO-P3 ``OIConfirm<40%`` underperformance). Bands are tunable —
    see config/conviction-score.md.
    """
    if pct is None or n is None or n < _OI_CONFIRM_MIN_N:
        return 0
    if pct >= 0.60:
        return 2
    if pct >= 0.40:
        return 1
    if pct >= 0.25:
        return -1
    return -2


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

        # Next-day OI open-confirmation (ref-03). Forward-confirmed, so neutral on
        # the latest live date (enrichment lags a session) and under-sampled names;
        # rewards genuine opening flow, demotes closing/rolling. See _oi_confirm_points.
        oi_confirm = _oi_confirm_points(r.get("oi_confirm_pct"), r.get("oi_n"))

        # Financing penalty — direction-agnostic demotion of stock-substitute flow.
        # The `flow`/`otm` components already RANK on extrinsic (intrinsic stripped),
        # but a name can still rank high on absolute extrinsic while its premium is
        # DOMINATED by |delta|≥0.85 financing/conversion legs — positioning, not a
        # bet on a move. The Fin% column flagged this advisorily; this turns it into
        # an actual demotion. Backtest (Mar 2025 panic, 20 trades): fin_share>0.6
        # names won 33% (avg −28%) vs 86% (avg +57%) below it. The 0.6 floor spares
        # borderline real bets (GLD 0.53 won) while demoting the clear financing
        # names (AMD/QQQ/TSLA/COIN). Scales with dominance; total clamped ≥0.
        # See config/conviction-score.md and config/backtest-tuning.md §Financing.
        fin_share = r.get("fin_share", 0.0)
        if fin_share > 0.90:
            fin_penalty = -4
        elif fin_share > 0.75:
            fin_penalty = -3
        elif fin_share > 0.60:
            fin_penalty = -2
        else:
            fin_penalty = 0

        parts = {
            "flow": flow, "rep": rep, "cross": cross,
            "voloi": voloi_pts, "otm": otm, "open": opening, "persist": persist,
            "oi_confirm": oi_confirm,
            "fin_penalty": fin_penalty,
        }
        total = max(0, sum(parts.values()))
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
        "wDTE", "Hzn", "wIV%", "IVpct", "IVspr", "IVskew",
        "OIConf%", "CPIR", "CPIRA",
        "Biggest trade",
    ]
    sep = " | ".join(["---"] * len(headers))
    lines = []
    for r in rollup:
        big_str = _biggest_trade_str(r["biggest"]) or "—"
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
            f"{r['iv_pct'] * 100:.0f}%" if r.get("iv_pct") is not None else "—",
            _fmt_iv_pts(r.get("iv_spread")),
            _fmt_iv_pts(r.get("iv_skew")),
            f"{r['oi_confirm_pct'] * 100:.0f}%" if r.get("oi_confirm_pct") is not None else "—",
            f"{r['cpir']:.2f}"        if r.get("cpir")            is not None else "—",
            f"{r['cpira']:.2f}"       if r.get("cpira")           is not None else "—",
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

    def _fmt_cell(v):
        if not v:
            return "—"
        return f"+{v:,}" if v > 0 else f"{v:,}"

    sections = []
    for r in rollup[:top_n]:
        bucket = r.get("oi_by_bucket", {})
        if not bucket:
            continue
        sym = r["symbol"]
        conf = r.get("oi_confirm_pct")
        cpir = r.get("cpir")
        cpira = r.get("cpira")
        meta = []
        if conf is not None:
            meta.append(f"Conf: {conf * 100:.0f}%")
        if cpir is not None:
            meta.append(f"CPIR: {cpir:.2f}")
        if cpira is not None:
            meta.append(f"CPIRA: {cpira:.2f}")
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
            cells = [bucket.get((dte_label, m), {}).get("doi", 0) for m in present_bands]
            if all(v == 0 for v in cells):
                continue
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


def _attach_iv_pct(rollup: list[dict], iv_pct: dict[str, int | None] | None) -> list[dict]:
    """Attach per-ticker IV rank (0–100 percentile of the day's IV in the name's own
    trailing range; see :mod:`lib.iv_history`) onto rollup rows as ``iv_pct``.

    Injected rather than computed here because the value is scraped (Barchart
    options-overview history) and enriched onto the compiled flow file by
    ``scripts/collector/fetch_iv_percentile.py`` — the caller reads it back off those rows and
    passes ``{UPPER_SYMBOL: rank}``, same pattern as ``counterpart_iv``. ``None``
    (missing or too-little-history) leaves the field ``None`` so displays show "—" and
    the framework falls back to the VIX proxy.
    """
    lut = iv_pct or {}
    for r in rollup:
        r["iv_pct"] = lut.get(r["symbol"].upper())
    return rollup


def build_scored_flow_rollup(
    rows: list[dict],
    unusual_rows: list[dict] | None = None,
    counterpart_iv: dict[str, list[dict]] | None = None,
    iv_pct: dict[str, int | None] | None = None,
) -> list[dict]:
    """Per-ticker flow rollup with conviction scores attached, sorted best-first.

    When ``unusual_rows`` (the matching unusual-activity section) is supplied the
    conviction score also credits cross-section overlap and Vol/OI strength.
    ``counterpart_iv`` (optional) supplies backfilled counterpart-leg settlement IV for
    the matched-pair / skew reads (see :func:`_flow_ticker_rows`). ``iv_pct``
    (optional) supplies the per-ticker IV percentile joined onto each row. Shared by
    the markdown summary and the CSV export so both see identical scoring and ordering.
    """
    rollup = _flow_ticker_rows(rows, counterpart_iv)
    unusual_syms = {(r.get(_UN_SYMBOL) or "").strip() for r in (unusual_rows or [])}
    unusual_syms.discard("")
    score_flow_rollup(rollup, unusual_syms, _voloi_by_symbol(unusual_rows))
    _attach_iv_pct(rollup, iv_pct)
    rollup.sort(key=lambda r: (r["score"], r.get("ext_total", r["premium_total"])), reverse=True)
    return rollup


def summarize_flow(
    rows: list[dict],
    title: str,
    top_n: int = 20,
    raw_n: int = 5,
    unusual_rows: list[dict] | None = None,
    focus: set[str] | None = None,
    counterpart_iv: dict[str, list[dict]] | None = None,
    iv_pct: dict[str, int | None] | None = None,
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
    rollup = build_scored_flow_rollup(rows, unusual_rows, counterpart_iv, iv_pct)
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
    "Flow", "Rep", "Cross", "VolOI", "Otm", "Open", "Persist", "OIConfirm", "FinPenalty",
    "Trades", "TotalPremium", "ExtPremium", "ExtCallPremium", "ExtPutPremium",
    "OTMExtPremium", "DeltaNotional", "FinancingShare", "Horizon",
    "Contracts", "PremPerContract",
    "CallPremium", "PutPremium", "CallPutRatio",
    "Bull", "Bear", "Mid", "BTO", "STO", "ToOpen",
    "wDTE", "wIV", "IVPct", "IVSpread", "IVSkew", "BiggestTrade",
    "OIConfirmPct", "OIN", "OIFC", "OIFP", "CPIR", "CPIRA",
]


def _rollup_metric_cells(r: dict) -> dict:
    """The deterministic rollup-context cells, formatted as in FLOW_CSV_COLUMNS.

    Single source of truth shared by :func:`flow_rollup_csv` (the audit CSV) and
    :func:`ticker_metrics` (the analysis-row / backfill join) so both emit
    byte-identical strings: ``oi_confirm_pct`` / ``cpir`` / ``iv_pct`` straight
    through (blank when None), ``iv_spread`` rounded to 1 decimal.
    """
    return {
        "oi_confirm_pct": r["oi_confirm_pct"] if r.get("oi_confirm_pct") is not None else "",
        "cpir": r["cpir"] if r.get("cpir") is not None else "",
        "iv_spread": round(r["iv_spread"], 1) if r.get("iv_spread") is not None else "",
        "iv_pct": r["iv_pct"] if r.get("iv_pct") is not None else "",
    }


def ticker_metrics(flow_rows: list[dict],
                   counterpart_iv: dict[str, list[dict]] | None = None,
                   iv_pct: dict[str, int | None] | None = None) -> dict[str, dict]:
    """``{UPPER_SYMBOL: {oi_confirm_pct, cpir, iv_spread, iv_pct}}`` for a flow section.

    The deterministic per-ticker rollup-context metrics, recomputed straight from
    parsed flow rows. Reuses :func:`_flow_ticker_rows` (the pure aggregation); these
    values do NOT depend on conviction scoring or the unusual-activity rows, so no
    scoring/CSV serialization is run. ``counterpart_iv`` is threaded through so the
    ``iv_spread`` matches the rollup markdown; ``iv_pct`` (``{UPPER_SYMBOL: rank}``)
    is joined onto each row. Formatting mirrors ``FLOW_CSV_COLUMNS`` via
    :func:`_rollup_metric_cells`.
    """
    rollup = _attach_iv_pct(_flow_ticker_rows(flow_rows, counterpart_iv), iv_pct)
    return {r["symbol"].upper(): _rollup_metric_cells(r) for r in rollup}


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
            cells = _rollup_metric_cells(r)  # IVSpread / OIConfirmPct / CPIR
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
                "OIConfirm": parts.get("oi_confirm", ""),
                "FinPenalty": parts.get("fin_penalty", ""),
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
                "IVPct": cells["iv_pct"],
                "IVSpread": cells["iv_spread"],
                "IVSkew": round(r["iv_skew"], 1) if r.get("iv_skew") is not None else "",
                "BiggestTrade": _biggest_trade_str(r["biggest"]),
                "OIConfirmPct": cells["oi_confirm_pct"],
                "OIN": r.get("oi_n", ""),
                "OIFC": round(r["oifc"], 2) if r.get("oifc") is not None else "",
                "OIFP": round(r["oifp"], 2) if r.get("oifp") is not None else "",
                "CPIR": cells["cpir"],
                "CPIRA": r.get("cpira", ""),
            })
    return buf.getvalue()


# Long-format OI audit: one row per (Section, Symbol, DTE bucket, Moneyness band)
# non-empty cell. Each cell carries the ref-03 factor contributions for that
# DTE × moneyness slice — CallOIF (→ OIFC) and PutOIF (→ OIFP) — plus the raw
# signed net ΔOI for context. The per-ticker OIFC/OIFP/CPIR/CPIRA/OIConf% scalars
# repeat on each of a ticker's rows, so CPIR reconciles directly against the
# grid: Σ CallOIF over a ticker = OIFC, Σ PutOIF = OIFP, CPIR = OIFC/(OIFC+OIFP).
OI_BREAKDOWN_CSV_COLUMNS = [
    "Section", "Symbol", "DTEBucket", "Moneyness",
    "CallOIF", "PutOIF", "NetOIChange",
    "OIFC", "OIFP", "CPIR", "CPIRA", "OIConfirmPct", "OIN",
]

# The DTEBucket column uses the prompt's `horizon` boundary convention
# (one of 14|60|180|720 — see config.py ANALYSIS_PROMPT_CONTRACT) rather than the
# internal event/tact/med/strat labels, so a play's `horizon` reconciles directly
# against the breakdown rows. Mirrors the _DTE_BUCKETS boundaries (strat → 720).
_DTE_BUCKET_HORIZON = {"event": 14, "tact": 60, "med": 180, "strat": 720}


def oi_breakdown_csv(sections: list[tuple[str, list[dict]]]) -> str:
    """Render the per-ticker OI-change breakdown (DTE × moneyness) as long CSV.

    ``sections`` is ``[(section_label, scored_rollup), ...]`` (same shape as
    :func:`flow_rollup_csv`). Emits one row per non-empty ``(dte, moneyness)``
    cell, ordered by :data:`_DTE_BUCKETS` then :data:`_MONEYNESS_BANDS`, carrying
    that cell's ``CallOIF``/``PutOIF`` factor contributions + signed net ΔOI, with
    the ticker's ``oifc``/``oifp``/``cpir``/``cpira``/``oi_confirm_pct`` repeated
    on each row. Returns ``""`` when no ticker in any section carries enriched OI
    data, so the caller can skip writing an empty file.
    """
    dte_order = [b[0] for b in _DTE_BUCKETS]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=OI_BREAKDOWN_CSV_COLUMNS)
    writer.writeheader()
    wrote_row = False
    for section_label, rollup in sections:
        for r in rollup:
            bucket = r.get("oi_by_bucket", {})
            if not bucket:
                continue
            for dte_label in dte_order:
                for m_band in _MONEYNESS_BANDS:
                    cell = bucket.get((dte_label, m_band))
                    if not cell:
                        continue
                    call_oif = cell.get("call", 0.0)
                    put_oif = cell.get("put", 0.0)
                    net_doi = cell.get("doi", 0)
                    if not call_oif and not put_oif and not net_doi:
                        continue
                    writer.writerow({
                        "Section": section_label,
                        "Symbol": r["symbol"],
                        "DTEBucket": _DTE_BUCKET_HORIZON.get(dte_label, dte_label),
                        "Moneyness": m_band,
                        "CallOIF": round(call_oif, 2),
                        "PutOIF": round(put_oif, 2),
                        "NetOIChange": net_doi,
                        "OIFC": round(r["oifc"], 2) if r.get("oifc") is not None else "",
                        "OIFP": round(r["oifp"], 2) if r.get("oifp") is not None else "",
                        "CPIR": r.get("cpir", ""),
                        "CPIRA": r.get("cpira", ""),
                        "OIConfirmPct": r.get("oi_confirm_pct", ""),
                        "OIN": r.get("oi_n", ""),
                    })
                    wrote_row = True
    return buf.getvalue() if wrote_row else ""


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
