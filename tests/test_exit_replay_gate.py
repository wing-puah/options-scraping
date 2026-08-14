"""Unit tests for the DEBIT_PROD exact-replay gate — corrected 2026-08-14.

Background (config/backtest-tuning/next-steps.md §0c(A)): the gate used to demand
that EVERY real debit row replay bit-exactly under `DEBIT_PROD`. On 2026-07-22
commit 31cb935 shipped `simulation.regime_exit.cells.BEAR_HE` (a .50/.50 trail),
so production began resolving a per-row effective exit config that the frozen
harness — which takes flat call args and never sees the signal date — cannot
reproduce. The gate therefore asserted a property production had stopped having,
and no future export could satisfy it; three studies were permanently disabled.

The corrected gate classifies each row exact / near-rounding-tie /
superseded-basis / HARD and stops only on HARD. These tests pin that behaviour,
including the two things that must NOT change: proxy admission stays exact-only,
and a genuine unreconcilable mismatch still stops the study.

All fixtures are tiny synthetic CSVs in tmp_path — nothing here touches the
gitignored backtests/to_evaluate/ exports or the network.
"""
from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study import exit_switch_mech_study as m
from scripts.backtest_study.harness import Trade, replay

SIGNAL = date(2024, 3, 4)     # Monday
EXPIRY = date(2024, 3, 15)    # Friday
DTE = (EXPIRY - SIGNAL).days
GRID_LEN = len(_weekday_grid(SIGNAL, SIGNAL + timedelta(days=min(DTE, 120))))

_BASE = {
    "market_regime": "BULL L-VOL", "regime": "BULL L-VOL", "horizon": "short",
    "delta": "0.30", "iv_entry_pct": "40", "entry_premium_total": "100",
    "max_loss_per_contract": "100", "mfe_pct": "0.5", "mae_pct": "-0.1",
    "mfe_day": "3", "mae_day": "1", "pnl_at_cap_pct": "1.10",
    "created_datetime": "2024-03-04 09:00:00", "realized_pnl_abs": "0",
}


def _row(ticker="AAA", structure="bear_put_spread", entry=1.00, marks=None,
         contracts=1, **extra):
    """A debit row that runs up then gives back — a path on which a trailing stop
    and DEBIT_PROD genuinely disagree, which is the whole point here.

    Peak pl is +0.80: above trig/trail 0.50 but BELOW pt 0.90, so the trail is
    the only rule that can fire. Under DEBIT_PROD the row instead rides to the
    time exit. Do not raise the peak past 0.90 — profit_target outranks
    trailing_stop in replay()'s priority order and the fixture stops testing
    anything.
      trail profile: day 3 pl +0.25 <= peak 0.80 - 0.50  -> trailing_stop
      DEBIT_PROD:    d >= int(11 * 0.75) = 8             -> time_exit at +0.20
    """
    if marks is None:
        marks = [1.00, 1.80, 1.25] + [1.20] * (GRID_LEN - 3)
    row = dict(_BASE)
    row.update({
        "signal_date": SIGNAL.isoformat(), "ticker": ticker, "structure": structure,
        "legs": f"{ticker}:{EXPIRY.isoformat()}:100:P +1",
        "contracts": str(contracts), "dte_entry": str(DTE),
        "entry_option_price": str(entry),
        "daily_price_csv": ",".join(f"{x:.4f}" for x in marks),
        "play": f"[DIRECTIONAL]\n{ticker} test play {structure}",
    })
    row.update(extra)
    return row


def _stamp(row, **prod):
    """Stamp the stored outcome from an ACTUAL replay under `prod`."""
    rp = replay(Trade(dict(row)), **prod)
    row["exit_reason"] = rp["exit_reason"]
    row["days_held"] = str(rp["days_held"])
    row["realized_pnl_pct"] = str(round(rp["pnl_pct"], 4))
    row["realized_pnl_abs"] = str(round(Trade(dict(row)).dollars(rp["pnl_pct"]), 2))
    return row


# ── unreachable_reasons: a property of the profile, not a guess ──────────────

def test_unreachable_reasons_for_debit_prod():
    """DEBIT_PROD sets pt/sl/tef and leaves trail/trig/be_after/und_buffer unset,
    so replay() can never emit those three reasons."""
    assert m.unreachable_reasons(m.DEBIT_PROD) == {
        "trailing_stop", "underlying_stop", "be_stop"}


def test_unreachable_reasons_shrinks_when_knobs_are_set():
    with_trail = {**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50}
    assert "trailing_stop" not in m.unreachable_reasons(with_trail)
    with_ratchet = {**m.DEBIT_PROD, "be_after": 0.50}
    assert "be_stop" not in m.unreachable_reasons(with_ratchet)


def test_trailing_stop_needs_both_knobs():
    """Attempt 12's logged trap: setting `trail` without `trig` silently no-ops,
    so such a profile still cannot emit trailing_stop."""
    half = {**m.DEBIT_PROD, "trail": 0.50}
    assert "trailing_stop" in m.unreachable_reasons(half)


def test_unconditional_reasons_are_never_unreachable():
    """dollar_stop / expired / cap_open have no governing knob in replay()."""
    unreachable = m.unreachable_reasons({})
    for reason in ("dollar_stop", "expired", "cap_open"):
        assert reason not in unreachable


# ── _classify: the four buckets ──────────────────────────────────────────────

def _classify(row):
    return m._classify(Trade(dict(row)), m.DEBIT_PROD,
                       m.unreachable_reasons(m.DEBIT_PROD))[0]


def test_classify_exact():
    assert _classify(_stamp(_row(), **m.DEBIT_PROD)) == "exact"


def test_classify_near_rounding_tie():
    row = _stamp(_row(), **m.DEBIT_PROD)
    stored = float(row["realized_pnl_pct"])
    row["realized_pnl_pct"] = str(stored + m.NEAR_MISS_TOL / 2)
    assert _classify(row) == "near"


def test_classify_superseded_when_stored_reason_is_unreachable():
    """The BEAR_HE case: the row was exported under the shipped trail, so its
    stored exit_reason is one DEBIT_PROD cannot produce."""
    row = _stamp(_row(), **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    assert row["exit_reason"] == "trailing_stop", "fixture must actually trail out"
    assert _classify(row) == "superseded"


def test_classify_hard_when_reason_is_reachable_but_wrong():
    """A reachable stored reason that still doesn't reproduce has no config
    explanation — that is the only bucket allowed to stop a study."""
    row = _stamp(_row(), **m.DEBIT_PROD)
    row["exit_reason"] = "time_exit"
    row["days_held"] = "999"
    row["realized_pnl_pct"] = "0.4242"
    assert _classify(row) == "hard"


def test_superseded_beats_near_only_on_reason():
    """A superseded row whose pnl happens to land within NEAR_MISS_TOL is still
    classified `near` — the near test is checked first and requires the reasons
    to MATCH, so this can only fire when the reason is reproduced anyway."""
    row = _stamp(_row(), **m.DEBIT_PROD)
    assert _classify(row) == "exact"
    row["exit_reason"] = "trailing_stop"
    assert _classify(row) == "superseded"


# ── the gate itself ──────────────────────────────────────────────────────────

def _write_book(tmp_path, monkeypatch, real_rows, proxy_rows=()):
    import csv

    cols = sorted({k for r in list(real_rows) + list(proxy_rows) for k in r}
                  | {"proxy_method"})
    br = tmp_path / "BacktestResults.csv"
    bp = tmp_path / "BacktestProxy.csv"
    for path, rows in ((br, real_rows), (bp, proxy_rows)):
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
    monkeypatch.setattr(m, "BR_PATH", br)
    monkeypatch.setattr(m, "BP_PATH", bp)
    return m.load_debit_trades()


def test_gate_passes_with_superseded_rows_and_keeps_them(tmp_path, monkeypatch, capsys):
    """The load-bearing case. A book with superseded rows must PASS, and those
    rows must remain in the returned trades — dropping them would bias the exact
    cell under test (they are the rows where the shipped rule changed the
    outcome, not a random subset)."""
    good = _stamp(_row(ticker="GOOD"), **m.DEBIT_PROD)
    sup = _stamp(_row(ticker="SUPD"), **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    trades, diag = _write_book(tmp_path, monkeypatch, [good, sup])

    rc = diag["real_calib"]
    assert (rc["ok"], rc["superseded"], rc["hard"]) == (1, 1, 0)
    assert {t.ticker for t in trades} == {"GOOD", "SUPD"}, "superseded row was dropped"

    m.harness_gate(diag)   # must not raise SystemExit
    out = capsys.readouterr().out
    assert "1 superseded-basis" in out
    assert "PASS" in out


def test_gate_tags_calibrated_per_row(tmp_path, monkeypatch):
    good = _stamp(_row(ticker="GOOD"), **m.DEBIT_PROD)
    sup = _stamp(_row(ticker="SUPD"), **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    trades, _ = _write_book(tmp_path, monkeypatch, [good, sup])
    by = {t.ticker: t for t in trades}
    assert by["GOOD"].calibrated is True
    assert by["SUPD"].calibrated is False


def test_gate_dollar_check_ignores_superseded_rows(tmp_path, monkeypatch):
    """The stored-vs-replay total is over CALIBRATED rows only. Over all rows the
    two are expected to differ by exactly the superseded rows' contribution, and
    that difference is reported rather than asserted away."""
    good = _stamp(_row(ticker="GOOD"), **m.DEBIT_PROD)
    sup = _stamp(_row(ticker="SUPD"), **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    _, diag = _write_book(tmp_path, monkeypatch, [good, sup])
    rc = diag["real_calib"]
    assert rc["replay"] == pytest.approx(rc["stored"], abs=0.01)
    assert abs(rc["replay_all"] - rc["stored_all"]) > 0.01


def test_gate_still_stops_on_a_true_hard_row(tmp_path, monkeypatch):
    """The correction must not turn the gate off. A mismatch with no exit-rule
    explanation still exits 1."""
    good = _stamp(_row(ticker="GOOD"), **m.DEBIT_PROD)
    bad = _stamp(_row(ticker="BAD"), **m.DEBIT_PROD)
    bad["exit_reason"] = "time_exit"
    bad["days_held"] = "999"
    bad["realized_pnl_pct"] = "0.4242"
    _, diag = _write_book(tmp_path, monkeypatch, [good, bad])
    assert diag["real_calib"]["hard"] == 1
    with pytest.raises(SystemExit) as ei:
        m.harness_gate(diag)
    assert ei.value.code == 1


def test_proxy_admission_is_unchanged(tmp_path, monkeypatch):
    """A pre-registered POPULATION choice, deliberately NOT widened by the gate
    correction: a non-exact proxy row stays excluded even when superseded."""
    good = _stamp(_row(ticker="GOOD"), **m.DEBIT_PROD)
    px_ok = _stamp(_row(ticker="PXOK"), **m.DEBIT_PROD)
    px_ok["proxy_method"] = "strike_expiry_tweak"
    px_sup = _stamp(_row(ticker="PXSUP"),
                    **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    px_sup["proxy_method"] = "strike_expiry_tweak"

    trades, diag = _write_book(tmp_path, monkeypatch, [good], [px_ok, px_sup])
    assert "PXSUP" not in {t.ticker for t in trades}
    assert "PXOK" in {t.ticker for t in trades}
    assert diag["proxy"]["excl_kinds"] == {"superseded": 1}


# ── bear_position_study: R must be re-replayed, never read off the row ───────

def test_bear_position_study_R_is_replayed_not_stored(tmp_path, monkeypatch):
    """bear_position_study.py:77 used to read `realized_pnl_pct` straight off the
    row, which imported a different exit config for exactly the superseded rows
    — 9 of the 12 on the real book are bear structures, this study's population,
    and it feeds deployment-rules.md §"Bear positions — hedge sleeve"."""
    from scripts.backtest_study import bear_position_study as bps

    sup = _stamp(_row(ticker="SUPD"), **{**m.DEBIT_PROD, "trig": 0.50, "trail": 0.50})
    trades, _ = _write_book(tmp_path, monkeypatch, [sup])

    class _NoLabels:
        def label(self, d):
            return None, None, False, None

    (rec,) = bps.build(trades, _NoLabels())
    stored = float(sup["realized_pnl_pct"])
    replayed = replay(trades[0], **m.DEBIT_PROD)["pnl_pct"]
    assert rec["R"] == pytest.approx(replayed)
    assert rec["R"] != pytest.approx(stored), \
        "R fell back to the stored column — the contamination is back"
