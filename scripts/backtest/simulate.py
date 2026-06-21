import logging
import math
from datetime import timedelta

from .helpers import (
    _bs_price, _bs_delta,
    _num, _opt_price, _row_iv, _contract_key,
    _price_asof,
    _get_prices, _price_on_or_after,
    _weekday_grid,
)
from .legs import format_legs

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

    out = {"daily_price_csv": ",".join(
        "" if p is None else f"{p:.4f}" for (_, _, p, _) in grid_marks)}

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

# Mark-source tags. Reappearance and barchart are both "real" data; only
# Black-Scholes is modelled. pct_real_days keys off any non-"bs" token.
_MARK_TAG = {"barchart": "barchart", "reappearance": "real", "bs": "bs"}


def _simulate(candidate, legs, entry_row, contract_index, barchart_series, sim_cfg,
              structure="", anchor_idx=0, price_fn=None):
    """Simulate one position expressed as a list of signed `Leg`s.

    Each leg is priced independently and netted by signed quantity into a single
    position value V = Σ qty·price. Returns a result dict, or {} if it cannot be
    priced.

    Pricing per leg, in order from sim_cfg['exit_sources']:
      barchart     — real per-contract daily price (Barchart history cache)
      reappearance — real Trade price when the contract recurs in a later flow scrape
      bs           — Black-Scholes (last resort)
    barchart_series / contract_index map contract_key -> sorted [(date, price)].

    Positions with >= sim_cfg['uniform_bs_min_legs'] legs (default 4, i.e. iron
    condors) are priced entirely with Black-Scholes at a single IV for internal
    consistency — mixing a real price on one leg with BS on others produces a
    spurious net when IVs differ across widely separated strikes.

    `entry_row` is the anchor leg's entry row (real flow Trade + IV/underlying/DTE).
    price_fn(ticker, date) -> float|None is injectable for testing.
    """
    if not legs:
        return {}

    ticker = candidate["ticker"]
    signal_date = candidate["signal_date"]
    r = sim_cfg.get("risk_free_rate", 0.05)

    price_fn = price_fn or (lambda tk, dt: _price_on_or_after(
        _get_prices(tk, signal_date, sim_cfg.get("path_cap_days", 120)), dt))

    iv = _row_iv(entry_row)
    S_entry = _num(entry_row.get("Price~", entry_row.get("Price")))
    dte_entry = _num(entry_row.get("DTE"))
    real_anchor = _opt_price(entry_row)
    if not (iv and S_entry and dte_entry and dte_entry > 0):
        return {}
    dte_entry = int(dte_entry)

    uniform_bs = len(legs) >= sim_cfg.get("uniform_bs_min_legs", 4)
    exit_sources = sim_cfg.get("exit_sources", ["barchart", "reappearance", "bs"])

    # Reject degenerate positions (two legs on the same contract — should be merged).
    seen = set()
    for leg in legs:
        ident = (leg.opt_type, round(leg.strike, 4), leg.expiration)
        if ident in seen:
            return {}
        seen.add(ident)

    def _key(leg):
        return _contract_key(leg.ticker, leg.opt_type, leg.strike, leg.expiration.isoformat())

    def _T(leg, d):
        return max(0.0, ((leg.expiration - signal_date).days - d) / 365)

    # ── Entry leg pricing ──
    def _entry_leg(leg, idx):
        if uniform_bs:
            return _bs_price(S_entry, leg.strike, _T(leg, 0), r, iv, leg.opt_type), "bs"
        if idx == anchor_idx and real_anchor is not None:
            return real_anchor, "real"
        real = _price_asof(barchart_series, _key(leg), signal_date, leg.expiration)
        if real is not None:
            return real, "barchart"
        return _bs_price(S_entry, leg.strike, _T(leg, 0), r, iv, leg.opt_type), "bs"

    entry_prices, entry_tags = [], []
    for idx, leg in enumerate(legs):
        p, tag = _entry_leg(leg, idx)
        if p is None:
            return {}
        entry_prices.append(p)
        entry_tags.append(tag)

    entry_net = sum(leg.qty * p for leg, p in zip(legs, entry_prices))
    if abs(entry_net) <= 1e-9:
        return {}
    entry_source = "bs" if uniform_bs else "+".join(entry_tags)

    # Theoretical value bounds for 2-leg verticals: independent per-leg pricing
    # from different scrape times can produce net values outside [0, width] for a
    # debit spread (or [-width, 0] for credit), which is arbitrage-impossible.
    # Clamp daily marks to prevent phantom losses exceeding the max defined risk.
    _v_clamp: tuple[float, float] | None = None
    if len(legs) == 2 and not uniform_bs:
        _spread_width = abs(legs[0].strike - legs[1].strike)
        if _spread_width > 0:
            _v_clamp = (0.0, _spread_width) if entry_net > 0 else (-_spread_width, 0.0)

    # Per-leg raw entry breakdown (so the netted entry_option_price, iv_entry_pct and
    # delta can be validated leg-by-leg). The anchor leg's delta is the real flow
    # value; the rest are BS model deltas at the entry IV. Each line leads with the
    # contract (never a sign) so the cell is sheet-safe.
    anchor_flow_delta = _num(entry_row.get("Delta"))
    detail_lines, net_delta = [], 0.0
    for idx, (leg, p, tag) in enumerate(zip(legs, entry_prices, entry_tags)):
        if idx == anchor_idx and not uniform_bs and anchor_flow_delta is not None:
            dlt = anchor_flow_delta
        else:
            dlt = _bs_delta(S_entry, leg.strike, _T(leg, 0), r, iv, leg.opt_type)
        net_delta += leg.qty * dlt
        cp = "C" if leg.opt_type == "Call" else "P"
        detail_lines.append(
            f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:{cp} {leg.qty:+d}"
            f"  px={p:g} iv={iv * 100:g}% delta={dlt:.3f} [{tag}]")
    entry_leg_detail = "\n".join(detail_lines)

    # ── Daily leg pricing ──
    def _mark_leg(leg, d, day):
        if uniform_bs:
            S = price_fn(ticker, day)
            if S is None:
                return None, None
            return _bs_price(S, leg.strike, _T(leg, d), r, iv, leg.opt_type), "bs"
        for src in exit_sources:
            if src == "barchart":
                p = _price_asof(barchart_series, _key(leg), day, leg.expiration)
                if p is not None:
                    return p, _MARK_TAG["barchart"]
            elif src == "reappearance":
                p = _price_asof(contract_index, _key(leg), day, leg.expiration)
                if p is not None:
                    return p, _MARK_TAG["reappearance"]
            elif src == "bs":
                S = price_fn(ticker, day)
                if S is None:
                    return None, None
                return _bs_price(S, leg.strike, _T(leg, d), r, iv, leg.opt_type), _MARK_TAG["bs"]
        return None, None

    def _mark_on(day, d):
        value, tags = 0.0, []
        for leg in legs:
            p, tag = _mark_leg(leg, d, day)
            if p is None:
                return None, ""
            value += leg.qty * p
            tags.append(tag)
        if _v_clamp is not None:
            value = max(_v_clamp[0], min(_v_clamp[1], value))
        return value, ("bs" if uniform_bs else "+".join(tags))

    contracts = _size_contracts(abs(entry_net), sim_cfg)
    profit_target = sim_cfg.get("profit_target", 0.50)
    stop_loss = sim_cfg.get("stop_loss", 1.00)
    _tex_frac = sim_cfg.get("time_exit_dte_fraction")
    time_exit_day = int(dte_entry * _tex_frac) if _tex_frac else None
    loss_days_exit = sim_cfg.get("loss_days_exit")

    # Trailing stop: both % of entry premium and % of portfolio are converted to
    # dollars and the minimum is used — whichever fires first protects the trade.
    _pos_value = abs(entry_net) * 100 * contracts  # total dollar value of position
    _portfolio = sim_cfg.get("portfolio_value")

    def _effective_threshold(pct_of_premium_key, pct_of_portfolio_key):
        """Return effective threshold as % of entry premium (min of both expressions)."""
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
        # Net position delta = Σ qty·delta (anchor uses the real flow delta, other
        # legs the BS model delta at entry IV — same values shown in entry_leg_detail).
        "delta": round(net_delta, 4),
        "entry_underlying": S_entry,
        "entry_option_price": round(entry_net, 4),
        "entry_premium_total": round(abs(entry_net) * 100 * contracts, 2),
        "entry_source": entry_source,
        "entry_leg_detail": entry_leg_detail,
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
    }

    # Path runs to the NEAREST leg expiration (a calendar's short leg bounds it),
    # capped at path_cap_days.
    nearest_dte = min((leg.expiration - signal_date).days for leg in legs)
    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = nearest_dte <= path_cap
    end_date = signal_date + timedelta(days=min(nearest_dte, path_cap))

    grid_marks = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        value, source = _mark_on(day, d)
        grid_marks.append((day, d, value, source))

    result.update(_summarize_path(
        grid_marks, entry_net, profit_target, stop_loss, contracts,
        cap_reached_expiry, _max_loss_abs(sim_cfg),
        time_exit_day=time_exit_day,
        trailing_stop_trigger=trailing_stop_trigger,
        trailing_stop_pct=trailing_stop_pct,
        loss_days_exit=loss_days_exit,
    ))
    return result
