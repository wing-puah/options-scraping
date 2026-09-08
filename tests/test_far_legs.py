"""Unit tests for `scripts/collector/fetch_far_legs.py`.

The far-call target rule: K* is the near-expiry paired strike nearest spot,
the far expiry is the ticker's FIRST cached expiry after the near one, and the
target is the call at K* there when it is not cached. Every "never invent"
edge is pinned — no paired grid, no later expiry, already cached — and so is
the one that moves an existing calendar: a call at K* cached at a FURTHER
expiry does not satisfy the first later one. Anchors follow
`hedge_structure.build_universe` (first record's spot per (date, ticker,
expiry)). The manifest is its own file, next to the sweep's.

Everything is synthetic; no network, no real cache.
"""
from datetime import date

from scripts.backtest.legs import Leg
from scripts.collector import fetch_far_legs as ffl
from scripts.collector import fetch_sweep_legs as fsl

E1 = date(2024, 6, 21)   # near expiry
E2 = date(2024, 7, 19)   # the ticker's first later expiry
E3 = date(2024, 8, 16)   # a further one


class _FakeTrade:
    def __init__(self, legs, entry_underlying):
        self.legs = legs
        self.row = {"entry_underlying": str(entry_underlying)}


def _rec(legs, spot, d="2024-06-03", ticker="AAA"):
    return {"t": _FakeTrade(legs, spot), "date": d, "ticker": ticker}


def _idx(**cells):
    """`_idx(AAA_E1={100: "CP", 105: "C"}, AAA_E2={100: "P"})` → strike index."""
    out = {}
    for name, strikes in cells.items():
        tk, exp = name.split("_")
        out[(tk, {"E1": E1, "E2": E2, "E3": E3}[exp])] = {
            float(k): set(v) for k, v in strikes.items()}
    return out


# --- anchors --------------------------------------------------------------------

def test_anchors_take_the_first_records_spot_per_date_ticker_expiry():
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    a = ffl.anchors([_rec(legs, 101.0), _rec(legs, 150.0)])
    assert a == {("2024-06-03", "AAA", E1): 101.0}


def test_anchors_keep_dates_apart_and_skip_a_missing_spot():
    legs = [Leg(1, "AAA", E1, 100.0, "Call")]
    a = ffl.anchors([_rec(legs, 101.0, d="2024-06-03"),
                     _rec(legs, 120.0, d="2024-06-10"),
                     _rec(legs, "", d="2024-06-17"),
                     _rec(legs, 0, d="2024-06-24")])
    assert a == {("2024-06-03", "AAA", E1): 101.0, ("2024-06-10", "AAA", E1): 120.0}


# --- the target rule --------------------------------------------------------------

def test_target_is_the_call_at_k_star_on_the_first_later_expiry():
    idx = _idx(AAA_E1={100: "CP", 105: "CP"}, AAA_E2={100: "P"})
    why, r = ffl.far_call_target(idx, "AAA", E1, 101.0)
    assert why == "target"
    assert (r["ticker"], r["expiration"], r["strike"], r["opt_type"]) == ("AAA", E2, 100.0, "C")
    assert r["category"] == "far_call"


def test_k_star_is_the_paired_strike_nearest_spot_never_a_call_only_one():
    idx = _idx(AAA_E1={100: "CP", 104: "C", 110: "CP"}, AAA_E2={95: "P"})
    _why, r = ffl.far_call_target(idx, "AAA", E1, 105.0)
    assert r["strike"] == 100.0        # 104 is nearer but not paired


def test_no_paired_grid_means_no_target():
    idx = _idx(AAA_E1={100: "C", 105: "C"}, AAA_E2={100: "P"})
    assert ffl.far_call_target(idx, "AAA", E1, 101.0) == ("no_grid", None)


def test_no_later_cached_expiry_means_no_target():
    idx = _idx(AAA_E1={100: "CP"})
    assert ffl.far_call_target(idx, "AAA", E1, 101.0) == ("no_later_expiry", None)


def test_another_tickers_later_expiry_is_not_evidence():
    idx = _idx(AAA_E1={100: "CP"}, BBB_E2={100: "CP"})
    assert ffl.far_call_target(idx, "AAA", E1, 101.0) == ("no_later_expiry", None)


def test_already_cached_far_call_means_no_target():
    idx = _idx(AAA_E1={100: "CP"}, AAA_E2={100: "C"})
    assert ffl.far_call_target(idx, "AAA", E1, 101.0) == ("cached", None)


def test_a_call_at_a_further_expiry_does_not_satisfy_the_first_later_one():
    """The study pairs with `later[0]` among expiries holding a call at K*; the
    rule wants the FIRST later listed expiry, and E2 is listed (a put sits
    there). Fetching E2's call is what moves the pair off E3."""
    idx = _idx(AAA_E1={100: "CP"}, AAA_E2={110: "P"}, AAA_E3={100: "C"})
    why, r = ffl.far_call_target(idx, "AAA", E1, 101.0)
    assert why == "target" and r["expiration"] == E2


def test_census_dedupes_across_dates_and_counts_every_anchor():
    idx = _idx(AAA_E1={100: "CP"}, AAA_E2={100: "P"}, BBB_E1={50: "C"})
    legs_a = [Leg(1, "AAA", E1, 100.0, "Call")]
    legs_b = [Leg(1, "BBB", E1, 50.0, "Call")]
    recs = [_rec(legs_a, 101.0, d="2024-06-03"),
            _rec(legs_a, 99.0, d="2024-06-10"),
            _rec(legs_b, 50.0, d="2024-06-03", ticker="BBB")]
    targets, census = ffl.far_call_census(recs, idx)
    assert [(r["ticker"], r["expiration"], r["strike"]) for r in targets] == [("AAA", E2, 100.0)]
    assert census["target"] == 2 and census["no_grid"] == 1 and census["anchors"] == 3


# --- integration with the sweep fetcher's contract --------------------------------

def test_manifest_is_its_own_file_beside_the_sweeps():
    assert ffl.MANIFEST_PATH != fsl.MANIFEST_PATH
    assert ffl.MANIFEST_PATH.parent == fsl.MANIFEST_PATH.parent


def test_targets_merge_into_a_manifest_the_sweep_helpers_read_back(tmp_path):
    idx = _idx(AAA_E1={100: "CP"}, AAA_E2={100: "P"})
    recs = [_rec([Leg(1, "AAA", E1, 100.0, "Call")], 101.0)]
    rows = fsl.merge_manifest({}, ffl.far_call_target_records(recs, idx))
    path = tmp_path / "far_legs_manifest.csv"
    fsl.write_manifest(path, rows)
    back = fsl.load_manifest(path)
    (row,) = back.values()
    got = (row["ticker"], row["expiration"], row["strike"], row["opt_type"],
           row["category"], row["status"])
    assert got == ("AAA", E2.isoformat(), "100.00", "C", "far_call", "pending")
