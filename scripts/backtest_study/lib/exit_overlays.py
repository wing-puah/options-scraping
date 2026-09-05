"""Exit OVERLAYS — composition wrappers around the FROZEN replay harness.

Infrastructure for `f2_management/exit_drawdown.py` (registration:
`research/pre-registrations/f2_management/exit_drawdown.md`). Nothing here is a
study; nothing here prints; nothing here decides a verdict.

WHY A COMPOSITION AND NOT A FORK
--------------------------------
`scripts/backtest_study/lib/harness.py` is FROZEN — every recorded tuning
conclusion rests on its exact exit scan, clamps and rounding, and its own
docstring says a behavioural change invalidates all of it *silently*. So this
module never edits it and never re-implements its loop. Each overlay rule
answers ONE question — "on which 1-indexed grid session does my rule first
fire?" — and `compose_earlier()` then takes the EARLIER of the harness's own
exit and the overlay's session. `staged_exit.py` needed the opposite shape (a
profile SWAP mid-path) and paid for it with a verbatim local copy of the loop;
an earlier-of composition needs no copy at all, which is why it is preferred
here.

The registration's **G-FORK** gate is the mechanical statement of that: every
overlay, with its own rule DISABLED, must reproduce `harness.replay` /
`account_sim.replay_sized` EXACTLY, on all rows, in both eras. `DISABLED` is
that no-op, and `tests/test_exit_overlays.py` pins the identity against the
committed `tests/fixtures/harness_replay.csv`.

THE INFORMATION SET, AND WHERE IT IS ENFORCED
---------------------------------------------
An exit decided at the CLOSE of session `d` may read: spread marks <= `d`,
underlying bars <= `d`, option `Volume` <= `d`, and option `Open Int` <= `d-1`
— Barchart publishes open interest the next morning, so same-session OI is not
knowable at that close. Each of those bounds lives in exactly one place:

  * marks        — `harness.replay` and `compose_earlier` only ever index
                   `t.marks[i-1]`, never past it.
  * bars         — `atr_stop_session` freezes ATR14 at the ENTRY session via
                   `underlying_features.atr14_pct(bars, entry_day)`, which
                   itself reads only bars `<= as_of`, and then compares closes
                   session by session.
  * Volume       — `vol_climax_session`'s median is EXPANDING and as-of `d`:
                   post-entry volumes on sessions up to AND INCLUDING `d`.
                   Taking it over the whole holding period would read volume
                   dated after `d` into `d`'s own trigger, which is exactly the
                   leak G1 exists to catch.
  * Open Int     — `lagged_by_session()` is the ONE encoding of the one-session
                   lag: the value usable at session `i` (i.e. on `t.grid[i-1]`)
                   is the one dated `t.grid[i-2]`. Applied at READ time, so no
                   downstream caller can forget it.

MISSING IS MISSING
------------------
`t.grid` is a WEEKDAY grid; market holidays are unpriced sessions, and a bar,
an OI value or a volume that is absent on a grid day is SKIPPED exactly as
`harness.replay` skips a `None` mark. It is never read as a flat move, a 100%
OI drop, or a zero volume. Blank `Open Int` is MISSING; `Open Int` literally 0
is a VALID full unwind — `load_oi` keeps the two distinct (`None` vs `0.0`),
because conflating them either fabricates exits or hides them.

THE MEMO KEY
------------
`account_sim.replay_sized`'s docstring records the 2026-08-13 G5 bug: a memo
key that omitted the exit profile served one arm's answer to another. The
overlay params are a second dimension of exactly that hazard, so every key
produced here is `replay_sized`'s key EXTENDED with the whole `Overlay`. The
`Overlay` is a frozen dataclass and is hashed in full — including its label —
because over-keying only costs a recomputation while under-keying is the bug
class.
"""
from __future__ import annotations

import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.lib.harness import (  # noqa: E402
    MAX_LOSS_ABS, Trade, replay,
)
from scripts.backtest_study.lib.underlying import (  # noqa: E402
    Bar, entry_day, load_bars,
)
from scripts.backtest_study.lib.underlying_features import atr14_pct  # noqa: E402

# Exit reasons this module can emit. They are NEW reasons, never a reuse of one
# of `harness.replay`'s nine: a reader segregating overlay exits from harness
# exits must be able to do it on the reason alone.
REASON_ATR = "atr_stop"
REASON_OI = "oi_unwind"
REASON_VOL = "vol_climax"
OVERLAY_REASONS = (REASON_ATR, REASON_OI, REASON_VOL)

# ARM O's volume variant: leg volume(d) >= VOL_CLIMAX_MULT x its expanding
# post-entry median AND the mark closed against the position. Registered, not
# swept — the registration fixes "3x" and names one variant only.
VOL_CLIMAX_MULT = 3.0

#: ARM O's registered exclusion: a row whose LAGGED `Open Int` is blank on this
#: share or more of its hold sessions is EXCLUDED from the arm and counted.
#: It lives HERE, next to `oi_blank_share` and `default_oi_for`, because it has
#: to bind at the READ BOUNDARY — a threshold that only the census knows about
#: is a threshold the run does not apply. `f2_management/exit_drawdown.py`
#: re-exports this constant rather than declaring a second one.
OI_BLANK_EXCLUSION = 0.20


# ════════════════════════════════════════════════════════════════════════════
# Data loaders
# ════════════════════════════════════════════════════════════════════════════

def leg_cache_path(leg: Leg, cache_dir: Path | None = None) -> Path:
    """Where a leg's scraped option history lives. `harness.Trade._load_underlying`
    builds the same path; this is that one line, named."""
    return cache_path(cache_dir or HISTORY_CACHE, leg.ticker, leg.expiration,
                      leg.strike, leg.opt_type)


@lru_cache(maxsize=None)
def _leg_flow(path_str: str) -> tuple[dict[date, float | None], dict[date, float | None]]:
    """`({date: Open Int}, {date: Volume})` for one cached option file.

    Both maps carry a key for EVERY dated row in the file, with `None` where the
    cell was blank. That is the whole point: a caller must be able to tell "the
    session is in the file but the field is blank" (missing — skip it) from
    "`Open Int` is 0" (a real full unwind) from "the session is not in the file
    at all" (no data for that day). `to_float` returns `None` for a blank or a
    sentinel and `0.0` for a literal zero, which is exactly that distinction.

    Cached, and the cached dicts are returned by reference — callers must not
    mutate them (same contract as `underlying._load_ohlc_cache`).
    """
    p = Path(path_str)
    if not p.exists():
        return ({}, {})
    try:
        details = parse_history_details(p.read_text(), require_mark=False)
    except Exception:
        return ({}, {})
    oi = {d: to_float(r.get("Open Int")) for d, r in details.items()}
    vol = {d: to_float(r.get("Volume")) for d, r in details.items()}
    return (oi, vol)


def load_oi(leg: Leg | None, cache_dir: Path | None = None) -> dict[date, float | None]:
    """`{date: Open Int}` for one leg — blank stays `None`, a literal 0 stays `0.0`.

    Modelled on `harness.Trade._load_underlying` (same `cache_path` +
    `parse_history_details(require_mark=False)` + `lib.parsing.to_float` path),
    which is what the registration asks for. There is no OI reader anywhere else
    in the repo.

    NOTE the lag is NOT applied here — this is the RAW dated series. The
    one-session lag is applied when the series is read against a position's
    grid, in `lagged_by_session()`, so that the single encoding sits next to the
    rule that needs it rather than being baked into a loader that other cuts
    (coverage census, diagnostics) also call.
    """
    if leg is None:
        return {}
    return _leg_flow(str(leg_cache_path(leg, cache_dir)))[0]


def load_volume(leg: Leg | None, cache_dir: Path | None = None) -> dict[date, float | None]:
    """`{date: Volume}` for one leg. Same file, same blank-vs-zero contract.

    Volume is NOT lagged: the registration's information set admits same-session
    `Volume` and lags `Open Int` alone.
    """
    if leg is None:
        return {}
    return _leg_flow(str(leg_cache_path(leg, cache_dir)))[1]


def entry_long_leg(t: Trade) -> Leg | None:
    """The single LONG leg of a debit vertical, or `None`.

    ARM O reads "the entry LONG leg", which is well defined only when there is
    exactly one. A structure with none (a pure credit sale) or several (a ratio,
    a condor) has no such leg, and returning `None` puts the row in the arm's
    counted exclusions rather than picking one on a guess.
    """
    longs = [leg for leg in (t.legs or []) if leg.qty > 0]
    return longs[0] if len(longs) == 1 else None


# ════════════════════════════════════════════════════════════════════════════
# Grid geometry — the one-session lag and the unpriced-day skip
# ════════════════════════════════════════════════════════════════════════════

def lagged_by_session(t: Trade, series: Mapping[date, float | None]) -> list[float | None]:
    """A 1-indexed lookup of `series` LAGGED one session onto `t.grid`.

    THE ONE ENCODING OF THE OI LAG. `out[i]` is the value usable at session `i`
    — i.e. at the close of `t.grid[i-1]` — and it is the value dated
    `t.grid[i-2]`, the PREVIOUS grid session. `out[0]` and `out[1]` are `None`:
    session 1 is the entry session and there is no prior grid session to read.

    Index 0 is unused padding so the list is indexed by session number directly;
    `len(out) == len(t.grid) + 1`.
    """
    out: list[float | None] = [None] * (len(t.grid) + 1)
    for i in range(2, len(t.grid) + 1):
        out[i] = series.get(t.grid[i - 2])
    return out


def first_priced_at_or_after(t: Trade, session: int) -> int | None:
    """The first session `>= session` whose mark is priced, or `None`.

    This is `harness.replay`'s `if m is None: continue` expressed as a lookup.
    An overlay that fires on an unpriced day cannot transact there, so it
    advances to the next priced session exactly as the frozen engine does.
    """
    for i in range(max(1, session), len(t.marks) + 1):
        if t.marks[i - 1] is not None:
            return i
    return None


def mark_pnl_at(t: Trade, session: int) -> float | None:
    """Rounded mark P&L at 1-based session `session`, or `None` if unpriced.

    Same rounding as the frozen engine (`round(pnl_of(m), 10)` — the 1-ulp clamp
    on the 4-decimal CSV round-trip). An overlay exit must report the value the
    harness would have reported at that session, not a differently-rounded one.
    """
    if session < 1 or session > len(t.marks):
        return None
    m = t.marks[session - 1]
    return None if m is None else round(t.pnl_of(m), 10)


def position_direction(structure: str | None) -> int | None:
    """`+1` for a `bull_*` structure, `-1` for `bear_*`, else `None`.

    The registration says ARM U's direction "comes from the structure (`bull_*`
    vs `bear_*`)" and scopes the arm to DEBIT VERTICALS. Anything else — a
    `long_call`, an `iron_condor`, an unrecognised label — returns `None` and is
    an EXCLUSION, not a guessed direction. Widening this to `long_*` would widen
    the arm's population past what was registered.
    """
    s = (structure or "").strip().lower()
    if s.startswith("bull"):
        return 1
    if s.startswith("bear"):
        return -1
    return None


# ════════════════════════════════════════════════════════════════════════════
# The rules — each returns the 1-indexed FIRST-FIRING session, or None
# ════════════════════════════════════════════════════════════════════════════

def atr_stop_session(t: Trade, bars: Mapping[date, Bar], k: float) -> int | None:
    """ARM U. First session whose underlying close is against the position by
    `>= k x ATR14`, measured from the ENTRY-session close. `None` = never fired,
    or the row cannot support the rule.

    ATR14 is FROZEN AT ENTRY: `underlying_features.atr14_pct(bars, entry)` — a
    SIMPLE 14-session mean of true range, NOT Wilder-smoothed — multiplied by the
    entry close to give a dollar distance. It is computed once, at entry, and
    never re-armed on a new peak. That entry-anchored, non-re-arming property is
    what distinguishes this from the three trailing stops the record already
    rejected; it does not exempt it from the continuation diagnostic.

    `None` (the row is EXCLUDED and counted by the caller) when:
      * there are no bars for the ticker;
      * `entry_day()` cannot anchor the fill (no bar on a grid day within
        `MAX_ENTRY_LAG_DAYS` — a hole in the series, not a holiday);
      * `atr14_pct` is `None`, which covers BOTH the below-minimum-observations
        case AND the close-only `Price~` fallback (no high/low, so no true
        range) — the registration's two ATR exclusions fall out of one check;
      * the structure gives no direction (see `position_direction`);
      * the frozen distance is non-positive, which would fire at zero move.

    Split-rescaled tickers are fine: the move is a ratio taken inside ONE bar
    series and a constant adjustment factor cancels.

    NO LOOKAHEAD: `atr14_pct` reads only bars `<= entry`, and the scan reads a
    session's own close. A grid day with no bar is SKIPPED — never a zero move.

    The exclusion test itself lives in `atr_frozen_distance()` so there is ONE
    encoding of "can the ATR rule govern this row?" — `replay_overlaid` has to
    ask that question BEFORE it decides whether variant (b) may strip the
    shipped `sl`, and two derivations of one rule is how two callers disagree.
    """
    frozen = atr_frozen_distance(t, bars, k)
    if frozen is None:
        return None
    ed, entry_close, distance = frozen
    sign = position_direction(t.structure)
    for i, day in enumerate(t.grid, start=1):
        if day < ed:
            continue
        bar = bars.get(day)
        if bar is None or bar.c is None:
            continue
        # Signed move WITH the position: negative means it went against us.
        move = (bar.c - entry_close) * sign
        if move <= -distance:
            return i
    return None


def atr_frozen_distance(t: Trade, bars: Mapping[date, Bar],
                        k: float) -> tuple[date, float, float] | None:
    """`(entry_day, entry_close, k x ATR14 in dollars)`, or `None` if ARM U
    cannot govern this row at all.

    THE SINGLE ENCODING OF ARM U's EXCLUSIONS, and the reason it is its own
    function: `atr_stop_session` needs the distance, while `replay_overlaid`
    needs only the yes/no — whether the ATR rule GOVERNS the row — because
    variant (b) replaces the shipped `sl` with it and must not strip a stop
    from a row the rule can never fire on. Those two questions must be answered
    by the same code or a row can end up with neither stop.

    `None` for each registered exclusion, in the census's own order: no bars for
    the ticker; no `entry_day()` anchor; `atr14_pct` `None` (which is BOTH the
    below-minimum-observations case and the close-only `Price~` fallback, since
    a close-only series has no true range); no `bull_*`/`bear_*` direction; a
    non-positive frozen distance, which would fire at a zero move.
    """
    if not bars:
        return None
    if position_direction(t.structure) is None:
        return None
    ed = entry_day(t, sessions=set(bars))
    if ed is None:
        return None
    entry_bar = bars.get(ed)
    if entry_bar is None or not entry_bar.c or entry_bar.c <= 0:
        return None
    atr_pct = atr14_pct(bars, ed)
    if atr_pct is None:
        return None
    distance = float(k) * atr_pct * entry_bar.c
    if distance <= 0:
        return None
    return ed, float(entry_bar.c), distance


def atr_governs(t: Trade, bars: Mapping[date, Bar], k: float) -> bool:
    """Whether ARM U's stop can govern this row — the exclusion test, named.

    A row for which this is False is one of the registration's ARM U EXCLUSIONS
    ("EXCLUDED and counted"), and variant (b) may NOT strip its `sl`: it replays
    the SHIPPED profile unchanged.
    """
    return atr_frozen_distance(t, bars, k) is not None


def oi_unwind_session(t: Trade, oi: Mapping[date, float | None], x: float) -> int | None:
    """ARM O. First session where the LAGGED `Open Int` has fallen to
    `<= (1 - x) x OI_max`, `OI_max` being the running max of the same lagged
    series since entry. `None` = never fired.

    THE LAG IS THE POINT. `lagged_by_session` supplies the value usable at
    session `i`, which is the one dated `t.grid[i-2]`; session 1 has no prior
    grid session and is therefore never evaluable. Reading `t.grid[i-1]`'s own
    OI would be reading a number Barchart does not publish until the next
    morning.

    The running max INCLUDES the session under test, which is what "running max
    ... over the sessions since entry" says and is also the conservative
    reading: a value that is itself the new max can only fire if it is <= 0.

    `OI_max` must be strictly positive before the rule can fire. A leg whose
    lagged OI has never been positive has nothing to unwind, and firing on
    `0 <= 0` there would be an artifact of the arithmetic, not a flow read.
    Once a positive max HAS been seen, a lagged OI of literally 0 fires — that
    is the full unwind the registration calls valid.

    A `None` value (blank cell, or no row for that date) is SKIPPED exactly as an
    unpriced mark is; it is never read as a 100% drop.
    """
    if not oi:
        return None
    lag = lagged_by_session(t, oi)
    running_max: float | None = None
    for i in range(2, len(t.grid) + 1):
        v = lag[i]
        if v is None:
            continue
        running_max = v if running_max is None else max(running_max, v)
        if running_max <= 0:
            continue
        if v <= (1.0 - float(x)) * running_max:
            return i
    return None


def vol_climax_session(t: Trade, vol: Mapping[date, float | None],
                       mult: float = VOL_CLIMAX_MULT) -> int | None:
    """ARM O's one volume variant. First session `d` where the leg's own volume
    is `>= mult x` its EXPANDING post-entry median AND the mark closed AGAINST
    the position. `None` = never fired.

    "Expanding and as-of `d`" is binding: the median is taken over the leg's
    post-entry volumes on sessions up to AND INCLUDING `d`, never over the whole
    holding period — the latter reads volume dated after `d` into `d`'s own
    trigger and is precisely the leak G1 exists to catch.

    Same-session `Volume` IS admissible; only `Open Int` is lagged.

    Sessions with a missing volume are SKIPPED, never read as zero, and the
    median is taken over the OBSERVED values only. A session whose expanding
    window holds no observed volume cannot form a median and so cannot fire —
    which, since `d`'s own volume must be observed for the comparison to exist
    at all, means the window is never empty when the rule is evaluated. No
    additional minimum-observation constant is invented here: the registration
    fixes none, and one chosen at build time would be an unregistered knob.

    "The mark closed against the position" = the rounded mark P&L at `d` is
    negative. A session with no mark cannot be judged and is skipped.
    """
    if not vol:
        return None
    observed: list[float] = []
    for i, day in enumerate(t.grid, start=1):
        v = vol.get(day)
        if v is None:
            continue
        observed.append(float(v))
        median = statistics.median(observed)
        if median <= 0:
            continue
        pl = mark_pnl_at(t, i)
        if pl is None:
            continue
        if v >= float(mult) * median and pl < 0:
            return i
    return None


# ════════════════════════════════════════════════════════════════════════════
# Composition
# ════════════════════════════════════════════════════════════════════════════

def compose_earlier(t: Trade, base: dict,
                    overlays: Sequence[tuple[str, int | None]]) -> dict:
    """The EARLIER of the harness's own exit and the overlays' first firings.

    `base` is `harness.replay(t, **profile)`'s dict; `overlays` is a sequence of
    `(exit_reason, session | None)` pairs, `session` being 1-indexed as the rule
    functions above return it. Returns a dict of the same shape
    (`exit_reason`, `days_held`, `pnl_pct`).

    THE TIE ORDER, TOTAL AND DECLARED:
      1. the HARNESS wins an exact tie — an overlay session equal to
         `base["days_held"]` leaves the frozen engine's own reason and value
         standing, so a composition can only ever move an exit EARLIER, never
         relabel one;
      2. among overlays, the FIRST in `overlays` order wins a tie. Callers fix
         that order once (see `_overlay_sessions`) rather than relying on dict
         iteration.

    MECHANICS, in this order:
      * each overlay session is CLAMPED to `1..len(t.grid)` so the index math
        `Pos.exit_sess` does downstream always holds;
      * it is then ADVANCED to the next PRICED session, exactly as
        `harness.replay` skips a `None` mark — an overlay cannot transact on a
        day with no mark. An overlay whose clamped session has no priced session
        at or after it is DROPPED (it cannot fire);
      * only a strictly earlier surviving session replaces the base.

    The returned `pnl_pct` is `round(t.pnl_of(mark), 10)` — the frozen engine's
    own rounding, so an overlay exit and a harness exit on the same session
    report the identical number.
    """
    best_session = int(base["days_held"])
    best_reason = base["exit_reason"]
    from_base = True

    for reason, session in overlays:
        if session is None:
            continue
        clamped = max(1, min(int(session), len(t.grid)))
        landed = first_priced_at_or_after(t, clamped)
        if landed is None:
            continue
        if landed < best_session:
            best_session, best_reason, from_base = landed, reason, False

    if from_base:
        return dict(base)
    pl = mark_pnl_at(t, best_session)
    # `first_priced_at_or_after` guarantees a mark here; the guard is a tripwire
    # for a future edit that changes that, not a silent fallback.
    assert pl is not None, "composed exit landed on an unpriced session"
    return dict(exit_reason=best_reason, days_held=best_session, pnl_pct=pl)


def knob_profile(pt: float | None, sl: float | None = None,
                 tef: float | None = None) -> dict:
    """One ARM W grid point as an exit profile: `{pt, sl, tef}`.

    `None` means the rule is OFF, which is exactly how `harness.replay`'s
    keyword defaults read it — `sl=None` runs no stop loss, `tef=None` no time
    exit. The other harness knobs (`trig`/`trail`/`be_after`/`und_buffer`) are
    deliberately ABSENT rather than set to `None`: ARM W's grid is three
    dimensions and a profile that mentioned the others would invite a fourth.
    """
    return dict(
        pt=None if pt is None else float(pt),
        sl=None if sl is None else float(sl),
        tef=None if tef is None else float(tef),
    )


# ════════════════════════════════════════════════════════════════════════════
# ARM P — partial scale-out
# ════════════════════════════════════════════════════════════════════════════

def _resized(t: Trade, contracts: int) -> Trade:
    """`t` rebuilt at `contracts` contracts.

    `Trade` is rebuilt from `t.row` rather than mutated because the frozen
    engine's dollar stop reads `t.contracts` through `t.dollars()`, and the row
    is the only input that count comes from. This mirrors
    `account_sim.replay_sized`'s own `row["contracts"] = str(scaled)` block
    exactly — including NOT carrying `t.underlying` across, so both code paths
    in this module see the same trade the host study's replay sees.
    """
    row = dict(t.row)
    row["contracts"] = str(int(contracts))
    return Trade(row)


def partial_scaleout(t: Trade, prof: dict,
                     pt: float | None = None) -> tuple[dict, dict] | None:
    """ARM P. Both halves of a scaled-out position, as two replay dicts.

    Half the contracts exit at the SHIPPED profit target; the other half replays
    the same profile with `pt=None`. Returns
    `(pt_half, rest_half)` — each a `harness.replay` dict extended with
    `contracts` and `half` — or `None` when the position cannot be split.

    * `pt` overrides the profit target of the first half; by default the half
      keeps whatever `prof` already carries (the shipped `pt .90` for a debit
      row), so the shipped knob has exactly one source of truth.
    * ODD counts: the `pt` half takes `ceil(n/2)`, the `pt=None` half
      `floor(n/2)` — the registration fixes this, it is not a build choice.
    * `n = 1` CANNOT be split (one half would be zero contracts, which is not a
      position) and returns `None`. Such rows are EXCLUDED from ARM P and
      counted in its census.

    Each half is replayed on its OWN rebuilt `Trade`, because the frozen dollar
    stop scales with the contract count: replaying both halves off the full-size
    trade would apply a full-size dollar stop to a half-size position.

    Quote R, not dollars, for the per-row comparison — the contract counts
    differ from the shipped row's. (The account-level MTM drawdown co-primary is
    a whole-book dollar figure and is unaffected by that scoping; see the
    registration.)
    """
    n = int(t.contracts)
    if n < 2:
        return None
    top = -(-n // 2)          # ceil(n/2)
    bottom = n // 2           # floor(n/2)

    prof_pt = dict(prof) if pt is None else {**prof, "pt": float(pt)}
    prof_rest = {**prof, "pt": None}

    a = replay(_resized(t, top), **prof_pt)
    b = replay(_resized(t, bottom), **prof_rest)
    return (dict(a, contracts=top, half="pt"),
            dict(b, contracts=bottom, half="rest"))


# ════════════════════════════════════════════════════════════════════════════
# The overlay spec and the drop-in replayers
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Overlay:
    """One arm's cell: which knobs to replay under, and which overlay rules run.

    Frozen and fully hashable ON PURPOSE — the whole object goes into the replay
    memo key (see the module docstring), so two cells can never serve each other
    a cached answer.

    Fields:
      `profile`          ARM W. A full knob override, replacing the row's
                         shipped profile. Accepts a dict and normalises it to a
                         sorted tuple; `None` means "use the shipped profile".
      `atr_k`            ARM U's `k`. `None` = the ATR stop is off.
      `atr_replaces_sl`  ARM U variant (b): the ATR stop REPLACES `sl` (the
                         profile's `sl` is set to `None`). Variant (a) — ADDED
                         to the shipped `sl .75` — is `False`, the default.
                         Inert while `atr_k` is `None`.
      `oi_x`             ARM O's `X`. `None` = the flow-unwind rule is off.
      `vol_climax`       ARM O's one volume variant, on/off.
      `vol_mult`         that variant's multiple; registered at 3x.
      `label`            reporting only. It is still hashed into the memo key —
                         over-keying costs a recomputation, under-keying is the
                         2026-08-13 G5 bug class.
    """

    profile: tuple[tuple[str, float | None], ...] | None = None
    atr_k: float | None = None
    atr_replaces_sl: bool = False
    oi_x: float | None = None
    vol_climax: bool = False
    vol_mult: float = VOL_CLIMAX_MULT
    label: str = ""

    def __post_init__(self) -> None:
        p = self.profile
        if isinstance(p, Mapping):
            object.__setattr__(
                self, "profile",
                tuple(sorted(p.items(), key=lambda kv: kv[0])))

    @property
    def profile_dict(self) -> dict:
        return dict(self.profile or ())

    @property
    def enabled(self) -> bool:
        """False for the G-FORK no-op: nothing overridden, no rule armed."""
        return (self.profile is not None or self.atr_k is not None
                or self.oi_x is not None or bool(self.vol_climax))


#: The G-FORK no-op. `make_replayer(DISABLED)` must reproduce
#: `account_sim.replay_sized` field for field, on every row, in both eras.
DISABLED = Overlay()


def default_profile_for(rec: dict) -> dict:
    """The SHIPPED profile for a row, from `account_sim.profile_for`.

    Imported inside the function, not at module scope. `account_sim` is the HOST
    study and will import this module's replayers; a module-scope import here
    would close that cycle at import time. `live_select.py` reaches back into
    `account_sim` the same deferred way, for the same reason.
    """
    from scripts.backtest_study.f4_deployment.account_sim import profile_for
    return profile_for(rec)


def default_bars_for(rec: dict) -> dict[date, Bar]:
    return load_bars(rec["t"].ticker)


#: `id(Trade) -> (Trade, days_held)` for `shipped_hold_sessions`. The Trade is
#: kept in the value so its id cannot be recycled under a live cache entry; the
#: rows are alive for the whole run anyway (`recs` holds them), so this adds no
#: lifetime, only a lookup.
_HOLD_SESSIONS: dict[int, tuple[Trade, int]] = {}


def shipped_hold_sessions(rec: dict,
                          profile_for: Callable[[dict], dict]
                          = default_profile_for) -> int:
    """`days_held` of the row under the SHIPPED profile — ARM O's denominator.

    The registration excludes a row blank on ">= 20% of its HOLD SESSIONS", and
    the hold window is the one the position is actually held for, NOT the whole
    weekday grid out to expiry / the 120-day path cap. Measured on the grid, a
    row that is held six sessions and blank on all six reads as blank on 6/120
    = 5% and is admitted — the exclusion then runs in the PERMISSIVE direction,
    which is the one it exists to close.

    THE SHIPPED REPLAY'S `days_held` IS THE ONLY NON-CIRCULAR HOLD WINDOW here.
    ARM O's own exit depends on the series being read, so using the ARM's hold
    window would make the exclusion depend on the rule it gates. The shipped
    profile's window is fixed before the arm runs and is the same for every
    ARM O cell, which is what makes the census and the read boundary agree.

    Contract scaling does not move it: `replay`'s exits are per-unit `pnl_pct`
    thresholds, so the unscaled `rec["t"]` gives the same `days_held` as
    `replay_overlaid`'s rebuilt-at-`scaled`-contracts trade.
    """
    t = rec["t"]
    hit = _HOLD_SESSIONS.get(id(t))
    if hit is not None and hit[0] is t:
        return hit[1]
    n = int(replay(t, **dict(profile_for(rec)))["days_held"])
    _HOLD_SESSIONS[id(t)] = (t, n)
    return n


def default_oi_for(rec: dict) -> dict[date, float | None]:
    """The OI series ARM O actually reads — WITH the registered exclusion applied.

    THE EXCLUSION BINDS HERE, AT THE READ BOUNDARY, and nowhere else. The
    registration says "rows with blank OI on >= 20% of their hold sessions are
    EXCLUDED and counted"; a threshold applied only in the census is a threshold
    the run does not apply, and the arm would still exit rows the registration
    forbids it to touch. Returning `{}` is exactly the "no series" case —
    `oi_unwind_session` returns `None` on an empty series, so the row replays
    the shipped profile and is counted in ARM O's census as excluded.

    THE DENOMINATOR IS THE SHIPPED HOLD WINDOW, not the whole grid — see
    `shipped_hold_sessions`. `f2_management/exit_drawdown.py::arm_o_census`
    calls the same helper, so the counted exclusions ARE the applied ones.

    `oi_blank_share` returning `None` (a hold window too short for the lag to be
    evaluable, so no hold session can be read) is likewise not usable by the
    arm and is excluded on the same footing.
    """
    oi = load_oi(entry_long_leg(rec["t"]))
    if not oi:
        return {}
    share = oi_blank_share(rec["t"], oi, shipped_hold_sessions(rec))
    if share is None or share >= OI_BLANK_EXCLUSION:
        return {}
    return oi


def default_vol_for(rec: dict) -> dict[date, float | None]:
    return load_volume(entry_long_leg(rec["t"]))


def _overlay_sessions(t: Trade, spec: Overlay, rec: dict,
                      bars_for, oi_for, vol_for) -> list[tuple[str, int | None]]:
    """`[(reason, session)]` for the armed rules, in the DECLARED tie order.

    ATR before OI before the volume variant. The order is fixed here, once, so
    two rules firing on the same session always resolve the same way (see
    `compose_earlier`'s tie order). Each loader is called only when its rule is
    armed — a disabled overlay must not touch the disk, or G-FORK would depend
    on caches being present.
    """
    out: list[tuple[str, int | None]] = []
    if spec.atr_k is not None:
        out.append((REASON_ATR, atr_stop_session(t, bars_for(rec), spec.atr_k)))
    if spec.oi_x is not None:
        out.append((REASON_OI, oi_unwind_session(t, oi_for(rec), spec.oi_x)))
    if spec.vol_climax:
        out.append((REASON_VOL, vol_climax_session(t, vol_for(rec), spec.vol_mult)))
    return out


def replay_overlaid(rec: dict, contracts: int, stop: float, spec: Overlay,
                    profile: dict | None = None, cache: dict | None = None,
                    *,
                    profile_for: Callable[[dict], dict] = default_profile_for,
                    bars_for: Callable[[dict], dict] = default_bars_for,
                    oi_for: Callable[[dict], dict] = default_oi_for,
                    vol_for: Callable[[dict], dict] = default_vol_for) -> dict:
    """`account_sim.replay_sized` with `spec`'s overlay composed onto it.

    Same call contract, same return contract:
    `dict(exit_reason, days_held, R, dollars, stop_exact)`.

    WHY THIS CANNOT CALL `replay_sized` AS A BLACK BOX. `replay_sized` rebuilds
    the row at `contracts x (MAX_LOSS_ABS / stop)` so the frozen $1,000 dollar
    stop lands on the caller's stop instead, then divides the dollars back. The
    overlay rules read that SAME trade — its grid, its marks, its rounding — so
    the scaling block has to be re-done HERE, around the composition, rather
    than applied to an answer that has already been reduced to five fields. The
    block below is `replay_sized`'s, reproduced line for line; do not "tidy" it.

    CREDIT ROWS ARE NEVER OVERLAID. Every arm keeps `CREDIT_PROD` on a credit
    row (there is no validated credit replay in this book), so a credit `rec`
    runs `DISABLED` whatever `spec` says — and, because `DISABLED` is exactly
    the G-FORK no-op, that path IS `replay_sized`.
    """
    # `profile or profile_for(rec)`, exactly as `replay_sized` writes it — an
    # empty dict falls through to the shipped profile there, and a composition
    # that "fixed" that would diverge from the host on a corner case.
    prof = dict(profile) if profile else dict(profile_for(rec))
    active = DISABLED if rec.get("credit") else spec

    if active.profile is not None:
        prof = active.profile_dict
    if active.atr_k is not None and active.atr_replaces_sl:
        # ARM U VARIANT (b) MAY ONLY STRIP A STOP IT REPLACES. The registration
        # scopes ARM U to the rows the ATR rule can GOVERN and EXCLUDES the rest
        # ("EXCLUDED and counted": no cached bars, no entry anchor, a close-only
        # `Price~` series, `atr14_pct` None, no bull_/bear_ direction). Removing
        # `sl` before asking that question left an excluded row with NEITHER the
        # shipped stop NOR an ATR stop — a naked-stop arm nobody registered, and
        # one whose book would be read as ARM U's. So the row is routed to the
        # SHIPPED profile unchanged instead, which is what an exclusion means.
        if atr_governs(rec["t"], bars_for(rec), active.atr_k):
            prof = {**prof, "sl": None}

    if cache is None:
        cache = {}
    # `replay_sized`'s key, EXTENDED with the whole overlay. The extra element
    # also makes these keys structurally unable to collide with `replay_sized`'s
    # own 4-tuples when a caller shares one cache between the two.
    key = (id(rec), int(contracts), round(float(stop), 6),
           tuple(sorted(prof.items(), key=lambda kv: kv[0])), active)
    if key in cache:
        return cache[key]

    # ── the scaling block, from account_sim.replay_sized ─────────────────────
    scaled_exact = MAX_LOSS_ABS * contracts / stop
    scaled = int(round(scaled_exact))
    exact = abs(scaled_exact - scaled) < 1e-9
    if not exact:
        scaled = int(math.ceil(scaled_exact))
    if abs(stop - MAX_LOSS_ABS / 2.0) < 1e-9 or abs(stop - MAX_LOSS_ABS) < 1e-9:
        assert exact, f"scaling identity non-integral: {scaled_exact}"
    row = dict(rec["t"].row)
    row["contracts"] = str(scaled)
    t2 = Trade(row)
    rp = replay(t2, **prof)
    # ─────────────────────────────────────────────────────────────────────────

    sessions = _overlay_sessions(t2, active, rec, bars_for, oi_for, vol_for)
    if sessions:
        rp = compose_earlier(t2, rp, sessions)

    out = dict(exit_reason=rp["exit_reason"], days_held=rp["days_held"],
               R=rp["pnl_pct"],
               dollars=t2.dollars(rp["pnl_pct"]) * contracts / scaled,
               stop_exact=exact)
    cache[key] = out
    return out


def make_replayer(overlay_spec: Overlay, **loaders) -> Callable[..., dict]:
    """A drop-in for `account_sim.replay_sized` that applies `overlay_spec`.

    The returned callable has `replay_sized`'s EXACT signature —
    `(rec, contracts, stop, profile=None, cache=None)` — so `simulate(...,
    replayer=...)` can call it positionally or by keyword without knowing which
    it got.

    `loaders` overrides `profile_for` / `bars_for` / `oi_for` / `vol_for`
    (each `rec -> data`). They are NOT part of the memo key: they supply the
    same series a rule would have read off disk, and a run that swapped one
    mid-flight would be a different study, not a different cell. Tests inject
    them; the study leaves them at their defaults.
    """
    def replayer(rec: dict, contracts: int, stop: float,
                 profile: dict | None = None, cache: dict | None = None) -> dict:
        return replay_overlaid(rec, contracts, stop, overlay_spec,
                               profile=profile, cache=cache, **loaders)
    replayer.overlay = overlay_spec           # type: ignore[attr-defined]
    return replayer


def make_blockwise_replayer(block_of_date: Callable[[date], object],
                            spec_by_block: Mapping[object, Overlay],
                            default: Overlay | None = None,
                            **loaders) -> Callable[..., dict]:
    """A drop-in replayer that dispatches each row's overlay by its BLOCK.

    This is what makes the walk-forward book ONE stitched out-of-sample
    `simulate()`: `block_of_date(rec["t"].signal_date)` names the block a
    position's signal date falls in, and `spec_by_block` says which
    configuration that block's TRAIN fit selected. Every position is therefore
    replayed under a configuration chosen without seeing its own date.

    BURN-IN IS NOT SILENTLY SHIPPED-PROFILE. A date with no block — the dates
    that exist only to train the first fit — raises `KeyError` unless the caller
    passes an explicit `default`. The registration excludes burn-in from the OOS
    headline and forbids folding it in under the shipped profile; making the
    caller say out loud what happens to those dates is how that stays true.

    The memo key already carries the whole `Overlay`, so two blocks that
    selected different configurations can never serve each other a cached
    answer, and two blocks that selected the SAME one correctly share it.
    """
    def replayer(rec: dict, contracts: int, stop: float,
                 profile: dict | None = None, cache: dict | None = None) -> dict:
        block = block_of_date(rec["t"].signal_date)
        spec = spec_by_block.get(block) if block is not None else None
        if spec is None:
            if default is None:
                raise KeyError(
                    f"no overlay for block {block!r} "
                    f"(signal date {rec['t'].signal_date}); pass an explicit "
                    f"`default` if burn-in dates are meant to replay")
            spec = default
        return replay_overlaid(rec, contracts, stop, spec,
                               profile=profile, cache=cache, **loaders)
    replayer.spec_by_block = spec_by_block    # type: ignore[attr-defined]
    return replayer


# ════════════════════════════════════════════════════════════════════════════
# Coverage helpers — G-COV's inputs, computed here, printed by the study
# ════════════════════════════════════════════════════════════════════════════

def oi_blank_share(t: Trade, oi: Mapping[date, float | None],
                   hold_sessions: int | None = None) -> float | None:
    """Share of the row's HOLD sessions whose lagged OI is missing, or `None`.

    ARM O excludes rows blank on `>= 20%` of their hold sessions. "Missing" is
    a blank cell OR no row for that date; a literal `0` is NOT missing. Measured
    on the LAGGED series, because that is the series the rule actually reads.

    `hold_sessions` defaults to the whole grid, which is the RIGHT default for
    a caller that wants the grid-wide picture and the WRONG one for the
    registered exclusion — the arm's callers (`default_oi_for` and the study's
    `arm_o_census`) both pass `shipped_hold_sessions(rec)`. Session 1 is never
    evaluable (no prior grid session) and is excluded from both numerator and
    denominator, so a one-session window returns `None` rather than a
    fabricated 0% or 100%.
    """
    last = len(t.grid) if hold_sessions is None else min(int(hold_sessions), len(t.grid))
    if last < 2:
        return None
    lag = lagged_by_session(t, oi)
    blanks = sum(1 for i in range(2, last + 1) if lag[i] is None)
    return blanks / (last - 1)


def bar_coverage(t: Trade, bars: Mapping[date, Bar]) -> dict:
    """`{has_bars, entry_day, source, has_ohlc, atr14_pct}` for one row.

    Everything G-COV needs to say why a row is in or out of ARM U, without the
    study re-deriving the entry anchor or the ATR a second time (two derivations
    of one rule is how the daily card and the fortnightly audit would disagree).
    """
    out = {"has_bars": bool(bars), "entry_day": None, "source": None,
           "has_ohlc": False, "atr14_pct": None}
    if not bars:
        return out
    ed = entry_day(t, sessions=set(bars))
    out["entry_day"] = ed
    if ed is None:
        return out
    bar = bars.get(ed)
    if bar is not None:
        out["source"] = bar.source
        out["has_ohlc"] = bar.has_ohlc
    out["atr14_pct"] = atr14_pct(bars, ed)
    return out


__all__ = [
    "Overlay", "DISABLED",
    "REASON_ATR", "REASON_OI", "REASON_VOL", "OVERLAY_REASONS",
    "VOL_CLIMAX_MULT",
    "atr_stop_session", "oi_unwind_session", "vol_climax_session",
    "compose_earlier", "knob_profile", "partial_scaleout",
    "load_oi", "load_volume", "leg_cache_path", "entry_long_leg",
    "lagged_by_session", "first_priced_at_or_after", "mark_pnl_at",
    "position_direction",
    "replay_overlaid", "make_replayer", "make_blockwise_replayer",
    "oi_blank_share", "bar_coverage", "atr_frozen_distance", "atr_governs",
    "default_profile_for", "default_bars_for", "default_oi_for",
    "default_vol_for", "shipped_hold_sessions", "OI_BLANK_EXCLUSION",
]
