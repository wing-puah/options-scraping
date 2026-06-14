import logging
from datetime import timedelta

from .helpers import (
    _bs_price, _bs_spread_price,
    _num, _opt_price, _row_iv, _contract_key, _parse_expiration,
    _short_strike,
    _get_prices, _price_on_or_after, _price_asof,
    _weekday_grid,
)

log = logging.getLogger("backtest")


# ─── Path summarizer ───────────────────────────────────────────────────────────

def _summarize_path(grid_marks, entry_price, is_credit, profit_target, stop_loss,
                    contracts, cap_reached_expiry) -> dict:
    """Turn a day-by-day price grid into the path string, realized exit, and MFE/MAE.

    Realized exit = the FIRST day profit_target or stop_loss is crossed (frozen at
    that day's mark). MFE/MAE are measured over the WHOLE path so the target/stop
    can be tuned in analysis.
    """

    def pnl_of(p):
        signed = (entry_price - p) if is_credit else (p - entry_price)
        return signed / entry_price

    out = {"daily_price_csv": ",".join(
        "" if p is None else f"{p:.4f}" for (_, _, p, _) in grid_marks)}

    priced = [(dt, d, p, src) for (dt, d, p, src) in grid_marks if p is not None]
    if not priced:
        out.update({"realized_pnl_pct": "", "realized_pnl_abs": "", "days_held": "",
                    "exit_reason": "no_data", "mfe_pct": "", "mfe_day": "",
                    "mae_pct": "", "mae_day": "", "pnl_at_cap_pct": "",
                    "pct_real_days": ""})
        return out

    mfe, mae, mfe_day, mae_day = -1e18, 1e18, None, None
    exit_reason = realized_p = None
    days_held = last_priced_idx = None
    for grid_idx, (dt, d, p, src) in enumerate(grid_marks, start=1):
        if p is None:
            continue
        last_priced_idx = grid_idx
        pl = pnl_of(p)
        if pl > mfe:
            mfe, mfe_day = pl, grid_idx
        if pl < mae:
            mae, mae_day = pl, grid_idx
        if exit_reason is None:
            if pl >= profit_target:
                exit_reason, realized_p, days_held = "profit_target", p, grid_idx
            elif pl <= -stop_loss:
                exit_reason, realized_p, days_held = "stop_loss", p, grid_idx

    if exit_reason is None:
        _, _, last_p, _ = priced[-1]
        realized_p, days_held = last_p, last_priced_idx
        exit_reason = "expired" if cap_reached_expiry else "cap_open"

    realized_pnl = pnl_of(realized_p)
    cap_p = priced[-1][2]
    real_days = sum(1 for (_, _, _, s) in priced if s and not s.startswith("bs"))

    out.update({
        "realized_pnl_pct": round(realized_pnl * 100, 2),
        "realized_pnl_abs": round(realized_pnl * entry_price * 100 * contracts, 2),
        "days_held": days_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe * 100, 2),
        "mfe_day": mfe_day,
        "mae_pct": round(mae * 100, 2),
        "mae_day": mae_day,
        "pnl_at_cap_pct": round(pnl_of(cap_p) * 100, 2),
        "pct_real_days": round(real_days / len(priced) * 100, 1),
    })
    return out


# ─── Iron condor ───────────────────────────────────────────────────────────────

def _iron_condor_strikes(
    strikes: list, K_sp_anchor: float, S_entry: float, spread_pct: float
) -> tuple[float, float, float, float]:
    """
    Resolve all four IC strikes as (K_lp, K_sp, K_sc, K_lc) — ascending.
      K_lp = long put  (wing)
      K_sp = short put (income leg)
      K_sc = short call (income leg)
      K_lc = long call  (wing)
    """
    if len(strikes) >= 4:
        s = sorted(strikes)
        return s[0], s[1], s[2], s[3]
    if len(strikes) == 2:
        K_sp, K_sc = sorted(strikes)
        return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)
    K_sp = K_sp_anchor
    d = abs(S_entry - K_sp) / S_entry if S_entry > 0 else spread_pct
    K_sc = S_entry * (1 + d)
    return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)


def _simulate_iron_condor(
    candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn=None
):
    """Simulate a 4-leg iron condor (bear call spread + bull put spread).

    Entry credit and exit cost both use Black-Scholes for internal consistency
    across all four legs — mixing a real flow price on one leg with BS on the
    others produces a spurious credit when IVs differ.
    """
    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, candidate["signal_date"], sim_cfg.get("path_cap_days", 120)), dt
    ))

    ticker = candidate["ticker"]
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)
    contracts = sim_cfg.get("contracts", 1)
    spread_pct = sim_cfg.get("spread_width_pct", 0.02)

    K_sp_matched = _num(entry_row.get("Strike"))
    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    dte_entry = _num(entry_row.get("DTE"))
    expiration_raw = str(entry_row.get("Expires", entry_row.get("Expiration Date", ""))).strip()

    if not (K_sp_matched and iv and S_entry and dte_entry and dte_entry > 0):
        return {}
    dte_entry = int(dte_entry)
    T_entry = dte_entry / 365
    expiration_date = _parse_expiration(expiration_raw, signal_date + timedelta(days=dte_entry))

    K_lp, K_sp, K_sc, K_lc = _iron_condor_strikes(
        cls.get("strikes", []), K_sp_matched, S_entry, spread_pct
    )

    ksp_entry = _bs_price(S_entry, K_sp, T_entry, r, iv, "Put")
    klp_entry = _bs_price(S_entry, K_lp, T_entry, r, iv, "Put")
    ksc_entry = _bs_price(S_entry, K_sc, T_entry, r, iv, "Call")
    klc_entry = _bs_price(S_entry, K_lc, T_entry, r, iv, "Call")

    entry_credit = (ksp_entry - klp_entry) + (ksc_entry - klc_entry)
    if entry_credit <= 0:
        return {}

    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": "iron_condor",
        "opt_type": "IC",
        "k_long": round(K_sp, 2),
        "k_short": f"{K_lp:.2f}/{K_sc:.2f}/{K_lc:.2f}",
        "expiration": expiration_raw,
        "dte_entry": dte_entry,
        "iv_entry_pct": round(iv * 100, 2),
        "delta": "",
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_credit, 4),
        "entry_premium_total": round(entry_credit * 100 * contracts, 2),
        "entry_source": "bs",
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
    }

    def _cost_on(day, d):
        S_exit = price_fn(ticker, day)
        if S_exit is None:
            return None, ""
        T_exit = max(0.0, (dte_entry - d) / 365)
        ksp_exit = _bs_price(S_exit, K_sp, T_exit, r, iv, "Put")
        klp_exit = _bs_price(S_exit, K_lp, T_exit, r, iv, "Put")
        ksc_exit = _bs_price(S_exit, K_sc, T_exit, r, iv, "Call")
        klc_exit = _bs_price(S_exit, K_lc, T_exit, r, iv, "Call")
        return max(0.0, (ksp_exit - klp_exit) + (ksc_exit - klc_exit)), "bs"

    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = dte_entry <= path_cap
    end_date = signal_date + timedelta(days=min(dte_entry, path_cap))
    if expiration_date:
        end_date = min(end_date, expiration_date)

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        cost, source = _cost_on(day, d)
        grid_marks.append((day, d, cost, source))

    result.update(_summarize_path(
        grid_marks, entry_credit, True, profit_target, stop_loss, contracts,
        cap_reached_expiry))
    return result


# ─── Single-leg and spread simulation ─────────────────────────────────────────

def _simulate(candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn=None):
    """Simulate one play. Returns a result dict, or {} if it cannot be priced.

    Exit price sources (in order from sim_cfg['exit_sources']):
      barchart     — real per-contract daily price (Barchart history cache)
      reappearance — real Trade price when the contract recurs in a later flow scrape
      bs           — Black-Scholes (last resort)
    barchart_series maps contract_key -> sorted [(date, price)].
    price_fn(ticker, date) -> float|None is injectable for testing (defaults to yfinance).
    """
    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, candidate["signal_date"], sim_cfg.get("path_cap_days", 120)), dt))

    if cls.get("structure") == "iron_condor":
        return _simulate_iron_condor(
            candidate, cls, entry_row, contract_index, barchart_series, sim_cfg, price_fn
        )

    ticker = candidate["ticker"]
    opt_type = cls["option_type"]
    structure = cls["structure"]
    is_credit = cls.get("is_credit", False)
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)
    contracts = sim_cfg.get("contracts", 1)

    K = _num(entry_row.get("Strike"))
    dte_entry = _num(entry_row.get("DTE"))
    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    real_entry_price = _opt_price(entry_row)
    expiration_raw = str(entry_row.get("Expires", entry_row.get("Expiration Date", ""))).strip()
    if not (K and dte_entry and dte_entry > 0 and iv and S_entry):
        return {}
    dte_entry = int(dte_entry)
    T_entry = dte_entry / 365
    expiration_date = _parse_expiration(expiration_raw, signal_date + timedelta(days=dte_entry))

    spread_pct = sim_cfg.get("spread_width_pct", 0.02)
    K_short = _short_strike(structure, K, cls.get("strikes", []), spread_pct)
    short_key = _contract_key(ticker, opt_type, K_short, expiration_raw) if K_short is not None else None

    # Guard against a degenerate spread where legs cross or collapse.
    if K_short is not None:
        if structure in ("bull_call_spread", "bear_call_spread") and K_short <= K:
            return {}
        if structure in ("bear_put_spread", "bull_put_spread") and K_short >= K:
            return {}

    def _short_leg_price(checkpoint, d, S_known=None):
        """Short-leg price: real Barchart history (mid) → Black-Scholes fallback."""
        if short_key is not None:
            real = _price_asof(barchart_series, short_key, checkpoint, expiration_date)
            if real is not None:
                return real, "barchart"
        S = S_known if S_known is not None else price_fn(ticker, checkpoint)
        if S is None:
            return None, None
        T = max(0, (dte_entry - d) / 365)
        return _bs_price(S, K_short, T, r, iv, opt_type), "bs"

    if K_short is None:
        entry_price = real_entry_price
        entry_source = "real"
        if entry_price is None:
            return {}
    else:
        primary_entry = real_entry_price or _bs_price(S_entry, K, T_entry, r, iv, opt_type)
        contra_entry, contra_src = _short_leg_price(signal_date, 0, S_entry)
        if contra_entry is None:
            return {}
        entry_price = primary_entry - contra_entry
        primary_tag = "real" if real_entry_price else "bs"
        entry_source = f"{primary_tag}+{contra_src}"
    if entry_price <= 0:
        return {}

    contract_key = _contract_key(ticker, opt_type, K, expiration_raw)
    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)
    exit_sources = sim_cfg.get("exit_sources", ["barchart", "reappearance", "bs"])

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": structure,
        "opt_type": opt_type,
        "k_long": K,
        "k_short": round(K_short, 2) if K_short else "",
        "expiration": expiration_raw,
        "dte_entry": dte_entry,
        "iv_entry_pct": round(iv * 100, 2),
        "delta": entry_row.get("Delta", ""),
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_price, 4),
        "entry_premium_total": round(entry_price * 100 * contracts, 2),
        "entry_source": entry_source,
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
    }

    def _real_long_leg(series, checkpoint, d):
        real = _price_asof(series, contract_key, checkpoint, expiration_date)
        if real is None:
            return None
        if K_short is None:
            return real, ""
        short, short_src = _short_leg_price(checkpoint, d)
        if short is None:
            return None
        return real - short, short_src

    def _bs_exit(checkpoint, d):
        S_exit = price_fn(ticker, checkpoint)
        if S_exit is None:
            return None
        T_exit = max(0, (dte_entry - d) / 365)
        if K_short is None:
            return _bs_price(S_exit, K, T_exit, r, iv, opt_type), ""
        return _bs_spread_price(S_exit, K, K_short, T_exit, r, iv, opt_type), "bs"

    _tag = {"barchart": "barchart", "reappearance": "real", "bs": "bs"}

    def _mark_on(day, d):
        for src in exit_sources:
            priced = None
            if src == "barchart":
                priced = _real_long_leg(barchart_series, day, d)
            elif src == "reappearance":
                priced = _real_long_leg(contract_index, day, d)
            elif src == "bs":
                priced = _bs_exit(day, d)
            if priced is not None and priced[0] is not None:
                price, short_src = priced
                source = _tag.get(src, src)
                if K_short is not None and src != "bs":
                    source += f"+{short_src}"
                if K_short is not None:  # spread cost-to-close floored at zero
                    price = max(0.0, price)
                return price, source
        return None, ""

    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = dte_entry <= path_cap
    end_date = signal_date + timedelta(days=min(dte_entry, path_cap))
    if expiration_date:
        end_date = min(end_date, expiration_date)

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        price, source = _mark_on(day, d)
        grid_marks.append((day, d, price, source))

    result.update(_summarize_path(
        grid_marks, entry_price, is_credit, profit_target, stop_loss, contracts,
        cap_reached_expiry))
    return result
