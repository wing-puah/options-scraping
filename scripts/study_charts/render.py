"""Emit the self-contained readout page.

Output is an HTML *fragment* by default — a `<title>`, an inline `<style>`, the
page body, and an inline `<script>` — because that is what the Artifact
publisher wants (it supplies the doctype and head itself). Pass
`standalone=True` to wrap the same bytes in a minimal document for opening the
file straight off disk.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"


# The verdict grammar account_sim emits, verbatim. "NOT FEASIBLE AT ..." carries
# the configured capital formatted into the string, so it is matched by prefix
# rather than by an exact, now-stale dollar figure.
def _is_named_verdict(head: str) -> bool:
    return head in ("FEASIBLE", "FEASIBLE-BUT-DEGRADED") or head.startswith("NOT FEASIBLE AT ")


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _caps_phrase(headline: dict) -> str:
    """Name the run's delta-notional caps from the report's headline cell.
    `inf` is a legal configured value (YAML `null`), so it gets prose rather
    than a number."""
    per_pos, net = headline["per_pos"], headline["net"]
    if per_pos == "inf" and net == "inf":
        return "no delta-notional caps at all"
    if per_pos == "inf":
        return f"an uncapped per-position delta-notional and a net cap of {net}x equity"
    if net == "inf":
        return f"a per-position delta-notional cap of {per_pos}x equity and no net cap"
    return f"delta-notional caps of {per_pos}x equity per position and {net}x net"


def asset_js(*names: str) -> str:
    """Inline JS assets in order, escaped so a string in them cannot close the
    surrounding <script>. kit.js goes first on every page: it defines the
    primitives the page script destructures at its top."""
    return "\n".join(
        (ASSETS / name).read_text().replace("</script", "<\\/script") for name in names
    )


def _gate_chip(gate: dict) -> str:
    good = gate["status"] == "PASS"
    detail = f'<div class="detail">{_esc(gate["note"])}</div>' if gate["note"] else ""
    return f"""      <div class="chip {'is-good' if good else 'is-bad'}">
        <span class="id">{_esc(gate['id'])}</span>
        <span class="mark">{'✓' if good else '✗'}</span>
        <div><div class="title">{_esc(gate['title'])}</div>{detail}</div>
        <span class="state">{_esc(gate['status'])}</span>
      </div>"""


def _provenance(prov: dict) -> str:
    inputs = " · ".join(
        f"{i['rows']:,} rows {Path(i['path']).name}" for i in prov["inputs"]
    )
    return f"""    <div class="provenance">
      <span><b>run</b> {_esc(prov['run_at'])}</span>
      <span><b>git</b> {_esc(prov['git'])}</span>
      <span><b>command</b> {_esc(prov['command'])}</span>
      <span><b>inputs</b> {_esc(inputs)}</span>
    </div>"""


def _episodes(notes: dict) -> str:
    rows = "".join(
        f"<tr><td>{_esc(e['id'])}</td><td>{_esc(e['start'])}</td><td>{_esc(e['end'])}</td>"
        f"<td>{e['dates']}</td><td>{e['sessions']}</td><td>{e['picks']}</td></tr>"
        for e in notes["episodes"]
    )
    head = ("<tr><th>Episode</th><th>From</th><th>To</th><th>Signal dates</th>"
            "<th>Sessions</th><th>Deployed picks</th></tr>")
    return f"""      <div class="table-view">
        <table>
          <thead>{head}</thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""


def build(parsed: dict, populations: dict, capital: float, source: dict) -> str:
    """Assemble the page fragment from parsed report + derived series."""
    prov = parsed["provenance"]
    verdict = parsed["verdict"]
    gates = parsed["gates"]
    notes = parsed["population_notes"]

    title = f"${capital / 1000:g}k Feasibility Readout"
    capital_str = f"${capital:,.0f}"
    # The intended per-position risk %, read back out of the report's own
    # GRANULARITY account line rather than assumed — accounts[1] is this run's
    # configured account (accounts[0] is the stored book's own historical size).
    risk_acc = parsed["populations"]["primary"]["granularity"]["accounts"][1]
    risk_pct_str = (
        f"{100 * risk_acc['budget'] / risk_acc['capital']:g}%" if risk_acc["capital"] else "its"
    )
    # The caps are config-driven (config/account-sim.yml), so the standfirst
    # quotes the report's own HEADLINE CELL rather than naming a value. A
    # hardcoded pair here silently outlives the config it describes.
    caps_str = _caps_phrase(parsed["populations"]["primary"]["cap_grid"]["headline"])
    # max_positions_per_day is config-driven too (config/account-sim.yml), read
    # back from the report's own header block rather than assumed as "three".
    positions_str = f"{parsed['account_config']['max_per_day']} positions a day"

    payload = {
        "capital": capital,
        "report": parsed,
        "populations": populations,
        "source": source,
    }
    data_json = json.dumps(payload, allow_nan=False).replace("</", "<\\/")

    css = (ASSETS / "page.css").read_text()
    js = asset_js("kit.js", "page.js")

    # "NO VERDICT MATCHES — A1 holds but A5, A6 fail(s)": the hero takes the
    # verdict, the body takes the qualifier, so neither repeats the other. The
    # em dash + qualifier only ever appear on that one no-match headline — the
    # other three (FEASIBLE, FEASIBLE-BUT-DEGRADED, NOT FEASIBLE AT the
    # configured capital) are bare.
    head, _, qualifier = verdict["headline"].partition("—")
    head = head.strip()
    qualifier = qualifier.strip().rstrip(".")
    qualifier_html = (
        f'<p class="verdict-body">On the primary population, {_esc(qualifier)}.</p>'
        if qualifier else ""
    )
    # Three outcomes are named by the verdict grammar; the run can also land
    # outside all three, which is what a no-match headline says. A headline
    # matching neither shape is one this page has nothing true to say about,
    # so it says nothing and shows the checklist — inventing a reading is
    # exactly the failure being fixed here. The old "NO PRE-REGISTERED..."
    # prefix is still accepted so an older report does not silently fall
    # through to the empty case.
    if head.startswith("NO VERDICT MATCHES") or head.startswith("NO PRE-REGISTERED VERDICT MATCHES"):
        partition_html = """<p class="verdict-body">The three
        verdicts (FEASIBLE, FEASIBLE-BUT-DEGRADED, NOT FEASIBLE AT the configured capital) do not
        partition the outcome space, and the run landed in the gap. Nothing has been relabelled to
        fit: the A1–A6 checklist is the result, and the verdict grammar is recorded as incomplete
        for whoever replicates this.</p>"""
    elif _is_named_verdict(head):
        partition_html = (
            '<p class="verdict-body">This is one of the three verdicts '
            '(FEASIBLE, FEASIBLE-BUT-DEGRADED, NOT FEASIBLE AT the configured capital); the A1–A6 '
            "checklist below is what carries it.</p>"
        )
    else:
        partition_html = ""
    arm_note = ""
    if parsed["structure_arm"]:
        sa = parsed["structure_arm"]
        arm_note = (
            f'<p class="note is-warning"><strong>Structure-universe arm.</strong> This run opened the '
            f'proxy calibration gate, widening the candidate set from {sa["universe_before"]} to '
            f'{sa["universe_after"]} rows and the deployed book from {sa["deployed_before"]} to '
            f'{sa["deployed_after"]} picks. It is an exploratory widening, not the frozen book.</p>'
        )

    return f"""<title>{title}</title>
<style>
{css}
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">backtest study · account_sim · research tier</p>
    <h1>Can the shipped ladder be traded in a {capital_str} account?</h1>
    <p class="standfirst">A pre-registered feasibility simulation of the deployment ladder at
      {capital_str} of capital, {risk_pct_str} risk per position on a max-loss basis, {positions_str}, and
      {caps_str}. Selection and exits are
      frozen; only the account is new.</p>
{_provenance(prov)}
  </header>

  <section id="verdict">
    <div class="verdict">
      <div class="verdict-head">
        <p class="verdict-figure">{_esc(head)}</p>
      </div>
      {qualifier_html}
      {partition_html}
      <p class="verdict-body"><strong>Nothing in this study ships.</strong> The cap values are a
        friction model, not tuned parameters. By construction the study prints no annualised
        figure, no Sharpe ratio and no time-to-recover, and this page does not add any.</p>
    </div>
    {arm_note}
  </section>

  <section id="gates">
    <div class="section-head">
      <h2>Gates G1–G5</h2>
      <p>Identity checks that must pass before any number below is admissible. A failure exits non-zero.</p>
    </div>
    <div class="chips">
{chr(10).join(_gate_chip(g) for g in gates['gates'])}
    </div>
    <p class="note" style="margin-top:16px">G5 is the one that makes the rest usable by an agent proposing live
      positions: every record is re-wrapped so that reading an outcome key raises, the outcome columns
      are deleted from the underlying row so a read cannot route around the wrapper, and the run must
      still produce a byte-identical book. No ordering, sizing or admission decision can be standing on
      a number that would not exist yet in real time.</p>
  </section>

  <section id="population">
    <div class="section-head">
      <h2>Population</h2>
      <p>{notes['signal_dates']} deployed signal dates, {_esc(notes['span'][0])} to {_esc(notes['span'][1])}.</p>
    </div>
    <p class="note">The primary population is the {len(notes['episodes'])} dense episodes — maximal runs of signal
      dates with no internal gap over 5 trading sessions and at least 10 dates. {notes['excluded_isolated']} isolated
      dates are excluded from it. The full sparse book is reported as secondary; the pre-registration
      says it is an availability upper bound and a concurrency lower bound, and may not carry a
      conclusion alone.</p>
{_episodes(notes)}
  </section>

  <div class="filters">
    <div class="switch" role="group" aria-label="Population">
      <button type="button" data-population="primary" aria-pressed="true">PRIMARY · dense episodes</button>
      <button type="button" data-population="secondary" aria-pressed="false">SECONDARY · full book</button>
    </div>
    <p class="filter-note">Everything below is scoped to the selected population.</p>
  </div>

  <div id="panels"></div>

  <footer>
    Rendered by <code>python -m scripts.study_charts.account_sim</code> from
    <code>{_esc(source['report'])}</code> and <code>{_esc(source['positions'])}</code>.
    Every figure is either read out of the study's own report text or recomputed from its positions
    export and reconciled against that report at build time — the build fails rather than draw a
    chart that disagrees with the study. Research tier: not a shippable rule.
  </footer>
</div>

<script>
window.__ACCOUNT_SIM__ = {data_json};
</script>
<script>
{js}
</script>
"""


def wrap_standalone(fragment: str) -> str:
    """Wrap the fragment in a minimal document for opening straight off disk."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"</head>\n<body>\n{fragment}\n</body>\n</html>\n"
    )
