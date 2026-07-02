import logging
import math
from datetime import timedelta

from .helpers import (
    _bs_price, _bs_delta,
    _num, _opt_price, _row_iv, _contract_key,
    _price_asof,
    _get_prices, _price_on_or_after,
    _weekday_grid,
    _defined_risk_bounds,
)
from .legs import format_legs, merge_legs

log = logging.getLogger("backtest")


def _size_contracts(entry_price: float, sim_cfg: dict) -> int:
    """Fixed-fractional position sizing: size so that hitting stop_loss costs at most
    risk_per_trade_pct × portfolio_value. Minimum 1 contract; a separate dollar stop
    in _summarize_path enforces the budget cap when 1 contract already exceeds it.
    Falls back to sim_cfg['contracts'] when portfolio_value is unset.

    `entry_price` is the per-unit premium magnitude (abs of the signed net)."""
    portfolio = sim_cfg.get("portfolio_value")
    risk_pct = sim_cfg.get("risk_per_trade_pct")
    stop = sim_cfg.get("stop_loss", 1.0)
    if portfolio and risk_pct and stop > 0 and entry_price > 0:
        dollar_risk = portfolio * risk_pct
        loss_per_contract = entry_price * 100 * stop
        return max(1, math.floor(dollar_risk / loss_per_contract))
    return sim_cfg.get("contracts", 1)


def _max_loss_abs(sim_cfg: dict) -> float | None:
    """Dollar loss cap per trade from portfolio config. None when not configured."""
    portfolio = sim_cfg.get("portfolio_value")
    risk_pct = sim_cfg.get("risk_per_trade_pct")
    if portfolio and risk_pct:
        return portfolio * risk_pct
    return None


# ─── Path summarizer ───────────────────────────────────────────────────────────

def _summarize_path(grid_marks, entry_net, profit_target, stop_loss,
                    contracts, cap_reached_expiry, max_loss_abs=None,
                    time_exit_day=None, trailing_stop_trigger=None,
                    trailing_stop_pct=None, loss_days_exit=None) -> dict:
    """Turn a day-by-day signed-value grid into the path string, realized exit, and MFE/MAE.

    Each grid mark holds the position's signed net value V = Σ qty·price. P&L is
    the single unified formula `(V − entry_net) / abs(entry_net)`, correct for both
    debit (entry_net > 0) and credit (entry_net < 0) positions with no flag.

    Realized exit = the FIRST exit condition crossed (frozen at that day's mark).
    MFE/MAE are measured over the WHOLE path so exit params can be tuned in analysis.

    Exit priority:
      1. profit_target  — activates trailing from peak (floor guarantee); exits only if
                          no trailing_stop_trigger/pct is configured (disabled when None)
      2. trailing_stop  — trails from peak once trailing_stop_trigger is reached OR
                          profit_target activates it (whichever comes first)
      3. dollar_stop    — hard per-trade $ loss cap from portfolio sizing
      4. stop_loss      — hard % loss floor
      5. loss_days_exit — N consecutive trading days in loss
      6. time_exit_day  — calendar days from entry; graceful time-based close
    """
    denom = abs(entry_net)

    def pnl_of(v):
        return (v - entry_net) / denom

    prices, sources = [], []
    for (_, _, p, src) in grid_marks:
        prices.append("" if p is None else f"{p:.4f}")
        sources.append("" if p is None else src)
    out = {
        "daily_price_csv": ",".join(prices),
        "daily_source_csv": ",".join(sources),
    }

    priced = [(dt, d, p, src) for (dt, d, p, src) in grid_marks if p is not None]
    if not priced:
        out.update({"realized_pnl_pct": "", "realized_pnl_abs": "", "days_held": "",
                    "exit_reason": "no_data", "mfe_pct": "", "mfe_abs": "", "mfe_day": "",
                    "mae_pct": "", "mae_abs": "", "mae_day": "", "pnl_at_cap_pct": "",
                    "pct_real_days": ""})
        return out

    mfe, mae, mfe_day, mae_day = -1e18, 1e18, None, None
    exit_reason = realized_p = None
    days_held = last_priced_idx = None
    peak_pnl = -1e18
    trailing_active = False
    loss_streak = 0
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
            peak_pnl = max(peak_pnl, pl)
            if trailing_stop_trigger is not None and peak_pnl >= trailing_stop_trigger:
                trailing_active = True
            loss_streak = loss_streak + 1 if pl < 0 else 0

            if profit_target is not None and pl >= profit_target:
                exit_reason, realized_p, days_held = "profit_target", p, grid_idx
            elif (trailing_active and trailing_stop_pct is not None
                  and pl <= peak_pnl - trailing_stop_pct):
                exit_reason, realized_p, days_held = "trailing_stop", p, grid_idx
            elif max_loss_abs is not None and pl * denom * 100 * contracts <= -max_loss_abs:
                exit_reason, realized_p, days_held = "dollar_stop", p, grid_idx
            elif pl <= -stop_loss:
                exit_reason, realized_p, days_held = "stop_loss", p, grid_idx
            elif loss_days_exit is not None and loss_streak >= loss_days_exit:
                exit_reason, realized_p, days_held = "loss_days", p, grid_idx
            elif time_exit_day is not None and d >= time_exit_day:
                exit_reason, realized_p, days_held = "time_exit", p, grid_idx

    if exit_reason is None:
        _, _, last_p, _ = priced[-1]
        realized_p, days_held = last_p, last_priced_idx
        exit_reason = "expired" if cap_reached_expiry else "cap_open"

    realized_pnl = pnl_of(realized_p)
    cap_p = priced[-1][2]
    real_days = sum(1 for (_, _, _, s) in priced
                    if s and any(t != "bs" for t in s.split("+")))

    out.update({
        "realized_pnl_pct": round(realized_pnl, 4),
        "realized_pnl_abs": round(realized_pnl * denom * 100 * contracts, 2),
        "days_held": days_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe, 4),
        "mfe_abs": round(mfe * denom * 100 * contracts, 2),
        "mfe_day": mfe_day,
        "mae_pct": round(mae, 4),
        "mae_abs": round(mae * denom * 100 * contracts, 2),
        "mae_day": mae_day,
        "pnl_at_cap_pct": round(pnl_of(cap_p), 4),
        "pct_real_days": round(real_days / len(priced), 4),
    })
    return out


# ─── Iron condor strike resolution ──────────────────────────────────────────────

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


# ─── Generic leg-list simulation ─────────────────────────────────────────────────

def _simulate(candidate, legs, entry_row, contract_index, barchart_series, sim_cfg,
              structure="", anchor_idx=0, price_fn=None):
    """Simulate one position expressed as a list of signed Legs.

    For each leg, pricing follows the source priority from sim_cfg['exit_sources']:
      real flow trade (anchor at entry only) → barchart → reappearance → bs

    Steps:
      1. price each leg at entry
      2. price each leg on each trading day
      3. multiply by qty (sign)
      4. multiply by contracts
      5. daily_price_csv + realized exit + MFE/MAE

    Returns a result dict, or {} if the position cannot be priced.
    barchart_series / contract_index map contract_key -> sorted [(date, price)].
    price_fn(ticker, date) -> float|None is injectable for testing (BS underlying).
    """
    legs = merge_legs(legs)
    if not legs:
        return {}

    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    dte_entry = _num(entry_row.get("DTE"))
    if not (iv and S_entry and dte_entry and dte_entry > 0):
        return {}
    dte_entry = int(dte_entry)

    ticker = candidate["ticker"]
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)
    exit_sources = sim_cfg.get("exit_sources", ["barchart", "reappearance", "bs"])
    entry_sources = sim_cfg.get("entry_sources", ["barchart"])

    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, signal_date, sim_cfg.get("path_cap_days", 120)), dt))

    def _key(leg):
        return _contract_key(leg.ticker, leg.opt_type, leg.strike, leg.expiration.isoformat())

    def _T(leg, d):
        return max(0.0, ((leg.expiration - signal_date).days - d) / 365)

    def _price_leg(leg, day, d, sources=None):
        if sources is None:
            sources = exit_sources
        key = _key(leg)
        for src in sources:
            if src == "barchart":
                p = _price_asof(barchart_series, key, day, leg.expiration)
                if p is not None:
                    return p, "barchart"
            elif src == "reappearance":
                p = _price_asof(contract_index, key, day, leg.expiration)
                if p is not None:
                    return p, "real"
            elif src == "bs":
                S = price_fn(ticker, day)
                if S is None:
                    return None, None
                return _bs_price(S, leg.strike, _T(leg, d), r, iv, leg.opt_type), "bs"
        return None, None

    # Step 1 — entry price for each leg (barchart only, all legs consistent EOD basis).
    entry_prices, entry_tags = [], []
    for leg in legs:
        p, tag = _price_leg(leg, signal_date, 0, sources=entry_sources)
        if p is None:
            return {}
        entry_prices.append(p)
        entry_tags.append(tag)

    entry_net = sum(leg.qty * p for leg, p in zip(legs, entry_prices))
    if abs(entry_net) <= 1e-9:
        return {}

    # Per-leg entry breakdown for diagnostics and delta.
    anchor_flow_delta = _num(entry_row.get("Delta"))
    detail_lines, net_delta = [], 0.0
    for i, (leg, p, tag) in enumerate(zip(legs, entry_prices, entry_tags)):
        dlt = anchor_flow_delta if (i == anchor_idx and anchor_flow_delta is not None) \
              else _bs_delta(S_entry, leg.strike, _T(leg, 0), r, iv, leg.opt_type)
        net_delta += leg.qty * dlt
        cp = "C" if leg.opt_type == "Call" else "P"
        detail_lines.append(
            f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:{cp} {leg.qty:+d}"
            f"  px={p:g} iv={iv * 100:g}% delta={dlt:.3f} [{tag}]")

    _v_clamp = _defined_risk_bounds(legs)

    # Steps 2-4 — for each trading day, price each leg and net by qty.
    nearest_dte = min((leg.expiration - signal_date).days for leg in legs)
    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = nearest_dte <= path_cap
    end_date = signal_date + timedelta(days=min(nearest_dte, path_cap))

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        value, tags = 0.0, []
        for leg in legs:
            p, tag = _price_leg(leg, day, d)
            if p is None:
                value = None
                break
            value += leg.qty * p
            tags.append(tag)
        if value is not None and _v_clamp is not None:
            value = max(_v_clamp[0], min(_v_clamp[1], value))
        grid_marks.append((day, d, value, "+".join(tags) if value is not None else ""))

    # Step 5 — daily_price_csv + realized exit + MFE/MAE.
    contracts = _size_contracts(abs(entry_net), sim_cfg)
    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)
    _tex_frac = sim_cfg.get("time_exit_dte_fraction")
    time_exit_day = int(dte_entry * _tex_frac) if _tex_frac else None
    loss_days_exit = sim_cfg.get("loss_days_exit")

    _pos_value = abs(entry_net) * 100 * contracts
    _portfolio = sim_cfg.get("portfolio_value")

    def _effective_threshold(pct_of_premium_key, pct_of_portfolio_key):
        opts = []
        v = sim_cfg.get(pct_of_premium_key)
        if v is not None:
            opts.append(v * _pos_value)
        p = sim_cfg.get(pct_of_portfolio_key)
        if p is not None and _portfolio:
            opts.append(p * _portfolio)
        if not opts or _pos_value == 0:
            return None
        return min(opts) / _pos_value

    trailing_stop_trigger = _effective_threshold(
        "trailing_stop_trigger", "trailing_stop_portfolio_trigger_pct")
    trailing_stop_pct = _effective_threshold(
        "trailing_stop_pct", "trailing_stop_portfolio_trail_pct")

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": structure,
        "legs": format_legs(legs),
        "contracts": contracts,
        "dte_entry": dte_entry,
        "iv_entry_pct": round(iv, 4),
        "delta": round(net_delta, 4),
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_net, 4),
        "entry_premium_total": round(abs(entry_net) * 100 * contracts, 2),
        "entry_source": "+".join(entry_tags),
        "entry_leg_detail": "\n".join(detail_lines),
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
        "oi_confirm_pct": candidate.get("oi_confirm_pct", ""),
        "cpir": candidate.get("cpir", ""),
        "iv_spread": candidate.get("iv_spread", ""),
        "iv_skew": candidate.get("iv_skew", ""),
        "iv_pct": candidate.get("iv_pct", ""),
    }

    result.update(_summarize_path(
        grid_marks, entry_net, profit_target, stop_loss, contracts,
        cap_reached_expiry, _max_loss_abs(sim_cfg),
        time_exit_day=time_exit_day,
        trailing_stop_trigger=trailing_stop_trigger,
        trailing_stop_pct=trailing_stop_pct,
        loss_days_exit=loss_days_exit,
    ))
    return result
