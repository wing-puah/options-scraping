"""Render the account_sim study's COMPOUNDING arm as its own HTML page.

    python -m scripts.study_charts.compounding
    python -m scripts.study_charts.compounding --standalone --open
    python -m scripts.study_charts.compounding --positions .../account_sim-positions-compounding-latest.csv

One `account_sim` run now produces two arms — the frozen, path-INDEPENDENT book
and this post-hoc compounding sensitivity, which re-marks SIZING to realized
equity at fixed calendar intervals — and each writes its own report and its own
positions CSV. This page exists so the second one can never overwrite the
first's: the frozen book keeps `account-sim-charts.html`, this arm gets
`account-sim-compounding.html`, and `cli.docs_dest` refuses either arm on the
other's page (both files are generated output, rebuilt by `make study-docs`).

It draws the SAME page builder as the frozen readout (`render.build`) because
the compounding report has the same shape — the same sections, the same
reconcile-or-write-nothing contract — plus two things only this arm has: the
`EQUITY MARKS` re-mark series, drawn here as its own section, and the study's
own inline statement that A2/A5 do not transfer to a compounded basis. Both are
QUOTED from the report rather than restated, for the reason the regime page
gives about its own framing: a warning a later edit can quietly reword is not a
warning.

The pipeline itself lives in `cli.py`, shared with the other pages.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.study_charts import cli, render, report  # noqa: E402
from scripts.study_charts.render import _esc  # noqa: E402

DOCS_NAME = "account-sim-compounding.html"
OUT_STEM = "account_sim-compounding-charts"
DEFAULT_POSITIONS = cli.OUT_DIR / "account_sim-positions-compounding-latest.csv"

# The criteria whose meaning the study says does not survive compounding. Both
# print the same warning; the page quotes it once, attributed to both.
NON_TRANSFERRING = ("A2", "A5")


def docs_dest(positions: Path, docs_dir: Path = cli.DOCS_DIR) -> Path | None:
    """Where this page's generated copy lives, or None off the compounding arm."""
    return cli.docs_dest(positions, DOCS_NAME, docs_dir)


def _quote(text: str, cite: str) -> str:
    """The report's own words, shown as written and attributed."""
    return (f'<blockquote class="quote">{_esc(text)}'
            f'<span class="cite">— {_esc(cite)}</span></blockquote>')


def _non_transfer_warning(parsed: dict) -> str:
    """The study's inline A2/A5 non-transfer text, verbatim.

    Required, not optional: this page's whole risk is that a reader takes a
    compounded ratio as an attrition or stability result. If the report stopped
    printing the warning, the honest move is to write no page at all rather
    than one that lost it.
    """
    for crit in parsed["populations"]["primary"]["criteria"]:
        if crit["id"] in NON_TRANSFERRING and crit["warning"]:
            return crit["warning"]
    raise SystemExit(
        "the compounding report carries no A2/A5 non-transfer warning under "
        f"{'/'.join(NON_TRANSFERRING)} — this page may not be drawn without it. "
        "Check that account_sim still prints COMPOUND_A2_A5_WARNING under the "
        "compounding arm."
    )


def _banner(parsed: dict, marks: dict) -> str:
    """The standing warning under the verdict: what arm this is, in whose words."""
    return (
        '<p class="note is-warning"><strong>Post-hoc compounding sensitivity — NOT the '
        'pre-registered book.</strong> This page draws the arm that re-marks sizing to '
        f'realized equity every {_esc(marks["interval"])}, under a '
        f'{_esc(marks["ceiling"])} budget ceiling. The frozen, path-independent book — the one '
        'A1–A6 were pre-registered against — is a different run with its own page '
        '(<code>account-sim-charts.html</code>). The mark interval and the ceiling are a '
        'friction model and may not be adopted on the basis of P&amp;L. The study says it '
        'itself:</p>\n    '
        + _quote(marks["note"], "account_sim, EQUITY MARKS")
        + '\n    <p class="note is-warning"><strong>A2 and A5 do not transfer to this arm.</strong> '
          'Their MET/NOT MET verdicts are still shown below exactly as the study printed them, '
          'and they are still not readable as attrition or stability here:</p>\n    '
        + _quote(_non_transfer_warning(parsed), "account_sim, printed under A2 and A5")
    )


def _marks_table(marks: dict) -> str:
    head = ("<tr><th>Mark session</th><th>Marked equity</th><th>Budget</th>"
            "<th>Per-pos cap $</th><th>Net cap $</th><th>Flags</th></tr>")
    rows = "".join(
        f"<tr><td>{_esc(m['session'])}</td><td>{m['equity']:,.0f}</td>"
        f"<td>{m['budget']:,.0f}</td><td>{m['per_pos']:,.0f}</td>"
        f"<td>{m['net']:,.0f}</td><td>{_esc(' '.join(m['flags']))}</td></tr>"
        for m in marks["marks"]
    )
    return f"""      <div class="table-view">
        <table>
          <thead>{head}</thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""


def _marks_population(pop: str, marks: dict) -> str:
    """One population's re-mark series, in the report's own figures."""
    label = report.POPULATIONS[pop]
    if not marks["count"]:
        body = '<p class="how">No marks — this population held no signal dates.</p>'
    else:
        summary = (
            f"{marks['count']} marks · first ${marks['first']:,.0f} · peak ${marks['peak']:,.0f} · "
            f"final ${marks['final']:,.0f} · starting capital ${marks['capital']:,.0f} · "
            f"budget ceiling bound on {marks['ceiling_bound']} of {marks['count']} · "
            f"ruin guard fired on {marks['ruined']}"
        )
        truncated = ""
        if marks["truncated"]:
            truncated = (f'\n      <p class="note">The report prints the first '
                         f'{marks["print_cap"]} marks; the remaining {marks["truncated"]} are not '
                         f'shown here either — this page quotes the report, it does not recompute '
                         f'the sizing path.</p>')
        body = f'<p class="how">{_esc(summary)}</p>\n{_marks_table(marks)}{truncated}'
    return f"""    <div class="panel">
      <div class="panel-head"><h3>{_esc(label)}</h3></div>
      {body}
    </div>"""


def _marks_section(parsed: dict, marks_by_pop: dict) -> str:
    """The EQUITY MARKS section — the one thing only this arm has.

    Both populations are laid out together rather than wired to the page's
    population switch: the switch drives the panels the study reconciles, and
    these figures are read straight out of the report, so putting them under it
    would suggest they came from the same recomputation.
    """
    bodies = "\n".join(_marks_population(pop, marks_by_pop[pop])
                       for pop in report.POPULATIONS if marks_by_pop.get(pop))
    bodies = f'    <div class="stack" style="margin-top:18px">\n{bodies}\n    </div>'
    return f"""
  <section id="equity-marks">
    <div class="section-head">
      <h2>Equity re-marks</h2>
      <p>Every session on which this arm re-marked its sizing basis, and what that did to the
        per-position budget and the two delta-notional caps. Read out of the study's own
        EQUITY MARKS table — not recomputed here.</p>
    </div>
    <p class="note is-warning">marked_equity counts only positions <strong>closed before</strong>
      the mark session; open positions are never marked to market. It moves SIZING only — the
      ledger's own capital is untouched, which is why G3 still balances against the starting
      capital. Nothing in this section is a criterion, and no rule may be read off it.</p>
{bodies}
  </section>
"""


def build(parsed: dict, populations: dict, capital: float, source: dict) -> str:
    """The compounding arm's page: the shared readout plus what only it has."""
    if not parsed["provenance"]["compound_arm"]:
        raise SystemExit(
            f"this page draws the compounding arm, but {source['report']} ran "
            f"`{parsed['provenance']['command']}`. The frozen book's page is "
            "scripts.study_charts.account_sim."
        )
    marks_by_pop = {pop: parsed["populations"][pop]["equity_marks"]
                    for pop in report.POPULATIONS}
    primary = marks_by_pop["primary"]
    if primary is None:
        raise SystemExit(
            f"{source['report']} is a --compounding run but prints no "
            "[PRIMARY dense episodes] EQUITY MARKS section; this page has nothing to draw "
            "that the frozen book's page does not already show."
        )

    facts = render.lede_facts(parsed, capital)
    standfirst = (
        f"The same frozen selection and exits as the pre-registered book, at the same "
        f"{facts['capital']} starting capital, {facts['risk_pct']} risk per position on a "
        f"max-loss basis, {facts['positions']}, and {facts['caps']} — but with the sizing basis "
        f"re-marked to realized equity every {_esc(primary['interval'])}. A labelled "
        f"sensitivity, not the book."
    )
    return render.build(
        parsed, populations, capital, source,
        title=f"${capital / 1000:g}k Compounding Sensitivity",
        heading="What changes when sizing is re-marked to realized equity?",
        standfirst=standfirst,
        banner=_banner(parsed, primary),
        sections=_marks_section(parsed, marks_by_pop),
        entry="scripts.study_charts.compounding",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_arguments(ap, DOCS_NAME)
    ap.set_defaults(positions=DEFAULT_POSITIONS)
    args = ap.parse_args(argv)
    if not cli.is_compounding_arm(args.positions):
        raise SystemExit(
            f"{args.positions.name} is the {cli.arm_of(args.positions)} arm's export, and this "
            "page draws the compounding arm. Render the frozen book with "
            "scripts.study_charts.account_sim."
        )
    return cli.run(args, build=build, out_stem=OUT_STEM, docs_name=DOCS_NAME,
                   module="compounding")


if __name__ == "__main__":
    raise SystemExit(main())
