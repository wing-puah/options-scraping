"""Unit tests for scripts/backtest_study/lib/text_corpus.py — the text corpus loader.

Two things are pinned here that matter more than the shapes:

  1. The play parser is pinned AGAINST THE WRITER. The round-trip case builds
     its input by calling `scripts.analysis_pipeline.core.analysis_to_rows`, so
     a change to how the pipeline assembles a play cell breaks this test rather
     than silently degrading every text feature to None.
  2. The join is pinned BY IDENTITY. `text_corpus` must reuse `book.norm_play`
     and `book._build_analysis_lookup`; a second copy would let the text a row
     carries disagree with the numbers `load_book` joined onto the same row.

Everything is synthetic and written to tmp_path — no network, no Drive, and no
dependence on the untracked backtests/to_evaluate/ exports.
"""
from datetime import date, timedelta

import pytest

from scripts.analysis_pipeline.core import analysis_to_rows
from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.lib import book, text_corpus as tc
from scripts.backtest_study.lib.harness import Trade, replay

SIGNAL = date(2024, 3, 4)     # Monday
EXPIRY = date(2024, 3, 15)    # Friday
DTE = (EXPIRY - SIGNAL).days
GRID_LEN = len(_weekday_grid(SIGNAL, SIGNAL + timedelta(days=min(DTE, 120))))


# ── the reused-join guard ───────────────────────────────────────────────────

def test_join_helpers_are_the_book_module_s_own_objects():
    assert tc.norm_play is book.norm_play
    assert tc._build_analysis_lookup is book._build_analysis_lookup


# ── parse_play, pinned to the writer ────────────────────────────────────────

def _written_play(**play_overrides) -> str:
    """The `play` cell `analysis_to_rows` would write for one play dict."""
    play = {
        "ticker": "AAA",
        "flow_intent": "directional",
        "pattern": "TF",
        "structure": "bull put spread 145/130",
        "thesis": "Long-dated opening call buys at the low end of the range.",
        "alternative_interpretation": "The 150-strike call block could be an overwrite.",
        "trigger": "BABA holds 155 on a closing basis; no entry before the print",
        "invalidation": "Daily close below 145 (the short strike)",
        "horizon": "60",
    }
    play.update(play_overrides)
    rows = analysis_to_rows({"regime": "BULL L-VOL", "signals": ["[FLOW] a"],
                             "plays": [play]},
                            "2024-03-04", "2024-03-01", "2024-03-04")
    return rows[1]["play"]


def test_parse_play_round_trips_the_writer_s_assembly():
    parsed = tc.parse_play(_written_play())
    assert parsed["intent"] == "DIRECTIONAL"
    assert parsed["pattern"] == "TF"
    assert parsed["structure_text"] == "bull put spread 145/130"
    assert parsed["thesis"].startswith("Long-dated opening call buys")
    assert parsed["alt"] == "The 150-strike call block could be an overwrite."


def test_parse_play_round_trips_with_no_alternative():
    parsed = tc.parse_play(_written_play(alternative_interpretation=""))
    assert parsed["alt"] is None
    assert parsed["structure_text"] == "bull put spread 145/130"


def test_parse_play_round_trips_with_no_intent_bracket():
    parsed = tc.parse_play(_written_play(flow_intent=""))
    assert parsed["intent"] is None
    assert parsed["pattern"] == "TF"
    assert parsed["thesis"].startswith("Long-dated opening call buys")


@pytest.mark.parametrize("cell", ["", None, "   ", 3.5])
def test_parse_play_degrades_instead_of_raising(cell):
    assert tc.parse_play(cell) == tc._EMPTY_PLAY


def test_parse_play_degrades_on_an_older_two_part_headline():
    """A v3-era cell whose headline lost its thesis still yields a structure."""
    parsed = tc.parse_play("[HEDGE]\nMR | bear put spread 290/265")
    assert parsed["intent"] == "HEDGE"
    assert parsed["pattern"] == "MR"
    assert parsed["structure_text"] == "bear put spread 290/265"
    assert parsed["thesis"] is None


def test_parse_play_degrades_on_a_bare_headline():
    parsed = tc.parse_play("long call 410, 60 DTE")
    assert parsed["structure_text"] == "long call 410, 60 DTE"
    assert parsed["intent"] is None and parsed["pattern"] is None


# ── split_signal ────────────────────────────────────────────────────────────

def test_split_signal_splits_on_newlines_and_extracts_tags():
    out = tc.split_signal("[FLOW] $224.5M puts vs $6.4M calls\n[VEGA] IVpct 13%")
    assert out == [("FLOW", "$224.5M puts vs $6.4M calls"), ("VEGA", "IVpct 13%")]


def test_split_signal_attaches_an_untagged_continuation_to_the_item_above():
    out = tc.split_signal("[FLOW] big put block\ncounter: the 300 calls were ToOpen")
    assert out == [("FLOW", "big put block counter: the 300 calls were ToOpen")]


def test_split_signal_splits_a_pipe_only_when_it_introduces_a_tag():
    out = tc.split_signal("[FLOW] a | [PRICE] b")
    assert out == [("FLOW", "a"), ("PRICE", "b")]
    # A bare pipe inside prose is not an item boundary.
    out = tc.split_signal("[FLOW] ratio a | b of the chain")
    assert out == [("FLOW", "ratio a | b of the chain")]


def test_split_signal_leading_untagged_line_becomes_its_own_item():
    assert tc.split_signal("no tag here") == [(None, "no tag here")]


@pytest.mark.parametrize("cell", ["", None, "  "])
def test_split_signal_is_empty_for_a_blank_cell(cell):
    assert tc.split_signal(cell) == []


# ── strikes and price levels ────────────────────────────────────────────────

@pytest.mark.parametrize("text,want", [
    ("bull put spread 145/130", [145.0, 130.0]),
    ("bear put spread 290/265 (120–199 DTE)", [290.0, 265.0]),
    ("bear put spread 550/500, 56 DTE", [550.0, 500.0]),
    ("bull call spread 400/430 Mar 15 (46 DTE)", [400.0, 430.0]),
    # A four-digit strike must not be vetoed as a calendar year.
    ("bull call spread 1600/1900, 90-120 DTE", [1600.0, 1900.0]),
    ("straddle 300", [300.0]),
    ("long put 210 (~95 DTE)", [210.0]),
    ("", []),
    (None, []),
])
def test_parse_strikes(text, want):
    assert tc.parse_strikes(text) == want


def test_parse_price_levels_skips_dtes_percentages_premiums_and_counts():
    text = ("166,080x $285 10d BuyToOpen on the ask ($26.9M), IVpct 13%, "
            "protection out to 2027, close below 297")
    assert tc.parse_price_levels(text) == [285.0, 297.0]


def test_parse_price_levels_skips_dates_and_sub_dollar_ratios():
    text = "Earnings on ~Nov 25 clear and C/P 0.03 holds; spot 155 on 2026-01-02"
    assert tc.parse_price_levels(text) == [155.0]


# ── text_features ───────────────────────────────────────────────────────────

def _text(**kw):
    base = dict(regime="", signal="", play="", trigger="", invalidation="",
                horizon="", created_datetime="", joined=True)
    base.update(kw)
    return base


def test_features_price_only_invalidation_inside_the_strikes():
    t = _text(play="[DIRECTIONAL]\nTF | bull put spread 145/130 | thesis words here",
              invalidation="Daily close below 140 (the short strike)")
    f = tc.text_features(t)
    assert f["invalidation_type"] == "price"
    assert f["invalidation_level"] == 140.0
    assert f["invalidation_inside_strikes"] is True


def test_features_price_invalidation_outside_the_strikes():
    t = _text(play="[DIRECTIONAL]\nTF | bull put spread 145/130 | thesis words here",
              invalidation="Daily close below 120")
    f = tc.text_features(t)
    assert f["invalidation_inside_strikes"] is False


@pytest.mark.parametrize("invalidation,want", [
    ("Index call demand reversing to net puts", "flow"),
    ("A hot CPI print or a VIX spike", "macro"),
    ("Daily close above 297, or C/P reverting", "mixed"),
    ("The thesis stops making sense", "none"),
    ("", "none"),
])
def test_features_classify_the_invalidation(invalidation, want):
    play = "[HEDGE]\nMR | bear put spread 290/265 | a thesis"
    f = tc.text_features(_text(play=play, invalidation=invalidation))
    assert f["invalidation_type"] == want


def test_features_inside_strikes_is_none_when_either_side_is_missing():
    # No level in the invalidation.
    f = tc.text_features(_text(play="[X]\nTF | bull put spread 145/130 | t",
                               invalidation="Flow reverses"))
    assert f["invalidation_inside_strikes"] is None
    # Single-leg structure: no min/max to be inside of.
    f = tc.text_features(_text(play="[X]\nTF | straddle 300 | t",
                               invalidation="Daily close below 280"))
    assert f["invalidation_inside_strikes"] is None


def test_features_trigger_conditionality_and_level():
    f = tc.text_features(_text(
        trigger="BABA holds 155 on a closing basis; no entry before the print"))
    assert f["trigger_conditional"] is True
    assert f["trigger_level"] == 155.0
    f = tc.text_features(_text(trigger="Enter on a daily close below 290."))
    assert f["trigger_conditional"] is False
    assert f["trigger_level"] == 290.0
    assert tc.text_features(_text())["trigger_conditional"] is False
    assert tc.text_features(_text())["trigger_level"] is None


def test_features_lengths_specificity_and_evidence_count():
    t = _text(
        play="[DIRECTIONAL]\nTF | bull call spread 47/55 | one two three four\n"
             "Alt: five six",
        signal="[FLOW] $12.5M calls at 113 DTE\n[PRICE] PxVec +1.00",
        trigger="Close above 47",
        invalidation="Daily close below 43, or 20% IV collapse",
    )
    f = tc.text_features(t)
    assert f["thesis_len"] == 4
    assert f["alt_len"] == 2
    assert f["alt_ratio"] == pytest.approx(0.5)
    assert f["evidence_n"] == 2
    assert f["numeric_specificity"] > 0
    # alt_ratio is None, not a ZeroDivisionError, on an empty thesis.
    assert tc.text_features(_text(play="[X]\nTF | straddle 300"))["alt_ratio"] is None


def test_features_degrade_on_a_v3_style_play_cell_without_raising():
    f = tc.text_features(_text(play="[HEDGE]\nsome free-text play with no pipes",
                               invalidation="Daily close below 43"))
    assert f["invalidation_inside_strikes"] is None
    assert f["invalidation_level"] == 43.0
    assert set(f) == set(tc.FEATURE_KEYS)


def test_every_feature_key_carries_a_rationale_note():
    assert set(tc.FEATURE_NOTES) == set(tc.FEATURE_KEYS)
    assert all(v.strip() for v in tc.FEATURE_NOTES.values())


# ── load_corpus on a synthetic era ──────────────────────────────────────────
#
# Fixture approach copied from tests/test_studies_book.py: tiny synthetic
# results/proxy CSVs, an absent mech table, check_era=False (these are
# deliberately partial books, not era-detectable populations).

_BASE = {
    "market_regime": "BULL L-VOL", "regime": "BULL L-VOL", "horizon": "60",
    "delta": "0.30", "iv_entry_pct": "40", "entry_premium_total": "100",
    "max_loss_per_contract": "100", "mfe_pct": "0.5", "mae_pct": "-0.1",
    "mfe_day": "3", "mae_day": "1", "score_total": "10",
    "pnl_at_cap_pct": "1.10", "created_datetime": "2024-03-04 09:00:00",
}


def _bt_row(ticker="AAA", structure="long_call", play=None, entry=1.00, **extra):
    row = dict(_BASE)
    row.update({
        "signal_date": SIGNAL.isoformat(), "ticker": ticker, "structure": structure,
        "legs": f"{ticker}:{EXPIRY.isoformat()}:100:C +1", "contracts": "1",
        "dte_entry": str(DTE), "entry_option_price": str(entry),
        "daily_price_csv": ",".join(["1.0000"] * (GRID_LEN - 1) + ["2.1000"]),
        "play": play if play is not None else f"[DIRECTIONAL]\nTF | long call 100 | {ticker} thesis",
    })
    row.update(extra)
    return row


def _stamp_calibrating(row):
    t = Trade(dict(row))
    rp = replay(t, **book.DEBIT_PROD)
    row["exit_reason"] = rp["exit_reason"]
    row["days_held"] = str(rp["days_held"])
    row["realized_pnl_pct"] = str(round(rp["pnl_pct"], 4))
    return row


def _stamp_noncalibrating(row):
    row.update({"exit_reason": "time_exit", "days_held": "999",
                "realized_pnl_pct": "-0.9999"})
    return row


def _write_csv(path, rows):
    import csv
    fieldnames = sorted(set().union(*[r.keys() for r in rows])) if rows else ["signal_date"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _analysis_row(ticker, play, **kw):
    row = {
        "date": SIGNAL.isoformat(), "ticker": ticker, "regime": "BULL L-VOL",
        "signal": "[FLOW] $4.68M calls at 30 DTE\n[PRICE] PxVec +1.00",
        "play": play, "horizon": "60",
        "trigger": "Close above 100; no entry before the print",
        "invalidation": "Daily close below 95, or call demand reversing",
        "created_datetime": "2024-03-04 09:00:00",
        "score_total": "10",
    }
    row.update(kw)
    return row


@pytest.fixture(autouse=True)
def _isolate_mech_table(tmp_path, monkeypatch):
    monkeypatch.setattr(book, "MECH_TABLE_CSV", tmp_path / "no_such_mech_table.csv")


@pytest.fixture
def era_files(tmp_path):
    """A synthetic era exercising every join and every unpriced reason."""
    joined = _bt_row(ticker="AAA")
    _stamp_calibrating(joined)
    unjoined = _bt_row(ticker="BBB", play="[HEDGE]\nMR | long call 100 | never analysed")
    _stamp_calibrating(unjoined)
    _write_csv(tmp_path / "results.csv", [joined, unjoined])

    bs_only = _bt_row(ticker="CCC", proxy_method="bs_options_hist")
    _stamp_calibrating(bs_only)
    dropped = _bt_row(ticker="DDD", proxy_method="strike_expiry_tweak")
    _stamp_noncalibrating(dropped)          # fails the proxy calibration gate
    _write_csv(tmp_path / "proxy.csv", [bs_only, dropped])

    analysis = [
        _analysis_row("MARKET", "", trigger="", invalidation=""),
        _analysis_row("AAA", joined["play"]),
        _analysis_row("CCC", bs_only["play"]),
        _analysis_row("DDD", dropped["play"]),
        _analysis_row("EEE", "[DIRECTIONAL]\nTF | long call 100 | EEE thesis"),  # never attempted
        _analysis_row("FFF", ""),                                               # blank play
    ]
    _write_csv(tmp_path / "analysis.csv", analysis)
    return dict(results_csv=tmp_path / "results.csv",
                proxy_csv=tmp_path / "proxy.csv",
                analysis_csv=tmp_path / "analysis.csv")


def _load(era_files, **kw):
    kw.setdefault("check_era", False)
    kw.setdefault("min_dates", 0)
    return tc.load_corpus(**era_files, **kw)


def test_load_corpus_joins_text_and_falls_back_when_the_key_misses(era_files):
    rows, _unpriced, diag = _load(era_files)
    by_ticker = {r["ticker"]: r for r in rows}
    assert set(by_ticker) == {"AAA", "BBB"}

    aaa = by_ticker["AAA"]
    assert aaa["text"]["joined"] is True
    assert aaa["text"]["invalidation"].startswith("Daily close below 95")
    assert aaa["features"]["evidence_n"] == 2
    assert aaa["features"]["parsed"]["intent"] == "DIRECTIONAL"

    bbb = by_ticker["BBB"]
    assert bbb["text"]["joined"] is False
    # The results export carries play/regime but never signal/invalidation.
    assert bbb["text"]["play"].startswith("[HEDGE]")
    assert bbb["text"]["regime"] == "BULL L-VOL"
    assert bbb["text"]["signal"] == "" and bbb["text"]["invalidation"] == ""
    assert bbb["features"]["parsed"]["intent"] == "HEDGE"

    assert diag["n_joined"] == 1 and diag["n_unjoined"] == 1


def test_load_corpus_leaves_the_load_book_record_keys_intact(era_files):
    rows, _unpriced, _diag = _load(era_files)
    records, _ = book.load_book(results_csv=era_files["results_csv"],
                                proxy_csv=era_files["proxy_csv"],
                                analysis_csv=era_files["analysis_csv"],
                                check_era=False, min_dates=0)
    base = {r["ticker"]: r for r in records}
    for row in rows:
        original = base[row["ticker"]]
        assert set(original) - set(row) == set(), "a load_book key went missing"
        for k, v in original.items():
            if k == "t":
                continue          # a fresh load_book builds its own Trade objects
            assert row[k] == v or (v != v and row[k] != row[k]), k
        assert "text" not in original and "features" not in original


def test_load_corpus_tags_every_unpriced_reason(era_files):
    _rows, unpriced, diag = _load(era_files)
    by_ticker = {u["ticker"]: u["reason"] for u in unpriced}
    assert by_ticker == {
        "MARKET": "market_row",
        "FFF": "no_play",
        "CCC": "bs_only",
        "DDD": "excluded_by_book",
        "EEE": "not_backtested",
    }
    assert diag["unpriced_by_reason"] == {
        "market_row": 1, "no_play": 1, "bs_only": 1,
        "excluded_by_book": 1, "not_backtested": 1,
    }
    # Unpriced rows carry the same text/features as priced ones.
    eee = next(u for u in unpriced if u["ticker"] == "EEE")
    assert eee["features"]["parsed"]["structure_text"] == "long call 100"


def test_bs_only_becomes_priced_when_include_bs_is_on(era_files):
    rows, unpriced, diag = _load(era_files, include_bs=True)
    assert "CCC" in {r["ticker"] for r in rows}
    assert "bs_only" not in diag["unpriced_by_reason"]
    assert "CCC" not in {u["ticker"] for u in unpriced}


def test_feature_coverage_is_a_share_per_feature(era_files):
    _rows, _unpriced, diag = _load(era_files)
    cov = diag["feature_coverage"]
    assert set(cov) == set(tc.FEATURE_KEYS)
    assert all(0.0 <= v <= 1.0 for v in cov.values())
    # thesis_len is always computable; invalidation_level only on the joined row.
    assert cov["thesis_len"] == 1.0
    assert cov["invalidation_level"] == 0.5


# ── citation_check ──────────────────────────────────────────────────────────

_FIXTURE_MD = """## Stocks — flow

Symbol | Strike | DTE | Premium
--- | --- | --- | ---
AAA | 145 | 30 | 4680000
AAA | 150 | 30 | 1200000
"""


@pytest.fixture
def _fixture_fetch(monkeypatch):
    """No network: the citation fetch returns a saved markdown fixture."""
    calls = []

    def _fake(date_str, cache_dir, force=False):
        calls.append((date_str, force))
        return _FIXTURE_MD

    monkeypatch.setattr(tc, "_fetch_analysis_markdown", _fake)
    return calls


def test_citation_check_counts_found_and_hallucinated_numbers(_fixture_fetch, tmp_path):
    rows = [{
        "date": "2024-03-04", "ticker": "AAA",
        "text": {"signal": (
            # cited: $4.68M premium (present, within rounding of 4,680,000),
            # 145 strike (present), 30 DTE (present), $777 strike (absent)
            "[FLOW] $4.68M of 145 strike calls at 30 DTE, plus a $777 print\n"
            "[VEGA] IVpct 13% — not a flow claim, never checked")},
    }]
    out = tc.citation_check("2024-03-04", cache_dir=tmp_path, rows=rows)
    assert out["cited_n"] == 4
    assert out["found_n"] == 3
    assert out["hallucination_rate"] == pytest.approx(0.25)
    assert out["rows"]["AAA"]["missing"] == ["strike:777"]


def test_citation_check_reports_an_unmeasured_rate_as_none(_fixture_fetch, tmp_path):
    rows = [{"date": "2024-03-04", "ticker": "AAA",
             "text": {"signal": "[PRICE] PxVec +1.00"}}]
    out = tc.citation_check("2024-03-04", cache_dir=tmp_path, rows=rows)
    assert out["cited_n"] == 0 and out["hallucination_rate"] is None


def test_citations_for_rows_is_capped_deterministically(_fixture_fetch, tmp_path):
    rows = [{"date": d, "ticker": "AAA", "text": {"signal": "[FLOW] 145 strike"}}
            for d in ("2024-03-06", "2024-03-04", "2024-03-05")]
    out = tc.citations_for_rows(rows, cache_dir=tmp_path, limit=2)
    assert sorted(out) == ["2024-03-04", "2024-03-05"]
