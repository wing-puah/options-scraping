"""Unit tests for scripts/backtest_study/f1_selection/prompt_eval.py — the
candidate-prompt scoring harness.

Nothing here touches the network, Google Sheets, or a real model: every
subprocess is monkeypatched and every book is written to tmp_path. The four
things pinned hardest are the ones a mistake would be silent in:

  1. The DATE RULE. Selection is deterministic, stratified across model regime x
     calendar year, matured-windows-only, and never draws a variance-set date.
  2. The DERIVED CONFIG. All six local-only keys, both `sheet_tab`s PRESENT and
     null, every path inside the run directory.
  3. The REFUSALS. A `--tab` anywhere in an argv, a non-null (or absent)
     `sheet_tab`, and a path escaping the run directory each exit with a
     designed refusal code rather than raising.
  4. The VERDICT GRAMMAR, which is the study's whole output, tested as a pure
     function so it cannot drift from the registration by way of a plumbing
     change.

The synthetic-era arm books follow tests/test_text_corpus.py's fixture approach:
tiny results/proxy/analysis CSVs, an absent mech table, and the documented
`check_era=False, min_dates=0` escape hatch.
"""
import csv
import json
from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f1_selection import prompt_eval as PE
from scripts.backtest_study.lib import book
from scripts.backtest_study.lib.harness import Trade, replay


# ── date-rule selection ─────────────────────────────────────────────────────

def _records(spec):
    """`{iso_date: model_dir}` -> the record shape `select_dates` reads."""
    return [{"date": d, "model_dir": m, "ticker": "AAA"} for d, m in spec.items()]


def _spec():
    """A synthetic era: two regimes x two years, plus immature dates."""
    out = {}
    for i in range(20):
        out[f"2024-01-{i + 1:02d}"] = "BULL"
    for i in range(10):
        out[f"2024-06-{i + 1:02d}"] = "RANGE"
    for i in range(10):
        out[f"2025-01-{i + 1:02d}"] = "BULL"
    for i in range(4):
        out[f"2025-06-{i + 1:02d}"] = "BEAR"
    # Inside the 90-day maturity window relative to the as-of below — must never
    # be selected, whatever the strata allocation says.
    for i in range(5):
        out[f"2026-08-{i + 1:02d}"] = "BULL"
    return out


AS_OF = date(2026, 9, 2)


def test_select_dates_is_deterministic():
    recs = _records(_spec())
    a, _ = PE.select_dates(recs, 12, AS_OF, set())
    b, _ = PE.select_dates(recs, 12, AS_OF, set())
    assert a == b
    assert len(a) == 12


def test_select_dates_takes_matured_windows_only():
    dates, _ = PE.select_dates(_records(_spec()), 40, AS_OF, set())
    cutoff = (AS_OF - timedelta(days=PE.MATURITY_DAYS)).isoformat()
    assert dates, "the rule selected nothing"
    assert all(d <= cutoff for d in dates)
    assert not any(d.startswith("2026-08") for d in dates)


def test_select_dates_stratifies_proportionally_across_regime_and_year():
    _dates, table = PE.select_dates(_records(_spec()), 22, AS_OF, set())
    by = {r["stratum"]: r for r in table}
    assert set(by) == {"BULLx2024", "RANGEx2024", "BULLx2025", "BEARx2025"}
    # 20 / 10 / 10 / 4 eligible out of 44, n = 22 -> half of each.
    assert by["BULLx2024"]["allocated"] == 10
    assert by["RANGEx2024"]["allocated"] == 5
    assert by["BULLx2025"]["allocated"] == 5
    assert by["BEARx2025"]["allocated"] == 2
    assert sum(r["allocated"] for r in table) == 22
    for row in table:
        assert row["allocated"] <= row["eligible"]


def test_select_dates_excludes_the_variance_set():
    recs = _records(_spec())
    variance, _ = PE.select_dates(recs, 5, AS_OF, set())
    backfill, table = PE.select_dates(recs, 30, AS_OF, set(variance))
    assert not set(backfill) & set(variance)
    # The exclusion also shrinks the eligible population it was drawn from.
    assert sum(r["eligible"] for r in table) == 44 - len(variance)


def test_allocate_never_exceeds_a_stratum_and_breaks_ties_on_name():
    alloc = PE.allocate({"b": 1, "a": 1, "c": 10}, 5)
    assert alloc["a"] <= 1 and alloc["b"] <= 1
    assert sum(alloc.values()) == 5
    assert PE.allocate({"a": 2, "b": 2}, 99) == {"a": 2, "b": 2}


def test_dates_file_round_trips_ignoring_comments(tmp_path):
    path = tmp_path / "d.txt"
    PE.write_dates_file(path, ["2024-01-02", "2024-01-03"], {"rule": "variance"})
    assert "# " in path.read_text()
    assert PE.read_dates_file(path) == ["2024-01-02", "2024-01-03"]


def test_read_dates_file_refuses_a_missing_set(tmp_path):
    with pytest.raises(PE.Refusal) as exc:
        PE.read_dates_file(tmp_path / "nope.txt")
    assert exc.value.code == PE.EXIT_MISSING_INPUT


# ── derived config ──────────────────────────────────────────────────────────

def test_derive_config_sets_all_six_local_only_keys(tmp_path):
    run_dir = tmp_path / "run"
    adir = run_dir / "cand"
    adir.mkdir(parents=True)
    path = PE.derive_config(adir, run_dir)

    import yaml
    cfg = yaml.safe_load(path.read_text())
    assert cfg["analysis"]["csv"] == str(adir / "analysis.csv")
    assert "tab" not in cfg["analysis"]
    assert cfg["output"]["local_csv"] == str(adir / "results.csv")
    assert cfg["output"]["sheet_tab"] is None
    assert cfg["proxy"]["local_csv"] == str(adir / "proxy_results.csv")
    assert cfg["proxy"]["sheet_tab"] is None
    assert cfg["proxy"]["results_source_csv"] == str(adir / "results.csv")
    assert "results_source_tab" not in cfg["proxy"]
    # Everything else is config/backtest.yml verbatim — only the prompt differs
    # between arms, never the exit rules.
    assert cfg["simulation"]["profit_target"] == 0.90
    assert cfg["entry"]["structure_veto"] == ["bear_call_spread"]


def test_derive_config_paths_all_resolve_inside_the_run_dir(tmp_path):
    run_dir = tmp_path / "run"
    adir = run_dir / "prod"
    adir.mkdir(parents=True)
    import yaml
    cfg = yaml.safe_load(PE.derive_config(adir, run_dir).read_text())
    for value in (cfg["analysis"]["csv"], cfg["output"]["local_csv"],
                  cfg["proxy"]["local_csv"], cfg["proxy"]["results_source_csv"]):
        assert PE._inside(value, run_dir)


# ── the refusal paths ───────────────────────────────────────────────────────

def test_refuses_an_argv_carrying_tab(tmp_path):
    for argv in (["run", "--tab", "AnalysisClaude"], ["run", "--tab=AnalysisClaude"]):
        with pytest.raises(PE.Refusal) as exc:
            PE.forbid_tab(argv)
        assert exc.value.code == PE.EXIT_ISOLATION
    # And at the process boundary: main() returns the code, never raises.
    assert PE.main(["--", "dates", "--tab", "AnalysisClaude"]) == PE.EXIT_ISOLATION


def test_refuses_a_subprocess_command_line_carrying_tab(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(PE.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(PE.Refusal) as exc:
        PE.run_cmd(["python", "-m", "scripts.backtest", "--tab", "BacktestResults"],
                   tmp_path)
    assert exc.value.code == PE.EXIT_ISOLATION
    assert not called, "the refusal must happen BEFORE the subprocess starts"


@pytest.mark.parametrize("mutate,fragment", [
    (lambda c: c["output"].__setitem__("sheet_tab", "BacktestResults"), "not null"),
    (lambda c: c["proxy"].__setitem__("sheet_tab", "BacktestProxy"), "not null"),
    (lambda c: c["output"].pop("sheet_tab"), "ABSENT"),
    (lambda c: c["proxy"].pop("sheet_tab"), "ABSENT"),
])
def test_refuses_a_derived_config_that_could_write_sheets(tmp_path, mutate, fragment):
    run_dir = tmp_path / "run"
    cfg = {"analysis": {"csv": str(run_dir / "a.csv")},
           "output": {"local_csv": str(run_dir / "r.csv"), "sheet_tab": None},
           "proxy": {"local_csv": str(run_dir / "p.csv"), "sheet_tab": None,
                     "results_source_csv": str(run_dir / "r.csv")}}
    mutate(cfg)
    with pytest.raises(PE.Refusal) as exc:
        PE.check_derived_config(cfg, run_dir)
    assert exc.value.code == PE.EXIT_ISOLATION
    assert fragment in exc.value.message


def test_refuses_a_derived_config_still_naming_an_analysis_tab(tmp_path):
    run_dir = tmp_path / "run"
    cfg = {"analysis": {"csv": str(run_dir / "a.csv"), "tab": "AnalysisClaude"},
           "output": {"local_csv": str(run_dir / "r.csv"), "sheet_tab": None},
           "proxy": {"local_csv": str(run_dir / "p.csv"), "sheet_tab": None,
                     "results_source_csv": str(run_dir / "r.csv")}}
    with pytest.raises(PE.Refusal) as exc:
        PE.check_derived_config(cfg, run_dir)
    assert exc.value.code == PE.EXIT_ISOLATION


def test_refuses_a_path_outside_the_run_dir(tmp_path):
    run_dir = tmp_path / "run"
    with pytest.raises(PE.Refusal) as exc:
        PE.require_inside(tmp_path / "elsewhere" / "results.csv", run_dir, "output.local_csv")
    assert exc.value.code == PE.EXIT_ISOLATION

    cfg = {"analysis": {"csv": str(run_dir / "a.csv")},
           "output": {"local_csv": "/tmp/escaped.csv", "sheet_tab": None},
           "proxy": {"local_csv": str(run_dir / "p.csv"), "sheet_tab": None,
                     "results_source_csv": str(run_dir / "r.csv")}}
    with pytest.raises(PE.Refusal) as exc:
        PE.check_derived_config(cfg, run_dir)
    assert exc.value.code == PE.EXIT_ISOLATION


def test_run_analysis_refuses_an_output_dir_outside_the_run_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "run_cmd", lambda *a, **k: pytest.fail("must not spawn"))
    with pytest.raises(PE.Refusal) as exc:
        PE.run_analysis(["2024-03-04"], tmp_path / "outside", tmp_path / "run",
                        None, None, None)
    assert exc.value.code == PE.EXIT_ISOLATION


def test_run_backtest_refuses_a_used_arm_dir(tmp_path, monkeypatch):
    """The proxy writer archives its local CSV and reads its idempotency set from
    it, so a second pass into a used arm dir truncates the book."""
    monkeypatch.setattr(PE, "run_cmd", lambda *a, **k: pytest.fail("must not spawn"))
    adir = tmp_path / "run" / "cand"
    adir.mkdir(parents=True)
    (adir / "proxy_results.csv").write_text("signal_date\n")
    with pytest.raises(PE.Refusal) as exc:
        PE.run_backtest(adir / "backtest.yml", adir, tmp_path / "run")
    assert exc.value.code == PE.EXIT_STALE_RUN_DIR


# ── the CANDIDATE.md requirement ────────────────────────────────────────────

def test_candidate_dir_without_a_rationale_is_refused(tmp_path):
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "analysis-framework.md").write_text("framework\n")
    with pytest.raises(PE.Refusal) as exc:
        PE.candidate_prompts(cand)
    assert exc.value.code == PE.EXIT_MISSING_INPUT
    assert "CANDIDATE.md" in exc.value.message


def test_candidate_dir_with_no_prompt_file_is_refused(tmp_path):
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "CANDIDATE.md").write_text("rationale\n")
    with pytest.raises(PE.Refusal) as exc:
        PE.candidate_prompts(cand)
    assert exc.value.code == PE.EXIT_MISSING_INPUT


def test_candidate_dir_may_override_just_one_prompt_file(tmp_path):
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "CANDIDATE.md").write_text("rationale\n")
    (cand / "claude.md").write_text("method\n")
    out = PE.candidate_prompts(cand)
    assert out["framework"] is None
    assert out["method"] == cand / "claude.md"


def test_analysis_cmd_carries_the_candidate_prompt_files(tmp_path):
    cmd = PE.analysis_cmd("2024-03-04", tmp_path / "out", tmp_path / "f.md",
                          tmp_path / "m.md", "claude-haiku-4-5-20251001")
    assert "--output-dir" in cmd and "--framework-file" in cmd and "--method-file" in cmd
    assert "--model" in cmd
    assert "--tab" not in cmd
    PE.forbid_tab(cmd)      # must not refuse


# ── synthetic arm books: the paired comparison ──────────────────────────────

_BASE = {
    "market_regime": "BULL L-VOL", "regime": "BULL L-VOL", "horizon": "60",
    "delta": "0.30", "iv_entry_pct": "40", "entry_premium_total": "100",
    "max_loss_per_contract": "100", "mfe_pct": "0.2", "mae_pct": "-0.1",
    "mfe_day": "3", "mae_day": "1", "score_total": "10",
    "pnl_at_cap_pct": "0.10",
}


def _bt_row(signal: date, ticker: str, ret: float, structure="bull_call_spread"):
    """A row whose replayed outcome is EXACTLY `ret`.

    A flat path at `1 + ret` with |ret| inside (-0.75, +0.90) trips neither the
    profit target nor the stop, so DEBIT_PROD's time exit fires and the realized
    P&L is `ret` by construction — which is what lets the paired arithmetic be
    asserted against a number rather than against itself.
    """
    expiry = signal + timedelta(days=40)
    dte = (expiry - signal).days
    grid = _weekday_grid(signal, signal + timedelta(days=min(dte, 120)))
    row = dict(_BASE)
    row.update({
        "signal_date": signal.isoformat(), "ticker": ticker, "structure": structure,
        "legs": f"{ticker}:{expiry.isoformat()}:100:C +1", "contracts": "1",
        "dte_entry": str(dte), "entry_option_price": "1.00",
        "daily_price_csv": ",".join([f"{1 + ret:.4f}"] * len(grid)),
        "play": f"[DIRECTIONAL]\nTF | bull call spread 100/110 | {ticker} thesis",
        "created_datetime": f"{signal.isoformat()} 09:00:00",
    })
    t = Trade(dict(row))
    rp = replay(t, **book.DEBIT_PROD)
    row["exit_reason"] = rp["exit_reason"]
    row["days_held"] = str(rp["days_held"])
    row["realized_pnl_pct"] = str(round(rp["pnl_pct"], 4))
    return row


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted(set().union(*[r.keys() for r in rows])) if rows else ["signal_date"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        w.writeheader()
        w.writerows(rows)


def _analysis_row(signal: date, ticker: str, play: str):
    return {"date": signal.isoformat(), "ticker": ticker, "regime": "BULL L-VOL",
            "signal": "[FLOW] $4.68M calls at 30 DTE", "play": play, "horizon": "60",
            "trigger": "Close above 100", "invalidation": "Daily close below 95",
            "created_datetime": f"{signal.isoformat()} 09:00:00", "score_total": "10"}


def _build_arm(adir, per_date: dict, extra_analysis=(), leaks=0):
    """Write one arm's three CSVs. `per_date` is `{date: [(ticker, ret), ...]}`.

    `leaks` adds `bear_call_spread` ANALYSIS rows with NO backtest row and no
    `structure` cell anywhere — which is exactly the shape a real leak has, since
    the structure is vetoed at intake and the proxy writes its structure blank.
    """
    rows, analysis = [], []
    for signal, plays in per_date.items():
        for ticker, ret in plays:
            r = _bt_row(signal, ticker, ret)
            rows.append(r)
            analysis.append(_analysis_row(signal, ticker, r["play"]))
    for signal, ticker in extra_analysis:                # emitted, never priced
        analysis.append(_analysis_row(signal, ticker,
                                      f"[DIRECTIONAL]\nTF | long call 100 | {ticker}"))
    for i in range(leaks):
        analysis.append(_analysis_row(
            sorted(per_date)[0], f"LK{chr(65 + i)}",
            "[DIRECTIONAL]\nMR | bear call spread 300/320 | vetoed at intake"))
    _write_csv(adir / "results.csv", rows)
    _write_csv(adir / "proxy_results.csv", [dict(signal_date="")])
    _write_csv(adir / "analysis.csv", analysis)
    return adir


@pytest.fixture(autouse=True)
def _isolate_mech_table(tmp_path, monkeypatch):
    monkeypatch.setattr(book, "MECH_TABLE_CSV", tmp_path / "no_such_mech_table.csv")


def _dates(n, start=date(2024, 3, 4)):
    return [start + timedelta(days=7 * i) for i in range(n)]


@pytest.fixture
def two_arms(tmp_path):
    """Six shared dates; CAND beats PROD by exactly +0.20 mean R on every one."""
    run_dir = tmp_path / "run"
    prod_spec, cand_spec = {}, {}
    for i, d in enumerate(_dates(6)):
        prod_spec[d] = [("AAA", 0.10), ("BBB", 0.20)]
        cand_spec[d] = [("AAA", 0.30), ("BBB", 0.40)]
    _build_arm(run_dir / "prod", prod_spec)
    _build_arm(run_dir / "cand", cand_spec, extra_analysis=[(_dates(6)[0], "ZZZ")])
    out = {}
    for arm in ("prod", "cand"):
        adir = run_dir / arm
        rows, unpriced, diag = PE.load_arm(adir)
        out[arm] = dict(name=arm, dir=adir, rows=rows, unpriced=unpriced, diag=diag,
                        calls=0, seconds=0.0, model=None, paths=PE.arm_paths(adir))
    out["run_dir"] = run_dir
    return out


def test_arm_books_load_through_the_documented_escape_hatch(two_arms):
    for arm in ("prod", "cand"):
        rows = two_arms[arm]["rows"]
        assert len(rows) == 12
        assert two_arms[arm]["diag"]["n_dates"] == 6
        # Every row is real, calibrated, and tier-eligible under the shipped ladder.
        assert all(r["source"] == "real" for r in rows)
        assert {r["tier"] for r in rows} == {"B"}


def test_paired_delta_R_is_the_by_date_mean_difference(two_arms):
    picks_p = PE.picks_of(two_arms["prod"]["rows"])
    picks_c = PE.picks_of(two_arms["cand"]["rows"])
    pairs = PE.paired_by_date(picks_c, picks_p, "cand", "prod")
    assert len(pairs) == 6
    assert all(p["cand"] == pytest.approx(0.35) for p in pairs)
    assert all(p["prod"] == pytest.approx(0.15) for p in pairs)
    lo, hi = PE.P.boot_ci_paired_by_date(pairs, "cand", "prod", n=500, seed=1)
    assert lo == pytest.approx(0.20) and hi == pytest.approx(0.20)


def test_top_k_per_day_caps_the_replay_at_three(tmp_path):
    run_dir = tmp_path / "run"
    spec = {d: [(f"T{chr(65 + i)}{chr(65 + i)}", 0.10) for i in range(5)]
            for d in _dates(2)}
    _build_arm(run_dir / "prod", spec)
    rows, _u, _d = PE.load_arm(run_dir / "prod")
    assert len(rows) == 10
    assert len(PE.picks_of(rows)) == 2 * PE.TOP_K


def test_compare_reports_every_measure_and_reads_underpowered(two_arms, tmp_path):
    rep = PE.Report()
    summary = PE.compare(rep, two_arms["prod"], two_arms["cand"], None,
                         date_set="BACKFILL", skip_citations=True)
    text = "\n".join(rep.lines)

    assert summary["n_paired_dates"] == 6
    assert summary["delta_mean_R"] == pytest.approx(0.20)
    assert summary["criteria"][7] is False            # 6 < 25 dates
    assert summary["criteria"][2] is None             # no floor established
    assert summary["criteria"][4] is None             # citations skipped
    assert summary["criteria"][5] is True             # no leaks in either arm
    assert summary["verdict"] == "UNDERPOWERED"

    # Every registered measure is printed regardless of outcome.
    for fragment in ("PAIRED ΔR BY DATE", "PAIRED PROFIT FACTOR", "TIER-MIX CENSUS",
                     "EMISSIONS PER DATE", "UNPRICEABLE SHARE", "CITATION CHECK",
                     "BEAR_CALL_SPREAD LEAKS", "VARIANCE FLOOR",
                     "LEAVE-ONE-DATE-OUT", "CRITERIA VECTOR"):
        assert fragment in text, fragment
    assert "check_era=False, min_dates=0" in text     # the escape hatch, stated inline
    assert "NOT ESTABLISHED" in text
    # The candidate emitted one play the backtest never priced.
    assert summary["unpriceable"]["CAND"]["share"] > 0
    assert summary["unpriceable"]["PROD"]["share"] == 0
    assert summary["tier_mix"]["CAND"]["B"] == 12
    assert summary["emissions"] == {"PROD": 12, "CAND": 13}


def test_compare_counts_a_bear_call_spread_leak(tmp_path):
    run_dir = tmp_path / "run"
    spec = {d: [("AAA", 0.10)] for d in _dates(3)}
    _build_arm(run_dir / "prod", spec)
    _build_arm(run_dir / "cand", spec, leaks=2)
    arms = {}
    for arm in ("prod", "cand"):
        adir = run_dir / arm
        rows, unpriced, diag = PE.load_arm(adir)
        arms[arm] = dict(name=arm, dir=adir, rows=rows, unpriced=unpriced, diag=diag,
                         calls=0, seconds=0.0, model=None, paths=PE.arm_paths(adir))
    summary = PE.compare(PE.Report(), arms["prod"], arms["cand"], None,
                         date_set="BACKFILL", skip_citations=True)
    assert summary["leaks"] == {"PROD": 0, "CAND": 2}
    assert summary["criteria"][5] is False
    # The leak has no backtest row and no `structure` cell — the shape a real one
    # has. Counting off an export column would read it as zero.
    assert "bear_call_spread" not in (run_dir / "cand" / "proxy_results.csv").read_text()


def test_compare_prints_and_binds_the_variance_floor(two_arms, tmp_path):
    floor = {"floor": 0.5, "model": "m", "engine": "claude", "repeats": 3,
             "dates": ["2024-03-04"], "_path": str(tmp_path / "variance.json")}
    rep = PE.Report()
    summary = PE.compare(rep, two_arms["prod"], two_arms["cand"], floor,
                         date_set="BACKFILL", skip_citations=True)
    # |ΔR| = 0.20 does not clear a 0.50 floor.
    assert summary["criteria"][2] is False
    assert "no |ΔR| smaller than this may be called a difference" in "\n".join(rep.lines)


def test_read_variance_floor_finds_the_sibling_run(tmp_path):
    (tmp_path / "variance.json").write_text(json.dumps({"floor": 0.03}))
    run_dir = tmp_path / "run-2"
    run_dir.mkdir()
    got = PE.read_variance_floor(run_dir)
    assert got["floor"] == 0.03
    assert got["_path"].endswith("variance.json")


# ── verdict grammar ─────────────────────────────────────────────────────────

def _crit(over=None):
    """The criteria vector, all passing, with `over` applied. Keys are INTs (the
    registration numbers them 1-7), so this cannot take **kwargs."""
    c = {i: True for i in range(1, 8)}
    c.update(over or {})
    return c


@pytest.mark.parametrize("crit,point,floor,want", [
    (_crit(), 0.2, True, "MET"),
    (_crit({7: False}), 0.2, True, "UNDERPOWERED"),
    (_crit(), 0.2, False, "UNDERPOWERED"),
    (_crit({3: False}), 0.2, True, "NOT MET"),
    (_crit({6: False}), 0.2, True, "NOT MET"),
    (_crit(), -0.2, True, "MET"),
    (_crit({3: False}), -0.2, True, "CONTRARY"),
    (_crit({4: None}), 0.2, True, "NO PRE-REGISTERED VERDICT MATCHES"),
    (_crit({4: None, 5: False}), 0.2, True, "NOT MET"),
])
def test_verdict_grammar(crit, point, floor, want):
    assert PE.verdict_of(crit, point, floor)[0] == want


def test_every_verdict_is_one_of_the_five_registered_words():
    registered = {"MET", "NOT MET", "UNDERPOWERED", "CONTRARY",
                  "NO PRE-REGISTERED VERDICT MATCHES"}
    for point in (-0.5, 0.0, 0.5):
        for floor in (True, False):
            for bad in range(1, 8):
                assert PE.verdict_of(_crit({bad: False}), point, floor)[0] in registered
                assert PE.verdict_of(_crit({bad: None}), point, floor)[0] in registered


def test_met_requires_the_date_floor_and_an_established_variance_floor():
    assert PE.verdict_of(_crit(), 0.2, True)[0] == "MET"
    assert PE.verdict_of(_crit({7: False}), 0.2, True)[0] == "UNDERPOWERED"
    assert PE.verdict_of(_crit(), 0.2, False)[0] == "UNDERPOWERED"


# ── draft mode ──────────────────────────────────────────────────────────────

_DRAFT_RESPONSE = """\
<<<FILE: analysis-framework.md>>>
NEW FRAMEWORK BODY
<<<END>>>
<<<FILE: claude.md>>>
NEW METHOD BODY
<<<END>>>
<<<FILE: CANDIDATE.md>>>
# Candidate
Tightened the invalidation instruction because finding 2 said so.
<<<END>>>
"""


class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _patch_claude(monkeypatch, text):
    monkeypatch.setattr(PE, "claude_text", lambda prompt, model, **kw: text)


def test_draft_writes_the_three_files_and_a_locally_computed_diff(tmp_path, monkeypatch):
    _patch_claude(monkeypatch, _DRAFT_RESPONSE)
    findings = tmp_path / "findings.md"
    findings.write_text("PROMPT-ROBUSTNESS FINDINGS\n- finding 2: invalidation is vague\n")
    out = tmp_path / "cand"
    assert PE.cmd_draft(_Args(findings=str(findings), out=str(out),
                              model="claude-opus-5")) == 0

    assert (out / "analysis-framework.md").read_text() == "NEW FRAMEWORK BODY\n"
    assert (out / "claude.md").read_text() == "NEW METHOD BODY\n"
    assert "Tightened the invalidation" in (out / "CANDIDATE.md").read_text()
    diff = (out / "draft.diff").read_text()
    assert "+NEW FRAMEWORK BODY" in diff and "--- prod/analysis-framework.md" in diff
    # The draft is a RECORD: nothing under config/prompts/ moved.
    assert PE.PROD_FRAMEWORK.read_text() != "NEW FRAMEWORK BODY\n"
    # The output directory is a valid candidate arm.
    assert PE.candidate_prompts(out)["framework"] == out / "analysis-framework.md"


def test_draft_falls_back_to_the_prod_file_for_a_missing_block(tmp_path, monkeypatch):
    _patch_claude(monkeypatch, """\
<<<FILE: claude.md>>>
ONLY THE METHOD CHANGED
<<<END>>>
<<<FILE: CANDIDATE.md>>>
method-only edit
<<<END>>>
""")
    findings = tmp_path / "f.md"
    findings.write_text("findings\n")
    out = tmp_path / "cand"
    assert PE.cmd_draft(_Args(findings=str(findings), out=str(out), model="m")) == 0
    assert (out / "analysis-framework.md").read_text() == PE.PROD_FRAMEWORK.read_text()
    assert (out / "claude.md").read_text() == "ONLY THE METHOD CHANGED\n"


def test_draft_refuses_a_response_without_a_rationale(tmp_path, monkeypatch):
    _patch_claude(monkeypatch, "<<<FILE: claude.md>>>\nx\n<<<END>>>\n")
    findings = tmp_path / "f.md"
    findings.write_text("findings\n")
    with pytest.raises(PE.Refusal) as exc:
        PE.cmd_draft(_Args(findings=str(findings), out=str(tmp_path / "c"), model="m"))
    assert exc.value.code == PE.EXIT_MISSING_INPUT
    assert "CANDIDATE.md" in exc.value.message


def test_draft_never_writes_into_config_prompts(tmp_path, monkeypatch):
    _patch_claude(monkeypatch, _DRAFT_RESPONSE)
    findings = tmp_path / "f.md"
    findings.write_text("findings\n")
    with pytest.raises(PE.Refusal) as exc:
        PE.cmd_draft(_Args(findings=str(findings),
                           out=str(PE.ROOT / "config" / "prompts" / "x"), model="m"))
    assert exc.value.code == PE.EXIT_ISOLATION


def test_draft_prompt_carries_the_findings_and_both_prod_files(tmp_path, monkeypatch):
    seen = {}

    def fake(prompt, model, **kw):
        seen["prompt"] = prompt
        seen["model"] = model
        return _DRAFT_RESPONSE

    monkeypatch.setattr(PE, "claude_text", fake)
    findings = tmp_path / "f.md"
    findings.write_text("MARKER-FINDING-42\n")
    PE.cmd_draft(_Args(findings=str(findings), out=str(tmp_path / "c"), model="M"))
    assert "MARKER-FINDING-42" in seen["prompt"]
    assert PE.PROD_FRAMEWORK.read_text()[:200] in seen["prompt"]
    assert PE.PROD_METHOD.read_text()[:200] in seen["prompt"]
    assert seen["model"] == "M"


# ── runner contract ─────────────────────────────────────────────────────────

def test_designed_refusal_codes_are_a_plain_set_literal_the_runner_can_parse():
    import ast
    from scripts.backtest_study import run as runner
    src = ast.parse(PE.__file__ and open(PE.__file__).read())
    found = None
    for node in src.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DESIGNED_REFUSAL_EXIT_CODES"
                for t in node.targets):
            found = ast.literal_eval(node.value)
    assert found == PE.DESIGNED_REFUSAL_EXIT_CODES
    codes = runner._refusal_codes("prompt_eval")
    for c in (PE.EXIT_ISOLATION, PE.EXIT_MISSING_INPUT, PE.EXIT_STALE_RUN_DIR):
        assert c in codes


def test_main_strips_the_runner_s_double_dash_separator(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "cmd_dates", lambda args: 0)
    assert PE.main(["--", "dates", "--rule", "variance", "--n", "5",
                    "--out", str(tmp_path / "d.txt")]) == 0


def test_claude_text_parses_the_cli_event_array(monkeypatch):
    """`draft`'s one model call, with the subprocess itself monkeypatched."""
    seen = {}

    class _Proc:
        returncode = 0
        stdout = json.dumps([{"type": "system"},
                             {"type": "result", "result": "THE DIFF"}])
        stderr = ""

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["input"] = kw.get("input")
        return _Proc()

    monkeypatch.setattr(PE.subprocess, "run", fake_run)
    assert PE.claude_text("PROMPT", "claude-haiku-4-5-20251001") == "THE DIFF"
    assert seen["cmd"][:2] == ["claude", "-p"]
    assert "claude-haiku-4-5-20251001" in seen["cmd"]
    assert seen["input"] == "PROMPT"


def test_claude_text_raises_on_a_reported_error(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = json.dumps({"is_error": True, "result": "nope"})
        stderr = ""

    monkeypatch.setattr(PE.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(RuntimeError):
        PE.claude_text("p", "m")


def test_run_cmd_logs_every_command_line(tmp_path, monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "out"
        stderr = ""

    monkeypatch.setattr(PE.subprocess, "run", lambda *a, **k: _Proc())
    run_dir = tmp_path / "run"
    PE.run_cmd(["python", "-m", "scripts.backtest", "--config", "x.yml"], run_dir,
               log_path=run_dir / "logs" / "backtest.log")
    log = (run_dir / "commands.log").read_text()
    assert "scripts.backtest" in log and "--config" in log
    assert (run_dir / "logs" / "backtest.log").read_text() == "out"
