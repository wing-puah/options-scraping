"""Tests for scripts/study_charts (no Drive, no Sheets, no study run).

Everything here is built from synthetic fixtures under tmp_path — the real
study output lives in gitignored `backtests/` scratch, which is not present in
a fresh checkout or a worktree.

The behaviour worth protecting is the reconciliation contract: the page is
allowed to recompute the study's headline numbers from its positions CSV only
because a mismatch is a hard error. Tests below pin the estimators that make
those numbers agree (the zero-baseline drawdown especially) and pin the failure
when a CSV is paired with a report from a different arm.
"""
import copy
import re
from pathlib import Path

import pytest

from scripts.study_charts import regime, render, render_regime, report, series
from scripts.study_charts.account_sim import docs_dest, is_structure_arm, main, pick_report

BANNER = "=" * 78


def _section(title: str, body: str) -> str:
    return f"{BANNER}\n{title}\n{BANNER}\n{body}\n"


def _cell_line(cell: str, structure: str, n: int, dollars: int, meanR: float,
               win: float, thin: bool = False) -> str:
    """One `DEPLOYED BOOK BY REGIME` cell row, laid out like the study's own."""
    return (f"  {cell:<12}{structure:<20}{n:>5}{dollars:>12,.0f}"
            f"{meanR:>+9.3f}{win:>8.3f}  {'thin' if thin else ''}".rstrip())


def _regime_section(tag: str, mech: list, model: list, census: list,
                    skips: list, considered: int, agreement: list) -> str:
    """The regime section, hand-written so the fixture asserts the layout rather
    than re-deriving it from the same code the parser is being tested against."""
    return _section(
        f"[{tag}] DEPLOYED BOOK BY REGIME (post-hoc, NOT pre-registered)",
        "  This study pre-registers NO cut by regime.\n"
        "\n--- MECHANICAL cell x structure, taken only ---------------------------------\n"
        f"  {'cell':<12}{'structure':<20}{'n':>5}{'dollars':>12}{'meanR':>9}{'win':>8}  flag\n"
        + "\n".join(_cell_line(*row) for row in mech)
        + "\n\n--- MODEL regime cell x structure, taken only -------------------------------\n"
        f"  {'cell':<12}{'structure':<20}{'n':>5}{'dollars':>12}{'meanR':>9}{'win':>8}  flag\n"
        + "\n".join(_cell_line(*row) for row in model)
        + "\n\n--- deployment census by mechanical cell, taken only ------------------------\n"
        f"  {'cell':<12}{'n':>5}{'tierA':>7}{'tierB':>7}{'avg reserved':>14}"
        f"{'avg delta-notional':>20}\n"
        + "\n".join(f"  {c:<12}{n:>5}{a:>7}{b:>7}{res:>14,.0f}{dn:>20,.0f}"
                    for c, n, a, b, res, dn in census)
        + "\n\n--- what the caps SKIPPED, by mechanical cell (every candidate) -------------\n"
        f"  {'cell':<12}{'bucket':<18}{'n':>5}\n"
        + "\n".join(f"  {c:<12}{b:<18}{n:>5}" for c, b, n in skips)
        + f"\n  {'TOTAL':<12}{'considered':<18}{considered:>5}"
        + "\n\n--- model read vs mechanical read, DIRECTION only, taken only ---------------\n"
        f"  {'model':<10}{'mech':<10}{'n':>5}\n"
        + "\n".join(f"  {m:<10}{k:<10}{n:>5}" for m, k, n in agreement)
        + f"\n  agreement {sum(n for m, k, n in agreement if m == k)} of "
          f"{sum(n for _, _, n in agreement)} "
          f"({sum(n for m, k, n in agreement if m == k) / sum(n for _, _, n in agreement):.3f})")


# The regime tables make_positions()'s rows actually produce. Hand-computed on
# purpose: if series._regime and the parser both drifted the same way, a fixture
# generated from either of them would keep agreeing with itself.
PRIMARY_REGIME = dict(
    mech=[("LVOL", "bull_call_spread", 2, 900, 0.350, 1.0, True),
          ("LVOL", "ALL", 2, 900, 0.350, 1.0),
          ("TOTAL", "ALL", 2, 900, 0.350, 1.0)],
    model=[("BULL/L-VOL", "bull_call_spread", 2, 900, 0.350, 1.0, True),
           ("BULL/L-VOL", "ALL", 2, 900, 0.350, 1.0),
           ("TOTAL", "ALL", 2, 900, 0.350, 1.0)],
    census=[("LVOL", 2, 2, 0, 500, 1000), ("TOTAL", 2, 2, 0, 500, 1000)],
    skips=[("LVOL", "net_delta", 2), ("LVOL", "per_pos_delta", 1), ("LVOL", "taken", 2)],
    considered=5,
    agreement=[("BULL", "BULL", 2)],
)
SECONDARY_REGIME = dict(
    mech=[("BEAR_HE", "bull_put_spread", 1, -500, -0.200, 0.0, True),
          ("BEAR_HE", "ALL", 1, -500, -0.200, 0.0),
          ("LVOL", "bull_call_spread", 2, 1700, 0.400, 1.0, True),
          ("LVOL", "ALL", 2, 1700, 0.400, 1.0),
          ("TOTAL", "ALL", 3, 1200, 0.200, 0.667)],
    model=[("BULL/L-VOL", "bull_call_spread", 2, 1700, 0.400, 1.0, True),
           ("BULL/L-VOL", "ALL", 2, 1700, 0.400, 1.0),
           ("RANGE/E-VOL", "bull_put_spread", 1, -500, -0.200, 0.0, True),
           ("RANGE/E-VOL", "ALL", 1, -500, -0.200, 0.0),
           ("TOTAL", "ALL", 3, 1200, 0.200, 0.667)],
    census=[("BEAR_HE", 1, 0, 1, 500, 1000), ("LVOL", 2, 2, 0, 500, 1000),
            ("TOTAL", 3, 2, 1, 500, 1000)],
    skips=[("BEAR_HE", "taken", 1), ("LVOL", "net_delta", 2),
           ("LVOL", "per_pos_delta", 1), ("LVOL", "taken", 2)],
    considered=6,
    agreement=[("BULL", "BULL", 2), ("RANGE", "BEAR", 1)],
)


def _population_sections(tag: str, n: int, dates: int, dollars: int, meanR: float,
                         maxdd: int, worst: int, win: int, a5: str = "MET", a6: str = "MET",
                         regime_tables: dict | None = None) -> str:
    """The eleven population-scoped sections `report.parse` requires."""
    return (
        _regime_section(tag, **(regime_tables or PRIMARY_REGIME))
        + _section(f"[{tag}] B1 / B2 BASELINES",
                   f"  B1  stored contracts, stored outcomes     n= {n + 4}  dates= {dates}"
                   f"  $    {dollars * 4:,}  meanR +0.511\n"
                   f"  B2  $25,000 max-loss sizing, unconstrained  n= {n + 2}  dates= {dates}"
                   f"  $    {dollars * 2:,}  meanR +0.298\n"
                   "  B2/B1 dollar ratio 0.51x — the small account holds fewer contracts")
        + _section(f"[{tag}] GRANULARITY — what 2% of $25k buys vs 2% of $50k",
                   f"  deployed picks {n + 4}   with usable max_loss {n + 2}   unsizable 2\n\n"
                   "  $50,000 account / $1,000 budget\n"
                   "    contracts distribution: 1c:73  2c:11  3c:3  ...\n"
                   "    mean 2.20 contracts   median 1.0\n"
                   f"    1-contract FLOOR share   31/{n + 2} (28%)  (int(budget/max_loss) == 0)\n"
                   f"    budget-BREACH share      31/{n + 2} (28%)  (max_loss > budget at 1 contract)\n"
                   "    realized per-position risk %: median 1.8%  p90 3.0%  max 6.1%\n\n"
                   "  $25,000 account / $500 budget\n"
                   "    contracts distribution: 1c:87  2c:11  3c:10\n"
                   "    mean 1.35 contracts   median 1.0\n"
                   f"    1-contract FLOOR share   73/{n + 2} (66%)  (int(budget/max_loss) == 0)\n"
                   f"    budget-BREACH share      73/{n + 2} (66%)  (max_loss > budget at 1 contract)\n"
                   "    realized per-position risk %: median 3.0%  p90 6.0%  max 12.2%")
        + _section(f"[{tag}] UTILISATION — reserved capital and delta-notional",
                   "  month      sess  res% avg  res% max  gross avg  gross max"
                   "   net avg   net max  open avg  open max\n"
                   "  2025-03      10      0.25      0.41       0.98       1.49"
                   "      0.98      1.49      10.9        16\n"
                   "  2025-04      22      0.28      0.41       1.09       1.50"
                   "      1.09      1.50      11.7        16")
        + _section(f"[{tag}] BINDING-CONSTRAINT CENSUS (A4 self-check)",
                   f"  taken                 {n}\n  taken_downsized        0\n  cash                   0\n"
                   "  per_pos_delta          1\n  net_delta              2\n  min1_refusal           0\n"
                   "  day3_cap               0\n  unsizable              0\n"
                   f"  TOTAL considered     {n + 3}\n"
                   "  MOST BINDING constraint: net_delta (2 of 3 exclusions)")
        + _section(f"[{tag}] ADVERSE-ORDERING CHECK — rejected vs taken counterfactual R",
                   f"  taken                n=  {n}  meanR {meanR:+.3f}\n"
                   "  rejected [net_delta     ] n=   2  meanR +0.500  delta vs taken +0.200\n"
                   "  rejected [per_pos_delta ] n=   1  meanR +0.100  delta vs taken -0.200")
        + _section(f"[{tag}] EQUITY CURVE — constrained vs B2, and drawdown",
                   f"  constrained        sessions=  {n}  total $     {dollars:,}"
                   f"  maxDD $    {maxdd:,}  worst session $   {worst:,}\n"
                   f"  B2 unconstrained   sessions=  {n + 20}  total $    {dollars * 2:,}"
                   f"  maxDD $    -3,816  worst session $   -1,329\n"
                   "  constrained maxDD 14.7% of $25,000 starting capital (A3 limit 25%)")
        + _section(f"[{tag}] ARMS — R vs D, F1 vs F2, and ARM H",
                   "  arm                             n  dates     total $    meanR    win    maxDD $\n"
                   f"  (R, F1)  HEADLINE              {n}     {dates}       {dollars:,}"
                   f"    {meanR:.3f}    {win}%     {maxdd:,}\n"
                   "  (R, F2)                        43     31       3,655    0.280    63%     -2,860\n"
                   "  (D, F1)                        52     28       7,550    0.262    62%     -3,313\n"
                   "  (D, F2)                        46     32       3,361    0.211    59%     -2,778")
        + _section(f"[{tag}] ARM H — the shipped bear sleeve on the constrained run",
                   "  without sleeve\n"
                   f"    signal positions   {n}  $     {dollars:,}   sleeve positions    0  $         0\n"
                   f"    total $     {dollars:,}   gross avg 0.68x max 1.50x   net avg 0.68x max 1.50x\n"
                   "  with sleeve\n"
                   "    signal positions   76  $    11,447   sleeve positions   33  $      -832\n"
                   "    total $    10,615   gross avg 1.15x max 4.14x   net avg 0.57x max 2.11x")
        + _section(f"[{tag}] CAP GRID — monotonicity read ONLY",
                   "--- HEADLINE CELL — per-pos 0.25 x net 1.50 (the configured cell, quoted first and alone)\n"
                   f"  n={n}  dates={dates}  ${dollars:,}  meanR {meanR:+.3f}\n\n"
                   "--- full grid (context; read monotonicity, nothing else) --------------------\n"
                   "  per-pos / net           1.00          1.50          2.50           inf\n"
                   "  0.15               3,776/45      6,204/56     10,855/67     13,101/72 \n"
                   f"  0.25               7,019/38      {dollars:,}/{n}     11,399/72     16,570/88 \n"
                   "  0.40               7,100/40      8,461/48     11,586/71     15,928/90 \n"
                   "  inf                7,164/37     10,512/53     10,752/66     17,622/95 \n\n"
                   "--- monotonicity read -------------------------------------------------------\n"
                   "  rows monotone in the net cap:      4/4\n"
                   "  columns monotone in the per-pos cap: 2/4")
        + _section(f"[{tag}] CRITERIA A1-A6",
                   f"  A1 EDGE SURVIVAL  meanR {meanR:+.3f}  CI95 [+0.055,+0.483]  years 2025:+0.381  2026:+0.152\n"
                   "     MET  (needs mean>0, CI excluding zero, every year positive)\n"
                   f"  A2 ATTRITION      constrained ${dollars:,} vs B2 on the same {dates} dates $7,964  = 99%\n"
                   "     MET  (needs >= 60%)\n"
                   f"  A3 NO BLOWUP      maxDD ${maxdd:,} = 14.7% of capital;  ledger violations 0\n"
                   "     MET  (needs no over-reservation and DD <= 25%)\n"
                   f"  A4 ATTRIBUTION    {n + 3} candidates partition exactly into {n} taken + exclusions\n"
                   "     MET  (mismatch FAILS the run)\n"
                   "  A5 STABILITY      constrained/B2 ratio ALL 99% (n=51)\n"
                   f"     {a5}  (needs <= 15 points of movement on both cuts)\n"
                   "  A6 CREDIT SENS.   debit-only n=39  meanR +0.181  CI95 [-0.093,+0.440]  years 2025:+0.300\n"
                   f"     {a6}  (A1 must hold on debit-only)")
    )


# The config file as the study echoes it: a comment, nested keys, a blank line,
# an inline comment, and — the shape that matters — a value followed by a run of
# four or more spaces, which is the EXIT group's row separator. A file line must
# never be read as a label/value row.
CONFIG_FILE = (
    "# account_sim — the account this run simulated\n"
    "account:\n"
    "  capital: 25000        # starting equity, and both caps' denominator\n"
    "  risk_per_trade_pct: 0.02\n"
    "\n"
    "caps:\n"
    "  per_position: 0.25\n"
    "  net: 2.50\n"
)

CONFIGURATION_BODY = (
    "  The file below IS the simulation. The EXITS group after it is not in it.\n"
    "\n"
    "--- the config file this run loaded, verbatim -------------------------------\n"
    + "\n".join(f"  {line}".rstrip() for line in CONFIG_FILE.rstrip("\n").split("\n"))
    + "\n\n"
    "--- exits — FROZEN, not in that file (book.py + the shipped merge) ----------\n"
    "  debit, non-bear                             take profit +90% · stop -75% · time exit at 75% of DTE\n"
    "  credit                                      take profit +65%\n"
    "  every position, on top of the above         hard dollar stop at $500 "
    "(account.risk_per_trade_pct x account.capital); expiry"
)


def make_report(path: Path, command: str = "python -m scripts.backtest_study.account_sim",
                primary=(2, 2, 900, 0.35, -300, -300, 50),
                secondary=(3, 3, 1200, 0.20, -500, -500, 67)) -> Path:
    """A structurally faithful account_sim report over synthetic numbers."""
    text = (
        _section("STUDY: account_sim",
                 "  run at    2026-08-13 16:05:44\n"
                 f"  command   {command}\n"
                 "  git       309c564 (main, working tree dirty)\n"
                 "  python    3.11.2\n"
                 "  inputs:\n"
                 "   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv")
        + _section("account_sim — $25,000 FEASIBILITY simulation of the shipped ladder",
                   "  config    config/account-sim.yml\n"
                   "  Selection FROZEN (top-3/day, tiers A+B, ladder_rank). Exits FROZEN\n"
                   "  (shipped debit merge / CREDIT_PROD). Capital $25,000, risk\n"
                   "  2% = $500 per position on a MAX-LOSS basis,\n"
                   "  3 positions/day, per-position delta-notional cap 0.25x equity,\n"
                   "  net cap 2.50x equity.\n"
                   "  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. No annualised figure,\n"
                   "  Sharpe, or time-to-recover appears anywhere in this report by construction.")
        + _section("CONFIGURATION — the account this run simulated (config/account-sim.yml)",
                   CONFIGURATION_BODY)
        + _section("GATES — G1..G5 (non-zero exit on any failure)",
                   "  G1: PASS\n  G2: PASS\n  G3: PASS  (0 violations)\n  G4: PASS\n  G5: PASS\n\n  GATES: ALL PASS")
        + _section("POPULATION — dense episodes FIRST (primary), full book secondary",
                   "  deployed signal dates: 90  (2024-06-17 .. 2026-04-07)\n\n"
                   "--- dense episodes ----------------------------------------------------------\n"
                   "  E1  2025-03-11 .. 2025-03-31    12 dates over  14 sessions    31 deployed picks\n"
                   "  total: 1 episodes, 12 dates, 31 deployed picks\n"
                   "  excluded from PRIMARY: 44 isolated dates")
        + _population_sections("PRIMARY dense episodes", *primary, regime_tables=PRIMARY_REGIME)
        + _population_sections("SECONDARY full book", *secondary, a5="NOT MET", a6="NOT MET",
                               regime_tables=SECONDARY_REGIME)
        + _section("VERDICT (PRIMARY dense episodes population — the pre-registered primary)",
                   "  A1  MET\n  A2  MET\n  A3  MET\n  A4  MET\n  A5  NOT MET\n  A6  NOT MET\n\n"
                   "  >>> NO VERDICT MATCHES — A1 holds but A5, A6 fail(s) <<<")
        + _section("CLOSE", "  verdict: NO VERDICT MATCHES")
    )
    path.write_text(text)
    return path


CSV_HEADER = (
    "population,arm,status,date,ticker,structure,credit,tier,contracts,reserved,dn,"
    "entry_sess,exit_sess,days_held,exit_reason,R,dollars,downsized,hedge,reject_reason,"
    "max_loss_per_contract,delta,dte,score_total,mfe,mae,market_regime,model_dir,model_vol,"
    "regime,mech_direction,mech_vol,mech_cell,shipped_R,shipped_exit_reason\n"
)


def _row(population, status, date, exit_sess, R, dollars, reject_reason="", contracts=1,
         exit_reason="profit_target", tier="A", structure="bull_call_spread", credit="False",
         days_held="14.0", mech_cell="LVOL", mech_direction="BULL",
         model_dir="BULL", model_vol="L-VOL"):
    return (
        f"{population},RF1,{status},{date},NVDA,{structure},{credit},{tier},{contracts},500.0,1000.0,"
        f"{date},{exit_sess},{days_held},{exit_reason},{R},{dollars},False,False,{reject_reason},"
        f"500.0,0.3,45.0,30.0,0.5,-0.2,{model_dir} + {model_vol},{model_dir},{model_vol},"
        f"{model_dir},{mech_direction},L-VOL,{mech_cell},,\n"
    )


def make_positions(path: Path) -> Path:
    """Two populations whose taken rows reproduce make_report's numbers.

    primary   2 taken over 2 dates, +$900, meanR +0.35, first session -$300
    secondary 3 taken over 3 dates, +$1,200, meanR +0.20, first session -$500
    """
    rows = [
        # primary: -300 then +1200 -> cum -300, +900; zero-baseline maxDD -300
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.10, -300),
        _row("primary", "taken", "2025-03-12", "2025-03-21", 0.60, 1200),
        _row("primary", "skipped:net_delta", "2025-03-13", "", 0.50, 0, "net_delta"),
        _row("primary", "skipped:net_delta", "2025-03-14", "", 0.50, 0, "net_delta"),
        _row("primary", "skipped:per_pos_delta", "2025-03-15", "", 0.10, 0, "per_pos_delta"),
        # secondary: -500, +900, +800 -> cum -500, +400, +1200; maxDD -500.
        # The first row sits in a different regime cell and structure from the
        # other two, so the regime cross-tab is exercised rather than being one
        # cell that every check trivially passes.
        _row("secondary", "taken", "2024-06-17", "2024-06-20", -0.20, -500,
             tier="B", structure="bull_put_spread", mech_cell="BEAR_HE",
             mech_direction="BEAR", model_dir="RANGE", model_vol="E-VOL"),
        _row("secondary", "taken", "2024-06-18", "2024-06-21", 0.30, 900),
        _row("secondary", "taken", "2024-06-19", "2024-06-24", 0.50, 800),
        _row("secondary", "skipped:net_delta", "2024-07-01", "", 0.50, 0, "net_delta"),
        _row("secondary", "skipped:net_delta", "2024-07-02", "", 0.50, 0, "net_delta"),
        _row("secondary", "skipped:per_pos_delta", "2024-07-03", "", 0.10, 0, "per_pos_delta"),
    ]
    path.write_text(CSV_HEADER + "".join(rows))
    return path


@pytest.fixture
def parsed(tmp_path):
    return report.parse(make_report(tmp_path / "account_sim-20260813-160544.txt"))


@pytest.fixture
def rows(tmp_path):
    return series.load(make_positions(tmp_path / "account_sim-positions-latest.csv"))


# ──────────────────────────────── report parsing ────────────────────────────

def test_parse_reads_provenance_and_flags_the_plain_arm(parsed):
    prov = parsed["provenance"]
    assert prov["git"].startswith("309c564")
    assert prov["structure_arm"] is False
    assert prov["inputs"][0]["rows"] == 1926


def test_parse_reads_all_five_gates(parsed):
    gates = parsed["gates"]
    assert [g["id"] for g in gates["gates"]] == ["G1", "G2", "G3", "G4", "G5"]
    assert all(g["status"] == "PASS" for g in gates["gates"])
    assert gates["headline"] == "ALL PASS"


def test_parse_keeps_the_two_populations_apart(parsed):
    primary = parsed["populations"]["primary"]
    secondary = parsed["populations"]["secondary"]
    assert primary["equity"]["constrained"]["total"] == 900
    assert secondary["equity"]["constrained"]["total"] == 1200


def test_parse_reads_the_cap_grid_and_marks_the_headline_cell(parsed):
    grid = parsed["populations"]["primary"]["cap_grid"]
    assert grid["net_caps"] == ["1.00", "1.50", "2.50", "inf"]
    assert [r["per_pos"] for r in grid["rows"]] == ["0.15", "0.25", "0.40", "inf"]
    assert grid["rows"][0]["cells"][0] == {"dollars": 3776.0, "n": 45}
    assert grid["headline"]["per_pos"] == "0.25" and grid["headline"]["net"] == "1.50"
    assert grid["monotone_rows"] == [4, 4] and grid["monotone_cols"] == [2, 4]


def test_parse_reads_four_arms_and_flags_the_headline(parsed):
    arms = parsed["populations"]["primary"]["arms"]
    assert [a["arm"] for a in arms] == ["(R, F1)", "(R, F2)", "(D, F1)", "(D, F2)"]
    assert [a["headline"] for a in arms] == [True, False, False, False]
    assert arms[0]["win"] == 0.50


def test_parse_reads_criteria_with_status_and_ci(parsed):
    crit = parsed["populations"]["primary"]["criteria"]
    assert [c["id"] for c in crit] == ["A1", "A2", "A3", "A4", "A5", "A6"]
    assert crit[0]["ci"] == [0.055, 0.483]
    assert crit[0]["years"] == {"2025": 0.381, "2026": 0.152}
    assert crit[4]["status"] == "MET"  # primary fixture: A5/A6 MET


def test_parse_reads_both_account_sizes_and_flags_truncated_distribution(parsed):
    accounts = parsed["populations"]["primary"]["granularity"]["accounts"]
    assert [a["capital"] for a in accounts] == [50000.0, 25000.0]
    assert accounts[0]["dist_truncated"] is True   # the report elides the tail with "..."
    assert accounts[1]["dist_truncated"] is False
    assert accounts[1]["risk_max"] == 12.2


def test_parse_raises_on_a_missing_section(tmp_path):
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace("[PRIMARY dense episodes] CAP GRID", "[PRIMARY] SOMETHING ELSE"))
    with pytest.raises(report.ReportParseError, match="CAP GRID"):
        report.parse(path)


def test_parse_raises_on_a_file_that_is_not_a_report(tmp_path):
    path = tmp_path / "junk.txt"
    path.write_text("just some prose\nwith no banners\n")
    with pytest.raises(report.ReportParseError, match="no banner sections"):
        report.parse(path)


def test_parse_census_reads_a_bucket_the_whitelist_never_had(tmp_path):
    """The census is the one table that may not drop a row, on either side of
    the reconcile — so the parser matches by shape, not by a fixed bucket list."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "  unsizable              0\n", "  unsizable              0\n  hedge_rejected         4\n"))
    buckets = report.parse(path)["populations"]["primary"]["census"]["buckets"]
    assert buckets["hedge_rejected"] == 4


def test_parse_raises_when_a_section_is_present_but_empty(tmp_path):
    """An emptied section must fail like a missing one — half-parsed is worse."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace("  A1  MET\n  A2  MET\n  A3  MET\n"
                                             "  A4  MET\n  A5  NOT MET\n  A6  NOT MET\n", ""))
    with pytest.raises(report.ReportParseError, match="checklist"):
        report.parse(path)


def test_structure_arm_block_is_absent_on_the_plain_run(parsed):
    assert parsed["structure_arm"] is None


# ──────────────────────── the CONFIGURATION echo ────────────────────────────

def test_parse_configuration_recovers_the_config_file_byte_for_byte(parsed):
    """The panel's whole claim is that it shows the file the run loaded, so the
    parser may only take the report's indent back off — nothing else."""
    cfg = parsed["configuration"]
    assert cfg["source"] == "config/account-sim.yml"
    assert cfg["file"] == CONFIG_FILE.strip("\n")
    # In particular, a file line whose value is followed by four or more spaces
    # is file content, not a label/value row that would be split in two.
    assert "  capital: 25000        # starting equity" in cfg["file"]


def test_parse_configuration_keeps_the_stop_levels_as_the_study_wrote_them(parsed):
    """The exit rows are the reason this section carries anything besides the
    file: the page must show the stop the replay applied, and no config states
    it."""
    exits = parsed["configuration"]["exits"]
    assert exits[0]["value"] == "take profit +90% · stop -75% · time exit at 75% of DTE"
    assert exits[1] == {"label": "credit", "value": "take profit +65%"}
    assert parsed["configuration"]["exits_title"].startswith("exits")


def test_parse_configuration_raises_rather_than_dropping_an_unsplittable_row(tmp_path):
    """A label long enough to eat the 4-space separator must fail the build.

    Dropping it instead would remove a stop level from the page while every
    other assertion still passed.
    """
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "  credit                                      take profit +65%",
        "  credit  take profit +65%"))
    with pytest.raises(report.ReportParseError, match="separator"):
        report.parse(path)


def test_parse_configuration_raises_on_a_group_header_it_cannot_read(tmp_path):
    """`sub()` pads to a fixed width, so a long title leaves too few dashes.

    Ignoring the line would fold the frozen exit rows into the config file the
    page shows — the page would then assert that editing the file moves them.
    """
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "--- exits — FROZEN, not in that file (book.py + the shipped merge) ----------",
        "--- exits — FROZEN, not in that file (book.py + the shipped merge) -"))
    with pytest.raises(report.ReportParseError, match="group header not recognised"):
        report.parse(path)


def test_parse_configuration_raises_when_a_group_goes_missing(tmp_path):
    """Losing the exits header folds its rows into the file group."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "--- exits — FROZEN, not in that file (book.py + the shipped merge) ----------\n", ""))
    with pytest.raises(report.ReportParseError, match="expected 2 CONFIGURATION groups"):
        report.parse(path)


def test_parse_configuration_raises_when_the_groups_are_not_the_two_it_knows(tmp_path):
    """The parser reads the two groups differently — one as a file, one as
    rows. A renamed group must fail rather than be read as the other kind."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "--- the config file this run loaded, verbatim ---",
        "--- the config file this run loaded, as text ---"))
    with pytest.raises(report.ReportParseError, match="is not the config-file echo"):
        report.parse(path)


def test_parse_configuration_raises_on_a_file_line_that_lost_its_indent(tmp_path):
    """Every echoed line carries the report's body indent. Dedenting one that
    does not would put text into the page's config panel that is not in the
    config file."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace(
        "  account:\n", "account:\n"))
    with pytest.raises(report.ReportParseError, match="not indented as file content"):
        report.parse(path)


def test_parse_configuration_reads_what_the_study_actually_prints(tmp_path, capsys):
    """The one test coupling this parser to the real emitter.

    Every other test here runs off a synthetic fixture, which can drift from
    the study without anything noticing. This one prints the section with
    account_sim's own code and parses that, so a layout change on either side
    fails loudly instead of producing a page with an empty setup panel.
    """
    from scripts.backtest_study import account_sim as study

    settings = study.load_settings()
    study.print_configuration(settings, "config/account-sim.yml")
    real = capsys.readouterr().out.lstrip("\n") + "\n"
    fixture = _section("CONFIGURATION — the account this run simulated (config/account-sim.yml)",
                       CONFIGURATION_BODY)
    path = make_report(tmp_path / "r.txt")
    assert fixture in path.read_text(), "the fixture section moved; this test substitutes it"
    path.write_text(path.read_text().replace(fixture, real))

    cfg = report.parse(path)["configuration"]
    assert cfg["source"] == "config/account-sim.yml"
    # The round trip that matters: what the page will show is the file on disk.
    assert cfg["file"] == settings.source_text.rstrip("\n")
    assert cfg["file"] == study.DEFAULT_CONFIG.read_text().rstrip("\n")
    assert cfg["exits_title"].startswith("exits")
    assert all(r["label"] and r["value"] for r in cfg["exits"])


def test_parse_configuration_raises_when_the_section_is_missing(tmp_path):
    """An older report renders no page rather than a page with an empty setup."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace("CONFIGURATION — the account", "SOMETHING ELSE — the account"))
    with pytest.raises(report.ReportParseError, match="CONFIGURATION"):
        report.parse(path)


def test_parse_configuration_raises_when_the_exits_group_is_emptied(tmp_path):
    path = make_report(tmp_path / "r.txt")
    body = path.read_text()
    for line in body.splitlines():
        if line.startswith("  debit,") or line.startswith("  credit ") \
                or line.startswith("  every position"):
            body = body.replace(line + "\n", "")
    path.write_text(body)
    with pytest.raises(report.ReportParseError, match="has no rows"):
        report.parse(path)


# ─────────────────────────────── derived series ─────────────────────────────

def test_equity_curve_books_pnl_on_the_exit_session(rows):
    curve = series.build(rows, "primary", 25_000.0)["equity"]
    assert [e["sess"] for e in curve] == ["2025-03-20", "2025-03-21"]
    assert [e["cum"] for e in curve] == [-300.0, 900.0]
    assert [e["drawdown"] for e in curve] == [-300.0, 0.0]


def test_max_drawdown_seeds_its_peak_at_zero(rows):
    """A book that opens underwater counts that as drawdown — the study's own
    `bear_deploy.max_drawdown` does, and a naive cummax would report 0."""
    assert series.build(rows, "primary", 25_000.0)["summary"]["maxDD"] == -300.0
    assert series.build(rows, "secondary", 25_000.0)["summary"]["maxDD"] == -500.0


def test_census_counts_every_candidate_once(rows):
    derived = series.build(rows, "primary", 25_000.0)
    assert {c["bucket"]: c["n"] for c in derived["census"]} == {
        "taken": 2, "net_delta": 2, "per_pos_delta": 1
    }
    assert sum(c["n"] for c in derived["census"]) == derived["summary"]["candidates"]


def test_summary_reproduces_the_reports_headline_numbers(rows):
    s = series.build(rows, "primary", 25_000.0)["summary"]
    assert s["n"] == 2 and s["dates"] == 2
    assert s["dollars"] == 900.0
    assert s["meanR"] == pytest.approx(0.35)
    assert s["win"] == 0.5


def test_adverse_buckets_carry_a_bootstrap_ci(rows):
    adverse = series.build(rows, "primary", 25_000.0)["adverse"]
    assert [a["bucket"] for a in adverse] == ["taken", "net_delta", "per_pos_delta"]
    assert adverse[1]["meanR"] == pytest.approx(0.50)
    assert adverse[0]["ci"] is not None and len(adverse[0]["ci"]) == 2


def _custom_rows(tmp_path, *rows):
    path = tmp_path / "custom-positions-latest.csv"
    path.write_text(CSV_HEADER + "".join(rows))
    return series.load(path)


def test_census_never_drops_a_bucket_the_whitelist_does_not_know(tmp_path):
    """ARM H emits hedge_taken/hedge_rejected. A bucket that vanishes from the
    census breaks the page's own "every candidate accounted for exactly once"."""
    rows = _custom_rows(
        tmp_path,
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.10, -300),
        _row("primary", "skipped:hedge_rejected", "2025-03-12", "", 0.50, 0, "hedge_rejected"),
    )
    census = {c["bucket"]: c["n"] for c in series.build(rows, "primary", 25_000.0)["census"]}
    assert census == {"taken": 1, "hedge_rejected": 1}


def test_exit_panel_accounts_for_every_taken_position(tmp_path):
    """The panel is presented as a decomposition of realized dollars, so an
    unknown reason — or none at all — must surface, not silently drop out."""
    rows = _custom_rows(
        tmp_path,
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.10, -300, exit_reason="be_stop"),
        _row("primary", "taken", "2025-03-12", "2025-03-21", 0.60, 1200, exit_reason="something_new"),
        _row("primary", "taken", "2025-03-13", "2025-03-24", 0.20, 100, exit_reason=""),
    )
    derived = series.build(rows, "primary", 25_000.0)
    exits = {e["reason"]: e["n"] for e in derived["exits"]}
    assert exits == {"be_stop": 1, "something_new": 1, series.NO_EXIT_REASON: 1}
    assert sum(e["n"] for e in derived["exits"]) == derived["summary"]["n"]
    assert sum(e["dollars"] for e in derived["exits"]) == derived["summary"]["dollars"]


def test_median_days_is_a_median_not_an_index_into_a_filtered_list(tmp_path):
    rows = _custom_rows(
        tmp_path,
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.1, 100, days_held="1.0"),
        _row("primary", "taken", "2025-03-12", "2025-03-21", 0.1, 100, days_held=""),
        _row("primary", "taken", "2025-03-13", "2025-03-24", 0.1, 100, days_held="5.0"),
    )
    assert series.build(rows, "primary", 25_000.0)["summary"]["median_days"] == 3.0


def test_load_raises_on_a_renamed_column(tmp_path):
    """A renamed header would otherwise read as an empty column and draw an
    empty panel with zero reconcile complaints."""
    path = tmp_path / "renamed.csv"
    path.write_text((CSV_HEADER + _row("primary", "taken", "2025-03-11", "2025-03-20", 0.1, 100))
                    .replace("max_loss_per_contract", "max_loss"))
    with pytest.raises(series.ReconcileError, match="max_loss_per_contract"):
        series.load(path)


# ──────────────────────────────── reconciliation ────────────────────────────

def test_reconcile_passes_when_csv_and_report_describe_the_same_run(parsed, rows):
    for pop in ("primary", "secondary"):
        assert series.reconcile(series.build(rows, pop, 25_000.0), parsed, pop) == []


def test_reconcile_reports_every_disagreement(tmp_path, rows):
    """The whole point of the pairing check: a report describing a different
    run must be caught, not silently drawn."""
    other = report.parse(make_report(tmp_path / "other.txt", primary=(9, 9, 5555, 0.99, -999, -999, 90)))
    problems = series.reconcile(series.build(rows, "primary", 25_000.0), other, "primary")
    joined = " ".join(problems)
    assert "positions" in joined and "total $" in joined and "meanR" in joined


def test_reconcile_catches_a_bucket_only_one_side_has(tmp_path, parsed):
    """Both directions: the CSV growing a bucket the report's census does not
    carry, and the report carrying one the CSV stopped emitting."""
    rows = _custom_rows(
        tmp_path,
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.10, -300),
        _row("primary", "taken", "2025-03-12", "2025-03-21", 0.60, 1200),
        _row("primary", "skipped:hedge_rejected", "2025-03-13", "", 0.50, 0, "hedge_rejected"),
    )
    joined = " ".join(series.reconcile(series.build(rows, "primary", 25_000.0), parsed, "primary"))
    assert "census/hedge_rejected" in joined      # only the CSV has it
    assert "census/net_delta" in joined           # only the report has it


def test_reconcile_refuses_a_capital_the_study_did_not_simulate(parsed, rows):
    """The page states $25,000 everywhere; charting the same run at another
    account size would relabel every risk figure on it."""
    problems = series.reconcile(series.build(rows, "primary", 50_000.0), parsed, "primary")
    assert any("capital" in p for p in problems)


# ──────────────────────────────── arm pairing ───────────────────────────────

def test_is_structure_arm_reads_the_positions_filename():
    assert is_structure_arm(Path("account_sim-positions-structure-latest.csv")) is True
    assert is_structure_arm(Path("account_sim-positions-latest.csv")) is False


def test_pick_report_prefers_the_report_from_the_matching_arm(tmp_path):
    make_report(tmp_path / "account_sim-20260813-100000.txt")
    make_report(tmp_path / "account_sim-20260813-200000.txt",
                command="python -m scripts.backtest_study.account_sim --structure-universe")
    plain = pick_report(tmp_path / "account_sim-positions-latest.csv", tmp_path)
    structure = pick_report(tmp_path / "account_sim-positions-structure-latest.csv", tmp_path)
    assert plain.name == "account_sim-20260813-100000.txt"
    assert structure.name == "account_sim-20260813-200000.txt"


def test_pick_report_ignores_review_and_digest_artifacts(tmp_path):
    (tmp_path / "account_sim-review-analyst-a-latest.md").write_text("not a report")
    (tmp_path / "account_sim-digest-latest.txt").write_text("not a report either")
    make_report(tmp_path / "account_sim-latest.txt")
    assert pick_report(tmp_path / "account_sim-positions-latest.csv", tmp_path).name == "account_sim-latest.txt"


def test_pick_report_raises_when_no_report_matches_the_arm(tmp_path):
    make_report(tmp_path / "account_sim-latest.txt")
    with pytest.raises(SystemExit, match="structure-universe"):
        pick_report(tmp_path / "account_sim-positions-structure-latest.csv", tmp_path)


# ──────────────────────────────── rendering ─────────────────────────────────

@pytest.fixture
def page(parsed, rows):
    populations = {p: series.build(rows, p, 25_000.0) for p in report.POPULATIONS}
    return render.build(parsed, populations, 25_000.0,
                        {"report": "account_sim-latest.txt", "positions": "account_sim-positions-latest.csv"})


def test_page_is_a_fragment_the_artifact_publisher_accepts(page):
    """Artifact supplies the doctype and head; the fragment must not."""
    lowered = page.lower()
    for tag in ("<!doctype", "<html", "<head>", "<body"):
        assert tag not in lowered
    assert page.startswith("<title>")


def test_page_inlines_its_assets_with_no_external_requests(page):
    """The Artifact CSP blocks every external host, so nothing may be fetched."""
    assert "<style>" in page and "<script>" in page
    assert "https://" not in page
    # the only absolute URL allowed is the SVG namespace, which is an identifier
    assert page.replace("http://www.w3.org/2000/svg", "").count("http://") == 0
    for attr in ('src="http', "src='http", 'href="http', "href='http"):
        assert attr not in page


def test_embedded_json_cannot_break_out_of_the_script_tag(page):
    assert "</script>" not in page.split("window.__ACCOUNT_SIM__")[1].split("\n")[0]


def test_page_shows_the_verdict_without_repeating_it(page):
    markup = page.split("window.__ACCOUNT_SIM__")[0]  # exclude the embedded data payload
    assert markup.count("NO VERDICT MATCHES") == 1, "hero and body must not both carry it"
    assert "A1 holds but A5, A6 fail(s)" in markup, "the body carries the qualifier"


def test_page_draws_no_verdict_from_the_adverse_ordering_deltas(page):
    """The study prints a delta per skipped bucket and concludes nothing from
    it; the chart layer used to conclude for it — off a mis-sorted 'worst'."""
    assert "is not neutral about which picks it drops" not in page
    assert "delta vs taken, per skipped bucket" in page  # the report's own numbers instead


def _page_for_headline(tmp_path, rows, headline):
    path = make_report(tmp_path / "hl.txt")
    path.write_text(path.read_text().replace(
        "NO VERDICT MATCHES — A1 holds but A5, A6 fail(s)", headline))
    parsed = report.parse(path)
    populations = {p: series.build(rows, p, 25_000.0) for p in report.POPULATIONS}
    return render.build(parsed, populations, 25_000.0, {"report": "r.txt", "positions": "p.csv"})


def test_page_does_not_hard_code_the_verdict_gap_for_every_outcome(tmp_path, rows):
    """A headline with no em-dash qualifier used to render "On the primary
    population, ." and still assert the run landed in the verdict gap."""
    markup = _page_for_headline(tmp_path, rows, "FEASIBLE").split("window.__ACCOUNT_SIM__")[0]
    assert "On the primary population, ." not in markup
    assert "landed in the gap" not in markup
    assert "one of the three verdicts" in markup


def test_page_says_nothing_it_cannot_support_about_an_unknown_headline(tmp_path, rows):
    markup = _page_for_headline(tmp_path, rows, "SOMETHING THE GRAMMAR NEVER HAD").split("window.__ACCOUNT_SIM__")[0]
    assert "SOMETHING THE GRAMMAR NEVER HAD" in markup
    assert "landed in the gap" not in markup
    assert "one of the three verdicts" not in markup


def test_page_never_introduces_a_statistic_the_study_refuses_to_print(page):
    """account_sim forbids these by construction; the renderer must not add them."""
    lowered = page.lower()
    for banned in ("annualised return", "annualized return", "sharpe ratio", "time to recover"):
        assert banned not in lowered.replace("no sharpe ratio", "").replace("no time-to-recover", "")


def test_page_shows_the_config_file_the_run_loaded(page):
    markup = page.split("window.__ACCOUNT_SIM__")[0]
    assert "<h2>Setup</h2>" in markup
    shown = markup.split('<section class="setup-file">')[1].split("</pre>")[0]
    # Every line of the file, in order, with only syntax spans added. The tags
    # are stripped here for the same reason they are added there: they are
    # presentation, and the text under them must still be the file.
    text = re.sub(r"<[^>]+>", "", shown.split("<pre>")[1])
    assert text == CONFIG_FILE.strip("\n")


def test_page_shows_the_exit_rows_as_the_study_wrote_them(page):
    markup = page.split("window.__ACCOUNT_SIM__")[0]
    assert "take profit +90% · stop -75% · time exit at 75% of DTE" in markup
    assert "<dt>every position, on top of the above</dt>" in markup


def test_exit_fields_stay_separated_once_the_browser_renders_them(page):
    """HTML collapses a run of spaces, so a whitespace-separated exit phrase
    would render as one run-on sentence — the page would stop matching the
    report it quotes, while a source-level assertion still passed."""
    value = page.split("<dt>debit, non-bear</dt><dd>")[1].split("</dd>")[0]
    assert "  " not in value, "no separator may depend on whitespace surviving HTML"
    assert value.count("·") == 2
    # belt and braces: the CSS also preserves runs, so a report field that does
    # contain spaces is shown as written.
    assert "white-space: pre-wrap" in page.split(".setup-row dd {")[1].split("}")[0]


def test_page_marks_the_exit_policy_as_not_coming_from_the_config(page):
    """Editing account-sim.yml cannot move the stops, so the page may not
    present them as if it could."""
    markup = page.split("window.__ACCOUNT_SIM__")[0]
    frozen = markup.split('class="setup-group is-frozen"')
    assert len(frozen) == 2, "exactly the exits group is shaded"
    assert "frozen exit policy" in frozen[1].split("</section>")[0]
    # ...and the file panel says the opposite: this half IS the config.
    assert "as this run read it" in markup.split('<section class="setup-file">')[1]


def test_page_never_re_flows_the_config_files_indentation(page):
    """YAML indentation is syntax. A wrapped config panel would show nesting
    the file does not have, which is a false claim about what was simulated."""
    css = page.split(".setup-file pre {")[1].split("}")[0]
    assert "white-space: pre" in css and "pre-wrap" not in css


def test_page_names_the_config_file_the_run_actually_read(tmp_path, rows):
    """A run driven by --config must not have the page name the default file."""
    path = make_report(tmp_path / "r.txt")
    path.write_text(path.read_text().replace("config/account-sim.yml", "config/my-account.yml"))
    parsed = report.parse(path)
    populations = {p: series.build(rows, p, 25_000.0) for p in report.POPULATIONS}
    markup = render.build(parsed, populations, 25_000.0,
                          {"report": "r.txt", "positions": "p.csv"}).split("window.__ACCOUNT_SIM__")[0]
    assert "config/my-account.yml" in markup
    assert "config/account-sim.yml" not in markup


def test_standalone_wrapper_produces_a_real_document(page):
    doc = render.wrap_standalone(page)
    assert doc.startswith("<!doctype html>")
    assert "<body>" in doc and doc.rstrip().endswith("</html>")


# ──────────────────────────────── the CLI itself ────────────────────────────

def _cli_inputs(tmp_path, **report_kwargs):
    return (
        make_report(tmp_path / "account_sim-latest.txt", **report_kwargs),
        make_positions(tmp_path / "account_sim-positions-latest.csv"),
    )


def _run(tmp_path, *extra, report_kwargs=None):
    rep, pos = _cli_inputs(tmp_path, **(report_kwargs or {}))
    out = tmp_path / "page.html"
    docs = tmp_path / "docs" / "account-sim-charts.html"
    code = main(["--report", str(rep), "--positions", str(pos),
                 "--out", str(out), "--docs", str(docs), *extra])
    return code, out, docs


def test_main_writes_the_fragment_and_the_tracked_docs_copy(tmp_path):
    """One run, two readers: the Artifact publisher wants the fragment, a fresh
    checkout wants a page that opens on a double-click."""
    code, out, docs = _run(tmp_path)
    assert code == 0
    assert out.read_text().startswith("<title>")
    assert docs.read_text().startswith("<!doctype html>")


def test_main_no_docs_leaves_the_docs_copy_alone(tmp_path):
    code, out, docs = _run(tmp_path, "--no-docs")
    assert code == 0 and out.exists()
    assert not docs.exists()


def test_main_writes_no_html_at_all_when_reconciliation_fails(tmp_path):
    """The contract the whole module rests on. A page that disagrees with the
    report it claims to draw must never reach disk — not even the docs copy,
    which is tracked and would otherwise be committed as a quiet lie."""
    code, out, docs = _run(tmp_path, report_kwargs={"primary": (9, 9, 5555, 0.99, -999, -999, 90)})
    assert code == 1
    assert not out.exists() and not docs.exists()


def test_main_refuses_a_report_from_the_other_arm(tmp_path):
    rep = make_report(tmp_path / "account_sim-latest.txt",
                      command="python -m scripts.backtest_study.account_sim --structure-universe")
    pos = make_positions(tmp_path / "account_sim-positions-latest.csv")
    with pytest.raises(SystemExit, match="arm mismatch"):
        main(["--report", str(rep), "--positions", str(pos), "--out", str(tmp_path / "p.html")])


def test_only_the_frozen_book_gets_a_tracked_docs_page(tmp_path):
    """The widened arm's page reads the same as the frozen one chart for chart,
    so it gets no tracked copy at all — one page, not two near-identical ones."""
    plain = docs_dest(Path("account_sim-positions-latest.csv"), tmp_path)
    assert plain.name == "account-sim-charts.html"
    assert docs_dest(Path("account_sim-positions-structure-latest.csv"), tmp_path) is None


def test_structure_arm_writes_the_fragment_but_no_docs_page(tmp_path):
    rep = make_report(tmp_path / "account_sim-latest.txt",
                      command="python -m scripts.backtest_study.account_sim --structure-universe")
    pos = make_positions(tmp_path / "account_sim-positions-structure-latest.csv")
    out = tmp_path / "page.html"
    code = main(["--report", str(rep), "--positions", str(pos), "--out", str(out)])
    assert code == 0 and out.exists()
    assert not (tmp_path / "docs").exists()


def test_structure_arm_refuses_an_explicit_docs_path(tmp_path):
    """A hand-typed --docs is how the frozen book's tracked page gets clobbered."""
    rep = make_report(tmp_path / "account_sim-latest.txt",
                      command="python -m scripts.backtest_study.account_sim --structure-universe")
    pos = make_positions(tmp_path / "account_sim-positions-structure-latest.csv")
    docs = tmp_path / "docs" / "account-sim-charts.html"
    with pytest.raises(SystemExit, match="no tracked docs page"):
        main(["--report", str(rep), "--positions", str(pos),
              "--out", str(tmp_path / "p.html"), "--docs", str(docs)])
    assert not docs.exists()


# ─────────────────────── the regime cut: parse, check, draw ─────────────────

def test_parse_regime_reads_both_readings_and_the_agreement(parsed):
    r = parsed["populations"]["secondary"]["regime"]
    assert {(c["cell"], c["structure"], c["n"]) for c in r["mech"]} == {
        ("BEAR_HE", "bull_put_spread", 1), ("LVOL", "bull_call_spread", 2)}
    assert {(c["cell"], c["n"]) for c in r["model"]} == {
        ("BULL/L-VOL", 2), ("RANGE/E-VOL", 1)}
    assert r["mech_total"]["n"] == 3 and r["mech_total"]["dollars"] == 1200
    assert r["agree"] == 2 and r["agree_total"] == 3
    assert r["considered"] == 6


def test_parse_regime_drops_the_per_cell_rollups(parsed):
    """The report prints an `ALL` row per cell as a reading aid; summing the
    cells plus their own rollups would double-count the whole book."""
    r = parsed["populations"]["secondary"]["regime"]
    assert all(c["structure"] != "ALL" for c in r["mech"])
    assert sum(c["n"] for c in r["mech"]) == r["mech_total"]["n"]


def test_parse_regime_keeps_the_thin_flag(parsed):
    r = parsed["populations"]["primary"]["regime"]
    assert [c["thin"] for c in r["mech"]] == [True]


def test_parse_regime_does_not_whitelist_the_cells_that_exist_today(tmp_path):
    """A fifth mechanical cell must surface, not be silently dropped."""
    extended = dict(PRIMARY_REGIME)
    extended["mech"] = [("NEW_CELL", "bull_call_spread", 2, 900, 0.350, 1.0, True),
                        ("NEW_CELL", "ALL", 2, 900, 0.350, 1.0),
                        ("TOTAL", "ALL", 2, 900, 0.350, 1.0)]
    text = make_report(tmp_path / "r.txt").read_text().replace(
        _regime_section("PRIMARY dense episodes", **PRIMARY_REGIME),
        _regime_section("PRIMARY dense episodes", **extended))
    path = tmp_path / "extended.txt"
    path.write_text(text)
    cells = report.parse(path)["populations"]["primary"]["regime"]["mech"]
    assert [c["cell"] for c in cells] == ["NEW_CELL"]


def test_parse_regime_raises_when_a_sub_block_is_missing(tmp_path):
    text = make_report(tmp_path / "r.txt").read_text().replace(
        "--- deployment census by mechanical cell", "--- something else entirely")
    path = tmp_path / "broken.txt"
    path.write_text(text)
    with pytest.raises(report.ReportParseError, match="deployment census"):
        report.parse(path)


def test_build_regime_reproduces_the_reports_own_tables(parsed, rows):
    """Two independent implementations of the same cut — the study's own print
    and this recomputation — must land on the same numbers."""
    for pop in ("primary", "secondary"):
        derived = series.build(rows, pop, 25_000.0)["regime"]
        want = parsed["populations"][pop]["regime"]
        assert {(c["cell"], c["structure"], c["n"], c["dollars"]) for c in derived["mech"]} == \
               {(c["cell"], c["structure"], c["n"], c["dollars"]) for c in want["mech"]}
        assert derived["agree"] == want["agree"]
        assert derived["considered"] == want["considered"]


def test_reconcile_catches_a_regime_cell_only_one_side_has(tmp_path, parsed):
    """Both directions, exactly like the census check: the report quietly
    dropping a cell and the CSV quietly dropping one must each fail."""
    rows = _custom_rows(
        tmp_path,
        _row("primary", "taken", "2025-03-11", "2025-03-20", 0.10, -300, mech_cell="RB_EVOL"),
        _row("primary", "taken", "2025-03-12", "2025-03-21", 0.60, 1200),
    )
    joined = " ".join(series.reconcile(series.build(rows, "primary", 25_000.0), parsed, "primary"))
    assert "mech/RB_EVOL/bull_call_spread: absent from the report" in joined
    assert "mech/LVOL/bull_call_spread" in joined


def test_reconcile_catches_a_regime_number_that_drifted(parsed, rows):
    drifted = copy.deepcopy(parsed)
    drifted["populations"]["primary"]["regime"]["mech"][0]["meanR"] += 0.05
    drifted["populations"]["primary"]["regime"]["agree"] += 1
    joined = " ".join(series.reconcile(series.build(rows, "primary", 25_000.0), drifted, "primary"))
    assert "mech/LVOL/bull_call_spread meanR" in joined
    assert "regime agreement n" in joined


@pytest.fixture
def regime_page(parsed, rows):
    populations = {p: series.build(rows, p, 25_000.0) for p in report.POPULATIONS}
    return render_regime.build(parsed, populations, 25_000.0,
                               {"report": "account_sim-latest.txt",
                                "positions": "account_sim-positions-latest.csv"})


def test_regime_page_is_a_fragment_with_its_assets_inlined(regime_page):
    lowered = regime_page.lower()
    assert not lowered.startswith("<!doctype") and "<html" not in lowered
    assert "<style>" in regime_page and "window.__account_sim_regime__" in lowered
    # kit.js first, then the page script that destructures it.
    assert regime_page.index("__STUDY_KIT__ =") < regime_page.index("window.__STUDY_KIT__;")


def test_regime_page_says_it_is_not_a_finding(regime_page):
    """The one thing this page must never let a reader forget."""
    assert "Nothing on this page is a finding" in regime_page
    assert "pre-registers no cut by regime" in regime_page


def test_regime_page_never_introduces_a_statistic_the_study_refuses_to_print(regime_page):
    lowered = regime_page.lower()
    for banned in ("annualised return", "annualized return", "sharpe ratio", "time to recover"):
        assert banned not in lowered.replace("no sharpe ratio", "").replace("no time-to-recover", "")


def _run_regime(tmp_path, *extra, report_kwargs=None):
    rep, pos = _cli_inputs(tmp_path, **(report_kwargs or {}))
    out = tmp_path / "regime.html"
    docs = tmp_path / "docs" / "account-sim-regime.html"
    code = regime.main(["--report", str(rep), "--positions", str(pos),
                        "--out", str(out), "--docs", str(docs), *extra])
    return code, out, docs


def test_regime_main_writes_the_fragment_and_the_tracked_docs_copy(tmp_path):
    code, out, docs = _run_regime(tmp_path)
    assert code == 0
    assert out.read_text().startswith("<title>")
    assert docs.read_text().startswith("<!doctype html>")


def test_regime_main_writes_no_html_at_all_when_reconciliation_fails(tmp_path):
    code, out, docs = _run_regime(tmp_path, report_kwargs={"primary": (9, 9, 5555, 0.99, -999, -999, 90)})
    assert code == 1
    assert not out.exists() and not docs.exists()


def test_regime_page_is_a_separate_tracked_file_from_the_readout(tmp_path):
    """Two pages, two names — the duplicate-page problem must not come back."""
    assert regime.docs_dest(Path("account_sim-positions-latest.csv"), tmp_path).name \
        == "account-sim-regime.html"
    assert docs_dest(Path("account_sim-positions-latest.csv"), tmp_path).name \
        == "account-sim-charts.html"
    assert regime.docs_dest(Path("account_sim-positions-structure-latest.csv"), tmp_path) is None
