"""spy_dip_forward: flags, entry clock, excess return, windows, episodes, floors,
bootstrap, Holm, verdict tables, PBO and gates, on SYNTHETIC series only. No
figure here comes from real market data."""
from __future__ import annotations

import itertools
import math
from datetime import date, timedelta

import numpy as np
import pytest

from lib.mech_regime import compute_mech_table
from scripts.backtest_study.f1_selection.regime.tail_breach import block_indices, ratio_problems
from scripts.backtest_study.f1_selection.signal import spy_dip_forward as sd


def weekdays(start: str, end: str, skip: tuple[str, ...] = ()) -> list[str]:
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def walk(n: int, seed: int = 1, vol: float = 0.012) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in 100 * np.cumprod(1 + rng.normal(0.0003, vol, n))]


def cal_of(dates, closes, adj=None):
    adj = closes if adj is None else adj
    return [(d, float(c), float(a)) for d, c, a in zip(dates, closes, adj)]


def data_of(dates, closes, adj=None, irx=None):
    irx = {d: 2.0 for d in dates} if irx is None else irx
    return sd.build_data(cal_of(dates, closes, adj), irx)


def res(point, lo, hi, p=0.01):
    return sd.Result(point, lo, hi, p, 0.0, 1000)


def make_rows(f, ep=None, reg=None, x=None, mae=None):
    f = np.asarray(f, dtype=float)
    n = len(f)
    return sd.Rows("HOLDOUT", "SMA50", 21, np.arange(n), f,
                   np.full(n, np.nan) if reg is None else np.asarray(reg, dtype=float),
                   np.zeros(n) if x is None else np.asarray(x, dtype=float),
                   np.zeros(n) if mae is None else np.asarray(mae, dtype=float),
                   np.zeros(n), np.full(n, -1) if ep is None else np.asarray(ep, dtype=int),
                   np.zeros(n, dtype=int), {})


# ── the flag ────────────────────────────────────────────────────────────────

def test_sma50_is_a_strict_close_below_the_50_row_mean_of_unadjusted_closes():
    dates = weekdays("2001-01-01", "2001-12-31")
    closes = [100.0] * 60 + [99.0] + walk(len(dates) - 61, seed=3)
    # The adjusted series trends hard the other way: the flag must not read it.
    adj = [c * (1 + 0.01 * i) for i, c in enumerate(closes)]
    d = data_of(dates, closes, adj)
    flag = d.flags["SMA50"]
    assert all(v is None for v in flag[:49])
    assert flag[59] is False                    # close == SMA: not strictly below
    assert flag[60] is True                     # 99 < mean of 49 x 100 and 99
    for i in range(49, len(closes)):
        assert flag[i] == (closes[i] < float(np.mean(closes[i - 49:i + 1])))


def test_own_helper_at_50_reproduces_compute_mech_table_on_every_session(tmp_path):
    dates = weekdays("2003-01-01", "2004-12-31")
    closes = walk(len(dates), seed=5)
    p = tmp_path / "t.csv"
    p.write_text("date,spy_close,vix_close\n" + "".join(f"{d},{c!r},\n" for d, c in zip(dates, closes)))
    shipped = [r["spy_below_sma"] for r in compute_mech_table(p)]
    assert shipped == [sd.below_sma_at(closes, i, 50) for i in range(len(closes))]
    assert sd.mech_flags(dates, closes) == shipped


def test_grid_definitions_as_written():
    c = [10.0] * 19 + [9.5]                     # 9.5 <= 0.95 x 10
    assert sd.pb5_at(c, 19) is True
    assert sd.pb5_at(c[:-1] + [9.51], 19) is False
    assert sd.pb5_at(c, 18) is None
    assert sd.dn3_at([4.0, 3.0, 2.0, 1.0], 3) is True
    assert sd.dn3_at([4.0, 3.0, 3.0, 1.0], 3) is False    # strict
    assert sd.dn3_at([4.0, 3.0, 2.0], 2) is None
    flat = [5.0] * 200
    assert sd.above200_at(flat, 199) is True              # tie goes to above
    assert sd.above200_at(flat[:-1] + [4.99], 199) is False
    assert sd.above200_at(flat, 198) is None


def test_changing_any_close_after_d_leaves_every_flag_at_d_unchanged():
    dates = weekdays("2005-01-01", "2006-06-30")
    closes = walk(len(dates), seed=7)
    base = sd.all_flags(dates, closes)
    rng = np.random.default_rng(11)
    for D in (60, 200, 250, len(dates) - 30):
        moved = closes[:D + 1] + [c * float(rng.uniform(0.5, 1.5)) for c in closes[D + 1:]]
        got = sd.all_flags(dates, moved)
        for k in base:
            assert got[k][:D + 1] == base[k][:D + 1], k
    assert sd.gx_check(dates, closes, base, n=12) == 12


def test_no_signal_reads_a_return():
    dates = weekdays("2005-01-01", "2006-03-31")
    closes = walk(len(dates), seed=8)
    a = data_of(dates, closes, closes)
    b = data_of(dates, closes, [c * (1 + 0.003 * i) for i, c in enumerate(closes)])
    assert a.flags == b.flags
    assert np.array_equal(a.ep, b.ep)


def test_gx_refuses_a_flag_that_reads_a_later_close():
    dates = weekdays("2005-01-01", "2005-12-31")
    closes = walk(len(dates), seed=9)
    flags = sd.all_flags(dates, closes)

    def peeking(dts, cl):                       # flag D on the NEXT close
        return [None] * 49 + [(cl[i + 1] < cl[i]) if i + 1 < len(cl) else None
                              for i in range(49, len(cl))]
    flags["SMA50"] = peeking(dates, closes)
    with pytest.raises(sd.LookaheadError):
        sd.gx_check(dates, closes, flags, n=20, mech=peeking)


# ── entry clock and excess return ──────────────────────────────────────────

def test_entry_is_at_the_close_after_d():
    n, h, i = 120, 5, 40
    adj = np.array(walk(n, seed=2))
    y = np.zeros(n)
    X, _ = sd.outcomes(adj, y, h, cost=0.0)
    assert X[i] == pytest.approx(adj[i + 1 + h] / adj[i + 1] - 1.0, abs=1e-15)
    adj2 = adj.copy()
    adj2[i] *= 1.3                              # D's own close is not the entry price
    assert sd.outcomes(adj2, y, h, cost=0.0)[0][i] == X[i]
    adj3 = adj.copy()
    adj3[i + 1] *= 1.3
    assert sd.outcomes(adj3, y, h, cost=0.0)[0][i] != X[i]


def test_forward_excess_return_formula_with_tbill_and_cost():
    n, h, i = 60, 5, 10
    adj = np.array(walk(n, seed=4))
    y = np.linspace(-0.3, 6.0, n)               # a negative yield is used as printed
    X, M = sd.outcomes(adj, y, h)
    e = i + 1
    tb = np.prod([1 + y[k - 1] / 100 / 252 for k in range(e + 1, e + h + 1)])
    assert X[i] == pytest.approx(adj[e + h] / adj[e] - tb - 0.0004, abs=1e-14)
    assert M[i] == pytest.approx(min(adj[k] / adj[e] - 1 for k in range(e + 1, e + h + 1)), abs=1e-15)
    assert all(math.isnan(v) for v in X[n - h - 1:])     # open: the window runs past the data


def test_mae_can_be_positive():
    adj = np.array([100.0, 100.0] + [100.0 + k for k in range(1, 30)])
    _, M = sd.outcomes(adj, np.zeros(len(adj)), 5)
    assert M[0] > 0


# ── windows ─────────────────────────────────────────────────────────────────

def test_window_membership_needs_d_entry_and_window_end_inside():
    dates = weekdays("2009-01-01", "2010-12-31")
    closes = walk(len(dates), seed=12, vol=0.02)
    d = data_of(dates, closes)
    for w, b in (("DISCOVERY", "2009-12-31"), ("HOLDOUT", "2025-12-31")):
        r = sd.build_rows(d, w, 21)
        for i in r.i:
            assert d.dates[i + 1] <= b and d.dates[i + 1 + 21] <= b
    disc = sd.build_rows(d, "DISCOVERY", 21)
    crossing = [i for i, v in enumerate(d.flags["SMA50"]) if v is not None
                and d.dates[i] <= "2009-12-31" < d.dates[i + 1 + 21]]
    assert disc.census["gap"] == len(crossing) > 0
    assert not set(crossing) & set(disc.i.tolist())
    hold = sd.build_rows(d, "HOLDOUT", 21)
    assert d.dates[hold.i[0]] >= "2010-01-01"
    assert hold.census["open"] == 21 and hold.census["no_entry"] == 1


def test_2026_is_never_graded():
    dates = weekdays("2024-01-01", "2026-06-30")
    closes = walk(len(dates), seed=13)
    d1 = data_of(dates, closes)
    adj2 = [c * (3.0 if dt >= "2026-01-01" else 1.0) for dt, c in zip(dates, closes)]
    d2 = data_of(dates, closes, adj2)
    h1, h2 = sd.build_rows(d1, "HOLDOUT"), sd.build_rows(d2, "HOLDOUT")
    assert np.array_equal(h1.x, h2.x) and np.array_equal(h1.mae, h2.mae)
    assert all(d1.dates[i + 1 + 21] <= "2025-12-31" for i in h1.i)
    M1, k1, _ = sd.pbo_matrix(d1)
    M2, _, _ = sd.pbo_matrix(d2)
    assert np.array_equal(M1, M2)
    assert all(d1.dates[i + 1 + 63] <= "2025-12-31" for i in k1)
    assert len(k1) % 16 == 0
    for w in ("DISCOVERY", "HOLDOUT", "PRE-BOOK"):
        assert not any(d1.dates[i] >= "2026-01-01" for i in sd.build_rows(d1, w).i)


def test_forward_window_starts_after_the_registration_date():
    w = sd.windows("2026-11-27")
    assert w["FORWARD"][0] == "2026-11-28" and w["2026"] == ("2026-01-01", "2026-11-27")


# ── episodes and floors ─────────────────────────────────────────────────────

def test_episode_definition():
    T, F = True, False
    ep, ordn = sd.episodes([None, T, T, F, F, F, F, F, T, F, F, F, F, F, F, T, T])
    # Five non-dip sessions continue the episode; six end it.
    assert ep.tolist() == [-1, 0, 0, -1, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, 1, 1]
    assert ordn.tolist() == [0, 1, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 1, 2]


def test_power_floors():
    def rows(n_dip, n_non, n_ep, big=None):
        ep = [k % n_ep for k in range(n_dip)]
        if big is not None:
            ep = [0] * big + [1 + k % (n_ep - 1) for k in range(n_dip - big)]
        return make_rows([1] * n_dip + [0] * n_non, ep=ep + [-1] * n_non)
    assert sd.gn(rows(250, 250, 20)).ok
    assert not sd.gn(rows(249, 250, 20)).ok
    assert not sd.gn(rows(250, 249, 20)).ok
    assert not sd.gn(rows(250, 250, 19)).ok
    assert sd.gn(rows(300, 300, 20, big=100)).ok          # exactly a third
    assert not sd.gn(rows(300, 300, 20, big=101)).ok

    def zrows(na, nb, ea, eb):
        f = [1] * (na + nb)
        reg = [1] * na + [0] * nb
        ep = [k % ea for k in range(na)] + [100 + k % eb for k in range(nb)]
        return make_rows(f, ep=ep, reg=reg)
    assert sd.gn_z(zrows(100, 100, 10, 10)).ok
    assert not sd.gn_z(zrows(99, 100, 10, 10)).ok
    assert not sd.gn_z(zrows(100, 100, 10, 9)).ok


# ── bootstrap ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,L,draws", [(10, 3, 7), (100, 63, 20), (37, 50, 5), (500, 31, 9)])
def test_draws_reproduce_block_indices(n, L, draws):
    starts, Lc = sd.boot_starts(n, L, draws, 99)
    assert np.array_equal(sd.expand(starts, n, Lc), block_indices(n, L, draws, 99))
    assert sd.draws_match_block_indices(n, L, draws, 99)


def test_block_bootstrap_resamples_whole_rows_with_flags_and_returns_together():
    rng = np.random.default_rng(3)
    n, L, draws = 300, 63, 200
    f = (rng.random(n) < 0.3).astype(float)
    reg = (rng.random(n) < 0.5).astype(float)
    x, mae = rng.normal(0, 0.03, n), -rng.random(n) * 0.1
    r = make_rows(f, reg=reg, x=x, mae=mae)
    got = sd.measure(r, L=L, draws=draws, seed=5)
    idx = block_indices(n, L, draws, 5)
    want_p = [sd.arm_p(x[j], f[j]) for j in idx]
    want_t = [sd.arm_t(mae[j], f[j]) for j in idx]
    want_z = [sd.arm_z(x[j], f[j], reg[j]) for j in idx]
    starts, Lc = sd.boot_starts(n, L, draws, 5)
    np.testing.assert_allclose(sd.boot_mean_diff(x, f == 1, f == 0, starts, n, Lc), want_p, atol=1e-12)
    np.testing.assert_allclose(sd.boot_q_diff(mae, f, starts, n, Lc), want_t, atol=1e-12)
    up, dn = (f == 1) & (reg == 1), (f == 1) & (reg == 0)
    np.testing.assert_allclose(sd.boot_mean_diff(x, up, dn, starts, n, Lc), want_z, atol=1e-12)
    assert got["P"].point == pytest.approx(sd.arm_p(x, f))
    # A return equal to its own flag: every draw keeps them paired, so P is 1.
    paired = make_rows(f, x=f)
    p = sd.boot_mean_diff(paired.x, f == 1, f == 0, starts, n, Lc)
    assert np.allclose(p[np.isfinite(p)], 1.0)
    # Dip and non-dip counts vary across draws: they are not resampled apart.
    counts = [int(f[j].sum()) for j in idx]
    assert len(set(counts)) > 1


def test_q_rows_matches_numpy_percentile():
    rng = np.random.default_rng(0)
    V = rng.normal(size=(50, 40))
    V[rng.random(V.shape) < 0.3] = np.nan
    V[0] = np.nan
    got = sd.q_rows(V)
    assert math.isnan(got[0])
    for k in range(1, 50):
        fin = V[k][np.isfinite(V[k])]
        assert got[k] == pytest.approx(np.percentile(fin, 10), abs=1e-14)


def test_ci_not_finite_when_more_than_one_percent_of_draws_are_nan():
    d = np.linspace(-1, 1, 1000)
    assert sd.summarize(0.1, d, 10).finite
    d2 = d.copy()
    d2[:11] = np.nan
    assert not sd.summarize(0.1, d2, 10).finite
    d3 = d.copy()
    d3[:10] = np.nan
    assert sd.summarize(0.1, d3, 10).finite


def test_p_value_convention():
    d = np.array([-1.0, 1.0, 2.0, 3.0])
    assert sd.summarize(1.0, d, 4).p == pytest.approx(0.5)
    assert sd.summarize(1.0, np.ones(10), 10).p == 0.0


# ── Holm ────────────────────────────────────────────────────────────────────

def test_holm_family_of_three():
    r = {"P": res(1, 0.1, 2, p=0.01), "T": res(1, 0.1, 2, p=0.02), "Z": res(1, 0.1, 2, p=0.04)}
    adj = sd.holm3(r, {"P": True, "T": True, "Z": True})
    assert adj == pytest.approx({"P": 0.03, "T": 0.04, "Z": 0.04})
    adj2 = sd.holm3(r, {"P": True, "T": False, "Z": True})
    assert adj2["T"] == 1.0 and adj2["P"] == pytest.approx(0.03)   # m stays 3


# ── verdict tables ──────────────────────────────────────────────────────────

CIS = [(0.01, 0.02), (-0.02, -0.01), (-0.01, 0.01), (0.0, 0.01), (float("nan"), float("nan"))]


def test_p_table_every_branch_gives_one_token():
    seen = set()
    for (lo, hi), padj, disc, pre, pbo, pw in itertools.product(
            CIS, (0.01, 0.2), (-1.0, 1.0, float("nan")), (-1.0, 1.0, float("nan")),
            (None, 0.3, 0.5, 0.6), (True, False)):
        w, notes = sd.p_word(res(0.0, lo, hi), pw, padj, disc, pre, pbo)
        assert w in sd.P_WORDS
        seen.add(w)
        finite = math.isfinite(lo)
        if not pw or not finite:
            assert w == sd.UNDERPOWERED
        elif hi < 0 and padj < 0.05:
            assert w == sd.CONTRARY
        elif lo > 0 and padj < 0.05 and disc > 0 and pre > 0:
            assert w == (sd.SUPPORTED if pbo is not None and pbo <= 0.5 else sd.PBO_VETO_W)
        else:
            assert w == sd.NULL
        if w != sd.NULL:
            assert notes == []
    assert seen == sd.P_WORDS


def test_p_null_notes_name_the_disagreeing_sign():
    up = res(0.02, 0.01, 0.03)
    assert sd.p_word(up, True, 0.01, -0.001, 0.01, 0.2) == (sd.NULL, ["holdout gain, discovery sign disagrees"])
    assert sd.p_word(up, True, 0.01, 0.01, -0.001, 0.2) == (sd.NULL, ["holdout gain, pre-book sign disagrees"])
    assert sd.p_word(up, True, 0.01, 0.01, float("nan"), 0.2)[0] == sd.NULL   # pre-book must be finite
    assert sd.p_word(up, True, 0.2, -1, -1, 0.2) == (sd.NULL, [])           # no holdout gain, no note
    assert sd.p_word(res(0, 0.0, 0.03), True, 0.01, 1, 1, 0.2)[0] == sd.NULL  # touching zero


def test_non_computable_pbo_vetoes():
    M = np.zeros((32, 12, 2))
    M[0, 0, 0] = np.nan
    r, why = sd.compute_pbo(M)
    assert r is None and why
    r2, _ = sd.compute_pbo(np.zeros((30, 12, 2)))           # 16 does not divide 30
    assert r2 is None
    assert sd.p_word(res(0.02, 0.01, 0.03), True, 0.01, 1, 1, None)[0] == sd.PBO_VETO_W


@pytest.mark.parametrize("fn,words,good,bad", [
    (sd.t_word, sd.T_WORDS, sd.SHALLOWER, sd.DEEPER),
    (sd.z_word, sd.Z_WORDS, sd.ABOVE_BETTER, sd.BELOW_BETTER)])
def test_t_and_z_tables(fn, words, good, bad):
    for (lo, hi), padj, pw in itertools.product(CIS, (0.01, 0.2), (True, False)):
        w = fn(res(0.0, lo, hi), pw, padj)
        assert w in words
        if not pw or not math.isfinite(lo):
            assert w == sd.UNDERPOWERED
        elif hi < 0 and padj < 0.05:
            assert w == bad
        elif lo > 0 and padj < 0.05:
            assert w == good
        else:
            assert w == sd.NULL
        wf = fn(res(0.0, lo, hi), pw, padj, forward=True)
        assert wf == (sd.STILL_OPEN if w == sd.UNDERPOWERED else w)


def test_forward_p_table_has_no_pbo_or_sign_clause():
    allowed = {sd.SUPPORTED, sd.CONTRARY, sd.NULL, sd.STILL_OPEN}
    for (lo, hi), padj, pw in itertools.product(CIS, (0.01, 0.2), (True, False)):
        w = sd.p_forward_word(res(0.0, lo, hi), pw, padj)
        assert w in allowed
        if not pw or not math.isfinite(lo):
            assert w == sd.STILL_OPEN
        elif lo > 0 and padj < 0.05:
            assert w == sd.SUPPORTED
        elif hi < 0 and padj < 0.05:
            assert w == sd.CONTRARY
        else:
            assert w == sd.NULL


# ── PBO metric ──────────────────────────────────────────────────────────────

def test_pbo_metric_is_delta_over_h():
    sub = np.zeros((4, 12, 2))
    sub[:, :, 0] = np.array([0.04, 0.02, 0.01, 0.01])[:, None]
    sub[:, :, 1] = np.array([1, 1, 0, 0])[:, None]
    got = sd.pbo_metric(sub)
    hs = np.array([h for _, h in sd.CELLS], dtype=float)
    np.testing.assert_allclose(got, (0.03 - 0.01) / hs)
    sub[:, 3, 1] = 1                                       # no non-dip row in cell 3
    assert math.isnan(sd.pbo_metric(sub)[3])


# ── gates ───────────────────────────────────────────────────────────────────

def test_ge_refuses_bad_inputs():
    good = [(d, 1.0, 1.0) for d in ["1993-01-29"] + weekdays("2025-12-01", "2026-04-30")]
    assert sd.ge_problems(good) == []
    assert sd.ge_problems([])
    assert sd.ge_problems([("1993-02-02", 1.0, 1.0)] + good[1:])
    few = [(d, 1.0, 1.0) for d in ["1993-01-29"] + weekdays("2025-12-01", "2026-03-31")]
    n_after = sum(1 for r in few if r[0] > "2025-12-31")
    assert (n_after >= 64) == (sd.ge_problems(few) == [])
    assert sd.ge_problems(few[:-(n_after - 63)])


def test_gb_refuses_a_split_and_a_jump():
    rows = [("2000-01-03", 100.0, 98.0), ("2000-01-04", 50.0, 49.0), ("2000-01-05", 51.0, 49.98)]
    assert ratio_problems([("2000-01-03", 100.0, 98.0), ("2000-01-04", 50.0, 98.0)])
    assert sd.gb_return_problems(rows)
    assert sd.gb_return_problems(rows[1:]) == []


def test_gm_allows_single_holidays_and_the_listed_closures_only():
    assert sd.gm_calendar_problems(weekdays("2015-01-01", "2015-12-31", skip=("2015-07-03",))) == []
    assert sd.gm_calendar_problems(weekdays("2015-01-01", "2015-12-31", skip=("2015-07-02", "2015-07-03")))
    for a, b in sd.GM_EXCEPTIONS:
        skip = tuple(weekdays(a, b))
        assert sd.gm_calendar_problems(weekdays(a[:4] + "-01-01", a[:4] + "-12-31", skip=skip)) == []
    assert sd.gm_calendar_problems(weekdays("2001-09-01", "2001-09-30",
                                            skip=tuple(weekdays("2001-09-10", "2001-09-14"))))


def test_gm_refuses_a_base_rate_session_missing_from_the_cache(tmp_path):
    dates = weekdays("2010-01-01", "2010-03-31")
    p = tmp_path / "base.csv"
    p.write_text("date,spy_close,vix_close\n" + "".join(f"{d},100,15\n" for d in dates))
    assert sd.gm_base_problems(dates, p) == []
    assert sd.gm_base_problems([d for d in dates if d != "2010-02-10"], p)
    assert sd.gm_base_problems(dates, tmp_path / "missing.csv")


def test_gs_refuses_outside_the_band_and_counts_inside():
    closes = [100.0] * 49 + [99.99, 90.0]
    dates = weekdays("2010-01-01", "2010-12-31")[:51]
    flag = [sd.below_sma_at(closes, i, 50) for i in range(51)]
    table = {dates[49]: not flag[49], dates[50]: flag[50]}
    g = sd.gs_compare(dates, closes, flag, table)
    assert (g.common, g.band, g.hard) == (2, 1, [])
    g2 = sd.gs_compare(dates, closes, flag, {dates[50]: not flag[50]})
    assert len(g2.hard) == 1


def test_gi_refuses_a_long_carry_disagreeing_copies_and_no_coverage():
    dates = weekdays("2010-01-01", "2010-06-30")
    closes = walk(len(dates), seed=1)
    irx = {d: 1.0 for d in dates}
    d = data_of(dates, closes, irx=irx)
    assert sd.gi_problems(d, 1, d.n - 1, irx, dict(irx)).problems == []
    gap = {k: v for j, (k, v) in enumerate(irx.items()) if not 50 <= j < 56}
    dg = data_of(dates, closes, irx=gap)
    assert sd.gi_problems(dg, 1, dg.n - 1, gap, None).problems
    ok5 = {k: v for j, (k, v) in enumerate(irx.items()) if not 50 <= j < 55}
    d5 = data_of(dates, closes, irx=ok5)
    assert sd.gi_problems(d5, 1, d5.n - 1, ok5, None).problems == []
    other = dict(irx)
    other[dates[10]] = 1.02
    assert sd.gi_problems(d, 1, d.n - 1, irx, other).problems
    late = {k: v for k, v in irx.items() if k > dates[5]}
    dl = data_of(dates, closes, irx=late)
    assert sd.gi_problems(dl, 1, dl.n - 1, late, None).problems


def test_negative_and_zero_irx_quotes_are_kept(tmp_path):
    p = tmp_path / "IRX.csv"
    p.write_text("date,close,adj_close\n2020-03-23,-0.05,-0.05\n2020-03-24,0.0,0.0\n"
                 "2020-03-25,0.01,0.01\n2020-03-26,,\n")
    irx = sd.read_irx(p)
    assert irx == {"2020-03-23": -0.05, "2020-03-24": 0.0, "2020-03-25": 0.01}
    y, own = sd.tbill(["2020-03-23", "2020-03-24", "2020-03-25", "2020-03-26"], irx)
    assert y.tolist() == [-0.05, 0.0, 0.01, 0.01] and own.tolist() == [True, True, True, False]
    g = sd.growth(y)
    assert g[1] < 1.0 and g[2] == 1.0


def test_missing_cache_refuses_with_exit_3(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sd, "SPY_CSV", tmp_path / "SPY.csv")
    assert sd.main([]) == 3
    out = capsys.readouterr().out
    assert "REFUSED (GE:" in out and "--refresh" in out and "REFUSED (GE) <<<" in out


def test_any_other_era_refuses_with_exit_2(monkeypatch):
    monkeypatch.setattr(sd.era_mod, "requested_era", lambda: "v3")
    assert sd.main([]) == 2
    assert 2 in sd.DESIGNED_REFUSAL_EXIT_CODES and 3 in sd.DESIGNED_REFUSAL_EXIT_CODES


# ── each row pairs a day's flag with ITS OWN forward return ────────────────

def _pairing_data():
    dates = weekdays("2009-01-01", "2010-12-31")
    closes = walk(len(dates), seed=12, vol=0.02)
    irx = {dt: 1.0 + 0.01 * k for k, dt in enumerate(dates)}
    return data_of(dates, closes, irx=irx), closes


def test_each_row_pairs_its_flag_and_return_with_its_own_signal_session():
    d, _ = _pairing_data()
    h = 21
    flags = d.flags[sd.PRIMARY]
    assert len({round(v, 12) for v in d.X[h][~np.isnan(d.X[h])]}) > 100   # a shift would show
    for w in ("DISCOVERY", "HOLDOUT"):
        r = sd.build_rows(d, w, h)
        assert r.n > 50
        for k in range(r.n):
            i = int(r.i[k])
            assert r.f[k] == (1.0 if flags[i] else 0.0)
            assert r.x[k] == d.X[h][i]
        assert 0 < r.f.sum() < r.n


def test_arm_p_equals_hand_computed_dip_mean_minus_non_dip_mean():
    d, closes = _pairing_data()
    h = 21
    n = len(closes)
    dates = d.dates
    c = np.array(closes)
    irx = np.array([1.0 + 0.01 * k for k in range(n)])
    flags = d.flags[sd.PRIMARY]
    dip, non = [], []
    for i in range(n):
        if flags[i] is None or not ("2010-01-01" <= dates[i] <= "2025-12-31"):
            continue
        e = i + 1
        if e + h >= n or not (dates[e] <= "2025-12-31" and dates[e + h] <= "2025-12-31"):
            continue
        # enter at the close of D+1, exit h sessions later; T-bill pays at the yield known before each day
        bill = 1.0
        for k in range(e + 1, e + h + 1):
            bill *= 1.0 + irx[k - 1] / 100.0 / 252
        x = c[e + h] / c[e] - bill - 0.0004
        (dip if flags[i] else non).append(x)
    assert dip and non
    expected = float(np.mean(dip)) - float(np.mean(non))
    r = sd.build_rows(d, "HOLDOUT", h)
    assert sd.arm_p(r.x, r.f) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("n,text", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
                                    (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"),
                                    (101, "101st"), (111, "111th")])
def test_ordinal_suffix(n, text):
    assert sd.ordinal(n) == text
