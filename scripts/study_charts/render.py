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
import re
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


def _yaml(text: str) -> str:
    """The config file, escaped, with comments and keys tinted.

    Presentational only: this adds `<span>`s around slices of the text and
    removes nothing, so what renders is still the file's own bytes. The comment
    rule is YAML's (a `#` at line start or after whitespace) minus the
    quoted-string exception, which this config has no occasion to use — the
    worst a miss can do is colour a run of text, never alter it.
    """
    lines = []
    for line in text.split("\n"):
        m = re.search(r"(?:^|(?<=\s))#.*$", line)
        code, comment = (line[: m.start()], line[m.start():]) if m else (line, "")
        key = re.match(r"(\s*(?:- )?)([\w.-]+)(:)", code)
        if key:
            html_ = (
                _esc(key.group(1))
                + f'<span class="y-key">{_esc(key.group(2))}</span>'
                + _esc(key.group(3))
                + _esc(code[key.end():])
            )
        else:
            html_ = _esc(code)
        if comment:
            html_ += f'<span class="y-com">{_esc(comment)}</span>'
        lines.append(html_)
    return "\n".join(lines)


def _setup(cfg: dict) -> str:
    """The config file this run loaded, plus the exits that file cannot set.

    The file is the report's echo of the bytes the run parsed, shown as text.
    The exit rows are the study's own words for what the frozen replay applied.
    Nothing here re-derives a value or restates one in the page's words: a page
    that paraphrased "2% risk" or "stop -75%" would be free to drift from the
    run that produced the charts below it.
    """
    rows = "".join(
        f'<div class="setup-row"><dt>{_esc(r["label"])}</dt>'
        f'<dd>{_esc(r["value"])}</dd></div>'
        for r in cfg["exits"]
    )
    return f"""    <div class="setup">
      <section class="setup-file">
        <h3>{_esc(cfg['source'])}<span class="origin">as this run read it</span></h3>
        <pre>{_yaml(cfg['file'])}</pre>
      </section>
      <section class="setup-group is-frozen">
        <h3>{_esc(cfg['exits_title'])}<span class="origin">frozen exit policy</span></h3>
        <dl>{rows}</dl>
      </section>
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


def lede_facts(parsed: dict, capital: float) -> dict:
    """The run's configured numbers, in words, read back out of its own report.

    Every one of these is config-driven (`config/account-sim.yml` or whatever
    `--config` named), so the page quotes the report rather than naming a
    value: a hardcoded pair here silently outlives the config it describes.
    Shared with the pages that write their own standfirst.
    """
    # accounts[1] is this run's configured account (accounts[0] is the stored
    # book's own historical size).
    risk_acc = parsed["populations"]["primary"]["granularity"]["accounts"][1]
    return {
        "capital": f"${capital:,.0f}",
        "risk_pct": (f"{100 * risk_acc['budget'] / risk_acc['capital']:g}%"
                     if risk_acc["capital"] else "its"),
        "caps": _caps_phrase(parsed["populations"]["primary"]["cap_grid"]["headline"]),
        "positions": f"{parsed['account_config']['max_per_day']} positions a day",
    }


def build(parsed: dict, populations: dict, capital: float, source: dict, *,
          title: str | None = None, heading: str | None = None,
          standfirst: str | None = None, banner: str = "", sections: str = "",
          entry: str = "scripts.study_charts.account_sim") -> str:
    """Assemble the page fragment from parsed report + derived series.

    The keyword arguments are what lets a second arm reuse this page instead of
    growing a near-copy of it: `title`/`heading`/`standfirst` replace the lede
    (the frozen book's says "pre-registered", which is only true of that arm),
    `banner` adds a standing warning under the verdict, `sections` adds page
    sections after the population panels, and `entry` names the module that
    rendered it in the footer. Defaulted, the output is byte-identical to what
    the frozen readout has always emitted.
    """
    prov = parsed["provenance"]
    verdict = parsed["verdict"]
    gates = parsed["gates"]
    notes = parsed["population_notes"]

    title = title or f"${capital / 1000:g}k Feasibility Readout"
    capital_str = f"${capital:,.0f}"
    facts = lede_facts(parsed, capital)
    risk_pct_str, caps_str, positions_str = facts["risk_pct"], facts["caps"], facts["positions"]
    heading = heading or f"Can the shipped ladder be traded in a {capital_str} account?"
    standfirst = standfirst or (
        f"A pre-registered feasibility simulation of the deployment ladder at\n      "
        f"{capital_str} of capital, {risk_pct_str} risk per position on a max-loss basis, "
        f"{positions_str}, and\n      {caps_str}. Selection and exits are\n      "
        f"frozen; only the account is new."
    )

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
    <h1>{heading}</h1>
    <p class="standfirst">{standfirst}</p>
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
    {banner}
  </section>

  <section id="setup">
    <div class="section-head">
      <h2>Setup</h2>
      <p>The config file this run loaded, echoed into its report from the same bytes it
        parsed — not re-read here from a file that may since have moved on.</p>
    </div>
{_setup(parsed['configuration'])}
    <p class="note" style="margin-top:16px"><code>{_esc(parsed['configuration']['source'])}</code>
      <strong>is</strong> the simulation: capital, caps, compounding, population, criteria, grids
      and gates all come from it, and copying it and passing <code>--config</code> is how a
      different account gets simulated. The shaded group is the <strong>exit policy</strong>,
      which is <em>not</em> in that file — it is the shipped ladder's, applied by the frozen replay
      harness, and no edit to the config can move it. The cap values and the compounding block are a
      friction model — no value in either may be adopted on the basis of P&amp;L.</p>
  </section>

  <section id="gates">
    <div class="section-head">
      <h2>Gates G2–G5</h2>
      <p>Identity checks that must pass before any number below is admissible. A failure exits non-zero.
        There is no G1: it was a checksum of the deployed book against constants stored in the config,
        removed in August 2026 because those constants fingerprinted a single export and so failed on
        every legitimate data refresh rather than on a regression. Its calibration numbers are still
        reported by the study, as description rather than as a verdict.</p>
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
{sections}
  <footer>
    Rendered by <code>python -m {entry}</code> from
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
