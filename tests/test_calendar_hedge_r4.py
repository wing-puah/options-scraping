"""Tests for `calendar_hedge`'s R4 gate — the same-run construction comparison.

R4 asks whether `calendar_hedge.build_universe`/`evaluate` has drifted from the
construction `vol_sleeve.synthesize` performs inline. It used to ask that by
comparing against `R4_EXPECT = dict(n=183, mean_r=0.158, dollars=28059.0, ...)`,
transcribed from vol_sleeve's 2026-08-12 report — two unknowns (this code, and
which cache it ran on) against one equation, so a mismatch could not be read as
drift rather than as the option-history cache having grown. It could not be
re-baselined either: keying it to a later run would define "no drift" as
"whatever that run printed".

Converted 2026-08-19: both sides are built in one process from the same book and
the same strike index, so the cache cancels. These tests pin the three pieces
that conversion rests on —

  1. the comparable form of a cell (`cell_fingerprint`) and the diff over it
     (`cell_diff`), which are pure and need no cache;
  2. the checkpoint store being keyed on its CACHE GENERATION, without which
     R4 would compare a cached side against a freshly built one and fail on the
     next scrape for a reason that is not drift;
  3. `vol_sleeve.synthesize` honouring `structures=`, the narrowing that lets
     R4 build the reference side without the straddle and strangle cells.

and the absence of any stored expectation, which is the regression that would
undo all of it.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.f3_structure import calendar_hedge as C  # noqa: E402
from scripts.backtest_study.f3_structure import vol_sleeve as VS  # noqa: E402


# ── the comparable form of a cell ────────────────────────────────────────────

def _stored(ticker="AAA", d="2026-01-05", expiry="2026-02-20", entry_net="1.234567",
            contracts="3", exit_reason="time_exit", days_held="12", R="0.1234567890"):
    """A row as the checkpoint store round-trips it: everything a string."""
    return dict(ticker=ticker, date=d, expiry=expiry, entry_net=entry_net,
                contracts=contracts, exit_reason=exit_reason,
                days_held=days_held, R=R)


def _synth(ticker="AAA", d="2026-01-05", expiry="2026-02-20", entry_net=1.234567,
           contracts=3, exit_reason="time_exit", days_held=12, R=0.1234567890):
    """The same row as `vol_sleeve.synthesize` holds it: native types."""
    return dict(ticker=ticker, date=d, expiry=expiry, entry_net=entry_net,
                contracts=contracts, exit_reason=exit_reason,
                days_held=days_held, R=R)


def test_a_stored_row_and_a_synth_row_of_the_same_candidate_compare_equal():
    # The whole gate depends on this: side A comes back through CSV as strings,
    # side B never left memory. If the two shapes did not normalise to one
    # value, R4 would report drift on every row.
    assert C.cell_fingerprint([_stored()]) == C.cell_fingerprint([_synth()])


def test_the_fingerprint_is_keyed_on_ticker_date_and_expiry():
    fp = C.cell_fingerprint([_synth(), _synth(ticker="BBB"),
                             _synth(expiry="2026-03-20")])
    assert set(fp) == {("AAA", "2026-01-05", "2026-02-20"),
                       ("BBB", "2026-01-05", "2026-02-20"),
                       ("AAA", "2026-01-05", "2026-03-20")}


def test_rounding_is_the_stores_own_precision_not_a_tolerance():
    # `evaluate` writes entry_net at 6dp and R at 10dp. Differences BELOW that
    # are round-trip noise; differences AT it are real and must survive.
    assert (C.cell_fingerprint([_synth(entry_net=1.2345674999)])
            == C.cell_fingerprint([_synth(entry_net=1.234567)]))
    assert (C.cell_fingerprint([_synth(R=0.1234567891)])
            != C.cell_fingerprint([_synth(R=0.1234567890)]))


def test_a_field_the_gate_compares_cannot_differ_silently():
    for field, other in (("contracts", 4), ("exit_reason", "profit_target"),
                         ("days_held", 13), ("R", 0.2)):
        mine = C.cell_fingerprint([_synth()])
        theirs = C.cell_fingerprint([_synth(**{field: other})])
        assert C.cell_diff(mine, theirs)[2], f"{field} differed and was not caught"


# ── the diff ─────────────────────────────────────────────────────────────────

def test_identical_cells_diff_to_nothing():
    fp = C.cell_fingerprint([_synth(), _synth(ticker="BBB")])
    assert C.cell_diff(fp, dict(fp)) == ([], [], [])


def test_the_diff_separates_missing_extra_and_disagreeing_keys():
    mine = C.cell_fingerprint([_synth(), _synth(ticker="BBB")])
    theirs = C.cell_fingerprint([_synth(ticker="BBB", R=0.9),
                                 _synth(ticker="CCC")])
    only_mine, only_theirs, disagreed = C.cell_diff(mine, theirs)
    assert [k[0] for k in only_mine] == ["AAA"]
    assert [k[0] for k in only_theirs] == ["CCC"]
    assert [k[0] for k in disagreed] == ["BBB"]


# ── no stored expectation ────────────────────────────────────────────────────

def test_r4_carries_no_transcribed_expectation():
    # The regression that would undo the conversion: re-adding a constant off
    # one run. A code-behaviour claim needing a fixed expectation belongs in
    # this directory against a committed fixture, not in the study.
    for name in ("R4_EXPECT", "R4_DOLLAR_TOL", "R3_EXPECT", "VOL_SLEEVE_RUN"):
        assert not hasattr(C, name), f"{name} is back in calendar_hedge"


def test_the_snapshot_subtraction_machinery_is_gone():
    # It reconstructed a past cache by removing the sweep's own additions — an
    # inverse that only held while every later addition was manifested too.
    for name in ("SNAPSHOT_STRUCTURE", "manifest_additions", "snapshot_index",
                 "LEGS_MANIFEST", "_r4_attribute"):
        assert not hasattr(C, name), f"{name} is back in calendar_hedge"


# ── the checkpoint store is keyed on its cache generation ────────────────────

def _store(tmp_path, sigs):
    return C.Store(path=tmp_path / "synth.csv", sigs=sigs)


def _ok_row(ticker="AAA", phash="deadbeef"):
    return dict(structure="calendar", ticker=ticker, date="2026-01-05",
                expiry="2026-02-20", profile_hash=phash, status="ok",
                entry_net="1.0", contracts="2", pnl_pct="0.1",
                exit_reason="time_exit", days_held="5")


def test_a_row_built_under_one_cache_generation_is_not_selected_under_another(tmp_path):
    st = _store(tmp_path, {"AAA": "10@1000"})
    st.put(_ok_row())
    st.flush()
    assert len(st.select("calendar", "deadbeef")) == 1

    # The cache grew: same code, different legs. The stored row describes a
    # candidate this run would no longer build, so it must not be read back.
    grown = C.Store(path=tmp_path / "synth.csv", sigs={"AAA": "11@2000"})
    assert grown.select("calendar", "deadbeef") == []


def test_a_stale_row_is_recomputed_rather_than_hit_as_cached(tmp_path):
    st = _store(tmp_path, {"AAA": "10@1000"})
    st.put(_ok_row())
    st.flush()
    grown = C.Store(path=tmp_path / "synth.csv", sigs={"AAA": "11@2000"})
    assert not grown.has(grown.key("calendar", "AAA", "2026-01-05",
                                   "2026-02-20", "deadbeef"))
    # ... and the row it WOULD have hit is still on disk, under the old
    # signature, so nothing was destroyed to get that answer.
    assert len(grown.rows) == 1


def test_a_row_written_before_the_column_existed_is_never_trusted(tmp_path):
    path = tmp_path / "synth.csv"
    path.write_text(
        ",".join(C.STORE_FIELDS) + "\n"
        + ",".join("" if f != "structure" else "calendar" for f in C.STORE_FIELDS)
        + "\n")
    st = C.Store(path=path, sigs={"AAA": "10@1000"})
    assert st.select("calendar", "") == []


def test_an_untouched_ticker_keeps_its_cached_rows_when_another_is_rescraped(tmp_path):
    # Per-ticker, not whole-cache: a scrape of one name must not empty the store.
    st = _store(tmp_path, {"AAA": "10@1000", "BBB": "10@1000"})
    st.put(_ok_row("AAA"))
    st.put(_ok_row("BBB"))
    st.flush()
    after = C.Store(path=tmp_path / "synth.csv",
                    sigs={"AAA": "11@2000", "BBB": "10@1000"})
    assert [r["ticker"] for r in after.select("calendar", "deadbeef")] == ["BBB"]


def test_a_failure_row_is_looked_up_under_the_current_generation_too(tmp_path):
    st = _store(tmp_path, {"AAA": "10@1000"})
    st.put(dict(structure="calendar", ticker="AAA", date="2026-01-05",
                expiry="2026-02-20", profile_hash=C.FAIL_HASH, status="no_grid"))
    st.flush()
    assert st.failed("calendar", "AAA", "2026-01-05", "2026-02-20") == "no_grid"
    grown = C.Store(path=tmp_path / "synth.csv", sigs={"AAA": "11@2000"})
    assert grown.failed("calendar", "AAA", "2026-01-05", "2026-02-20") is None


# ── vol_sleeve.synthesize honours the narrowing R4 asks for ──────────────────

class _Leg:
    def __init__(self, expiration):
        self.expiration = expiration


class _Trade:
    def __init__(self, expiration):
        self.row = {"entry_underlying": "100"}
        self.legs = [_Leg(expiration)]


def _book():
    return [{"date": "2026-01-05", "ticker": "AAA",
             "t": _Trade(date(2026, 2, 20))}]


def test_synthesize_builds_every_structure_by_default():
    _, diag = VS.synthesize(_book(), {}, require_recon=False)
    built = {k.rsplit("_no_grid", 1)[0] for k in diag if k.endswith("_no_grid")}
    assert built == set(VS.STRUCTURES)


def test_synthesize_narrows_to_the_structures_it_is_given():
    _, diag = VS.synthesize(_book(), {}, require_recon=False,
                            structures=("calendar",))
    assert {k for k in diag if k.endswith("_no_grid")} == {"calendar_no_grid"}
