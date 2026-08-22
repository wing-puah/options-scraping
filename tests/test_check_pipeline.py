"""Verdict logic for the collection-tier watchdog.

Every test here exercises the PURE half of scripts/check_pipeline.py against a
hand-built state dict — no Drive, no Sheets, no yfinance, nothing mocked. Same
shape as tests/test_align_tab_headers.py, and the reason the pure/IO split
exists at all.

The bulk of these are FALSE-ALARM cases. A watchdog that cries wolf gets
ignored, at which point it is worse than not having one, so each way the checker
could fabricate an alarm gets pinned here.
"""
import pytest

from datetime import datetime, timezone

from check_pipeline import (
    EXIT_GAP, EXIT_OK, MISSING, NOT_DUE, OK, PARTIAL,
    HealthConfig, StageSpec, evaluate, load_config, settled_sessions, silence_gap,
    summarise, CONFIG_PATH,
)

PREFIXES = ("etfs-flow", "stocks-flow")
SESSIONS = ["2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20"]

SCRAPE = StageSpec("scrape", "flow_present", 0, 1.0, PREFIXES, "")
COMPILE = StageSpec("compile", "compiled_present", 0, 1.0, PREFIXES, "")
OI = StageSpec("enrich_oi", "enrichment", 1, 0.95, PREFIXES, "oi")
IV = StageSpec("iv_percentile", "enrichment", 0, 0.90, PREFIXES, "iv")
CP = StageSpec("counterpart_iv", "counterpart", 0, 0.90, (), "")
BASE = StageSpec("baseline", "baseline_row", 0, 1.0, (), "")

CFG = HealthConfig(stages=(), lookback_sessions=4, max_silence_sessions=3,
                   commit_age_warn_days=45, chain_complete_utc_hour=23)


def _healthy(sessions=SESSIONS, snapshots=9):
    """A state dict where every stage is complete for every session."""
    return {
        "flow": {s: {p: {"compiled": True, "snapshots": snapshots} for p in PREFIXES}
                 for s in sessions},
        "enrich": {s: {p: {"oi": (100, 100), "iv": (50, 50), "price": (50, 50)}
                       for p in PREFIXES} for s in sessions},
        "counterpart": {s: (40, 40) for s in sessions},
        "baseline": set(sessions),
    }


def _verdicts(findings, stage):
    return {f.session: f.verdict for f in findings if f.stage == stage}


# ── the baseline: a healthy pipeline is silent ──────────────────────────────

def test_healthy_pipeline_reports_nothing():
    findings = evaluate(_healthy(), [SCRAPE, COMPILE, OI, IV, CP, BASE], SESSIONS)
    assert not [f for f in findings if f.verdict not in (OK, NOT_DUE)]
    code, report = summarise(findings, SESSIONS, "2026-08-20", 0, 3, CFG)
    assert code == EXIT_OK
    assert "OK" in report.splitlines()[0]


# ── false alarms that must NOT fire ─────────────────────────────────────────

def test_holiday_is_simply_not_a_session():
    """A market holiday never reaches evaluate(): it is absent from the session
    list, because the list comes from dates SPY actually traded. No holiday
    table, no exclusion rule, nothing to alarm about."""
    holiday = "2026-05-25"
    sessions = [s for s in SESSIONS if s != holiday]
    findings = evaluate(_healthy(sessions), [SCRAPE, COMPILE], sessions)
    assert holiday not in {f.session for f in findings}


def test_newest_session_oi_is_not_due_never_missing():
    """enrich_oi is structurally D+1 — OI CHANGE for session D needs D+1's open
    interest. The newest session's OI being absent is NORMAL."""
    state = _healthy()
    state["enrich"][SESSIONS[-1]] = {p: {"oi": (0, 100)} for p in PREFIXES}
    findings = evaluate(state, [OI], SESSIONS)
    v = _verdicts(findings, "enrich_oi")
    assert v[SESSIONS[-1]] == NOT_DUE
    assert all(v[s] == OK for s in SESSIONS[:-1])


def test_lag_is_counted_in_sessions_not_calendar_days():
    """Friday -> Monday is ONE session apart. Counting lag in calendar days
    would walk the check back into the weekend and assert against a day that
    never traded."""
    sessions = ["2026-08-13", "2026-08-14", "2026-08-17"]   # Thu, Fri, Mon
    state = _healthy(sessions)
    state["enrich"]["2026-08-17"] = {p: {"oi": (0, 100)} for p in PREFIXES}
    v = _verdicts(evaluate(state, [OI], sessions), "enrich_oi")
    assert v == {"2026-08-13": OK, "2026-08-14": OK, "2026-08-17": NOT_DUE}


def test_gcd_snapshots_are_healthy_not_missing():
    """gc_flow.py --all TRASHES raw snapshots once verified present in the
    compiled file, so `snapshots == 0` on a past session is the healthy steady
    state. Counting snapshots would fail on every historical date."""
    state = _healthy()
    for p in PREFIXES:
        state["flow"][SESSIONS[0]][p] = {"compiled": True, "snapshots": 0}
    f = _verdicts(evaluate(state, [SCRAPE], SESSIONS), "scrape")
    assert f[SESSIONS[0]] == OK


def test_thin_session_with_nothing_to_enrich_passes():
    """A quiet day with no contracts is not a failure — 0/0 is complete."""
    state = _healthy()
    state["enrich"][SESSIONS[0]] = {p: {"oi": (0, 0), "iv": (0, 0)} for p in PREFIXES}
    state["counterpart"][SESSIONS[0]] = (0, 0)
    findings = evaluate(state, [OI, IV, CP], SESSIONS)
    assert all(f.verdict in (OK, NOT_DUE) for f in findings if f.session == SESSIONS[0])


def test_half_day_passes_on_thin_but_present_data():
    """A short session still trades, so SPY has a bar and the data is merely
    thin. Thin must not read as missing."""
    state = _healthy()
    for p in PREFIXES:
        state["flow"][SESSIONS[-1]][p] = {"compiled": True, "snapshots": 2}
    state["enrich"][SESSIONS[-1]] = {p: {"iv": (3, 3)} for p in PREFIXES}
    findings = evaluate(state, [SCRAPE, COMPILE, IV], SESSIONS)
    assert all(f.verdict == OK for f in findings if f.session == SESSIONS[-1])


def test_commit_age_inside_the_bound_is_quiet():
    findings = evaluate(_healthy(), [SCRAPE], SESSIONS)
    assert summarise(findings, SESSIONS, "2026-08-20", 0, 44, CFG)[0] == EXIT_OK


# ── real gaps that MUST fire ────────────────────────────────────────────────

def test_missing_compile_is_reported():
    state = _healthy()
    state["flow"][SESSIONS[2]]["stocks-flow"] = {"compiled": False, "snapshots": 0}
    findings = evaluate(state, [COMPILE], SESSIONS)
    assert _verdicts(findings, "compile")[SESSIONS[2]] == MISSING
    assert summarise(findings, SESSIONS, "2026-08-20", 0, 3, CFG)[0] == EXIT_GAP


def test_enrichment_below_threshold_is_partial():
    """'Ran but produced almost nothing' is the failure a green workflow hides."""
    state = _healthy()
    state["enrich"][SESSIONS[0]]["etfs-flow"]["iv"] = (44, 100)
    findings = evaluate(state, [IV], SESSIONS)
    gap = [f for f in findings if f.verdict == PARTIAL]
    assert len(gap) == 1 and "44/100" in gap[0].detail and "need 90%" in gap[0].detail


def test_threshold_boundary_is_inclusive():
    state = _healthy()
    state["enrich"][SESSIONS[0]]["etfs-flow"]["iv"] = (90, 100)
    assert _verdicts(evaluate(state, [IV], SESSIONS), "iv_percentile")[SESSIONS[0]] == OK
    state["enrich"][SESSIONS[0]]["etfs-flow"]["iv"] = (89, 100)
    assert _verdicts(evaluate(state, [IV], SESSIONS), "iv_percentile")[SESSIONS[0]] == PARTIAL


def test_never_ran_reads_differently_from_ran_and_undershot():
    """The email must distinguish the two — they need different fixes."""
    state = _healthy()
    state["enrich"][SESSIONS[0]]["etfs-flow"]["iv"] = None          # no compiled file
    state["enrich"][SESSIONS[1]]["etfs-flow"]["iv"] = (10, 100)     # ran, undershot
    by_session = {f.session: f for f in evaluate(state, [IV], SESSIONS)}
    assert by_session[SESSIONS[0]].verdict == MISSING
    assert by_session[SESSIONS[1]].verdict == PARTIAL
    assert by_session[SESSIONS[0]].detail != by_session[SESSIONS[1]].detail


def test_missing_baseline_row_is_reported():
    state = _healthy()
    state["baseline"].discard(SESSIONS[1])
    assert _verdicts(evaluate(state, [BASE], SESSIONS), "baseline")[SESSIONS[1]] == MISSING


def test_missing_counterpart_sidecar_is_reported():
    state = _healthy()
    state["counterpart"][SESSIONS[1]] = None
    f = [x for x in evaluate(state, [CP], SESSIONS) if x.session == SESSIONS[1]][0]
    assert f.verdict == MISSING and "sidecar" in f.detail


# ── the outage headline ─────────────────────────────────────────────────────

def test_total_outage_leads_with_pipeline_silent():
    """A dead pipeline must not present as N interchangeable per-stage gaps."""
    state = _healthy()
    state["flow"] = {SESSIONS[0]: state["flow"][SESSIONS[0]]}
    assert silence_gap(state, SESSIONS) == 3
    findings = evaluate(state, [SCRAPE, COMPILE], SESSIONS)
    code, report = summarise(findings, SESSIONS, "2026-08-20", 3, 3, CFG)
    assert code == EXIT_GAP
    assert "PIPELINE SILENT" in report
    assert report.index("PIPELINE SILENT") < report.index("gap(s)")


def test_silence_gap_is_zero_while_data_still_lands():
    assert silence_gap(_healthy(), SESSIONS) == 0


def test_one_stale_session_is_not_yet_an_outage():
    """Below max_silence_sessions, report the gaps — do not declare an outage."""
    state = _healthy()
    del state["flow"][SESSIONS[-1]]
    assert silence_gap(state, SESSIONS) == 1
    _, report = summarise(evaluate(state, [SCRAPE], SESSIONS), SESSIONS,
                          "2026-08-20", 1, 3, CFG)
    assert "PIPELINE SILENT" not in report


def test_stale_repo_warns_before_github_disables_the_schedules():
    """>45 days without a commit and GitHub is 15 days from disabling every
    schedule in the repo, this watchdog included."""
    findings = evaluate(_healthy(), [SCRAPE], SESSIONS)
    code, report = summarise(findings, SESSIONS, "2026-08-20", 0, 46, CFG)
    assert code == EXIT_GAP
    assert "REPO QUIET" in report


def test_unknown_commit_age_does_not_alarm():
    """No git checkout is not evidence of a quiet repo."""
    assert summarise(evaluate(_healthy(), [SCRAPE], SESSIONS), SESSIONS,
                     "2026-08-20", 0, None, CFG)[0] == EXIT_OK


# ── the in-flight session ───────────────────────────────────────────────────

def _utc(iso, hour):
    return datetime.fromisoformat(iso).replace(hour=hour, tzinfo=timezone.utc)


def test_todays_session_is_in_flight_until_the_chain_runs():
    """Compile Flow fires at 22:30 UTC on the session it compiles. Mid-session
    none of its downstream evidence exists yet — demanding it is a false alarm,
    and false alarms are how an operator learns to ignore the watchdog."""
    assert settled_sessions(SESSIONS, _utc(SESSIONS[-1], 14), 23) == SESSIONS[:-1]


def test_session_settles_once_the_chain_has_run():
    assert settled_sessions(SESSIONS, _utc(SESSIONS[-1], 23), 23) == SESSIONS


def test_ci_run_time_settles_the_newest_session():
    """The watchdog runs at 01:45 UTC, by which point the newest trading session
    is already the previous UTC date — so the in-flight rule costs CI nothing."""
    next_day = "2026-08-21"
    assert settled_sessions(SESSIONS, _utc(next_day, 1), 23) == SESSIONS


def test_in_flight_session_is_not_due_not_missing():
    """The live-run false alarm this rule exists to kill: today's compile and
    baseline are legitimately absent while the session is still open."""
    state = _healthy()
    del state["flow"][SESSIONS[-1]]
    state["baseline"].discard(SESSIONS[-1])
    settled = SESSIONS[:-1]
    findings = evaluate(state, [COMPILE, BASE], SESSIONS, settled)
    in_flight = [f for f in findings if f.session == SESSIONS[-1]]
    assert all(f.verdict == NOT_DUE for f in in_flight)
    assert all("in flight" in f.detail for f in in_flight)
    assert summarise(findings, SESSIONS, SESSIONS[-1], 0, 3, CFG)[0] == EXIT_OK


def test_in_flight_does_not_mask_an_older_gap():
    """Suppressing today must not suppress yesterday."""
    state = _healthy()
    del state["flow"][SESSIONS[-1]]
    state["flow"][SESSIONS[1]]["stocks-flow"] = {"compiled": False, "snapshots": 0}
    findings = evaluate(state, [COMPILE], SESSIONS, SESSIONS[:-1])
    assert _verdicts(findings, "compile")[SESSIONS[1]] == MISSING
    assert summarise(findings, SESSIONS, SESSIONS[-1], 0, 3, CFG)[0] == EXIT_GAP


def test_in_flight_and_lag_compose():
    """enrich_oi's D+1 lag stacks with the in-flight cut rather than fighting it:
    with today in flight, OI is due only through the day before yesterday."""
    v = _verdicts(evaluate(_healthy(), [OI], SESSIONS, SESSIONS[:-1]), "enrich_oi")
    assert v[SESSIONS[-1]] == NOT_DUE and v[SESSIONS[-2]] == NOT_DUE
    assert v[SESSIONS[0]] == OK and v[SESSIONS[1]] == OK


# ── the shipped config ──────────────────────────────────────────────────────

def test_shipped_config_loads_and_covers_every_collection_stage():
    cfg = load_config(CONFIG_PATH)
    names = {s.name for s in cfg.stages}
    assert names == {"scrape", "compile", "enrich_oi", "iv_percentile",
                     "price_catalyst", "counterpart_iv", "baseline"}
    assert {s.name: s.lag_sessions for s in cfg.stages}["enrich_oi"] == 1
    assert all(0 < s.min_complete <= 1.0 for s in cfg.stages), "percent, not fraction"
    assert cfg.chain_complete_utc_hour >= 23, "Compile Flow fires at 22:30 UTC"


def test_malformed_config_is_rejected(tmp_path):
    p = tmp_path / "bad.yml"
    p.write_text("stages:\n  - kind: compiled_present\n")
    with pytest.raises(ValueError):
        load_config(p)
    p.write_text("stages: []\n")
    with pytest.raises(ValueError):
        load_config(p)
