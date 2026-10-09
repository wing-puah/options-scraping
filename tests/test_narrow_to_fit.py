"""Tests for `narrow_to_fit` (F3 / F4) and the floor rule it adds to account_sim.

No book and no network. Every test builds its own records, its own in-memory
option chain, or a temporary cache directory, so the properties pinned here
are the registration's gates:

  * GN1 REFUSE IDENTITY — F3 with every narrowing forced to refuse is F2;
  * GN2 STOP IDENTITY   — F4 with its stop set back to the budget is F1;
  * GN3 PRICING MIRROR  — the builder reproduces a row production priced,
                          and a changed mark fails it;
  * GN4 STRIKE BLINDNESS — cutting substitute histories after the entry day
                          never changes the strike chosen;
  * the leg-choice rule — a debit vertical moves its SOLD leg, a credit
                          vertical its LONG leg (operator ruling 2);
  * the default account_sim path is unchanged by the three-valued floor.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.f4_deployment.account_sim import (  # noqa: E402
    Cfg, book_signature, simulate,
)
from scripts.backtest_study.lib.harness import Trade  # noqa: E402

SIGNAL = date(2025, 1, 6)            # a Monday
ENTRY = date(2025, 1, 7)             # next_open entry day
EXPIRY = date(2025, 2, 21)


def _cfg(**kw):
    base = dict(label="t", capital=25_000.0, per_pos_cap=float("inf"),
                net_cap=float("inf"), risk_pct=0.02, max_per_day=3,
                enforce_cash=False)
    base.update(kw)
    return Cfg(**base)


def _grid(signal=SIGNAL, expiry=EXPIRY):
    out, d = [], signal + timedelta(days=1)
    while d <= expiry:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _row(legs: str, entry: float, marks, structure="bull_call_spread",
         signal=SIGNAL, expiry=EXPIRY, dte=None, **extra):
    row = {"signal_date": signal.isoformat(), "ticker": "TEST",
           "structure": structure, "contracts": "1",
           "dte_entry": str(dte if dte is not None else (expiry - ENTRY).days),
           "entry_option_price": str(entry), "entry_underlying": "100",
           "legs": legs, "daily_price_csv": ",".join(str(m) for m in marks)}
    row.update(extra)
    return row


def _rec(mlpc, marks, entry=5.0, credit=False, day=SIGNAL, delta=0.30,
         structure="bull_call_spread"):
    legs = (f"TEST:{EXPIRY.isoformat()}:100:C +1\nTEST:{EXPIRY.isoformat()}:110:C -1")
    t = Trade(_row(legs, entry, marks, structure=structure, signal=day,
                   dte=(EXPIRY - day).days - 1))
    return {"t": t, "credit": credit, "structure": structure, "mech_cell": "PROD",
            "max_loss_per_contract": mlpc, "delta": delta,
            "date": day.isoformat(), "ticker": "TEST"}


def _book():
    """Three dates, a mix of affordable and over-budget picks, one losing hard
    enough to hit a $500 stop but not a $1,000 one."""
    out = []
    for i, day in enumerate((date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 20))):
        n = len(_grid(day))
        recs = [
            _rec(300.0, [5.5] * n, entry=5.0, day=day),             # fits $500
            _rec(800.0, [5.0 - 0.1 * k for k in range(n)], entry=8.0, day=day),
            _rec(1200.0, [12.0 + 0.05 * k for k in range(n)], entry=12.0, day=day),
        ]
        out.append((day.isoformat(), recs))
    return out


# ── the floor rule: default path unchanged ───────────────────────────────────

def test_floor_none_derives_take_and_refuse_from_take_floor():
    assert _cfg().floor_rule == "take"
    assert _cfg(take_floor=False).floor_rule == "refuse"
    assert _cfg(floor="narrow").floor_rule == "narrow"
    with pytest.raises(ValueError):
        _ = _cfg(floor="widen").floor_rule


def test_explicit_floor_reproduces_the_bool_it_replaces():
    book = _book()
    assert book_signature(simulate(book, _cfg())) == \
        book_signature(simulate(book, _cfg(floor="take")))
    assert book_signature(simulate(book, _cfg(take_floor=False))) == \
        book_signature(simulate(book, _cfg(floor="refuse")))


def test_narrow_floor_without_a_narrower_is_refused():
    with pytest.raises(ValueError):
        simulate(_book(), _cfg(floor="narrow"))


# ── GN1 / GN2 on a synthetic book ────────────────────────────────────────────

def test_gn1_forced_refuse_is_f2_position_for_position():
    book = _book()
    refuser = NTF.Narrower(None, set(), {}, force_refuse=True)
    forced = simulate(book, _cfg(floor="narrow"), narrower=refuser)
    f2 = simulate(book, _cfg(take_floor=False))
    assert book_signature(forced) == book_signature(f2)
    assert forced.census["narrow_no_fit"] == f2.census["min1_refusal"] > 0
    assert forced.census["narrow_offered"] == f2.census["min1_refusal"]


def test_gn2_f4_with_its_stop_back_at_the_budget_is_f1():
    book = _book()
    f1 = simulate(book, _cfg())
    f4_back = simulate(book, _cfg(stop_abs=500.0))
    assert book_signature(f4_back) == book_signature(f1)
    # ...and the decoupled stop does move the book, so the identity is not vacuous.
    f4 = simulate(book, _cfg(stop_abs=1000.0))
    assert book_signature(f4) != book_signature(f1)


def test_a_narrowed_record_is_sized_admitted_and_replayed_like_any_other():
    book = _book()
    kept = []

    def narrower(rec, budget):
        r = dict(rec)
        r["max_loss_per_contract"] = 450.0
        r["narrowed"] = True
        kept.append(r)                       # alive for the id()-keyed memo
        return r, None

    sim = simulate(book, _cfg(floor="narrow"), narrower=narrower)
    narrowed = [p for p in sim.signal_pos if p.rec.get("narrowed")]
    assert len(narrowed) == sim.census["narrowed"] == 6
    assert all(p.contracts == 1 and p.reserved == 450.0 for p in narrowed)


# ── the leg-choice rule ─────────────────────────────────────────────────────

def _legs(k_long, k_short, cp="C"):
    opt = "Call" if cp == "C" else "Put"
    return [Leg(1, "TEST", EXPIRY, float(k_long), opt),
            Leg(-1, "TEST", EXPIRY, float(k_short), opt)]


def test_debit_vertical_anchors_the_bought_leg_and_moves_the_sold_leg():
    legs = _legs(100, 110)
    anchor, mover = NTF.vertical_roles(legs, credit=False)
    assert legs[anchor].qty > 0 and legs[mover].qty < 0


def test_credit_vertical_anchors_the_sold_leg_and_moves_the_long_leg():
    legs = _legs(90, 100, cp="P")          # bull put: long 90P, short 100P
    anchor, mover = NTF.vertical_roles(legs, credit=True)
    assert legs[anchor].qty < 0 and legs[anchor].strike == 100
    assert legs[mover].qty > 0 and legs[mover].strike == 90


def test_non_vertical_has_no_roles():
    assert NTF.vertical_roles(_legs(100, 110)[:1], credit=False) is None
    calendar = [Leg(1, "TEST", EXPIRY, 100.0, "Call"),
                Leg(-1, "TEST", EXPIRY + timedelta(days=28), 100.0, "Call")]
    assert NTF.vertical_roles(calendar, credit=False) is None


def test_inward_walks_from_the_mover_toward_the_anchor():
    grid = [101.0, 102.0, 105.0, 109.0]
    a, m = Leg(1, "T", EXPIRY, 100.0, "Call"), Leg(-1, "T", EXPIRY, 110.0, "Call")
    assert NTF.inward(a, m, grid) == [109.0, 105.0, 102.0, 101.0]
    a, m = Leg(-1, "T", EXPIRY, 100.0, "Put"), Leg(1, "T", EXPIRY, 90.0, "Put")
    assert NTF.inward(a, m, [91.0, 95.0, 99.0]) == [91.0, 95.0, 99.0]


# ── an in-memory chain for the strike choice ─────────────────────────────────

def _quote(px, delta=None):
    return {"Open": str(px), "Bid": f"{px - 0.05:.2f}", "Ask": f"{px + 0.05:.2f}",
            "Latest": str(px), "Volume": "10", "IV": "30", "_mark": px,
            "Delta": "" if delta is None else str(delta), "Price~": "100"}


def _history(prices: dict[date, float]):
    series = sorted(prices.items())
    details = {d: _quote(p) for d, p in prices.items()}
    return series, details


def _chain(contracts: dict[tuple, dict[date, float]]):
    """`contracts`: {(strike, "Call"/"Put"): {day: price}} on TEST/EXPIRY."""
    idx = {("TEST", EXPIRY): {}}
    ch = NTF.Chain(idx=idx)
    for (k, opt), prices in contracts.items():
        idx[("TEST", EXPIRY)].setdefault(float(k), set()).add("C" if opt == "Call" else "P")
        ch._memo[("TEST", EXPIRY, round(float(k), 4), opt)] = _history(prices)
    return ch


def _pick(legs_text, entry, structure, credit):
    n = len(_grid())
    t = Trade(_row(legs_text, entry, [entry] * n, structure=structure))
    return {"t": t, "credit": credit, "structure": structure}


def _days(price_on_entry, later=None):
    """A price on the signal day and the entry day, then `later` after it."""
    out = {SIGNAL: price_on_entry, ENTRY: price_on_entry}
    for i, d in enumerate(_grid()[1:], start=1):
        out[d] = price_on_entry if later is None else later
    return out


def test_debit_choice_moves_the_sold_call_inward_to_the_widest_that_fits():
    # Bull call 100/110 at 8.00 - 1.00 = 7.00 debit ($700): over a $500 budget.
    ch = _chain({(100, "Call"): _days(8.0), (110, "Call"): _days(1.0),
                 (109, "Call"): _days(1.5), (108, "Call"): _days(2.0),
                 (107, "Call"): _days(3.4), (106, "Call"): _days(4.0)})
    # Every grid strike 101..109 must be visible for the walk to prove the
    # widest; 101..105 are cached too so nothing is unproven.
    for k, px in ((105, 4.5), (104, 5.0), (103, 5.6), (102, 6.3), (101, 7.1)):
        ch.idx[("TEST", EXPIRY)].setdefault(float(k), set()).add("C")
        ch._memo[("TEST", EXPIRY, float(k), "Call")] = _history(_days(px))
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1", 7.0,
                "bull_call_spread", False)
    roles = NTF.vertical_roles(list(rec["t"].legs), False)
    got = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY)
    # 109: 8.0-1.5=6.5 ($650) no; 108: 6.0 no; 107: 4.6 ($460) fits.
    assert got.reason == "fit" and got.strike == 107.0
    assert got.max_loss == pytest.approx(460.0)


def test_credit_choice_moves_the_long_put_inward_and_keeps_the_sold_put():
    # Bull put 100/90: sell 100P at 6.00, buy 90P at 1.00 -> 5.00 credit,
    # max loss (10 - 5) x 100 = $500 > a $400 budget.
    prices = {100: 6.0, 99: 5.4, 98: 4.8, 97: 4.2, 96: 3.7, 95: 3.2, 94: 2.7,
              93: 2.2, 92: 1.8, 91: 1.4, 90: 1.0}
    ch = _chain({(k, "Put"): _days(p) for k, p in prices.items()})
    rec = _pick(f"TEST:{EXPIRY}:100:P -1\nTEST:{EXPIRY}:90:P +1", -5.0,
                "bull_put_spread", True)
    roles = NTF.vertical_roles(list(rec["t"].legs), True)
    got = NTF.choose_strike(rec, 400.0, ch, set(), roles, ENTRY)
    # 91: credit 4.6, loss (9-4.6)=4.4 no; 92: 4.2 -> 3.8 ($380) fits.
    assert got.reason == "fit" and got.strike == 92.0
    assert got.net == pytest.approx(-(6.0 - 1.8))


def test_an_uncached_strike_in_the_walk_is_unproven_not_skipped():
    ch = _chain({(100, "Call"): _days(8.0), (110, "Call"): _days(1.0),
                 (105, "Call"): _days(4.5)})
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1", 7.0,
                "bull_call_spread", False)
    roles = NTF.vertical_roles(list(rec["t"].legs), False)
    got = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY)
    # Cached spacing 5 and the $2.50 listing step: the walk meets 107.5 first.
    assert got.reason == "unproven" and "107.50C" in got.detail


def test_only_evidence_entries_count_as_unlisted():
    ch = _chain({(100, "Call"): _days(8.0), (110, "Call"): _days(1.0),
                 (105, "Call"): _days(4.5)})
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1", 7.0,
                "bull_call_spread", False)
    roles = NTF.vertical_roles(list(rec["t"].legs), False)
    evidence = {NTF.contract_stem("TEST", EXPIRY, 107.5, "Call")}
    got = NTF.choose_strike(rec, 500.0, ch, evidence, roles, ENTRY)
    assert got.reason == "fit" and got.strike == 105.0


def test_unlisted_evidence_ignores_seeded_entries(tmp_path):
    p = tmp_path / "_unlisted.jsonl"
    p.write_text(
        '{"key": "A_20250221_10.00C", "expiry": "2025-02-21", "last_checked": '
        '"2026-09-27", "n_checks": 1, "reason": "http_404"}\n'
        '{"key": "B_20250221_10.00C", "expiry": "2025-02-21", "last_checked": '
        '"2026-09-26", "n_checks": 1, "reason": "seeded_from_log_2026-09-26"}\n')
    assert NTF.unlisted_evidence(p) == {"A_20250221_10.00C"}



def test_unlisted_evidence_needs_two_confirmations_of_an_empty_feed(tmp_path):
    p = tmp_path / "_unlisted.jsonl"
    p.write_text(
        '{"key": "A_20250221_10.00C", "expiry": "2025-02-21", "last_checked": '
        '"2026-10-07", "n_checks": 1, "reason": "no_rows"}\n'
        '{"key": "B_20250221_10.00C", "expiry": "2025-02-21", "last_checked": '
        '"2026-10-08", "n_checks": 2, "reason": "no_rows"}\n')
    assert NTF.unlisted_evidence(p) == {"B_20250221_10.00C"}

# ── the net floor (declared secondary, resolved at build 2026-10-09) ────────

def _near_zero_pick():
    """MU 2026-09-21's shape: one step inward, the narrowed debit spread is
    $0.06 on a 40-wide spread — $6 of max loss, so it fits any budget and
    sizes to dozens of contracts."""
    ch = _chain({(100, "Call"): _days(6.06), (141, "Call"): _days(0.50),
                 (140, "Call"): _days(6.00)})
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:141:C -1", 5.56,
                "bull_call_spread", False)
    return ch, rec, NTF.vertical_roles(list(rec["t"].legs), False)


def test_near_zero_net_is_kept_without_the_floor():
    ch, rec, roles = _near_zero_pick()
    got = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY)
    assert got.reason == "fit" and got.strike == 140.0
    assert got.net == pytest.approx(0.06) and got.max_loss == pytest.approx(6.0)


def test_near_zero_net_is_refused_under_the_floor():
    ch, rec, roles = _near_zero_pick()
    got = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY,
                            net_floor=NTF.NET_FLOOR_SHARE)
    assert NTF.NET_FLOOR_SHARE == 0.20
    # The floor refuses the widest fit; it never walks on to a narrower strike.
    assert got.reason == "below_floor" and got.strike == 140.0


def test_the_floor_keeps_a_debit_at_or_above_a_fifth_of_width():
    assert not NTF.below_net_floor(2.0, 10.0, False, 0.20)       # exactly 20%
    assert NTF.below_net_floor(1.99, 10.0, False, 0.20)
    assert not NTF.below_net_floor(0.06, 40.0, False, None)      # registered rule
    # A credit spread is never floored: a tiny credit cannot size up.
    assert not NTF.below_net_floor(-0.06, 40.0, True, 0.20)


def test_the_floor_leaves_an_ordinary_narrowing_unchanged():
    ch = _chain({(100, "Call"): _days(8.0), (110, "Call"): _days(1.0),
                 (109, "Call"): _days(1.5), (108, "Call"): _days(2.0),
                 (107, "Call"): _days(3.4), (106, "Call"): _days(4.0)})
    for k, px in ((105, 4.5), (104, 5.0), (103, 5.6), (102, 6.3), (101, 7.1)):
        ch.idx[("TEST", EXPIRY)].setdefault(float(k), set()).add("C")
        ch._memo[("TEST", EXPIRY, float(k), "Call")] = _history(_days(px))
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1", 7.0,
                "bull_call_spread", False)
    roles = NTF.vertical_roles(list(rec["t"].legs), False)
    plain = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY)
    floored = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY, net_floor=0.20)
    assert (plain.reason, plain.strike) == (floored.reason, floored.strike) == ("fit", 107.0)


def test_the_narrower_files_a_below_floor_pick_as_no_fit():
    ch, rec, _roles = _near_zero_pick()
    floored = NTF.Narrower(ch, set(), {}, net_floor=NTF.NET_FLOOR_SHARE)
    n = floored.narrow(rec, 500.0)
    assert (n.bucket, n.reason) == ("narrow_no_fit", "below_net_floor")
    assert floored(rec, 500.0) == (None, "narrow_no_fit")


# ── GN4 strike blindness ─────────────────────────────────────────────────────

def test_gn4_cutting_substitutes_after_entry_never_moves_the_choice():
    # The substitutes go wild AFTER the entry day; the choice must not see it.
    base = {(100, "Call"): _days(8.0), (110, "Call"): _days(1.0)}
    subs = {(k, "Call"): _days(px, later=0.01)
            for k, px in ((109, 1.5), (108, 2.0), (107, 3.4), (106, 4.0),
                          (105, 4.5), (104, 5.0), (103, 5.6), (102, 6.3), (101, 7.1))}
    ch = _chain({**base, **subs})
    rec = _pick(f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1", 7.0,
                "bull_call_spread", False)
    roles = NTF.vertical_roles(list(rec["t"].legs), False)
    full = NTF.choose_strike(rec, 500.0, ch, set(), roles, ENTRY)
    cut = {("TEST", EXPIRY, float(k), "Call"): ENTRY for (k, _o) in subs}
    blind = NTF.choose_strike(rec, 500.0, NTF.Chain(cutoff=cut, parent=ch), set(),
                              roles, ENTRY)
    assert (full.reason, full.strike) == (blind.reason, blind.strike) == ("fit", 107.0)


def test_a_strike_first_quoted_after_entry_is_not_listed_that_day():
    late = {d: 4.6 for d in _grid()[2:]}     # no quote on the signal or entry day
    ch = _chain({(100, "Call"): _days(8.0), (110, "Call"): _days(1.0),
                 (107, "Call"): late})
    leg = Leg(-1, "TEST", EXPIRY, 107.0, "Call")
    px, tag = NTF.entry_fill(ch, leg, ENTRY, SIGNAL)
    assert px is None and tag == "first_quote_after_entry"


# ── GN3 pricing mirror on a temporary cache ─────────────────────────────────

_HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
           "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _csv(prices: dict[date, float], delta: float) -> str:
    lines = [_HEADER]
    for d, p in sorted(prices.items()):
        lines.append(f"{d.isoformat()},{p},{p},{p},{p},0,0%,10,100,30,{delta},"
                     f"0,0,0,0,{p},100,{p - 0.05:.2f},{p + 0.05:.2f}")
    return "\n".join(lines) + "\n"


def test_gn3_builder_reproduces_a_production_row_and_catches_a_changed_mark(
        tmp_path, monkeypatch):
    from lib.barchart.options import cache_path
    monkeypatch.setattr(NTF, "HISTORY_CACHE", tmp_path)
    long_px = {d: 8.0 + 0.05 * i for i, d in enumerate([SIGNAL, ENTRY] + _grid()[1:])}
    short_px = {d: 1.0 + 0.02 * i for i, d in enumerate([SIGNAL, ENTRY] + _grid()[1:])}
    cache_path(tmp_path, "TEST", EXPIRY, 100.0, "Call").write_text(_csv(long_px, 0.6))
    cache_path(tmp_path, "TEST", EXPIRY, 110.0, "Call").write_text(_csv(short_px, 0.2))

    sim_cfg = {"entry_timing": "next_open", "exit_sources": ["barchart"],
               "entry_sources": ["barchart"], "path_cap_days": 120,
               "profit_target": 0.9, "stop_loss": 0.75}
    chain = NTF.Chain(idx={("TEST", EXPIRY): {100.0: {"C"}, 110.0: {"C"}}})
    legs_text = f"TEST:{EXPIRY}:100:C +1\nTEST:{EXPIRY}:110:C -1"
    n = len(_grid())
    seed = {"t": Trade(_row(legs_text, 7.0, [7.0] * n)), "credit": False,
            "structure": "bull_call_spread"}
    stored, refusal = NTF.build_position(seed, list(seed["t"].legs), chain, sim_cfg,
                                         ENTRY)
    assert stored is not None, refusal
    row = {k: str(v) for k, v in stored.items()}
    rec = {"t": Trade(row), "credit": False, "structure": "bull_call_spread"}
    assert NTF.reproduces(rec, chain, sim_cfg) == (True, "ok")

    marks = row["daily_price_csv"].split(",")
    marks[3] = f"{float(marks[3]) + 0.5:.4f}"
    bad = dict(row, daily_price_csv=",".join(marks))
    ok, why = NTF.reproduces({"t": Trade(bad), "credit": False,
                              "structure": "bull_call_spread"}, chain, sim_cfg)
    assert not ok and "daily marks differ" in why


# ── grading helpers ─────────────────────────────────────────────────────────

def test_q2_verdict_follows_the_registered_table():
    met = dict(N4=True, N5=True, lo=0.01, hi=0.2)
    assert NTF.q2_verdict(True, True, True, met) == "AWAITING SCRAPE"
    assert NTF.q2_verdict(False, False, True, None) == "UNDERPOWERED"
    assert NTF.q2_verdict(False, True, True, met) == "NARROW-FEASIBLE"
    assert NTF.q2_verdict(False, True, False, met) == "AFFORDABILITY"
    assert NTF.q2_verdict(False, True, True,
                          dict(N4=False, N5=False, lo=-0.3, hi=-0.01)) == "SELECTION"
    assert NTF.q2_verdict(False, True, True,
                          dict(N4=False, N5=False, lo=-0.1, hi=0.1)) == "NULL"


def test_strike_grid_takes_the_finer_step_and_keeps_cached_strikes():
    grid = NTF.strike_grid([100.0, 102.5, 105.0, 107.0], 104.0, 100.0, 110.0)
    # Cached spacing 2.0 is finer than the $2.50 listing step at $104.
    assert {102.0, 102.5, 104.0, 105.0, 106.0, 107.0, 108.0} <= set(grid)
    assert all(100.0 < k < 110.0 for k in grid)
