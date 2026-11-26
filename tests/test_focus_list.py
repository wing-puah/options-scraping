"""focus_list: the frozen list, the arms, the null band, the verdict table and
the one-shot forward read.

research/pre-registrations/f1_selection/benchmark/focus_list.md. Synthetic
rows only; no test reads the real exports, the option cache or the journal.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.backtest_study.f1_selection.benchmark import focus_list as FL

ROOT = Path(__file__).resolve().parent.parent
REGISTRATION = ROOT / "research/pre-registrations/f1_selection/benchmark/focus_list.md"


def row(date, ticker, tier="A", R=0.0, score=10.0, exit_date=None, pending=False):
    return dict(date=date, ticker=ticker, tier=tier, R=R, score_total=score, post13c=True,
                exit_date=exit_date or date, pending=pending)


# ── the list ────────────────────────────────────────────────────────────────

def test_list_hash_is_the_registered_one():
    assert FL.list_hash() == FL.LW_SHA256
    text = REGISTRATION.read_text()
    assert FL.list_string() in text
    assert FL.LW_SHA256 in text


def test_a_changed_list_changes_the_hash():
    changed = (("semis", ("MU", "TSM")),) + FL.GROUPS[1:]
    assert FL.list_hash(changed) != FL.LW_SHA256


def test_list_is_fourteen_tickers_in_five_groups():
    assert len(FL.LW) == 14 and len(FL.GROUPS) == 5
    assert FL.group_of("XLF") == "traditional" and FL.group_of("JPM") is None


# ── windows ─────────────────────────────────────────────────────────────────

def test_windows_cut_at_the_registered_dates():
    rows = [row(d, "MU") for d in ("2026-09-22", "2026-09-23", "2026-11-15", "2026-11-16")]
    ins, gap, fwd = FL.windows(rows)
    assert [r["date"] for r in ins] == ["2026-09-22"]
    assert [r["date"] for r in gap] == ["2026-09-23", "2026-11-15"]
    assert [r["date"] for r in fwd] == ["2026-11-16"]


# ── the arms ────────────────────────────────────────────────────────────────

def test_ties_go_to_the_earlier_ticker_whatever_the_input_order():
    day = [row("2026-01-05", t) for t in ("ZZZ", "MMM", "BBB", "AAA")]
    assert [r["ticker"] for r in FL.picks(day)] == ["AAA", "BBB", "MMM"]
    assert [r["ticker"] for r in FL.picks(day[::-1])] == ["AAA", "BBB", "MMM"]


def test_tier_a_ranks_before_tier_b_and_c_is_never_taken():
    day = [row("2026-01-05", "AAA", tier="B"), row("2026-01-05", "ZZZ", tier="A"),
           row("2026-01-05", "CCC", tier="C")]
    assert [r["ticker"] for r in FL.picks(day)] == ["ZZZ", "AAA"]


def test_arm_f_takes_only_list_names_and_d1_excludes_them():
    day = [row("2026-01-05", t) for t in ("MU", "JPM", "GLD", "XOM")]
    assert {r["ticker"] for r in FL.picks(day, FL.LW)} == {"MU", "GLD"}
    assert {r["ticker"] for r in FL.picks(day, exclude=FL.LW)} == {"JPM", "XOM"}


def test_identical_picks_give_a_zero_difference():
    day = [row("2026-01-05", "MU", R=0.4), row("2026-01-05", "GLD", R=-0.2)]
    f_by, c_by = FL.by_date(FL.picks(day, FL.LW)), FL.by_date(FL.picks(day))
    assert FL.paired_x(f_by, c_by) == [("2026-01-05", 0.0)]


def test_gain_is_a_mean_of_per_date_differences():
    rows = [row("2026-01-05", "MU", R=1.0), row("2026-01-05", "JPM", R=-1.0),
            row("2026-01-06", "MU", R=0.5)]
    g = FL.grade(rows, FL.LW, boot_n=200, draws=50)
    # date 1: F = [MU] 1.0, C = [JPM, MU] 0.0 -> +1.0; date 2: identical -> 0.0
    assert g["xs"] == [("2026-01-05", 1.0), ("2026-01-06", 0.0)]
    assert g["gain"] == pytest.approx(0.5)
    assert g["overlap"] == 2 and g["identical"] == 1 and g["gf4"]


# ── ARM N ───────────────────────────────────────────────────────────────────

def test_null_draws_stay_inside_arm_f_tier():
    # ARM F holds one Tier A list row; the only other Tier A row has R = 5.
    # Tier B rows have R = -9 and must never be drawn.
    rows = [row("2026-01-05", "MU", tier="A", R=1.0), row("2026-01-05", "JPM", tier="A", R=5.0),
            row("2026-01-05", "XOM", tier="B", R=-9.0), row("2026-01-05", "CVX", tier="B", R=-9.0)]
    f_by, c_by = FL.by_date(FL.picks(rows, FL.LW)), FL.by_date(FL.picks(rows))
    e_by = FL.by_date(rows)
    c_mean = FL.mean_r(c_by["2026-01-05"])
    gains = FL.null_gains(f_by, c_by, e_by, draws=200, seed=1)
    assert {round(v + c_mean, 6) for v in gains} == {1.0, 5.0}


def test_a_date_with_no_spare_row_copies_arm_f():
    rows = [row("2026-01-05", "MU", R=0.3), row("2026-01-05", "GLD", R=0.1)]
    f_by, c_by = FL.by_date(FL.picks(rows, FL.LW)), FL.by_date(FL.picks(rows))
    plan = FL.tier_plan(f_by, FL.by_date(rows), ["2026-01-05"])
    assert FL.spare_dates(plan) == 0
    assert set(FL.null_gains(f_by, c_by, FL.by_date(rows), draws=20, seed=1)) == {0.0}


def test_too_few_spare_dates_makes_criterion_2_not_evaluable():
    rows = [row("2026-01-05", "MU", R=1.0), row("2026-01-05", "JPM", R=-1.0)]
    g = FL.grade(rows, FL.LW, boot_n=100, draws=20)
    assert g["gf5_dates"] == 1 and g["c2"] is None


# ── criteria 5 and 6 ────────────────────────────────────────────────────────

def test_largest_name_merges_the_two_share_classes():
    rows = [row("d1", "GOOG"), row("d2", "GOOGL"), row("d3", "GOOGL"), row("d4", "NVDA"),
            row("d5", "NVDA")]
    assert FL.largest_name(rows) == "GOOG"
    assert FL.without_name(FL.LW, "GOOG") == FL.LW - {"GOOG", "GOOGL"}


def test_curve_stats_seeds_the_peak_at_zero():
    rows = [row("d", "MU", R=-1.0, exit_date="2026-01-02"),
            row("d", "MU", R=3.0, exit_date="2026-01-03"),
            row("d", "MU", R=-2.0, exit_date="2026-01-04")]
    assert FL.curve_stats(rows) == (0.0, 2.0)


@pytest.mark.parametrize("f_rs, c_rs, want", [
    ([-1.0, 0.5], [1.0, -0.5], False),   # ARM F total <= 0 fails
    ([1.0, 1.0], [1.0, -0.5], True),     # ARM F has no drawdown: the better
    ([1.0, 1.0], [1.0, 1.0], True),      # neither has one: holds
    ([2.0, -1.0], [1.0, 1.0], False),    # only ARM C has none: the card is better
    ([4.0, -1.0], [2.0, -1.0], True),    # ratio 3 against 1
    ([2.0, -1.0], [4.0, -1.0], False),
])
def test_criterion_6_edge_cases(f_rs, c_rs, want):
    def mk(rs):
        return [row("d", "MU", R=r, exit_date=f"2026-01-{i + 2:02d}") for i, r in enumerate(rs)]
    assert FL.crit6(mk(f_rs), mk(c_rs))[0] is want


# ── verdicts ────────────────────────────────────────────────────────────────

ALL = dict(gf0=True, c1=True, c2=True, c3=True, c4=True, c5=True, c6=True, trails=False)


@pytest.mark.parametrize("change, want", [
    ({}, FL.BEATS),
    ({"gf0": False}, FL.UNDERPOWERED),
    ({"c2": False}, FL.NOT_THE_LIST),
    ({"c2": None}, FL.NULL),                       # NOT EVALUABLE never reads NOT-THE-LIST
    ({"c3": False}, FL.NULL),
    ({"c1": False, "c2": False}, FL.NULL),
    ({"c1": False, "c2": False, "trails": True}, FL.TRAILS),
    ({"gf0": False, "trails": True}, FL.UNDERPOWERED),
])
def test_verdict_takes_the_first_matching_row(change, want):
    assert FL.verdict({**ALL, **change}) == want


def test_failed_names_the_criteria_that_did_not_hold():
    assert FL.failed({**ALL, "c2": None, "c5": False}) == "2 (NOT EVALUABLE), 5"


def test_trails_needs_the_interval_both_windows_and_the_largest_name():
    # 40 dates, the list row loses to an off-list row every day.
    rows = []
    for i in range(40):
        d = f"2025-06-{i % 28 + 1:02d}" if i < 28 else f"2025-07-{i - 27:02d}"
        rows += [row(d, "MU", R=-1.0), row(d, "NVDA", R=-1.0), row(d, "JPM", R=1.0),
                 row(d, "XOM", R=1.0), row(d, "AAA", R=1.0)]
    g = FL.grade(rows, FL.LW, boot_n=300, draws=50)
    assert g["gain"] < 0 and g["ci"][1] < 0 and g["trails"]
    assert FL.verdict(g) == FL.TRAILS


# ── the forward read ────────────────────────────────────────────────────────

def forward_rows(n_dates=40):
    rows = []
    for i in range(n_dates):
        d = f"2027-01-{i + 1:02d}" if i < 31 else f"2027-02-{i - 30:02d}"
        rows += [row(d, "MU", R=0.5), row(d, "GLD", R=0.4), row(d, "JPM", R=-0.5),
                 row(d, "XOM", R=-0.4), row(d, "AAA", R=-0.3)]
    return rows


def test_forward_read_stays_open_while_the_seal_holds(tmp_path):
    store = tmp_path / "fwd.json"
    fr = FL.forward_read(forward_rows(), seal_lifted=None, store=store)
    assert fr["verdict"] == FL.STILL_OPEN and not store.exists()


def test_forward_read_stays_open_below_the_counts(tmp_path):
    store = tmp_path / "fwd.json"
    fr = FL.forward_read(forward_rows(10), seal_lifted="2027-03-01", store=store)
    assert fr["verdict"] == FL.STILL_OPEN and fr["n_dates"] == 10 and not store.exists()


def test_forward_read_runs_once_and_is_not_repeated(tmp_path):
    store = tmp_path / "fwd.json"
    first = FL.forward_read(forward_rows(), seal_lifted="2027-03-01", store=store,
                            today="2027-03-02")
    assert first["verdict"] in (FL.FWD_CONFIRMED, FL.FWD_REFUTED, FL.FWD_NULL)
    assert store.exists() and first["n_dates"] == 40
    # A second run with different rows returns the stored read unchanged.
    again = FL.forward_read(forward_rows(35), seal_lifted="2027-03-01", store=store)
    assert again["stored"] and again["n_dates"] == 40 and again["read_on"] == "2027-03-02"


def test_complete_prefix_stops_before_the_first_pending_date():
    rows = [row("2027-01-01", "MU"), row("2027-01-02", "MU"),
            row("2027-01-02", "JPM", pending=True), row("2027-01-03", "MU")]
    assert [r["date"] for r in FL.complete_prefix(rows)] == ["2027-01-01"]


def test_forward_verdict_table():
    assert FL.forward_verdict(dict(c1=True, c3=True, gain=0.1, ci=(0.01, 0.2),
                                   f_ci=(0.01, 0.2))) == FL.FWD_CONFIRMED
    assert FL.forward_verdict(dict(c1=False, c3=True, gain=-0.1, ci=(-0.2, -0.01),
                                   f_ci=(0.01, 0.2))) == FL.FWD_REFUTED
    assert FL.forward_verdict(dict(c1=False, c3=False, gain=0.0, ci=(-0.1, 0.1),
                                   f_ci=(-0.3, -0.1))) == FL.FWD_REFUTED
    assert FL.forward_verdict(dict(c1=False, c3=True, gain=0.0, ci=(-0.1, 0.1),
                                   f_ci=(0.01, 0.2))) == FL.FWD_NULL


# ── L-LIVE ──────────────────────────────────────────────────────────────────

def test_live_cut_reports_counts_only_and_no_dollars(tmp_path, monkeypatch):
    trades = tmp_path / "trades.csv"
    trades.write_text("date,ticker,action,realized_pnl\n"
                      "2026-11-12,MU,CLOSE,-999\n"       # before the forward window
                      "2026-11-17,MU,CLOSE,123.45\n"
                      "2026-11-18,JPM,CLOSE,-67.89\n"
                      "2026-11-18,GLD,OPEN,\n")
    out = tmp_path / "live.txt"
    monkeypatch.setattr(FL, "ROOT", tmp_path)
    monkeypatch.setattr(FL.era_mod, "SEAL_LIFTED", None)  # tests the sealed branch
    line = FL.live_cut(trades_csv=trades, out=out)
    detail = out.read_text()
    assert "on-list closes 1" in detail and "off-list closes 1" in detail
    assert "withheld" in detail
    for text in (line, detail):
        assert "123" not in text and "67" not in text and "999" not in text
    # The report line is copied into tracked files: it names the file only.
    assert not any(ch.isdigit() for ch in line.replace(str(out), ""))


# ── gaps the pre-run review named ───────────────────────────────────────────

def test_boot_ci_uses_the_protocol_index_convention():
    xs = [(f"d{i}", float(i)) for i in range(20)]
    lo, hi = FL.boot_ci(xs, n=400, seed=7)
    import random
    import statistics
    rng = random.Random(7)
    vals = [x for _d, x in xs]
    means = sorted(statistics.fmean(rng.choices(vals, k=20)) for _ in range(400))
    assert (lo, hi) == (means[int(0.025 * 400)], means[int(0.975 * 400)])


def test_gf5_boundary_is_thirty_dates():
    def book(n):
        rows = []
        for i in range(n):
            d = f"2025-{i // 28 + 1:02d}-{i % 28 + 1:02d}"
            rows += [row(d, "MU", R=0.1), row(d, "JPM", R=0.0)]
        return rows
    assert FL.grade(book(29), FL.LW, boot_n=50, draws=10)["c2"] is None
    assert FL.grade(book(30), FL.LW, boot_n=50, draws=10)["c2"] is not None


def test_criterion_4_fails_on_a_window_sign_flip():
    # The whole gain sits in March 2025; without that window it turns negative.
    rows = []
    for i in range(1, 11):
        d = f"2025-03-{i:02d}"
        rows += [row(d, "MU", R=5.0), row(d, "JPM", R=-5.0)]
    for i in range(1, 21):
        d = f"2025-06-{i:02d}"
        rows += [row(d, "MU", R=-0.2), row(d, "JPM", R=0.2)]
    g = FL.grade(rows, FL.LW, boot_n=100, draws=20)
    assert g["gain"] > 0 and g["windows"]["ex_2025_mar_apr"] < 0 and g["c4"] is False


def test_criterion_4_ignores_a_year_with_fewer_than_ten_positions():
    rows = []
    for i in range(1, 21):                       # 2025: 20 positions, list wins
        d = f"2025-06-{i:02d}"
        rows += [row(d, "MU", R=1.0), row(d, "JPM", R=-1.0)]
    for i in range(1, 4):                        # 2026: 3 positions, list loses
        d = f"2026-06-{i:02d}"
        rows += [row(d, "MU", R=-1.0), row(d, "JPM", R=1.0)]
    g = FL.grade(rows, FL.LW, boot_n=100, draws=20)
    assert g["years"]["2026"][0] == 3 and g["years"]["2026"][1] < 0
    assert g["c4"] is True


def test_criterion_5_rebuilds_arm_f_and_leaves_arm_c_alone():
    rows = []
    for i in range(1, 6):
        d = f"2025-06-{i:02d}"
        rows += [row(d, "NVDA", R=2.0), row(d, "MU", R=-1.0), row(d, "JPM", R=0.0),
                 row(d, "XOM", R=0.0), row(d, "ZZZ", R=0.0)]
    g = FL.grade(rows, FL.LW, boot_n=100, draws=20)
    assert g["largest"] == "MU"                  # tie at 5 positions: the earlier name
    # Without MU, ARM F is NVDA alone (+2.0); ARM C still holds JPM, MU, NVDA (+1/3).
    assert g["gain_ex"] == pytest.approx(2.0 - 1.0 / 3.0)


def test_complete_prefix_ignores_a_pending_row_no_arm_can_take():
    rows = [row("2027-01-01", "MU"), row("2027-01-02", "MU"),
            row("2027-01-02", "JPM", tier="C", pending=True), row("2027-01-03", "MU")]
    assert len(FL.complete_prefix(rows)) == 3


def test_pending_displaced_counts_picks_and_dates_only():
    rows = [row("2026-01-05", "MU", pending=True), row("2026-01-05", "GLD"),
            row("2026-01-06", "JPM", pending=True), row("2026-01-06", "MU")]
    assert FL.pending_displaced(rows) == (2, 2)          # ARM C
    assert FL.pending_displaced(rows, FL.LW) == (1, 1)   # ARM F


def test_an_unregistered_era_is_refused(monkeypatch, capsys):
    monkeypatch.setattr(FL, "load_book", lambda **kw: ([], {"era": "v5", "n_dates": 0}))
    assert FL.main([]) == 3
    assert "GF1 FAIL" in capsys.readouterr().out


def test_the_cleaner_pins_the_forward_read():
    from scripts import clean_study_output as C
    assert FL.FORWARD_JSON.name in C.CODE_INPUTS
