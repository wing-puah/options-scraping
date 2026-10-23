"""baseline_read — research/pre-registrations/f1_selection/regime/baseline_read.md.

Pins the registered definitions (metrics, the trailing midrank percentile, HEAVY
at 0.80), the verdict words and their sign flip, the Holm gating, the READ table,
the refusals (era exit 2, header and GE exit 3), the seal, FORWARD, and that a
planted shift is detected. Every fixture is synthetic; nothing reads the real
exports.
"""
from __future__ import annotations

import ast
import csv
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from lib.baseline import BASELINE_COLUMNS, WINDOW_ROWS
from scripts.backtest_study.f1_selection.regime import baseline_read as B
from scripts.backtest_study.f1_selection.regime import market_read as MR
from scripts.backtest_study.lib import era

SRC = Path(B.__file__).read_text()


# ── constants, fixed by the registration ────────────────────────────────────

def test_window_is_the_production_window():
    assert B.W == WINDOW_ROWS == 60
    assert B.WINDOW_MIN == 50


def test_block_and_horizon_are_market_reads():
    assert B.BLOCK == MR.BLOCK == 21
    assert B.H == MR.H == 21


def test_registered_constants():
    assert B.THRESH == 0.80
    assert (B.BOOT_N, B.SEED) == (10_000, 20261023)
    assert (B.ARM_DATES, B.ARM_BLOCKS) == (20, 12)
    assert (B.FWD_DATES, B.FWD_BLOCKS) == (20, 6)
    assert B.GC_MIN_DATES == 300
    assert (B.GP_SIMS, B.GP_SEED, B.GP_DRAWS, B.GP_SHIFT, B.GP_PASS) == (
        200, 20261024, 2_000, 0.03, 0.80)
    assert (B.POWER_SIMS, B.POWER_SEED) == (100, 20261025)
    assert B.POWER_SHIFTS == (-0.03, -0.02, -0.01, 0.01, 0.02, 0.03)
    assert B.GRID_THRESH == (0.70, 0.80, 0.90) and B.GRID_WINDOWS == (40, 60, 90)
    assert [B.grid_need(w) for w in B.GRID_WINDOWS] == [34, 50, 75]
    assert B.CONTRASTS == (("P1", "M1", "ret21"), ("P2", "M1", "dd21"),
                           ("S1", "M2", "ret21"), ("S2", "M2", "dd21"),
                           ("S3", "M3", "ret21"), ("S4", "M3", "dd21"))


def test_designed_refusal_codes_are_a_literal():
    """run.py reads this by `ast`, so it must be a literal module-level set."""
    for node in ast.parse(SRC).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
                for t in node.targets):
            assert ast.literal_eval(node.value) == {2, 3}
            return
    pytest.fail("DESIGNED_REFUSAL_EXIT_CODES not declared")


def test_seal_is_passed_and_never_bypassed():
    assert "drop_sealed" in SRC
    assert "sealed_read" not in SRC


def test_market_read_helpers_are_imported_not_copied():
    for name in ("def load_calendar", "def outcomes", "def mean_diff", "def summarize",
                 "def lag_bin", "class Draws"):
        assert name not in SRC, name


# ── the trailing percentile ─────────────────────────────────────────────────

def test_midrank_ties_count_half():
    assert B.midrank_share([1.0, 2.0, 2.0, 3.0], 2.0) == 0.5
    assert B.midrank_share([1.0, 1.0, 1.0], 1.0) == 0.5
    assert B.midrank_share([1.0, 2.0], 5.0) == 1.0
    assert B.midrank_share([1.0, 2.0], 0.0) == 0.0


def test_window_is_strictly_prior_and_exactly_w_rows():
    vals = [float(x) for x in range(61)]
    # Today (60) is above all 60 prior rows; were it in its own window this
    # would read (60 + 0.5) / 61.
    assert B.trailing_pct(vals, 60) == 1.0
    # Row 0 (a huge value) falls outside row 61's window of rows 1..60.
    vals = [1e9] + [0.0] * 60 + [0.5]
    assert B.trailing_pct(vals, 61) == 1.0


def test_no_lookahead():
    rng = np.random.default_rng(7)
    vals = list(rng.normal(size=200))
    before = [B.trailing_pct(vals, j) for j in range(200)]
    for j in (60, 99, 150):
        changed = vals[:j + 1] + list(rng.normal(size=199 - j) * 100)
        after = [B.trailing_pct(changed, k) for k in range(j + 1)]
        assert after == before[:j + 1]


def test_first_w_rows_are_out():
    vals = [float(x) for x in range(100)]
    assert all(B.trailing_pct(vals, j) is None for j in range(60))
    assert B.trailing_pct(vals, 60) is not None


def test_window_needs_fifty_numeric_values():
    vals = [1.0] * 70
    for j in range(5, 15):          # 10 blanks inside row 65's window (rows 5..64)
        vals[j] = None
    assert B.trailing_pct(vals, 65) is not None
    vals[15] = None                  # 11 blanks: 49 numeric
    assert B.trailing_pct(vals, 65) is None


def test_blank_today_is_out():
    vals = [1.0] * 61
    vals[60] = None
    assert B.trailing_pct(vals, 60) is None


def test_expanding_twin_needs_sixty_prior_values():
    vals = [float(x) for x in range(100)]
    assert B.expanding_pct(vals, 59) is None
    assert B.expanding_pct(vals, 60) == 1.0
    assert B.expanding_pct(vals, 99) == 1.0


def test_heavy_is_inclusive_at_080():
    assert B.is_heavy(0.80) and not B.is_rest(0.80)
    assert B.is_rest(0.7999) and not B.is_heavy(0.7999)
    assert not B.is_heavy(None) and not B.is_rest(None)


# ── the metrics ─────────────────────────────────────────────────────────────

def _cells(**kw):
    base = {"spy_put_prem": "30", "qqq_put_prem": "20", "iwm_put_prem": "10",
            "spy_call_prem": "20", "qqq_call_prem": "10", "iwm_call_prem": "10",
            "etfs_cp_prem": "1.5", "stocks_pct_put_dom": "0.42", "stocks_cp_prem": "3"}
    base.update(kw)
    return base


def test_m1_is_the_index_put_share():
    assert B.m1(_cells()) == pytest.approx(60 / 100)


@pytest.mark.parametrize("col", ["spy_put_prem", "qqq_call_prem", "iwm_put_prem"])
def test_m1_blank_when_any_of_six_blank(col):
    assert B.m1(_cells(**{col: ""})) is None
    assert B.m1(_cells(**{col: "n/a"})) is None


def test_m1_blank_on_a_zero_denominator():
    zero = {c: "0" for c in ("spy_put_prem", "qqq_put_prem", "iwm_put_prem",
                             "spy_call_prem", "qqq_call_prem", "iwm_call_prem")}
    assert B.m1(_cells(**zero)) is None


def test_m2_is_one_over_one_plus_cp():
    assert B.m2(_cells()) == pytest.approx(1 / 2.5)
    assert B.m2(_cells(etfs_cp_prem="0")) == 1.0
    assert B.m2(_cells(etfs_cp_prem="")) is None
    assert B.m2(_cells(etfs_cp_prem="-1")) is None


def test_m3_m4_m5():
    assert B.m3(_cells()) == 0.42
    assert B.m3(_cells(stocks_pct_put_dom="")) is None
    assert B.m4(_cells()) == pytest.approx(0.25)
    assert B.m5(_cells()) == 60.0
    assert B.m5(_cells(qqq_put_prem="")) is None


# ── verdict words ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("key,lo,hi,word", [
    ("ret21", -2.0, -1.0, "HEDGE-WARNS"),
    ("ret21", 1.0, 2.0, "HEDGE-CONTRARIAN"),
    ("ret21", -1.0, 1.0, "NULL"),
    ("dd21", 1.0, 2.0, "HEDGE-WARNS"),          # the signs flip on drawdown depth
    ("dd21", -2.0, -1.0, "HEDGE-CONTRARIAN"),
    ("dd21", -1.0, 1.0, "NULL"),
])
def test_ci_word_signs(key, lo, hi, word):
    assert B.ci_word(lo, hi, True, key) == word


@pytest.mark.parametrize("key", ["ret21", "dd21"])
def test_ci_word_underpowered(key):
    assert B.ci_word(-2.0, -1.0, False, key) == "UNDERPOWERED"
    assert B.ci_word(float("nan"), 1.0, True, key) == "UNDERPOWERED"


@pytest.mark.parametrize("w1,w2,read", [
    ("UNDERPOWERED", "HEDGE-WARNS", "UNDERPOWERED"),
    ("HEDGE-WARNS", "UNDERPOWERED", "UNDERPOWERED"),
    ("NULL", "NULL", "NO-FORECAST"),
    ("HEDGE-WARNS", "NULL", "WARNS"),
    ("NULL", "HEDGE-WARNS", "WARNS"),
    ("HEDGE-WARNS", "HEDGE-WARNS", "WARNS"),
    ("HEDGE-CONTRARIAN", "NULL", "CONTRARIAN"),
    ("HEDGE-CONTRARIAN", "HEDGE-CONTRARIAN", "CONTRARIAN"),
    ("HEDGE-WARNS", "HEDGE-CONTRARIAN", "MIXED"),
    ("HEDGE-CONTRARIAN", "HEDGE-WARNS", "MIXED"),
])
def test_read_table(w1, w2, read):
    assert B.read_word(w1, w2) == read


def test_forward_read_maps_still_open():
    assert B.forward_read("STILL-OPEN", "NULL") == "STILL-OPEN"
    assert B.forward_read("NULL", "NULL") == "NO-FORECAST"
    assert B.forward_read("HEDGE-WARNS", "NULL") == "WARNS"


def test_holm_turns_a_ci_word_into_null():
    assert B.holm_word("HEDGE-WARNS", 0.06) == "NULL"
    assert B.holm_word("HEDGE-CONTRARIAN", 0.05) == "NULL"
    assert B.holm_word("HEDGE-WARNS", 0.049) == "HEDGE-WARNS"
    assert B.holm_word("UNDERPOWERED", 0.001) == "UNDERPOWERED"
    # Two CI words at p 0.03 and 0.04: Holm m = 2 lifts both to 0.06.
    adj = MR.holm({"P1": 0.03, "P2": 0.04})
    assert [B.holm_word("HEDGE-WARNS", adj[k][0]) for k in ("P1", "P2")] == ["NULL", "NULL"]


# ── synthetic populations ───────────────────────────────────────────────────

def _recs(n_blocks=40, heavy_every=4, effect=0.0, noise=0.005, seed=3,
          metrics=("M1", "M2", "M3")):
    """One rec per session; every `heavy_every`-th date HEAVY on each metric;
    HEAVY dates carry `effect` on ret21 and `-effect` on dd21."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_blocks * 21):
        heavy = i % heavy_every == 0
        p = 0.9 if heavy else 0.3
        ret = rng.normal(0.0, noise) + (effect if heavy else 0.0)
        dd = abs(rng.normal(0.02, noise)) - (effect if heavy else 0.0)
        out.append(B.Rec(f"d{i:05d}", i, i, "RETRO", "BULL", {m: 0.5 for m in metrics},
                         {m: p for m in metrics}, {"ret21": ret, "dd21": dd}))
    return out


def test_grade_reads_a_strong_planted_effect(monkeypatch):
    pop = B.BPop(_recs(effect=-0.05), n=500)
    g = B.grade(pop, {m: True for m in B.GRADED}, gp_pass=True)
    assert g["P1"].word == "HEDGE-WARNS" and g["P2"].word == "HEDGE-WARNS"
    assert B.read_word(g["P1"].word, g["P2"].word) == "WARNS"
    assert all(g[s].word == "HEDGE-WARNS" for s in ("S1", "S3"))


def test_gp_failure_makes_the_primaries_underpowered():
    pop = B.BPop(_recs(effect=-0.05), n=500)
    g = B.grade(pop, {m: True for m in B.GRADED}, gp_pass=False)
    assert g["P1"].word == g["P2"].word == "UNDERPOWERED"
    assert g["S1"].word == "HEDGE-WARNS"          # GP gates P1 and P2 only


def test_gc_failure_makes_that_metric_underpowered():
    pop = B.BPop(_recs(effect=-0.05), n=500)
    g = B.grade(pop, {"M1": True, "M2": False, "M3": True}, gp_pass=True)
    assert g["S1"].word == g["S2"].word == "UNDERPOWERED"
    assert g["S3"].word == "HEDGE-WARNS"


def test_floors_unmet_is_underpowered():
    pop = B.BPop(_recs(n_blocks=8, effect=-0.05), n=300)     # 8 blocks < 12
    g = B.grade(pop, {m: True for m in B.GRADED}, gp_pass=True)
    assert g["P1"].word == "UNDERPOWERED"


def test_planted_shift_is_detected():
    recs = _recs(effect=0.0)
    warn = B.planted_power(recs, -0.03, sims=20, seed=1, draws=300)
    assert warn.ret >= 0.95 and warn.dd >= 0.95
    assert warn.ret_point == pytest.approx(-0.03, abs=0.005)
    contra = B.planted_power(recs, 0.03, sims=20, seed=1, draws=300)
    assert contra.ret >= 0.95 and contra.dd >= 0.95
    tiny = B.planted_power(recs, -1e-6, sims=20, seed=1, draws=300)
    assert tiny.ret <= 0.2 and tiny.dd <= 0.2


def test_planted_power_keeps_each_blocks_heavy_count():
    """The shuffle is within blocks, so the HEAVY arm's dates per block never move."""
    recs = _recs(effect=0.0)
    a = B.planted_power(recs, -0.03, sims=5, seed=11, draws=200)
    b = B.planted_power(recs, -0.03, sims=5, seed=11, draws=200)
    assert a == b                                 # seeded


# ── build, seal, GE, FORWARD on a synthetic export ──────────────────────────

class _FakeLabeler:
    def label(self, d):
        return ("BULL", "L-VOL", True, d)

    @classmethod
    def from_csv(cls, _path):
        return cls()


def _sessions(start: date, n: int) -> list[str]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _baseline_rows(dates: list[str], seed: int = 5) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for d in dates:
        r = {c: "" for c in BASELINE_COLUMNS}
        for c in ("spy", "qqq", "iwm", "hyg", "tlt", "gld"):
            r[f"{c}_call_prem"] = str(int(rng.integers(1_000, 9_000)))
            r[f"{c}_put_prem"] = str(int(rng.integers(1_000, 9_000)))
        r.update(date=d, etfs_cp_prem=f"{rng.uniform(0.3, 2):.4f}",
                 stocks_cp_prem=f"{rng.uniform(0.5, 3):.4f}",
                 stocks_pct_put_dom=f"{rng.uniform(0.1, 0.9):.3f}",
                 created_datetime="2026-07-01 10:00:00")
        rows.append(r)
    return rows


def _calendar(dates: list[str], seed: int = 9):
    rng = np.random.default_rng(seed)
    closes = 400 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
    return MR.Calendar.from_pairs(zip(dates, closes))


def _write(path: Path, fields, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_seal_withholds_rows_from_its_start(monkeypatch):
    days = _sessions(date(2024, 1, 2), 130)
    cal = _calendar(days)
    rows = _baseline_rows(days[5:105])
    monkeypatch.setattr(era, "SEAL_START", days[85])
    b = B.build(rows, cal, _FakeLabeler())
    assert b.seal == {"rows": 20, "dates": 20, "reader": None}
    assert all(r.date < days[85] for r in b.recs) and len(b.recs) == 80
    assert "withheld 20 rows" in era.seal_line(b.seal)


def test_forward_is_still_open_while_sealed(monkeypatch, capsys):
    days = _sessions(date(2024, 1, 2), 130)
    cal = _calendar(days)
    monkeypatch.setattr(era, "SEAL_START", days[85])
    b = B.build(_baseline_rows(days[5:105]), cal, _FakeLabeler())
    out = B.report_forward(b)
    assert out["read"] == out["p1"] == out["p2"] == "STILL-OPEN"
    assert "forward: STILL-OPEN" in capsys.readouterr().out


def test_forward_below_its_floor_is_still_open_once_lifted(monkeypatch):
    days = _sessions(date(2024, 1, 2), 160)
    cal = _calendar(days)
    monkeypatch.setattr(era, "SEAL_START", days[100])
    monkeypatch.setattr(era, "SEAL_LIFTED", "2027-01-01")
    monkeypatch.setattr(B, "BOOT_N", 300)
    b = B.build(_baseline_rows(days[5:120]), cal, _FakeLabeler())
    assert b.seal["rows"] == 0
    out = B.report_forward(b)
    assert out["n"] > 0
    assert out["p1"] == out["p2"] == out["read"] == "STILL-OPEN"   # never UNDERPOWERED


def test_ge_refuses_an_open_in_sample_window():
    days = _sessions(date(2024, 1, 2), 100)
    cal = _calendar(days[:95])                    # the table stops 4 sessions after the data
    b = B.build(_baseline_rows(days[5:90]), cal, _FakeLabeler())
    with pytest.raises(B.Refused) as exc:
        B.ge_windows(B.in_sample_candidates(b), cal)
    assert exc.value.code == 3


def test_outcomes_never_read_a_close_at_or_before_the_date():
    days = _sessions(date(2024, 1, 2), 60)
    cal = _calendar(days)
    i = 20
    extra = B.extra_outcomes(cal, i)
    c = cal.close
    assert extra["ret0"] == pytest.approx(math.log(c[i] / c[i - 1]))
    assert extra["ret_prev5"] == pytest.approx(math.log(c[i] / c[i - 5]))
    expect = -min(0.0, c[i + 2:i + 23].min() / c[i + 1] - 1)
    assert extra["dd21_next"] == pytest.approx(expect)


# ── refusals ────────────────────────────────────────────────────────────────

def test_header_refusal_exit_3(tmp_path, monkeypatch):
    bad = tmp_path / "bad.csv"
    _write(bad, BASELINE_COLUMNS[:-1], [])
    with pytest.raises(B.Refused) as exc:
        B.load_baseline(bad)
    assert exc.value.code == 3
    swapped = tmp_path / "swapped.csv"
    cols = list(BASELINE_COLUMNS)
    cols[1], cols[2] = cols[2], cols[1]
    _write(swapped, cols, [])
    with pytest.raises(B.Refused) as exc:
        B.load_baseline(swapped)
    assert exc.value.code == 3
    with pytest.raises(B.Refused) as exc:
        B.load_baseline(tmp_path / "absent.csv")
    assert exc.value.code == 3
    monkeypatch.delenv("STUDY_ERA", raising=False)
    monkeypatch.setattr(B, "BASELINE_CSV", bad)
    assert B.main([]) == 3


@pytest.mark.parametrize("asked", ["v3", "v4"])
def test_any_era_but_current_exits_2(monkeypatch, capsys, asked):
    monkeypatch.setenv("STUDY_ERA", asked)
    assert B.main([]) == 2
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("REFUSED")


def test_current_era_passes_the_era_check(monkeypatch):
    monkeypatch.setenv("STUDY_ERA", "current")
    B.check_era()
    monkeypatch.delenv("STUDY_ERA")
    B.check_era()


# ── end to end, synthetic, small draw counts ────────────────────────────────

def _synthetic_run(tmp_path, monkeypatch, capsys) -> str:
    days = _sessions(date(2024, 1, 2), 460)
    rows = _baseline_rows(days[5:425])
    base = tmp_path / "analysis - BaselineDaily.csv"
    _write(base, BASELINE_COLUMNS, rows)
    cal = _calendar(days)
    table = tmp_path / "spy_vix_daily_full.csv"
    _write(table, ["date", "spy_close"],
           [{"date": d, "spy_close": f"{c:.4f}"} for d, c in zip(cal.dates, cal.close)])
    monkeypatch.delenv("STUDY_ERA", raising=False)
    monkeypatch.setattr(B, "BASELINE_CSV", base)
    monkeypatch.setattr(B, "MECH_TABLE_CSV", table)
    monkeypatch.setattr(B, "MechLabeler", _FakeLabeler)
    for name, value in (("BOOT_N", 200), ("GP_SIMS", 5), ("GP_DRAWS", 100),
                        ("POWER_SIMS", 3)):
        monkeypatch.setattr(B, name, value)
    assert B.main([]) == 0
    return capsys.readouterr().out


def test_end_to_end_prints_every_section_and_the_banner(tmp_path, monkeypatch, capsys):
    out = _synthetic_run(tmp_path, monkeypatch, capsys)
    assert "era: current (inputs are unversioned)" in out
    assert "population: BaselineDaily (unversioned tab), 420 rows," in out
    assert "\ngit: " in out and "inputs read:" in out
    for title in ("POPULATION AND DROPS", "GATES", "P1, P2, S1-S4", "DOSE", "RHO", "LEVEL",
                  "GRID", "MECH and HP-MECH", "CUTS", "HALVES", "MODE and BOUNDARY",
                  "H5, H10, NEXT, B42", "TAIL and CONC", "YEAR", "M4 and M5", "FORWARD"):
        assert title in out, title
    verdict = out.split("\nVERDICT\n", 1)[1].splitlines()[1:]
    assert len(verdict) < 40
    banner = [ln.strip() for ln in verdict if ln.strip().startswith(">>>")]
    assert [b.split(" (")[0] for b in banner] == [
        ">>> baseline_read P1", ">>> baseline_read P2", ">>> baseline_read READ",
        ">>> baseline_read SECONDARY", ">>> baseline_read FORWARD"]
    assert banner[-1].endswith("STILL-OPEN <<<")
    # VERDICT is the last banner-titled section, so summary.py quotes it.
    assert out.rstrip().endswith("Nothing ships from this study (baseline_read.md).")


def test_end_to_end_is_seeded(tmp_path, monkeypatch, capsys):
    a = _synthetic_run(tmp_path, monkeypatch, capsys)
    b = _synthetic_run(tmp_path, monkeypatch, capsys)
    assert a == b
