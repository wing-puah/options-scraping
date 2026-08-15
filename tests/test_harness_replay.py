"""Frozen-fixture regression test for the FROZEN exit-replay engine.

WHY THIS EXISTS
---------------
`scripts/backtest_study/lib/harness.py` is the exit-replay engine every tuning
conclusion in `research/current.md` rests on. Its own docstring says: "DO NOT
'improve' the exit scan, the clamps, or the rounding here ... a behavioural
change invalidates all of it silently (the replay would still run, just
disagree with history)." That is the danger this file guards: the failure mode
is not a crash, it is a study that keeps producing plausible numbers which no
longer mean what the recorded conclusions say they mean.

WHAT IT REPLACED
----------------
Until now the only thing that would notice such a change was a set of
hardcoded expectations embedded in two research studies — `account_sim`'s gate
G1 (220 positions / 90 dates / $63,553) and `calendar_hedge`'s `R3_EXPECT`,
which asserted the same figures. Those were deleted, and rightly: they
fingerprinted ONE data export. Any legitimate refresh of
`backtests/to_evaluate/` — a new signal date, one more proxy row admitted —
moved the totals and broke the gate, so an operator hand-edited the constants
back to green. A check whose expected value is routinely rewritten by hand has
stopped being a regression check; it is a chore that launders drift.

The question those gates were really asking was a CODE question — "does the
frozen replay engine still behave identically?" — asked through a DATA
artifact. Asked directly, against a frozen fixture, it cannot rot: growing the
book cannot invalidate a row that was already exported, and nothing here reads
the live exports at all.

WHAT IS PINNED
--------------
`tests/fixtures/harness_replay.csv` holds 28 cases drawn from the v3 book
(real analysis plays — market data only, no broker fills, no account ids),
each with the trade inputs, the exit profile's knobs SPELLED OUT (so a change
to `book.DEBIT_PROD` cannot silently redefine what the fixture means), and the
`(exit_reason, days_held, round(R, 4))` the engine produced at freeze time.
Every row carries a `why` column stating which branch it is there for; the
classes are, collectively:

  - all nine reachable exit reasons: profit_target, trailing_stop,
    underlying_stop, dollar_stop, be_stop, stop_loss, time_exit, expired,
    cap_open;
  - both sides: debit rows (positive `entry_option_price`) and credit rows
    (negative — `pnl_of`/`dollars` denominate on `abs(entry_net)`, so a credit
    row scores positive on decay);
  - a same-day exit (`days_held == 1`) and two hold-to-expiry rows, plus both
    sides of the `expired` vs `cap_open` split AND a row whose nearest expiry
    lands EXACTLY on `PATH_CAP_DAYS` — only a boundary row can catch that
    comparison being tightened from `<=` to `<`, and the whole v3 book
    contains three;
  - SIX exit-PRIORITY cases, where two or three rules are true on the SAME
    day and only the comparison ORDER decides the answer. Reordering the scan
    is exactly the kind of "harmless" edit that a totals-based gate would wave
    through, so these are the heart of the file;
  - three ROUNDING cases. `replay()` compares `round(pnl_of(m), 10)`, not the
    raw quotient. Only three rows in the entire 795-row v3 book are sensitive
    to that clamp — all three are here. Two of them change exit reason and day
    without it; the third changes only the reported R at 4dp, which pins that
    the ROUNDED value is what gets returned, not merely what gets compared;
  - a TRUNCATION case for the other clamp: `te_day = int(dte_entry * tef)`.
    Replacing that `int()` with a `round()` moves one fixture row's exit from
    day 9 at -0.1475 to day 10 at +0.3944. The plain `debit_time_exit` row
    does NOT discriminate the two — it was added only after a deliberate
    perturbation of `int()` failed to make anything fail;
  - an unpriced day inside the path, which is skipped without evaluating a
    rule yet still counts toward `days_held`;
  - a `trail` set without a `trig`, which must silently no-op (the trap logged
    in Attempt 12) — asserted against the same trade replayed WITH the trigger,
    so the pair proves the latch rather than a coincidence;
  - the `und_buffer` rule with a control: the same trade replayed without the
    buffer exits somewhere else entirely. One `und_buffer` row is replayed
    under the PRE-Attempt-13 credit stop (`sl` 1x) purely because that is the
    only profile in which a real v3 row has `underlying_stop` and a mark stop
    true on the same day — it is a priority fixture, not a claim about
    production.

Assertions are EXACT, never approximate. The rounding is the thing being
pinned, so a tolerance would defeat the point.

If a case here fails, the correct response is almost never to update the
fixture. Either the change to `harness.py` was unintended (revert it), or the
exit mechanism is genuinely being changed — which the module docstring says is
a NEW study with its own calibration gate, copying the module rather than
editing it in place. Rewriting these expectations to match new behaviour
silently rebases every conclusion in `research/current.md` onto an engine that
did not produce them.

KNOWN GAPS
----------
Three branches no v3 row can reach, confirmed by scanning the whole 795-row
book rather than assumed. Recorded here so a later reader knows they were
looked for and not found, not overlooked:

  - the straddle/strangle ("breakeven basis") branch of
    `Trade.breach_thresholds()` — the book holds no short straddle or strangle;
  - `profit_target` vs `trailing_stop` on the SAME day. It needs a peak of at
    least `pt + trail`; across every (pt, trig, trail) combination in the
    studies' variant grids, no row in the book gets there;
  - the `priced[-1]` tail fallback picking a day EARLIER than the last grid
    day. That needs an `expired`/`cap_open` row whose final grid day is
    unpriced; there are none.

This fixture is drawn from real rows and stays that way, so these are not
filled in with invented paths here. `tests/test_exit_replay_gate.py` builds
synthetic paths and is the right home if any of them needs covering.
"""
import csv
from datetime import date
from pathlib import Path

import pytest

from scripts.backtest_study.lib.harness import Trade, replay

FIXTURE = Path(__file__).parent / "fixtures" / "harness_replay.csv"

KNOBS = ("pt", "sl", "trig", "trail", "tef", "be_after", "und_buffer")


def _cases():
    with open(FIXTURE, newline="") as fh:
        return list(csv.DictReader(fh))


CASES = _cases()


def _profile(case: dict) -> dict:
    """The exit knobs, read off the fixture row itself.

    Deliberately NOT imported from `book.DEBIT_PROD` / `CREDIT_PROD`: this file
    tests the ENGINE, and a future change to those production constants must
    not quietly change what these frozen expectations mean.
    """
    return {k: (None if case[k] == "" else float(case[k])) for k in KNOBS}


def _trade(case: dict) -> Trade:
    """Rebuild a `Trade` from the fixture alone.

    `load_underlying=False` always — the real loader reads the ~337MB scraped
    option-history cache under `backtests/`, which a fresh checkout does not
    have. The underlying series the one `und_buffer` case needs is carried in
    the fixture and injected here; `replay()` only ever looks up grid days, so
    a grid-restricted series is exactly equivalent to the cached one.
    """
    t = Trade({
        "signal_date": case["signal_date"],
        "ticker": case["ticker"],
        "structure": case["structure"],
        "entry_option_price": case["entry_option_price"],
        "contracts": case["contracts"],
        "dte_entry": case["dte_entry"],
        "legs": case["legs"],
        "daily_price_csv": case["daily_price_csv"],
    }, load_underlying=False)
    if case["underlying_csv"]:
        t.underlying = {
            date.fromisoformat(d): float(p)
            for d, p in (pair.split(":") for pair in case["underlying_csv"].split(";"))
        }
    return t


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_replay_reproduces_the_frozen_outcome(case):
    """Each fixture row replays to exactly the triple recorded at freeze time.

    A mismatch means `harness.py`'s behaviour moved. See this file's docstring
    before touching the fixture.
    """
    rp = replay(_trade(case), **_profile(case))
    got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
    want = (case["expect_exit_reason"], int(case["expect_days_held"]),
            round(float(case["expect_R"]), 4))
    assert got == want, f'{case["case_id"]}: {case["why"]}'


# ── fixture self-checks: guard the guard ─────────────────────────────────────
# A fixture that quietly lost its interesting rows would still pass every test
# above. These assert the coverage claims the docstring makes.

def test_fixture_covers_every_reachable_exit_reason():
    """All nine reasons `replay()` can emit are represented. A tenth appearing
    here means a new exit rule shipped and this list needs a decision, not an
    edit."""
    assert {c["expect_exit_reason"] for c in CASES} == {
        "profit_target", "trailing_stop", "underlying_stop", "dollar_stop",
        "be_stop", "stop_loss", "time_exit", "expired", "cap_open",
    }


def test_fixture_covers_both_signs_of_entry():
    """Debit and credit rows both present — `pnl_of`/`dollars` denominate on
    `abs(entry_net)`, and a sign-handling regression would only show on one."""
    signs = {float(c["entry_option_price"]) > 0 for c in CASES}
    assert signs == {True, False}


def test_fixture_covers_a_same_day_exit_and_a_hold_to_expiry():
    """The two ends of the holding-period range: an exit on grid day 1, and a
    row that reaches expiry with no rule ever firing."""
    assert any(int(c["expect_days_held"]) == 1 for c in CASES)
    assert any(c["expect_exit_reason"] == "expired" for c in CASES)


def test_fixture_keeps_a_row_sitting_exactly_on_the_path_cap():
    """`cap_reached_expiry = nearest_dte <= PATH_CAP_DAYS`. Only a row whose
    nearest expiry is EXACTLY at the cap distinguishes `<=` from `<`, so this
    asserts the fixture still holds one — a replacement drawn from elsewhere in
    the book would very likely not."""
    from scripts.backtest.legs import parse_legs
    from scripts.backtest_study.lib.harness import PATH_CAP_DAYS

    at_cap = []
    for c in CASES:
        signal = date.fromisoformat(c["signal_date"])
        at_cap.append(min((leg.expiration - signal).days
                          for leg in parse_legs(c["legs"])) == PATH_CAP_DAYS)
    assert any(at_cap), "no row left whose nearest expiry is exactly at the path cap"


def test_fixture_case_ids_are_unique():
    """Duplicate ids would collapse parametrize output and could hide a row."""
    ids = [c["case_id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_every_fixture_row_states_why_it_is_there():
    """The `why` column is the fixture's comment field. A row without one is a
    row nobody can decide about when it fails."""
    assert all(c["why"].strip() for c in CASES)


def test_fixture_carries_no_broker_or_account_fields():
    """These are research rows (analysis plays), not fills. Nothing account-
    identifying may enter a tracked fixture — see CLAUDE.md's `/journal/` rule."""
    banned = {"account", "account_id", "acct", "source_ref", "exec_id",
              "net_liq", "netliquidation", "conid"}
    assert banned.isdisjoint({k.lower() for k in CASES[0]})


def test_trail_without_a_trigger_is_a_no_op_on_the_same_trade():
    """Paired assertion, stated here rather than left implicit in two rows: the
    SAME trade exits `trailing_stop` with `trig` set and falls through to
    `time_exit` without it. Either row alone could pass by coincidence."""
    by_id = {c["case_id"]: c for c in CASES}
    with_trig = by_id["debit_trailing_stop_beats_time_exit"]
    without = by_id["debit_trail_without_trigger_never_fires"]
    assert (with_trig["signal_date"], with_trig["ticker"]) == \
           (without["signal_date"], without["ticker"]), "the pair drifted apart"
    assert with_trig["expect_exit_reason"] == "trailing_stop"
    assert without["expect_exit_reason"] == "time_exit"
    assert without["trail"] and not without["trig"]


def test_fixture_keeps_a_time_exit_row_that_discriminates_int_from_round():
    """`te_day = int(dte_entry * tef)` truncates. This asserts the fixture still
    holds a row where `dte_entry * tef` has a fractional part >= 0.5, i.e. one
    that an `int()` -> `round()` edit would actually move. Without it the
    truncation is untested and the plain time_exit row passes either way."""
    tef_rows = [c for c in CASES if c["tef"] and c["expect_exit_reason"] == "time_exit"]
    assert any(int(c["dte_entry"]) * float(c["tef"]) % 1 >= 0.5 for c in tef_rows), \
        "no time_exit row left where int() and round() disagree"


def test_underlying_stop_case_has_a_no_buffer_control_on_the_same_trade():
    """Same pairing logic for `und_buffer`: without it the trade exits
    elsewhere, so the underlying rule is provably what moved the outcome."""
    by_id = {c["case_id"]: c for c in CASES}
    on = by_id["credit_underlying_stop"]
    off = by_id["credit_underlying_stop_off_without_buffer"]
    assert (on["signal_date"], on["ticker"]) == (off["signal_date"], off["ticker"])
    assert on["expect_exit_reason"] == "underlying_stop"
    assert off["expect_exit_reason"] != "underlying_stop"
    assert off["und_buffer"] == ""
