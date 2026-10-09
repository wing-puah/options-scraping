"""`ruin_bound` and its vectorised walk (`lib/ruin_walk.py`).

No export, no network: every test builds its own table or its own hand-made
`Trade` rows. What is pinned here is what the study's verdict leans on —

  * the stationary sampler: the identity at L >= n, geometric blocks that
    continue and wrap, and a restart share of about 1 / L;
  * the walk's ledger: booking, release, cash, the day cap, an unsizable pick
    burning a slot, the F2 refusal, the net cap, and ruin;
  * each guardrail (G-M, G-K, G-C) acting on the session after the close it
    reads, never on the same one;
  * each overlay (O1 long delta only, O2 full loss) and the R5 order that must
    hold path by path up to the shock;
  * the R4 truncation property: scrambling every outcome after a cut never
    changes a decision up to it;
  * gate R2's identity against `account_sim.simulate()` on a hand-built book.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.f4_deployment import ruin_bound as RB  # noqa: E402
from scripts.backtest_study.lib import ruin_walk as RW  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402


# ── a hand-built table ──────────────────────────────────────────────────────

def make_table(n, picks, capital=1000.0, max_per_day=3):
    """`picks` is a list of dicts with `t` (entry session) and optional `res`,
    `dn`, `dol`, `marks` (offsets 0..k), `uns`, `over`, `pp`. Ids follow list
    order, and each session lists its picks in that order."""
    C = len(picks)
    per = {}
    for cid, p in enumerate(picks):
        per.setdefault(p["t"], []).append(cid)
    K = max((len(v) for v in per.values()), default=1)
    cand = np.full((n, K), -1, dtype=np.int64)
    for t, ids in per.items():
        cand[t, :len(ids)] = ids
    marks_rows = [list(p.get("marks", [0.0])) for p in picks]
    W = max(len(m) for m in marks_rows) if picks else 1
    marks = np.zeros((C + 1, W))
    for cid, m in enumerate(marks_rows):
        marks[cid, :len(m)] = m
        marks[cid, len(m):] = m[-1]
    return RW.Table(
        n=n, cand=cand,
        reserved=np.array([p.get("res", 100.0) for p in picks], dtype=float),
        dn=np.array([p.get("dn", 0.0) for p in picks], dtype=float),
        dollars=np.array([p.get("dol", p.get("marks", [0.0])[-1]) for p in picks],
                         dtype=float),
        k=np.array([len(p.get("marks", [0.0])) - 1 for p in picks], dtype=np.int64),
        entry=np.array([p["t"] for p in picks], dtype=np.int64),
        unsizable=np.array([p.get("uns", False) for p in picks], dtype=bool),
        over_budget=np.array([p.get("over", False) for p in picks], dtype=bool),
        pp_bad=np.array([p.get("pp", False) for p in picks], dtype=bool),
        marks=marks, capital=capital, max_per_day=max_per_day)


def ident(tab):
    return np.arange(tab.n)[None, :]


def cfg(**kw):
    base = dict(label="t", net_cap=10.0, take_floor=True)
    base.update(kw)
    return RW.WalkCfg(**base)


def taken_ids(res):
    return [c for _p, _t, c in res.decisions]


# ── the sampler ─────────────────────────────────────────────────────────────

def test_identity_path_when_block_length_reaches_the_series():
    rng = np.random.default_rng(1)
    idx = RW.stationary_indices(7, 7, 7, 3, rng)
    assert (idx == np.arange(7)).all()


def test_stationary_blocks_continue_wrap_and_restart_about_once_per_L():
    rng = np.random.default_rng(2)
    n, H, L, P = 50, 400, 5, 500
    idx = RW.stationary_indices(n, H, L, P, rng)
    assert idx.min() >= 0 and idx.max() < n
    step = (idx[:, 1:] - idx[:, :-1]) % n
    restarts = step != 1
    # a restart can land on the next index by chance (1/n), so the share of
    # non-continuations sits just under 1/L
    assert abs(restarts.mean() - (1 / L) * (1 - 1 / n)) < 0.01
    wraps = (idx[:, :-1] == n - 1) & (idx[:, 1:] == 0)
    assert wraps.any()


def test_wilson_interval():
    lo, hi = RW.wilson(0, 100)
    assert lo == pytest.approx(0.0, abs=1e-12) and hi == pytest.approx(0.0370, abs=1e-3)
    lo, hi = RW.wilson(50, 100)
    assert lo == pytest.approx(1 - hi)


def test_block_lengths_round_up_to_fives_with_a_floor_of_twenty():
    assert RB.block_lengths(45.0) == (45, 25, 70)
    assert RB.block_lengths(12.0) == (20, 10, 30)
    assert RB.block_lengths(46.0) == (50, 25, 75)


def test_seal_drops_signal_dates_on_or_after_the_seal():
    recs = [{"date": "2026-09-22"}, {"date": RB.SEAL_START}, {"date": "2026-10-01"}]
    kept, dropped = RB.seal(recs)
    assert [r["date"] for r in kept] == ["2026-09-22"] and dropped == 2


# ── the ledger ──────────────────────────────────────────────────────────────

def test_a_position_marks_books_and_releases():
    tab = make_table(5, [dict(t=0, res=100.0, marks=[10.0, 20.0, 30.0])])
    r = RW.walk(tab, ident(tab), cfg(), record=True)
    assert list(r.equity) == [1010.0, 1020.0, 1030.0, 1030.0, 1030.0]
    assert list(r.reserved) == [100.0, 100.0, 100.0, 0.0, 0.0]
    assert r.dollars[0] == 30.0 and r.taken[0] == 1
    assert r.ledger_err < 1e-9 and r.neg_cash == 0


def test_cash_refuses_and_a_release_frees_it_on_the_next_session_only():
    picks = [dict(t=0, res=100.0, marks=[0.0, 0.0]),     # exits at close of 1
             dict(t=0, res=100.0),                        # no cash
             dict(t=1, res=100.0),                        # still no cash
             dict(t=2, res=100.0)]                        # released, taken
    tab = make_table(4, picks, capital=150.0)
    r = RW.walk(tab, ident(tab), cfg(), record=True)
    assert taken_ids(r) == [0, 3]


def test_day_cap_unsizable_and_f2():
    picks = [dict(t=0, uns=True), dict(t=0), dict(t=0, over=True), dict(t=0), dict(t=0)]
    tab = make_table(1, picks, capital=10_000.0)
    f1 = RW.walk(tab, ident(tab), cfg(), record=True)
    assert taken_ids(f1) == [1, 2]                        # the unsizable pick burns a slot
    f2 = RW.walk(tab, ident(tab), cfg(take_floor=False), record=True)
    assert taken_ids(f2) == [1, 3]                        # refused, slot not burned


def test_per_position_and_net_caps():
    picks = [dict(t=0, dn=900.0), dict(t=0, dn=900.0), dict(t=0, pp=True)]
    tab = make_table(1, picks)
    r = RW.walk(tab, ident(tab), cfg(net_cap=1.5), record=True)
    assert taken_ids(r) == [0]


def test_ruin_is_marked_equity_at_or_below_half():
    tab = make_table(4, [dict(t=0, res=700.0, marks=[-100.0, -500.0, -600.0])])
    r = RW.walk(tab, ident(tab), cfg())
    assert r.ruined[0] and r.ruin_t[0] == 1
    assert r.maxdd[0] == pytest.approx(0.6) and r.rmaxdd[0] == pytest.approx(0.6)


# ── guardrails ──────────────────────────────────────────────────────────────

def test_gm_refuses_reserve_above_m_of_the_previous_close():
    picks = [dict(t=0, res=400.0, marks=[0.0, 0.0, 0.0]),
             dict(t=1, res=200.0), dict(t=1, res=50.0)]
    tab = make_table(3, picks)
    r = RW.walk(tab, ident(tab), cfg(guard="M", m=0.5), record=True)
    assert taken_ids(r) == [0, 2] and r.fired[0]
    assert taken_ids(RW.walk(tab, ident(tab), cfg(), record=True)) == [0, 1, 2]


def test_gk_stops_entries_after_the_close_that_trips_it():
    picks = [dict(t=0, res=400.0, marks=[0.0, -300.0, -300.0, -300.0]),
             dict(t=1), dict(t=2), dict(t=3)]
    tab = make_table(4, picks)
    r = RW.walk(tab, ident(tab), cfg(guard="K", k=0.25), record=True)
    assert taken_ids(r) == [0, 1] and r.fired[0]


def test_gc_pauses_b_sessions_after_a_shock_day():
    picks = [dict(t=0, res=400.0, marks=[0.0, -60.0, -60.0, -60.0, -60.0, -60.0]),
             dict(t=2), dict(t=3), dict(t=4)]
    tab = make_table(6, picks)
    r = RW.walk(tab, ident(tab), cfg(guard="C", c=0.05, b=2), record=True)
    assert taken_ids(r) == [0, 3] and r.fired[0]


# ── overlays ────────────────────────────────────────────────────────────────

def test_o2_marks_and_books_the_full_reserve_from_the_shock_on():
    tab = make_table(5, [dict(t=0, res=100.0, marks=[5.0, 5.0, 5.0, 5.0])])
    r = RW.walk(tab, ident(tab), cfg(), overlay="O2", shock_t=np.array([1]),
                record=True)
    assert list(r.equity[:4]) == [1005.0, 900.0, 900.0, 900.0]
    assert r.dollars[0] == -100.0
    assert r.o2_loss[0] == pytest.approx(105.0 / 1005.0)


def test_o1_hits_long_delta_only_and_floors_at_the_reserve():
    picks = [dict(t=0, res=100.0, dn=500.0, marks=[0.0, 0.0, 0.0]),
             dict(t=0, res=100.0, dn=-500.0, marks=[0.0, 0.0, 0.0]),
             dict(t=0, res=30.0, dn=5000.0, marks=[0.0, 0.0, 0.0])]
    tab = make_table(4, picks)
    r = RW.walk(tab, ident(tab), cfg(), overlay="O1", g=0.10, shock_t=np.array([1]),
                record=True)
    # long: min(100, 50) = 50; short: nothing; the third: min(30, 500) = 30
    assert r.equity[1] == pytest.approx(1000.0 - 80.0)
    assert r.dollars[0] == pytest.approx(-80.0)


def _random_table(seed, n=60, C=90):
    rng = np.random.default_rng(seed)
    picks = []
    for _ in range(C):
        k = int(rng.integers(0, 12))
        res = float(rng.uniform(50, 400))
        walk = np.cumsum(rng.normal(0, res / 6, k + 1))
        picks.append(dict(t=int(rng.integers(0, n)), res=res,
                          dn=float(rng.normal(0, 2000)),
                          marks=list(np.maximum(walk, -res)),
                          over=bool(rng.random() < 0.2), uns=bool(rng.random() < 0.05)))
    return make_table(n, picks, capital=2500.0)


@pytest.mark.parametrize("guard", RW.GUARDS)
def test_overlay_order_holds_path_by_path_up_to_the_shock(guard):
    tab = _random_table(3)
    c = cfg(guard=guard, net_cap=1.5, m=0.5, k=0.15, c=0.03, b=3)
    paths = RW.resample_paths(tab, 8, 400, 7, (0, 0, 8))
    r0 = RW.walk(tab, paths, c)
    r1 = RW.walk(tab, paths, c, overlay="O1", shock_t=r0.peak_resv_t)
    r2 = RW.walk(tab, paths, c, overlay="O2", shock_t=r0.peak_resv_t)
    order = RW.overlay_order(r0, r1, r2, r0.peak_resv_t)
    assert order["paths"] > 0 and order["eq_bad"] == 0 and order["ruin_bad"] == 0
    for r in (r0, r1, r2):
        assert r.ledger_err < 1e-6 and r.neg_cash == 0


@pytest.mark.parametrize("guard", RW.GUARDS)
def test_truncation_never_changes_a_decision_up_to_the_cut(guard):
    tab = _random_table(4)
    c = cfg(guard=guard, net_cap=1.5, m=0.5, k=0.15, c=0.03, b=3)
    base = RW.walk(tab, ident(tab), c, record=True).decisions
    for cut in (5, 17, 30, 44):
        pert = RW.walk(RB.perturbed(tab, cut), ident(tab), c, record=True).decisions
        assert [d for d in base if d[1] <= cut] == [d for d in pert if d[1] <= cut]
    # and the scramble does reach later decisions, or the check proves nothing
    assert any(RW.walk(RB.perturbed(tab, cut), ident(tab), c, record=True).decisions != base
               for cut in (5, 17, 30))


def test_summarize_counts_ruin_and_unfired_kill():
    tab = make_table(4, [dict(t=0, res=700.0, marks=[-100.0, -500.0, -600.0])])
    r = RW.walk(tab, np.tile(np.arange(4), (3, 1)), cfg(guard="K", k=0.9))
    s = RW.summarize(r, "K")
    assert s["n_ruin"] == 3 and s["p_ruin"] == 1.0 and s["ruin_unfired"] == 3


# ── R2 on a hand-built book ─────────────────────────────────────────────────

def _rec(signal: date, marks, entry=2.0, mlpc=150.0, delta=0.3, tier="A", dte=20):
    exp = signal + timedelta(days=dte)
    row = {
        "signal_date": signal.isoformat(), "ticker": "TK" + chr(65 + signal.day % 26),
        "structure": "long_call", "contracts": "1", "dte_entry": str(dte),
        "entry_option_price": str(entry), "entry_underlying": "100",
        "legs": "TK" + chr(65 + signal.day % 26) + f":{exp.isoformat()}:100:C +1",
        "daily_price_csv": ",".join(str(m) for m in marks),
        "daily_pnl_csv": ",".join(f"{(m - entry) * 100:.2f}" for m in marks),
    }
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": mlpc, "delta": delta,
            "date": signal.isoformat(), "ticker": "TK" + chr(65 + signal.day % 26), "tier": tier}


def _grid_len(signal, dte=20):
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _settings():
    return AS.Settings(
        capital=600.0, risk_pct=0.25, max_per_day=2, per_pos_cap=10.0, net_cap=10.0,
        per_pos_grid=(0.25,), net_grid=(1.5,), capital_ladder=(600.0,),
        capital_ladder_posthoc=(), hedge_risk_fraction=0.5, episode_max_gap=5,
        episode_min_dates=2, attrition_floor=0.6, maxdd_fraction=0.25,
        ratio_tolerance=0.15, compound_enabled=False, mark_interval="month",
        budget_ceiling=None, source=Path("t.yml"), source_text="account: {}\n")


def test_identity_walk_reproduces_simulate_on_a_hand_built_book():
    rng = np.random.default_rng(5)
    recs = []
    for i, d0 in enumerate([date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 6),
                            date(2025, 3, 10), date(2025, 3, 11)]):
        for j in range(3):
            n = _grid_len(d0)
            marks = list(np.round(np.maximum(0.05, 2.0 + np.cumsum(rng.normal(0, 0.3, n))), 2))
            recs.append(_rec(d0, marks, mlpc=float(120 + 40 * j), tier="A" if j else "B"))
    st = _settings()
    cache = AS.new_cache()
    b = RB.build(recs, st, cache, charge_cost=False)
    for net, f1 in ((10.0, True), (6.0, True), (10.0, False)):
        wc = RW.WalkCfg(label="x", net_cap=net, take_floor=f1)
        mine = RB.identity(b, wc)
        sim = AS.simulate(b.day_lists, RB.as_cfg(st, wc), cache=cache)
        assert RB.signature(RB.positions(b, mine)) == RB.signature(sim.signal_pos)
        _, vals = AS.equity_curve(sim.signal_pos)
        assert mine.rmaxdd[0] == pytest.approx(-AS.max_drawdown(vals) / st.capital)
        assert len(sim.signal_pos) > 0
