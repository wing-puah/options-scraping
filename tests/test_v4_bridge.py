"""Tests for the v4 emission-composition bridge.

This study cannot run for real until v4 accumulates ~20 dates, so its machinery
would otherwise sit unexercised for a month and then be trusted on its first
output. These tests prove the three things that matter before then:

  1. the gates fire (sample size, and era-swap — the guard against comparing a
     book against itself and calling the null a validation);
  2. a shift the size of the v2->v3 credit jump is actually DETECTED;
  3. standardisation removes a mech_cell-mix confound rather than reporting it
     as a behaviour change.

(3) is the one worth having. The whole reason the study standardises is that
accumulated v4 dates do not overlap v3 dates, so the two books are drawn from
different regime mixes by construction.
"""

import sys

import pandas as pd
import pytest

from backtest_study import v4_bridge as vb


# --------------------------------------------------------------------------
# synthetic books
# --------------------------------------------------------------------------
PLAYS = {
    "bull_call_spread": "[DIRECTIONAL]\nTF | bull call spread 220/240 | x",
    "bull_put_spread": "[DIRECTIONAL]\nTF-S | bull put spread 600/580 | x",
    "bear_put_spread": "[DIRECTIONAL]\nMR | bear put spread 440/400 | x",
}


def _book(spec, era="v3", regime="RANGE + L-VOL"):
    """spec: {date: [(mech_cell, structure), ...]} -> a raw analysis-tab frame."""
    rows = []
    for date, entries in spec.items():
        cell = entries[0][0]
        rows.append({"date": date, "ticker": "MARKET", "play": "",
                     "regime": regime, "mech_cell": cell})
        for i, (cell, struct) in enumerate(entries):
            rows.append({"date": date, "ticker": f"T{i}", "play": PLAYS[struct],
                         "regime": "per-play regime, not the market read",
                         "mech_cell": cell})
    df = pd.DataFrame(rows)
    if era == "v3":
        df["score_flow"] = 10
        df["score_dealer"] = 5
    return df


def _dates(n, cell, structures, start=1):
    return {f"2026-0{1 + (d // 28)}-{1 + (d % 28):02d}": [(cell, s) for s in structures]
            for d in range(start, start + n)}


def _write(tmp_path, name, df):
    p = tmp_path / name
    df.to_csv(p, index=False)
    return p


def _run(monkeypatch, v3_path, v4_path):
    monkeypatch.setattr(sys, "argv", ["v4_bridge", "--v3-csv", str(v3_path),
                                      "--v4-csv", str(v4_path)])
    return vb.main()


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    (PLAYS["bull_call_spread"], "bull_call_spread"),
    (PLAYS["bull_put_spread"], "bull_put_spread"),
    (PLAYS["bear_put_spread"], "bear_put_spread"),
    ("no recognisable structure here", "other"),
])
def test_play_structure(text, expected):
    assert vb.play_structure(text) == expected


def test_detect_era_reads_the_schema_not_the_filename():
    assert vb.detect_era(_book(_dates(1, "LVOL", ["bull_call_spread"]), "v3")) == "v3"
    assert vb.detect_era(_book(_dates(1, "LVOL", ["bull_call_spread"]), "v4")) == "v4"


def test_load_excludes_market_rows_and_joins_the_market_regime(tmp_path):
    df = _book(_dates(2, "LVOL", ["bull_call_spread"]), "v4", regime="RANGE + E-VOL")
    out = vb.load(_write(tmp_path, "v4.csv", df))
    assert (out["ticker"] != "MARKET").all()
    assert (out["market_regime"] == "RANGE + E-VOL").all()
    # per-play regime must never leak into the market read (the core.py invariant)
    assert "per-play" not in "".join(out["market_regime"])


def test_ladder_tier_matches_the_shipped_ladder():
    assert vb.ladder_tier("bull_call_spread", "RANGE + L-VOL") == "A"
    assert vb.ladder_tier("bull_call_spread", "BULL + E-VOL") == "A"
    assert vb.ladder_tier("bull_call_spread", "BULL + L-VOL") == "B"
    assert vb.ladder_tier("bear_call_spread", "BULL + L-VOL") == "VETO"
    assert vb.ladder_tier("bull_call_spread", "BEAR + H-VOL") == "VETO"
    # documented divergence from book.ladder_tier: no delta/dte on an analysis
    # row, so bull_puts cannot reach Tier B here
    assert vb.ladder_tier("bull_put_spread", "BULL + L-VOL") == "C"


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------
def test_sample_size_gate_returns_2_and_refuses_to_run(tmp_path, monkeypatch, capsys):
    v3 = _write(tmp_path, "v3.csv", _book(_dates(30, "LVOL", ["bull_call_spread"]), "v3"))
    v4 = _write(tmp_path, "v4.csv", _book(_dates(3, "LVOL", ["bull_call_spread"]), "v4"))
    assert _run(monkeypatch, v3, v4) == 2
    out = capsys.readouterr().out
    assert "GATE NOT MET" in out
    assert "3 of 20" in out


def test_era_swap_guard_returns_3(tmp_path, monkeypatch, capsys):
    book = _dates(30, "LVOL", ["bull_call_spread"])
    v3 = _write(tmp_path, "a.csv", _book(book, "v3"))
    # v4 slot handed a v3-schema export -> must abort, not report a null
    assert _run(monkeypatch, v3, v3) == 3
    assert "ABORT" in capsys.readouterr().out


def test_gate_threshold_is_the_pre_registered_value():
    """Lowering this to make a run happen would invalidate the pre-registration."""
    assert vb.MIN_V4_DATES == 20
    assert vb.ALPHA == 0.05


# --------------------------------------------------------------------------
# does it actually detect a shift?
# --------------------------------------------------------------------------
def test_identical_composition_carries_forward(tmp_path, monkeypatch, capsys):
    mix = ["bull_call_spread"] * 6 + ["bull_put_spread"] * 2 + ["bear_put_spread"] * 2
    v3 = _write(tmp_path, "v3.csv", _book(_dates(60, "LVOL", mix), "v3"))
    v4 = _write(tmp_path, "v4.csv", _book(_dates(25, "LVOL", mix, start=61), "v4"))
    assert _run(monkeypatch, v3, v4) == 0
    out = capsys.readouterr().out
    assert "LADDER CARRIES FORWARD" in out
    assert "*** SHIFT" not in out


def test_a_v2_to_v3_sized_credit_jump_is_detected(tmp_path, monkeypatch, capsys):
    """19% -> 34% credit share was the only significant version change on record.

    If the study cannot see a shift that size, it is not worth waiting a month
    for.
    """
    v3_mix = ["bull_put_spread"] * 2 + ["bull_call_spread"] * 8   # 20% credit
    v4_mix = ["bull_put_spread"] * 7 + ["bull_call_spread"] * 13  # 35% credit
    v3 = _write(tmp_path, "v3.csv", _book(_dates(60, "LVOL", v3_mix), "v3"))
    v4 = _write(tmp_path, "v4.csv", _book(_dates(25, "LVOL", v4_mix, start=61), "v4"))
    assert _run(monkeypatch, v3, v4) == 0
    out = capsys.readouterr().out
    assert "LADDER UNVALIDATED" in out
    assert "2. credit share" in out.split("Shifted:")[1].split("\n")[0]


def test_a_bear_share_shift_is_detected(tmp_path, monkeypatch, capsys):
    v3_mix = ["bull_call_spread"] * 9 + ["bear_put_spread"]
    v4_mix = ["bull_call_spread"] * 5 + ["bear_put_spread"] * 5
    v3 = _write(tmp_path, "v3.csv", _book(_dates(60, "LVOL", v3_mix), "v3"))
    v4 = _write(tmp_path, "v4.csv", _book(_dates(25, "LVOL", v4_mix, start=61), "v4"))
    assert _run(monkeypatch, v3, v4) == 0
    assert "4. bear share" in capsys.readouterr().out.split("Shifted:")[1]


def test_plays_per_day_shift_is_detected(tmp_path, monkeypatch, capsys):
    v3 = _write(tmp_path, "v3.csv",
                _book(_dates(60, "LVOL", ["bull_call_spread"] * 10), "v3"))
    v4 = _write(tmp_path, "v4.csv",
                _book(_dates(25, "LVOL", ["bull_call_spread"] * 3, start=61), "v4"))
    assert _run(monkeypatch, v3, v4) == 0
    assert "3. plays per day" in capsys.readouterr().out.split("Shifted:")[1]


# --------------------------------------------------------------------------
# the reason standardisation exists
# --------------------------------------------------------------------------
def test_standardisation_removes_a_mech_cell_mix_confound(tmp_path):
    """Same behaviour per regime, different regime mix -> same standardised share.

    v3 is 90% LVOL dates, v4 is 50/50 LVOL/BEAR_HE. Within each cell both eras
    emit the identical mix, so the standardised shares must agree even though
    the raw ones need not.
    """
    def book(n_lvol, n_bear, era, start):
        spec = {}
        spec.update(_dates(n_lvol, "LVOL",
                           ["bull_call_spread"] * 8 + ["bull_put_spread"] * 2,
                           start=start))
        spec.update(_dates(n_bear, "BEAR_HE",
                           ["bull_call_spread"] * 2 + ["bull_put_spread"] * 8,
                           start=start + 100))
        return _book(spec, era)

    a = vb.load(_write(tmp_path, "v3.csv", book(45, 5, "v3", 1)))
    b = vb.load(_write(tmp_path, "v4.csv", book(12, 12, "v4", 201)))

    weights = b["mech_cell"].value_counts().to_dict()
    s3 = vb.standardised_share(a, a["is_credit"], weights)
    s4 = vb.standardised_share(b, b["is_credit"], weights)

    assert s3 == pytest.approx(s4, abs=1e-9), "standardisation failed to align mixes"
    # ...and the raw shares genuinely differ, i.e. the confound was real
    raw3, raw4 = a["is_credit"].mean(), b["is_credit"].mean()
    assert abs(raw3 - raw4) > 0.10
