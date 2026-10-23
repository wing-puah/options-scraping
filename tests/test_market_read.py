"""market_read — the registered parse, lag bins, outcomes, blocks, verdict words,
duplicate rule, seal and P3's sign (research/pre-registrations/f1_selection/regime/market_read.md)."""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study.f1_selection.regime import market_read as M
from scripts.backtest_study.lib import era


# ── tokeniser ────────────────────────────────────────────────────────────────

def test_range_head_whose_prose_says_bear_reads_range():
    lb = M.parse_label("RANGE + E-VOL + RISK-OFF + HP — puts pile up; a BEAR turn is possible")
    assert (lb.dir, lb.vol, lb.risk, lb.hp, lb.transition) == ("RANGE", "E-VOL", "RISK-OFF", True, False)
    assert lb.head == "RANGE + E-VOL + RISK-OFF + HP"


def test_range_to_bear_reads_range_and_is_a_transition():
    lb = M.parse_label("RANGE-to-BEAR + E-VOL + RISK-OFF + HP — two call blocks")
    assert lb.dir == "RANGE" and lb.transition
    assert lb.vol == "E-VOL"


def test_unclosed_parenthesis_ends_the_head():
    lb = M.parse_label("BULL + L-VOL (low confidence")
    assert lb.head == "BULL + L-VOL"
    assert (lb.dir, lb.vol) == ("BULL", "L-VOL")


def test_vol_token_only_in_prose_is_no_vol():
    lb = M.parse_label("RANGE + RISK-OFF. VIX is E-VOL-like today")
    assert lb.dir == "RANGE" and lb.vol is None and lb.risk == "RISK-OFF"


def test_missing_vol_and_risk():
    lb = M.parse_label("BULL: indexes at highs")
    assert (lb.dir, lb.vol, lb.risk, lb.hp) == ("BULL", None, None, False)


@pytest.mark.parametrize("raw", [float("nan"), None, "", "nan", "no direction word — BULL later"])
def test_no_direction_is_other(raw):
    assert M.parse_label(raw).dir == "OTHER"


def test_separators_dash_and_colon():
    assert M.label_head("BEAR + H-VOL - prose") == "BEAR + H-VOL"
    assert M.label_head("BEAR + H-VOL: prose") == "BEAR + H-VOL"
    assert M.label_head("BEAR + H-VOL. Prose") == "BEAR + H-VOL"


def test_whole_words_only():
    assert M.parse_label("BEARISH tape + L-VOL").dir == "OTHER"
    assert M.parse_label("RISK-ON BULL + C-VOL").dir == "BULL"
    assert M.parse_label("BULL + C-VOL + RISK-ON").vol == "C-VOL"
    assert not M.parse_label("BULL + HPQ").hp


# ── lag bins ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("created,expected", [
    ("2026-08-11", "LIVE"),            # lag 0
    ("2026-08-12", "LIVE"),            # lag 1
    ("2026-08-13", "NEAR"),            # lag 2
    ("2026-08-18", "NEAR"),            # lag 7
    ("2026-08-19", "RETRO"),           # lag 8
    ("2026-08-12 23:59:59", "LIVE"),   # timestamp suffix is ignored
    ("2026-08-10", "UNKNOWN"),         # negative
    ("", "UNKNOWN"),
    (None, "UNKNOWN"),
])
def test_lag_bin_edges(created, expected):
    assert M.lag_bin(created, "2026-08-11") == expected


# ── outcomes ─────────────────────────────────────────────────────────────────

def _cal(closes, first=date(2025, 1, 1)):
    """One session per calendar day from `first`; the dates only need to sort."""
    dates = [(first + timedelta(days=k)).isoformat() for k in range(len(closes))]
    return M.Calendar.from_pairs(list(zip(dates, closes)))


def test_outcomes_on_a_synthetic_series():
    closes = [100.0] + [100.0 - k for k in range(1, 11)] + [95.0] * 30
    cal = _cal(closes)
    out = M.outcomes(cal, 0)
    assert out["ret5"] == pytest.approx(math.log(95 / 100))
    assert out["ret10"] == pytest.approx(math.log(90 / 100))
    assert out["ret21"] == pytest.approx(math.log(95 / 100))
    assert out["mae21"] == pytest.approx(-0.10)
    assert out["dd21"] == pytest.approx(0.10)
    lr = np.diff(np.log(np.array(closes[:22])))
    assert out["rv21"] == pytest.approx(np.std(lr, ddof=1) * 100)
    assert out["ret21_next"] == pytest.approx(math.log(closes[22] / closes[1]))


def test_mae_is_clipped_at_zero_and_dd_is_its_negative():
    cal = _cal([100.0 + k for k in range(40)])
    out = M.outcomes(cal, 0)
    assert out["mae21"] == 0.0 and out["dd21"] == 0.0
    assert out["dd21"] == -out["mae21"]


def test_causality_uses_only_later_closes():
    # A crash ON the signal date's own close and before it never enters the window.
    closes = [50.0, 100.0] + [100.0] * 30
    cal = _cal(closes)
    out = M.outcomes(cal, 1)
    assert out["mae21"] == 0.0 and out["ret21"] == 0.0


def test_window_past_the_end_is_dropped():
    cal = _cal([100.0] * 25)
    out = M.outcomes(cal, 10)
    assert "ret5" in out and "ret10" in out
    assert "ret21" not in out and "dd21" not in out and "rv21" not in out
    assert "ret21_next" not in out


class _Lab:
    """Fake MechLabeler: every session labelled BULL L-VOL, mapped to itself."""

    def __init__(self, mapping=None):
        self.mapping = mapping or {}

    def label(self, d):
        return self.mapping.get(d, ("BULL", "L-VOL", True, d))


def _row(d, regime="BULL + L-VOL + RISK-ON — x", created="2026-08-20 10:00:00"):
    return {"date": d, "ticker": "MARKET", "regime": regime, "created_datetime": created}


def test_off_calendar_date_is_dropped_never_mapped():
    cal = _cal([100.0] * 60)
    rows = [_row(cal.dates[3]), _row("2024-12-31")]     # before the table: not a session
    b = M.build(rows, cal, _Lab())
    assert [r.date for r in b.recs] == [cal.dates[3]]
    assert b.counts["off_calendar"] == 1 and b.off_calendar == ["2024-12-31"]


def test_label_mapped_to_another_date_is_dropped():
    cal = _cal([100.0] * 60)
    d = cal.dates[5]
    b = M.build([_row(d)], cal, _Lab({d: ("BULL", "L-VOL", True, cal.dates[4])}))
    assert not b.recs and b.counts["no_mech"] == 1


# ── blocks ───────────────────────────────────────────────────────────────────

def test_block_ids():
    assert [M.block_of(i) for i in (0, 20, 21, 41, 42)] == [0, 0, 1, 1, 2]
    assert [M.block_of(i, 42) for i in (0, 41, 42, 83, 84)] == [0, 0, 1, 1, 2]


def test_draws_resample_as_many_blocks_as_the_population_holds():
    d = M.Draws([0, 0, 1, 3], n=50, seed=1)
    assert d.k == 3 and d.W.shape == (50, 3)
    assert np.all(d.W.sum(axis=1) == 3)


# ── verdict words ────────────────────────────────────────────────────────────

def test_word():
    assert M.word(0.1, 0.2, True) == "SUPPORTED"
    assert M.word(-0.2, -0.1, True) == "CONTRARY"
    assert M.word(-0.1, 0.1, True) == "NULL"
    assert M.word(0.1, 0.2, False) == "UNDERPOWERED"
    assert M.word(float("nan"), 0.2, True) == "UNDERPOWERED"


@pytest.mark.parametrize("w1,w2,expected", [
    ("CONTRARY", "UNDERPOWERED", "CONTRARY"),      # CONTRARY wins before UNDERPOWERED
    ("UNDERPOWERED", "CONTRARY", "CONTRARY"),
    ("SUPPORTED", "UNDERPOWERED", "UNDERPOWERED"),
    ("SUPPORTED", "SUPPORTED", "MODEL-ADDS"),
    ("SUPPORTED", "NULL", "MECH-COVERS"),
    ("NULL", "SUPPORTED", "INCREMENTAL-ONLY"),
    ("NULL", "NULL", "NO-FORECAST"),
])
def test_read_table_order(w1, w2, expected):
    assert M.read_word(w1, w2) == expected


def test_forward_read_maps_still_open():
    assert M.forward_read("STILL-OPEN", "SUPPORTED") == "STILL-OPEN"
    assert M.forward_read("SUPPORTED", "NULL") == "MECH-COVERS"


def test_holm_demotes_an_unadjusted_p3_word():
    assert M.holm_word("SUPPORTED", 0.06) == "NULL"
    assert M.holm_word("CONTRARY", 0.01) == "CONTRARY"
    assert M.holm_word("UNDERPOWERED", 1.0) == "UNDERPOWERED"


def test_p4_word():
    flag = M.Result(point=0.02, lo=0.01, hi=0.03)
    gauge = M.Result(point=0.0)
    assert M.p4_word(False, flag, gauge, 0.01) == "STILL-OPEN"
    assert M.p4_word(True, flag, gauge, 0.01) == "RECALL-FLAGGED"
    assert M.p4_word(True, flag, M.Result(point=0.05), 0.01) == "RECALL-NOT-SHOWN"
    assert M.p4_word(True, flag, gauge, 0.06) == "RECALL-NOT-SHOWN"


# ── duplicates ───────────────────────────────────────────────────────────────

def test_duplicate_dates_that_disagree_are_ambiguous():
    rows = [_row("2026-02-19", "BEAR + E-VOL — a"), _row("2026-02-19", "RANGE + E-VOL — b"),
            _row("2026-02-20", "BULL + L-VOL — c"), _row("2026-02-20", "BULL + H-VOL — d"),
            _row("2026-02-23", "RANGE + L-VOL — e")]
    kept, findings = M.dedupe(rows)
    assert sorted(r["date"] for r in kept) == ["2026-02-20", "2026-02-23"]
    assert {f["date"]: f["agree"] for f in findings} == {"2026-02-19": False, "2026-02-20": True}
    assert next(r for r in kept if r["date"] == "2026-02-20")["regime"].endswith("c")


# ── the seal ─────────────────────────────────────────────────────────────────

def test_sealed_dates_are_withheld(monkeypatch):
    cal = _cal([100.0] * 80)
    monkeypatch.setattr(era, "SEAL_START", cal.dates[10])
    monkeypatch.setattr(era, "SEAL_LIFTED", None)
    rows = [_row(cal.dates[k]) for k in (5, 9, 10, 30)]
    b = M.build(rows, cal, _Lab())
    assert [r.date for r in b.recs] == [cal.dates[5], cal.dates[9]]
    assert b.seal["rows"] == 2
    assert all(r.scope == "in" for r in b.recs)


def test_lifted_seal_reads_every_date(monkeypatch):
    cal = _cal([100.0] * 80)
    monkeypatch.setattr(era, "SEAL_START", cal.dates[10])
    monkeypatch.setattr(era, "SEAL_LIFTED", cal.dates[60])
    b = M.build([_row(cal.dates[k]) for k in (5, 30)], cal, _Lab())
    assert [r.scope for r in b.recs] == ["in", "gap"]


# ── P3's sign ────────────────────────────────────────────────────────────────

def test_p3_is_positive_when_spy_falls_after_e_vol_dates(monkeypatch):
    monkeypatch.setattr(era, "SEAL_LIFTED", None)
    n = 1500
    closes = np.full(n, 100.0)
    e_dates = list(range(0, n - 60, 50))
    for i in e_dates:                       # a 10-session dip, recovered by i + 11
        closes[i + 1:i + 11] = 92.0
    cal = _cal(closes, date(2018, 1, 1))
    recs = []
    for i in e_dates:
        for j, vol in ((i, "E-VOL"), (i + 25, "L-VOL")):
            lab = M.parse_label(f"RANGE + {vol} + RISK-OFF — x")
            mvol = "L-VOL" if (j // 100) % 2 == 0 else "H-VOL"   # both strata hold both arms
            recs.append(M.Rec(cal.dates[j], "", lab, "RETRO", j, "RANGE", mvol, M.outcomes(cal, j)))
    pop = M.Pop(recs)
    res = M.p3(pop)
    assert set(res.weights) == {"L-VOL", "H/E-VOL"}
    assert res.point > 0 and res.lo > 0
    assert M.p3_unstratified(pop).point == pytest.approx(0.08)


def test_p1_points_the_right_way():
    """BULL dates followed by a rise give a positive P1."""
    n = 900
    closes = 100.0 * np.exp(np.cumsum(np.where((np.arange(n) // 30) % 2 == 0, 0.002, -0.002)))
    cal = _cal(closes, date(2018, 1, 1))
    recs = []
    for i in range(0, n - 30, 5):
        rising = (i // 30) % 2 == 0 and (i % 30) <= 5
        falling = (i // 30) % 2 == 1 and (i % 30) <= 5
        if not (rising or falling):
            continue
        lab = M.parse_label("BULL + L-VOL" if rising else "RANGE + L-VOL")
        recs.append(M.Rec(cal.dates[i], "", lab, "RETRO", i, "RANGE", "L-VOL", M.outcomes(cal, i)))
    assert M.p1(M.Pop(recs)).point > 0
