"""vol_expansion_long_vol — synthetic labels and quotes only; no real-quote figure."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import daily_vol_structure as DVS
from scripts.backtest_study.f3_structure import vol_expansion_long_vol as V

E = "E-VOL"
H = "H-VOL"
L_ = "L-VOL"


# ── helpers ──────────────────────────────────────────────────────────────────

def sessions(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def labels(vols, start=date(2024, 1, 1)):
    return list(zip(sessions(start, len(vols)), vols))


def row(bid, ask, latest=None, volume=0, iv=20.0):
    r = {"Bid": str(bid), "Ask": str(ask), "Volume": str(volume), "IV": str(iv)}
    if latest is not None:
        r["Latest"] = str(latest)
    return r


class FakeChain:
    """`{(expiry, strike, opt): {day: row}}`; the series mark is the row's mid."""

    def __init__(self, data: dict, series_skip: dict | None = None):
        self.data = data
        self.series_skip = series_skip or {}
        self.idx = {}
        for (e, k, o) in data:
            self.idx.setdefault((V.TICKER, e), {}).setdefault(float(k), set()).add(o[0])

    def cached(self, ticker, expiry, strike, opt_type):
        return (expiry, float(strike), opt_type) in self.data

    def strikes(self, ticker, expiry):
        return sorted(self.idx.get((ticker, expiry), {}))

    def history(self, leg: Leg):
        rows = self.data.get((leg.expiration, float(leg.strike), leg.opt_type), {})
        skip = self.series_skip.get((leg.expiration, float(leg.strike), leg.opt_type), set())
        series = []
        for d in sorted(rows):
            b, a = float(rows[d]["Bid"]), float(rows[d]["Ask"])
            if d not in skip:
                series.append((d, (b + a) / 2))
        return series, dict(rows)


@pytest.fixture(autouse=True)
def _trust_depth(monkeypatch):
    monkeypatch.setattr(DVS, "depth_trusted", lambda *a, **k: True)


# ── onsets, calm weeks, the label ────────────────────────────────────────────

def test_onset_needs_five_labelled_non_evol_sessions_and_rearms_after_five():
    vols = [L_] * 6 + [E, E, L_, L_, L_, L_, L_, E] + [L_] * 5 + [E]
    labs = labels(vols)
    on, why = V.find_onsets(labs)
    days = [d for d, _ in labs]
    # index 6 is an onset and 7 is in its run. 13's prior five (8..12) are all
    # L-VOL, so the label re-armed and 13 is an onset; 19 likewise.
    assert on == [days[6], days[13], days[19]]
    assert why["in_run"] == 1


def test_onset_blocked_by_an_unlabelled_prior_session():
    vols = [L_, L_, None, L_, L_, L_, E] + [L_] * 6 + [E]
    labs = labels(vols)
    on, why = V.find_onsets(labs)
    assert labs[6][0] not in on and why["no_rearm_history"] == 1
    assert on == [labs[-1][0]]
    # fewer than five prior sessions also blocks
    on2, why2 = V.find_onsets(labels([L_, L_, E]))
    assert on2 == [] and why2["no_rearm_history"] == 1


def _vix_rows(vix, start=date(2024, 1, 1)):
    return [{"date": d.isoformat(), "spy_close": "100", "vix_close": str(v)}
            for d, v in zip(sessions(start, len(vix)), vix)]


def test_label_for_d_reads_nothing_after_d():
    vix = [15.0] * 30 + [19.5] + [15.0] * 10
    rows = _vix_rows(vix)
    base = V.vol_labels(rows)
    d_idx = 30
    perturbed = [dict(r) for r in rows]
    for r in perturbed[d_idx + 1:]:
        r["vix_close"] = "80"
    after = V.vol_labels(perturbed)
    assert base[:d_idx + 1] == after[:d_idx + 1]
    assert base[d_idx][1] == E          # 19.5 / 15 - 1 = +30% >= +25%
    assert after[d_idx + 1][1] == E
    # the cut drops later rows before the label is computed
    cut = V.vol_labels(perturbed, end=V._d(rows[d_idx]["date"]))
    assert cut == base[:d_idx + 1]


def test_calm_week_is_first_session_with_six_clean_labels():
    labs = labels([L_] * 10 + [H, E, L_] + [L_] * 20, start=date(2024, 1, 1))
    lo, hi = labs[0][0], labs[-1][0]
    calm, why = V.find_calm_weeks(labs, lo, hi)
    for d in calm:
        i = [x for x, _ in labs].index(d)
        assert d.weekday() == 0 or labs[i - 1][0].isocalendar()[:2] != d.isocalendar()[:2]
        assert all(v not in (E, None) for _, v in labs[max(0, i - 5):i + 1])
        assert i >= 5
    # week 1 (fewer than six labels) and the week holding the E-VOL fail
    assert why["unlabelled_in_six"] >= 1 and why["evol_in_six"] >= 1
    # a week whose first session is before `lo` is outside the window
    calm2, _ = V.find_calm_weeks(labs, labs[16][0], hi)
    assert all(d >= labs[16][0] for d in calm2)


def test_gl_reports_disagreeing_onsets():
    a = labels([L_] * 20 + [E] + [L_] * 10)
    b = labels([L_] * 20 + [L_] + [L_] * 10)
    start, only_a, only_b = V.gl_mismatch(a, b, a[-1][0])
    assert start == b[10][0] and only_a == [a[20][0]] and only_b == []
    assert V.gl_mismatch(a, a, a[-1][0])[1:] == ([], [])


# ── selection ────────────────────────────────────────────────────────────────

FILL = date(2024, 3, 1)
EXP = date(2024, 4, 19)       # monthly nearest 30 DTE with >= 21 from 2024-03-01


def test_headline_expiry_respects_21_dte_floor():
    from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB
    assert MB.monthly_for(FILL, *V.EXPIRY_RULES["H"]) == EXP   # 03-15 is 14 DTE, too near
    assert MB.monthly_for(date(2024, 3, 22), *V.EXPIRY_RULES["H"]) == EXP  # 28 DTE
    assert (MB.monthly_for(FILL, *V.EXPIRY_RULES["L"]) - FILL).days >= 45


def _listed(k, opts=("Call", "Put"), day=FILL, bid=1.0, ask=1.1):
    return {(EXP, float(k), o): {day: row(bid, ask)} for o in opts}


def test_strike_walk_atm_wings_and_await():
    data = {}
    data.update(_listed(500))
    data.update(_listed(525, ("Call",)))
    data.update(_listed(475, ("Put",)))
    ch = FakeChain(data)
    en = V.select_entry(ch, set(), FILL - timedelta(days=1), FILL, {5: FILL}, 500.2, "H")
    assert en.expiry == EXP and en.atm == 500.0
    assert en.wing == {"BC": 525.0, "BP": 475.0}
    assert en.status == {"S": "built", "BC": "built", "BP": "built"}
    # spot 500.6: nearest $1 strike 501 is not cached -> every arm awaits it
    en2 = V.select_entry(ch, set(), FILL - timedelta(days=1), FILL, {5: FILL}, 500.6, "H")
    assert all(en2.status[a] == "await" for a in V.ARMS)
    assert ("Call", EXP, 501.0) in en2.fetch["S"] and ("Put", EXP, 501.0) in en2.fetch["S"]
    # skip-listed on evidence: step on to the next nearest (500)
    from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
    ev = {NTF.contract_stem("SPY", EXP, 501.0, o) for o in ("Call", "Put")}
    en3 = V.select_entry(ch, ev, FILL - timedelta(days=1), FILL, {5: FILL}, 500.6, "H")
    assert en3.atm == 500.0 and en3.status["S"] == "built"


def test_failed_wing_drops_only_its_arm_and_no_spot_drops_all():
    data = {}
    data.update(_listed(500))
    data.update(_listed(525, ("Call",)))
    ch = FakeChain(data)
    ev = set()
    from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
    for k in range(467, 485):   # every put near 475 skip-listed
        ev.add(NTF.contract_stem("SPY", EXP, float(k), "Put"))
    en = V.select_entry(ch, ev, FILL, FILL, {5: FILL}, 500.0, "H")
    assert en.status["BP"] == "drop" and en.reason["BP"] == "no_listed_strike"
    assert en.status["S"] == "built" and en.status["BC"] == "built"
    en0 = V.select_entry(ch, ev, FILL, FILL, {5: FILL}, None, "H")
    assert set(en0.reason.values()) == {"no_spot"}


def test_selection_reads_nothing_after_fill():
    """GX: change every later quote and listing; the choices are identical."""
    data = {}
    data.update(_listed(500))
    data.update(_listed(525, ("Call",)))
    data.update(_listed(475, ("Put",)))
    a = V.select_entry(FakeChain(data), set(), FILL, FILL, {5: FILL}, 500.2, "H")
    later = {k: dict(v) for k, v in data.items()}
    for k in later:
        later[k][FILL + timedelta(days=3)] = row(9.0, 9.5)
    # a strike nearer the target that lists only AFTER the fill
    later.update(_listed(526, ("Call",), day=FILL + timedelta(days=3)))
    b = V.select_entry(FakeChain(later), set(), FILL, FILL, {5: FILL}, 500.2, "H")
    assert (a.expiry, a.atm, a.wing, a.status) == (b.expiry, b.atm, b.wing, b.status)


def test_cut_chain_hides_quotes_after_the_cut():
    """GC: nothing after the cut reaches the in-sample run."""
    d0, d1 = date(2026, 9, 22), date(2026, 9, 23)
    data = {(EXP, 500.0, "Call"): {d0: row(1, 1.1), d1: row(5, 5.1)}}
    cc = V.CutChain(FakeChain(data), V.CUT)
    series, details = cc.history(Leg(1, "SPY", EXP, 500.0, "Call"))
    assert list(details) == [d0] and [d for d, _ in series] == [d0]


# ── pricing ──────────────────────────────────────────────────────────────────

def _entry(arm_wing=None, exits=None):
    en = V.Entry(signal=FILL - timedelta(days=1), fill=FILL, exits=exits or {5: X5}, kind="H",
                 expiry=EXP, spot=500.0, atm=500.0, wing=arm_wing or {"BC": 525.0, "BP": 475.0})
    for a in V.ARMS:
        en.status[a], en.reason[a] = "built", ""
    return en


SESS = sessions(FILL, 12)
X5 = SESS[5]
SPOTS = {d: 500.0 for d in SESS}


def test_max_loss_points_for_each_structure_including_a_credit_1x2():
    assert V.max_loss_points("S", 500, None, 12.0) == 12.0
    assert V.max_loss_points("BC", 500, 525, 1.5) == 26.5        # debit 1x2
    assert V.max_loss_points("BC", 500, 525, -2.0) == 23.0       # credit 1x2
    assert V.max_loss_points("BP", 500, 475, -1.0) == 24.0


def _two_day(entry_px, exit_px, opt, k, extra_days=None):
    rows_ = {FILL: row(entry_px - 0.05, entry_px + 0.05), X5: row(exit_px - 0.05, exit_px + 0.05)}
    for d in SESS[1:5]:
        rows_.setdefault(d, row(entry_px - 0.05, entry_px + 0.05))
    if extra_days:
        rows_.update(extra_days)
    return {(EXP, float(k), opt): rows_}


def test_credit_1x2_R_uses_width_minus_credit_and_fixed_exit():
    data = {}
    data.update(_two_day(10.0, 11.0, "Call", 500))     # sold ATM call
    data.update(_two_day(4.0, 5.0, "Call", 525))       # two bought wings
    ch = FakeChain(data)
    p = V.price_trade(ch, _entry(), "BC", 5, SESS, SPOTS)
    assert not isinstance(p, str)
    assert p.exit == X5 == SESS[5]                    # F + 5 sessions
    assert p.net == pytest.approx(-10.0 + 8.0)        # a credit of 2.00
    assert p.max_loss == pytest.approx(25 - 2.0)
    comm = 0.65 * 2 * 3
    pnl = ((-11.0 + 10.0) - (-2.0)) * 100 - comm
    assert p.R == pytest.approx(pnl / (23.0 * 100 + comm))


def test_straddle_R_is_over_the_debit_plus_commission():
    data = {}
    data.update(_two_day(6.0, 7.0, "Call", 500))
    data.update(_two_day(5.0, 3.0, "Put", 500))
    p = V.price_trade(FakeChain(data), _entry(), "S", 5, SESS, SPOTS)
    comm = 0.65 * 2 * 2
    assert p.net == pytest.approx(11.0)
    assert p.R == pytest.approx(((10.0 - 11.0) * 100 - comm) / (11.0 * 100 + comm))


def test_bp_R_denominator():
    data = {}
    data.update(_two_day(9.0, 9.0, "Put", 500))
    data.update(_two_day(3.0, 3.0, "Put", 475))
    p = V.price_trade(FakeChain(data), _entry(), "BP", 5, SESS, SPOTS)
    assert p.max_loss == pytest.approx(25 + (-9.0 + 6.0))
    assert p.R == pytest.approx(-3.9 / (22.0 * 100 + 3.9))


def test_entry_fills_on_f_close_only():
    data = {}
    data.update(_two_day(6.0, 7.0, "Call", 500,
                         {FILL - timedelta(days=1): row(50, 50.1)}))
    data.update(_two_day(5.0, 3.0, "Put", 500))
    p = V.price_trade(FakeChain(data), _entry(), "S", 5, SESS, SPOTS)
    assert p.net == pytest.approx(11.0)               # the D quote is never read
    # no row on F: no later day is tried
    del data[(EXP, 500.0, "Put")][FILL]
    assert V.price_trade(FakeChain(data), _entry(), "S", 5, SESS, SPOTS) == "no_entry_quote"


def test_nonpositive_max_loss_refuses():
    data = {}
    data.update(_two_day(1.0, 1.0, "Call", 500))
    data.update(_two_day(14.0, 14.0, "Call", 525))     # inconsistent: wing dearer
    r = V.price_trade(FakeChain(data), _entry(), "BC", 5, SESS, SPOTS)
    assert r in ("nonpositive_max_loss", "non_monotonic_entry_quote")


def test_stale_and_missing_exit_marks_drop():
    leg = Leg(1, "SPY", EXP, 500.0, "Call")
    good = row(2.0, 2.2)
    junk_no_trade = row(0.5, 3.0, latest=1.0, volume=0)
    ch = FakeChain({(EXP, 500.0, "Call"): {SESS[3]: good, X5: junk_no_trade}})
    assert V.exit_mark(ch, leg, X5) == "stale_exit_mark"
    assert V.exit_mark(ch, leg, SESS[4]) == "no_exit_quote"
    # junk that traded on the day marks at Latest, dated the day: kept
    traded = row(0.5, 3.0, latest=1.2, volume=5)
    ch2 = FakeChain({(EXP, 500.0, "Call"): {SESS[3]: good, X5: traded}})
    assert V.exit_mark(ch2, leg, X5) == (1.2, "barchart_last")
    # a carried mark tagged "barchart": the row exists but the series snap is older
    ch3 = FakeChain({(EXP, 500.0, "Call"): {SESS[3]: good, X5: row(2.0, 2.2)}},
                    series_skip={(EXP, 500.0, "Call"): {X5}})
    assert V.exit_mark(ch3, leg, X5) == "stale_exit_mark"


def test_book_exit_is_d_plus_6_and_gate_blocks_pricing():
    labs = labels([L_] * 8 + [E] + [L_] * 20)
    spots = {d: 500.0 for d, _ in labs}
    bk = V.Book(FakeChain({}), set(), labs, spots, labs[0][0], labs[-1][0], labs[-1][0])
    d = bk.onsets[0]
    i = bk.pos[d]
    en = bk.entry(d, "H")
    assert en.fill == bk.sessions[i + 1] and en.exits[5] == bk.sessions[i + 6]
    assert en.exits[10] == bk.sessions[i + 11]
    with pytest.raises(V.AwaitingScrape):
        bk.price(en, "S", 5)
    assert bk.headline_awaiting() > 0
    with pytest.raises(V.AwaitingScrape):
        bk.open_outcomes()


def test_entry_needs_d_plus_11_inside_the_cut():
    labs = labels([L_] * 8 + [E] + [L_] * 8)
    bk = V.Book(FakeChain({}), set(), labs, {}, labs[0][0], labs[-1][0], labs[-1][0])
    assert bk.onsets == [] and bk.truncated["onset"] == 1


# ── grading ──────────────────────────────────────────────────────────────────

def rows_(pairs):
    return [dict(date=d, R=r) for d, r in pairs]


def test_c2_drops_whole_month_clusters_from_arm_and_calm():
    arm = rows_([("2024-01-05", 0.5), ("2024-01-20", 0.5), ("2024-02-05", -0.1),
                 ("2024-03-05", 0.2)])
    calm = rows_([("2024-01-08", -1.0), ("2024-02-08", 0.0), ("2024-03-08", 0.0)])
    c2 = V.c2_check(arm, calm)
    assert c2["mean"] is True            # without January: (-0.1 + 0.2) / 2 > 0
    # both January trades leave together: one-trade removal would keep the sign
    # (folds +0.2, +0.2, ...) but the cluster removal leaves 0.0, no sign -> fails
    arm_b = rows_([("2024-01-05", 0.5), ("2024-01-20", 0.5), ("2024-02-05", -0.1),
                   ("2024-03-05", 0.1)])
    assert V.c2_check(arm_b, calm)["mean"] is False
    # removing a month from ARM C too: without March, calm is -0.5 on two weeks;
    # the gain stays positive in every fold
    assert c2["gain"] is True
    assert len(c2["folds_m"]) == 3


def test_c3_cuts_both_selloff_windows():
    arm = rows_([("2025-03-10", 2.0), ("2026-03-10", 2.0), ("2024-06-01", -0.1)])
    calm = rows_([("2024-06-03", 0.0), ("2025-04-01", 5.0)])
    c3 = V.c3_check(arm, calm)
    assert c3["n"] == 1 and c3["n_c"] == 1
    assert c3["mean"] is False          # +1.3 full, -0.1 cut
    assert V.in_selloff("2025-04-30") and V.in_selloff("2026-02-01")
    assert not V.in_selloff("2025-05-01")


def test_holm_two_families_of_three_missing_p_enters_as_one():
    adj = V.holm_family({"S": 0.01, "BC": None, "BP": 0.02})
    assert adj["S"] == pytest.approx(0.03) and adj["BP"] == pytest.approx(0.04)
    assert adj["BC"] == pytest.approx(1.0)
    gr = {"S": {"p": 0.01, "gain_p": 0.5}, "BC": {"p": 0.04, "gain_p": 0.01},
          "BP": {"p": None, "gain_p": None}}
    V.apply_holm(gr)
    assert gr["S"]["p_adj"] == pytest.approx(0.03)
    assert gr["BC"]["p_adj"] == pytest.approx(0.08)
    assert gr["BC"]["gain_p_adj"] == pytest.approx(0.03)   # its own family
    assert gr["BP"]["p_adj"] == 1.0


def test_bootstrap_resamples_month_clusters_and_p_rule():
    import numpy as np
    assert V.p_two_sided(np.array([1.0, 2.0, 3.0, 4.0])) == 0.0
    assert V.p_two_sided(np.array([-1.0, 1.0])) == 1.0
    arm = rows_([(f"2024-{m:02d}-05", 0.2 + 0.01 * m) for m in range(1, 13)])
    calm = rows_([(f"2024-{m:02d}-09", 0.0) for m in range(1, 13)])
    b = V.bootstrap(arm, calm, n=2000)
    assert b["ci"][0] > 0 and b["p"] < 0.05 and b["gain_ci"][0] > 0


def _grade(**kw):
    g = dict(n=25, n_c=80, mean=0.2, ci=(0.05, 0.35), p_adj=0.01, gain=0.2,
             gain_ci=(0.05, 0.35), gain_p_adj=0.01, c2_mean=True, c2_gain=True,
             c3_mean=True, c3_gain=True)
    g.update(kw)
    return g


def test_verdict_first_match_logic():
    assert V.decide(_grade(), None, None, 0.2, "ok") == (V.LVP, "")
    assert V.decide(_grade(n=19), None, None, 0.2, "ok")[0] == V.UNDERPOWERED
    assert V.decide(_grade(n_c=59), None, None, 0.2, "ok")[0] == V.UNDERPOWERED
    assert V.decide(_grade(n=5), None, None, None, "ok", forward=True)[0] == V.STILL_OPEN
    # gain fails -> PAYS-NOT-SIGNAL, not NULL
    assert V.decide(_grade(gain_ci=(-0.1, 0.3)), None, None, 0.2, "ok")[0] == V.PNS
    assert V.decide(_grade(c2_gain=False), None, None, 0.2, "ok")[0] == V.PNS
    # PBO exactly 0.50 bars promotion
    assert V.decide(_grade(), None, None, 0.5, "ok") == (V.NULL, "PBO veto")
    assert V.decide(_grade(), None, None, None, "other") == (V.NULL, "PBO not computed")
    # NOT BUILT when a PBO cell awaits and the positive word otherwise holds
    assert V.decide(_grade(), None, None, None, "await")[0] == V.NOT_BUILT
    # ...but an arm whose positive conditions fail prints its own word
    assert V.decide(_grade(ci=(-0.1, 0.3)), None, None, None, "await")[0] == V.NULL
    # C2 / C3 failures name themselves
    assert V.decide(_grade(c2_mean=False), None, None, 0.2, "ok") == (V.NULL, "C2 fails")
    assert V.decide(_grade(c3_mean=False), None, None, 0.2, "ok") == (V.NULL, "C3 fails")
    # CONTRARY needs no PBO
    neg = _grade(mean=-0.2, ci=(-0.35, -0.05), gain_ci=(-0.3, -0.1))
    assert V.decide(neg, None, None, 0.9, "other") == (V.CONTRARY, "")
    assert V.decide(_grade(ci=(-0.35, -0.05), p_adj=0.2), None, None, 0.2, "ok")[0] == V.NULL
    # forward ignores C3 and PBO
    assert V.decide(_grade(c3_mean=False, c3_gain=False), None, None, None, "other",
                    forward=True)[0] == V.LVP


def test_exit_drop_rerun_can_demote_a_word():
    weak = _grade(ci=(0.0001, 0.3))
    bad_rerun = _grade(ci=(-0.1, 0.3))
    assert V.decide(weak, bad_rerun, None, 0.2, "ok") == (V.NULL, "exit-drop sensitive")
    # LVP fails only on its re-run's gain -> falls to PAYS-NOT-SIGNAL
    gain_bad = _grade(gain_ci=(-0.2, 0.2))
    assert V.decide(_grade(), gain_bad, None, 0.2, "ok")[0] == V.PNS
    neg = _grade(mean=-0.2, ci=(-0.35, -0.05))
    got = V.decide(neg, None, _grade(ci=(-0.3, 0.1)), 0.2, "ok")
    assert got == (V.NULL, "exit-drop sensitive")


def test_regrade_exit_drop_sets_drops_and_keeps_other_arms_p():
    arm = rows_([(f"2024-{m:02d}-05", 0.3) for m in range(1, 13)])
    calm = rows_([(f"2024-{m:02d}-09", 0.0) for m in range(1, 13)])
    grades = {"S": {"p": 0.5, "gain_p": 0.5}, "BC": {"p": 0.001, "gain_p": 0.001},
              "BP": {"p": 0.9, "gain_p": 0.9}}
    assert V.regrade_exit_drop("BC", arm, calm, [], grades, -1.0) is None
    g = V.regrade_exit_drop("BC", arm, calm, [date(2024, 6, 20)] * 3, grades, -1.0, n=2000)
    assert g["n"] == 15
    assert g["mean"] == pytest.approx((12 * 0.3 - 3) / 15)
    assert grades["S"]["p"] == 0.5          # the other arms' p are not touched


def test_pbo_matrix_quarters_and_channels():
    cells = {n: [] for n in range(1, 13)}
    cells[1] = rows_([("2022-03-15", 0.5), ("2026-09-01", -0.2), ("2026-09-15", 0.1)])
    M = V.pbo_matrix(cells)
    assert M.shape == (19, 12, 2)
    assert M[0, 0].tolist() == [0.5, 1.0]
    assert M[-1, 0, 1] == 2.0
    res, T, padded = V.run_pbo(cells)
    assert T == 19 and padded == 1 and res.S == 20 and res.n_rows == 20


# ── the outcome path end to end, on a synthetic chain ────────────────────────

class AllListedChain:
    """Every contract listed with a two-sided quote on every session; the mark
    drifts with the day so P&L is not zero. Synthetic, never a real quote."""

    def __init__(self, days):
        self.days = days
        self.idx = {}

    def cached(self, *a):
        return True

    def strikes(self, *a):
        return []

    def history(self, leg):
        rows_, series = {}, []
        for i, d in enumerate(self.days):
            if d > leg.expiration:
                break
            mid = round(max(0.05, 8.0 - 0.3 * abs(leg.strike - 500) / 5 + 0.01 * (i % 7)), 2)
            rows_[d] = row(round(mid - 0.02, 2), round(mid + 0.02, 2))
            series.append((d, mid))
        return series, rows_


def test_outcomes_run_end_to_end_on_synthetic_quotes(tmp_path, monkeypatch, capsys):
    vols = []
    for k in range(12):
        vols += [L_] * 9 + [E]
    vols += [L_] * 20
    labs = labels(vols, start=date(2024, 1, 1))
    days = [d for d, _ in labs]
    spots = {d: 500.0 for d in days}
    ch = AllListedChain(days)
    ins = V.Book(ch, set(), labs, spots, days[0], days[-1], days[-1])
    fwd = V.Book(ch, set(), labels([L_] * 3, start=days[-1] + timedelta(days=30)), {},
                 days[-1] + timedelta(days=30), None, None, forward=True)
    monkeypatch.setattr(V, "TRADES_CSV", tmp_path / "trades.csv")
    monkeypatch.setattr(V, "OUT_DIR", tmp_path)
    ins.open_outcomes()
    assert V.outcomes(ins, fwd) == 0
    out = capsys.readouterr().out
    words = (V.LVP, V.PNS, V.CONTRARY, V.NULL, V.UNDERPOWERED)
    for a in V.ARMS:
        line = next(x for x in out.splitlines() if x.startswith(f">>> vol_expansion_long_vol ARM {a} "))
        assert any(f": {w}" in line for w in words) and V.PEEK_NOTE in line
    assert ">>> vol_expansion_long_vol PBO (12 cells, gates all three arms): " in out
    assert "ARM S STILL-OPEN ARM BC STILL-OPEN ARM BP STILL-OPEN" in out
    assert (tmp_path / "trades.csv").exists()
    # per-arm blocks sit under GRADED ARMS, the PBO lines under C4
    lines = out.splitlines()
    ig = next(i for i, x in enumerate(lines) if x.startswith("GRADED ARMS"))
    ic = next(i for i, x in enumerate(lines) if x.startswith("C4 — PBO"))
    for a in V.ARMS:
        ia = next(i for i, x in enumerate(lines) if x.startswith(f"  ARM {a}: n "))
        assert ig < ia < ic
    ip = next(i for i, x in enumerate(lines) if x.startswith("  quarters ") or "not computed" in x)
    assert ip > ic
    # 12 onsets and fewer than 60 calm weeks: every arm is UNDERPOWERED
    assert out.count(f": {V.UNDERPOWERED} — ") == 3
