"""Tests for the `portfolio_delta` study's forked machinery and its band labels.

Three properties carry the study, and they are exactly the three the
pre-registration names as the module's test obligations:

  * `admission_banded` at the DEGENERATE band (the committed `caps.net`) is
    `account_sim.admission` decision-for-decision. The fork exists because a
    signed band is different machinery from a magnitude cap; the moment the
    copy drifts on the shared path, every ARM B cell is measuring the copy.
  * a banded WALK at the committed cap reproduces
    `book_signature(account_sim.simulate(...))` exactly — the study's G-EQUIV,
    pinned here on a small hand-built book so a regression fails on the commit
    that caused it rather than on the next study run.
  * the band labels are exact AT THE EDGES. `[0,0.5)` and `[0.5,1)` are a
    frozen partition; an off-by-one at 0.5 would silently re-cell ARM D's whole
    dose-response.

No CSV, no book, no Sheets export: every record is built here, from a hand-made
`Trade`, so what is pinned is the code and not one export's numbers.
"""
import ast
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.f4_deployment import portfolio_delta as PD  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402


# ── fixtures: a reduced book, built by hand ──────────────────────────────────

def _cfg(**kw):
    """A `Cfg` at the committed account values, any of which a test overrides.

    Mirrors `tests/test_studies_account_sim.py::_cfg` deliberately: the two
    files must agree about what "the committed account" means, or the
    equivalence pinned here would be an equivalence between two different
    simulations.
    """
    base = dict(label="t", capital=25_000.0, per_pos_cap=0.25, net_cap=2.50,
                risk_pct=0.02, max_per_day=3)
    base.update(kw)
    return A.Cfg(**base)


def _grid_len(dte: int, signal: date) -> int:
    end = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _rec(signal: date, ticker: str, *, mark: float, entry: float = 5.00,
         mlpc: float = 400.0, delta: float = 0.25, underlying: float = 150.0,
         dte: int = 20, structure: str = "bull_call_spread", tier: str = "A",
         score: float = 30.0, credit: bool = False, source: str = "real"):
    """One deployed-book record: a single long call whose marks are flat.

    Flat marks keep the replay deterministic and the exit reason stable, which
    is what makes a `book_signature()` comparison a statement about ADMISSION
    rather than about the exit engine.
    """
    n = _grid_len(dte, signal)
    exp = signal + timedelta(days=dte)
    row = {
        "signal_date": signal.isoformat(), "ticker": ticker,
        "structure": structure, "contracts": "1", "dte_entry": str(dte),
        "entry_option_price": f"{entry}", "entry_underlying": str(underlying),
        "legs": f"{ticker}:{exp.isoformat()}:100:C +1",
        "daily_price_csv": ",".join(f"{mark}" for _ in range(n)),
    }
    return {"t": Trade(row), "credit": credit, "structure": structure,
            "mech_cell": "PROD", "max_loss_per_contract": mlpc,
            "delta": delta, "date": signal.isoformat(), "ticker": ticker,
            "tier": tier, "score_total": score, "post13c": True,
            "source": source, "dte": dte}


def _bear_rec(signal: date, ticker: str = "SPY"):
    """A bear-DEBIT sleeve candidate: negative delta, so it can pull net down.

    Sized so ONE contract sits inside the per-position delta-notional cap
    (0.30 x 100 x 100 = $3,000 against 0.25 x $25,000 = $6,250) — the sleeve
    has to be admissible at the shipped size before a re-sized one means
    anything.
    """
    return _rec(signal, ticker, mark=4.80, entry=5.00, mlpc=500.0,
                delta=-0.30, underlying=100.0, structure="bear_put_spread")


def _book():
    """Three signal dates, three candidates each — small enough to run fast,
    wide enough that the day cap, the net cap and the release rule all fire."""
    days = [date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 21)]
    recs = []
    for i, d in enumerate(days):
        # Every candidate is admissible at one contract under the committed
        # per-position cap (0.25 x $25,000 = $6,250 of delta-notional), so what
        # the walk does is decided by the NET cap and the day cap — which is
        # what these tests are about.
        recs.append(_rec(d, "AAA", mark=6.20, delta=0.25, underlying=150.0,
                         score=40.0 - i))                       # dn $3,750
        recs.append(_rec(d, "BBB", mark=4.10, delta=0.20, underlying=100.0,
                         mlpc=250.0, tier="B", score=30.0 - i))  # 2c, dn $4,000
        recs.append(_rec(d, "CCC", mark=5.50, delta=0.15, underlying=120.0,
                         mlpc=300.0, tier="B", score=20.0 - i))  # dn $1,800
    return recs


def _day_lists(recs):
    return P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)


# ════════════════════════════════════════════════════════════════════════════
# (1) admission_banded at the degenerate band == account_sim.admission
# ════════════════════════════════════════════════════════════════════════════

# Chosen to land on both sides of every constraint, including exactly ON the
# boundaries (the EPS tolerance is part of what the copy must reproduce).
_ADMISSION_CASES = [
    (500.0, 5_000.0, 25_000.0, 0.0),          # inside every cap
    (900.0, 100.0, 800.0, 0.0),               # cash binds
    (100.0, 6_300.0, 25_000.0, 0.0),          # per-position delta binds
    (100.0, 6_250.0, 25_000.0, 0.0),          # exactly ON the per-position cap
    (100.0, 6_000.0, 25_000.0, 60_000.0),     # net delta binds
    (100.0, 6_000.0, 25_000.0, 56_500.0),     # exactly ON the net cap
    (100.0, -6_000.0, 25_000.0, 60_000.0),    # a SHORT position, net absorbed
    (100.0, -6_000.0, 25_000.0, -60_000.0),   # net short and getting shorter
    (0.0, 0.0, 0.0, 0.0),                     # degenerate everything
]


@pytest.mark.parametrize("args", _ADMISSION_CASES)
@pytest.mark.parametrize("net_band", [None, 2.50])
def test_admission_banded_degenerate_matches_account_sim(args, net_band):
    """The fork's whole licence: at `caps.net` it IS `account_sim.admission`.

    Both the boolean AND the named binding constraint must match — the
    constraint name is what the census attributes an exclusion to, so a copy
    that agreed on the verdict and disagreed on the reason would corrupt the
    census without changing a single position.
    """
    cfg = _cfg()
    assert PD.admission_banded(*args, cfg, net_band=net_band) == \
        A.admission(*args, cfg)


@pytest.mark.parametrize("args", _ADMISSION_CASES)
def test_admission_banded_degenerate_matches_under_a_remarked_equity(args):
    """`equity` is forwarded identically. The study never re-marks, but the
    copy must not silently drop the parameter that would make it diverge if a
    later arm did."""
    cfg = _cfg()
    for equity in (None, 25_000.0, 40_000.0, 12_500.0):
        assert PD.admission_banded(*args, cfg, equity=equity,
                                   net_band=cfg.net_cap) == \
            A.admission(*args, cfg, equity=equity)


def test_admission_banded_ceiling_is_the_only_thing_the_band_changes():
    cfg = _cfg()
    # 1.00x equity = $25,000 of net delta-notional; 2.50x = $62,500.
    args = (100.0, 6_000.0, 25_000.0, 20_000.0)
    assert A.admission(*args, cfg) == (True, None)
    assert PD.admission_banded(*args, cfg, net_band=2.50) == (True, None)
    assert PD.admission_banded(*args, cfg, net_band=1.00) == (False, "net_delta")
    # ...and an infinite band never binds on net, while cash/per-position still do.
    assert PD.admission_banded(*args, cfg, net_band=float("inf")) == (True, None)
    assert PD.admission_banded(900.0, 100.0, 800.0, 0.0, cfg,
                               net_band=float("inf")) == (False, "cash")
    assert PD.admission_banded(100.0, 6_300.0, 25_000.0, 0.0, cfg,
                               net_band=float("inf")) == (False, "per_pos_delta")


def test_solve_contracts_banded_degenerate_matches_account_sim():
    kw = dict(max_c=10, unit_reserved=10.0, unit_dn=2_500.0, cash=25_000.0,
              net_open=0.0, cfg=_cfg())
    assert PD.solve_contracts_banded(**kw, net_band=None) == \
        A.solve_contracts(**kw)
    assert PD.solve_contracts_banded(**kw, net_band=kw["cfg"].net_cap) == \
        A.solve_contracts(**kw)
    # A tighter band can only ever reduce the count.
    assert PD.solve_contracts_banded(**kw, net_band=0.10) <= A.solve_contracts(**kw)


def test_admission_banded_matches_decision_for_decision_along_a_fixture_walk():
    """The states an actual walk visits, not just hand-picked tuples.

    The walk is replayed once, and at every admission decision the two
    implementations are asked the same question with the same ledger state.
    """
    recs = _book()
    cfg = _cfg()
    day_lists = _day_lists(recs)
    checked = 0
    for _, ranked in day_lists:
        cash, net_open = cfg.capital, 0.0
        for rec in ranked:
            mlpc = rec["max_loss_per_contract"]
            c = A.risk_contracts(mlpc, cfg.budget)
            unit_dn = A.signed_dn(rec, 1)
            got = PD.admission_banded(c * mlpc, c * unit_dn, cash, net_open, cfg,
                                      net_band=cfg.net_cap)
            assert got == A.admission(c * mlpc, c * unit_dn, cash, net_open, cfg)
            checked += 1
            if got[0]:
                cash -= c * mlpc
                net_open += c * unit_dn
    assert checked >= 9, "the fixture walk must actually offer candidates"


# ════════════════════════════════════════════════════════════════════════════
# (2) the banded walk at caps.net reproduces book_signature(simulate(...))
# ════════════════════════════════════════════════════════════════════════════

def test_banded_walk_at_the_committed_cap_reproduces_the_shipped_book():
    """G-EQUIV, pinned in pytest on a reduced book.

    `book_signature` is order-sensitive and carries contracts, R, dollars and
    the exit reason, so this is the strongest available statement: the fork
    makes the same trades, in the same order, at the same size, with the same
    outcome.
    """
    recs = _book()
    day_lists = _day_lists(recs)
    cfg = _cfg(label="equiv")
    ref = A.simulate(day_lists, cfg, cache=A.new_cache())
    got = PD.simulate_banded(day_lists, cfg, cache=A.new_cache())
    assert ref.taken, "the fixture book must admit positions or this proves nothing"
    assert A.book_signature(got) == A.book_signature(ref)
    assert dict(got.census) == dict(ref.census)
    assert got.ledger.realized == pytest.approx(ref.ledger.realized)
    assert not got.ledger.violations


def test_banded_walk_reproduces_the_shipped_book_with_the_sleeve_on():
    """ARM H* forks the sleeve path too, so the sleeve path is pinned too."""
    recs = _book()
    bear = [_bear_rec(d) for d in
            (date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 21))]
    day_lists = _day_lists(recs)
    bear_by_day = {r["date"]: [r] for r in bear}
    cfg = _cfg(label="equiv-hedge", hedge=True)
    ref = A.simulate(day_lists, cfg, bear_by_day=bear_by_day, cache=A.new_cache())
    got = PD.simulate_banded(day_lists, cfg, bear_by_day=bear_by_day,
                             cache=A.new_cache())
    assert any(p.hedge for p in ref.taken), "the sleeve must actually open"
    assert A.book_signature(got) == A.book_signature(ref)
    assert dict(got.census) == dict(ref.census)


@pytest.mark.parametrize("net_band", [None, 2.50])
def test_banded_walk_is_degenerate_for_both_spellings_of_the_committed_cap(net_band):
    """`net_band=None` and `net_band=cfg.net_cap` must be the same walk — the
    two spellings G-EQUIV and ARM B respectively use."""
    day_lists = _day_lists(_book())
    cfg = _cfg()
    ref = A.simulate(day_lists, cfg, cache=A.new_cache())
    got = PD.simulate_banded(day_lists, cfg, cache=A.new_cache(),
                             net_band=net_band)
    assert A.book_signature(got) == A.book_signature(ref)


def test_a_tighter_band_can_only_remove_positions():
    """The ceiling grid's monotonicity as a CODE property, not a P&L reading.

    A band strictly tighter than the committed cap must hold a subset of the
    committed walk's positions on the first date it binds; it may never invent
    one. (Later dates can diverge either way — the walk is stateful — so the
    claim is scoped to the census bucket that has to grow.)
    """
    day_lists = _day_lists(_book())
    cfg = _cfg()
    loose = PD.simulate_banded(day_lists, cfg, cache=A.new_cache(), net_band=2.50)
    tight = PD.simulate_banded(day_lists, cfg, cache=A.new_cache(), net_band=0.05)
    assert len(tight.signal_pos) < len(loose.signal_pos)
    assert tight.census["net_delta"] > loose.census["net_delta"]
    assert not tight.ledger.violations


def test_simulate_banded_refuses_compounding_rather_than_ignoring_it():
    day_lists = _day_lists(_book())
    with pytest.raises(ValueError, match="path-INDEPENDENT"):
        PD.simulate_banded(day_lists, _cfg(compound=True), cache=A.new_cache())


# ════════════════════════════════════════════════════════════════════════════
# (3) band labelling — exact at the edges
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("x,expected", [
    (0.0, 0),               # the lower edge of band 0 is INCLUSIVE
    (0.0001, 0),
    (0.4999999, 0),
    (0.5, 1),               # the boundary belongs to the UPPER band
    (0.7, 1),
    (0.9999999, 1),
    (1.0, 2),
    (1.5, 2),
    (1.9999999, 2),
    (2.0, 3),
    (5.0, 3),
    (1e9, 3),
])
def test_band_index_boundaries_are_exact(x, expected):
    assert PD.band_index(x) == expected


@pytest.mark.parametrize("x", [-1e-9, -0.01, -1.0, -50.0])
def test_a_net_short_session_is_out_of_bands_not_folded_into_the_first_band(x):
    """The registered bands start at 0. A net-SHORT session is a FINDING on a
    book the registration calls long-only, so it gets its own label and is
    counted, never rounded into `[0.0,0.5)`."""
    assert PD.band_index(x) is None
    assert PD.band_label(None) == "OUT-OF-BANDS"


@pytest.mark.parametrize("x", [None, float("nan")])
def test_a_missing_reading_is_unbanded(x):
    assert PD.band_index(x) is None


def test_band_labels_name_the_frozen_partition():
    assert [PD.band_label(i) for i in range(len(PD.BANDS))] == [
        "[0.0,0.5)", "[0.5,1.0)", "[1.0,2.0)", "[2.0,inf)"]


def test_the_bands_partition_the_non_negative_line():
    """Every band's upper edge is the next band's lower edge, and the last is
    unbounded — so no non-negative reading can fall between two bands."""
    for (lo, hi), (nlo, _) in zip(PD.BANDS, PD.BANDS[1:]):
        assert hi == nlo and lo < hi
    assert PD.BANDS[0][0] == 0.0
    assert PD.BANDS[-1][1] == float("inf")


# ════════════════════════════════════════════════════════════════════════════
# ARM H* — the ONLY thing it changes is the contract count
# ════════════════════════════════════════════════════════════════════════════

def test_hedge_target_sizes_enough_contracts_to_reach_the_target():
    # net open $60,000; target $25,000; each sleeve contract carries -$5,000.
    # 35,000 / 5,000 = 7 contracts exactly.
    assert PD.hedge_contracts_for_target(60_000.0, -5_000.0, 25_000.0) == 7
    # A non-integral requirement rounds UP — landing INSIDE the target, never
    # just outside it.
    assert PD.hedge_contracts_for_target(61_000.0, -5_000.0, 25_000.0) == 8


def test_hedge_target_floors_at_one_when_the_book_is_already_inside():
    """The sleeve position the shipped rule already opened stays opened — only
    its SIZE changes. A book inside the target takes the 1-contract floor."""
    assert PD.hedge_contracts_for_target(10_000.0, -5_000.0, 25_000.0) == 1
    assert PD.hedge_contracts_for_target(25_000.0, -5_000.0, 25_000.0) == 1
    assert PD.hedge_contracts_for_target(-90_000.0, -5_000.0, 25_000.0) == 1


def test_hedge_target_will_not_scale_a_candidate_that_moves_net_the_wrong_way():
    assert PD.hedge_contracts_for_target(60_000.0, +5_000.0, 25_000.0) == 1
    assert PD.hedge_contracts_for_target(60_000.0, 0.0, 25_000.0) == 1


def test_hedge_target_changes_only_the_sleeve_and_never_the_signal_picks():
    """Selection is untouched: the sleeve enters AFTER the day's picks, so on
    the FIRST date the signal positions are identical whatever the target."""
    recs = _book()
    bear = [_bear_rec(d) for d in
            (date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 21))]
    day_lists = _day_lists(recs)
    bear_by_day = {r["date"]: [r] for r in bear}
    cfg = _cfg(hedge=True)
    shipped = PD.simulate_banded(day_lists, cfg, bear_by_day=bear_by_day,
                                 cache=A.new_cache())
    targeted = PD.simulate_banded(day_lists, cfg, bear_by_day=bear_by_day,
                                  cache=A.new_cache(), hedge_target=0.15)
    first = day_lists[0][0]
    sig_a = [(p.rec["ticker"], p.contracts) for p in shipped.signal_pos
             if p.rec["date"] == first]
    sig_b = [(p.rec["ticker"], p.contracts) for p in targeted.signal_pos
             if p.rec["date"] == first]
    assert sig_a == sig_b and sig_a
    # ...and the sleeve on that date is re-sized rather than re-chosen.
    hedge_a = [p for p in shipped.taken if p.hedge and p.rec["date"] == first]
    hedge_b = [p for p in targeted.taken if p.hedge and p.rec["date"] == first]
    assert [p.rec["ticker"] for p in hedge_a] == [p.rec["ticker"] for p in hedge_b]
    assert hedge_b[0].contracts > hedge_a[0].contracts


# ════════════════════════════════════════════════════════════════════════════
# session-open exposure — the quantity ARM D bands on
# ════════════════════════════════════════════════════════════════════════════

def test_open_net_before_excludes_the_sessions_own_entries():
    """The band is read BEFORE the day's picks. `session_series` counts a
    position on its own entry session, which is why this study derives its own
    reading and reconciles the two rather than banding on the series."""
    day_lists = _day_lists(_book())
    sim = PD.simulate_banded(day_lists, _cfg(), cache=A.new_cache())
    first_sess = day_lists[0][1][0]["t"].grid[0]
    assert PD.open_net_before(sim, first_sess) == 0.0
    ser = A.session_series(sim)
    assert ser[first_sess]["net"] > 0.0

    # The identity the report reconciles: series net == session-open net + what
    # opened that session.
    by_date = PD.entry_sessions(day_lists)
    checked, bad = PD.reconcile_session_series(sim, by_date)
    assert checked >= 1 and bad == 0


def test_session_bands_label_every_deployed_date_even_an_empty_one():
    """`entry_sessions` reads the CANDIDATE lists, so a date an arm admitted
    nothing on still carries a band — which is what lets G-INVENTORY compare
    two arms date for date."""
    day_lists = _day_lists(_book())
    sim = PD.simulate_banded(day_lists, _cfg(), cache=A.new_cache(),
                             net_band=0.0)
    assert not sim.signal_pos, "a zero band must admit nothing"
    bands = PD.session_bands(sim, PD.entry_sessions(day_lists), 25_000.0)
    assert len(bands) == len(day_lists)
    assert all(b == 0 for _, _, b in bands.values())


# ════════════════════════════════════════════════════════════════════════════
# the runner contract
# ════════════════════════════════════════════════════════════════════════════

def test_designed_refusal_exit_codes_is_a_plain_module_level_set_literal():
    """`run.py` AST-parses this constant and never imports the module. An alias
    to `era.DESIGNED_REFUSAL_EXIT_CODES` (a frozenset CALL) would be invisible
    to it, and a designed refusal would be reported as FAILED with its report
    deleted."""
    src = Path(PD.__file__).read_text()
    for node in ast.parse(src).body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name)
                        and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
                        for t in node.targets)):
            assert isinstance(node.value, ast.Set)
            assert {ast.literal_eval(e) for e in node.value.elts} == {2, 3}
            break
    else:
        pytest.fail("DESIGNED_REFUSAL_EXIT_CODES is not a module-level assignment")


def test_the_frozen_grids_are_the_registered_ones():
    """Anti-tuning, as a test: bands at four, ceilings at five, targets at
    three, ARM N at 200 seeded draws, power stop at 25 dates, cells at 20."""
    assert len(PD.BANDS) == 4
    assert PD.CEILINGS == (1.0, 1.5, 2.0, 2.5, float("inf"))
    assert PD.HEDGE_TARGETS == (1.0, 1.5, 2.0)
    assert PD.DRAWS == 200 and PD.SEED == 20260819
    assert PD.MIN_MOVED_DATES == 25
    assert PD.MIN_CELL_N == 20
    assert PD.DELTA_TOL == 0.05
    assert PD.MIN_DELTA_AGREE == 0.90 and PD.MIN_DELTA_AVAIL == 0.95
