"""Emit the regime readout page.

Same contract as `render.py`: an HTML *fragment* by default (what the Artifact
publisher wants), wrappable into a standalone document. It shares that module's
page shell helpers and `assets/page.css`, and inlines `assets/kit.js` ahead of
its own `assets/regime.js`.

This page describes a cut the study does not pre-register, which is the whole
reason its framing is fixed here in Python rather than left to the chart layer:
the banner, the thin-cell rule and the "nothing here is a finding" sentence are
part of the page, not decoration a later edit can quietly drop.
"""
from __future__ import annotations

import json

from scripts.study_charts.render import ASSETS, _esc, _provenance, asset_js


def build(parsed: dict, populations: dict, capital: float, source: dict) -> str:
    """Assemble the regime page fragment.

    `populations` carries the CSV-derived series — the same object the readout
    page draws — and only its `regime` and `summary` slices reach the payload.
    Those were reconciled against the report's own DEPLOYED BOOK BY REGIME
    section before this was called, so quoting the recomputed side is not a
    second opinion; it is the checked one.
    """
    prov = parsed["provenance"]
    notes = parsed["population_notes"]

    title = f"${capital / 1000:g}k Deployed Book by Regime"
    capital_str = f"${capital:,.0f}"

    payload = {
        "capital": capital,
        "populations": {
            pop: {"regime": series["regime"], "summary": series["summary"]}
            for pop, series in populations.items()
        },
        "source": source,
    }
    data_json = json.dumps(payload, allow_nan=False).replace("</", "<\\/")

    css = (ASSETS / "page.css").read_text()
    js = asset_js("kit.js", "regime.js")

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
    <h1>Which structures did the account deploy, and in which regimes?</h1>
    <p class="standfirst">A description of the book the {capital_str} feasibility walk actually opened:
      what it deployed, under which of the two regime readings the book carries, what each cell
      cost in capital and delta-notional, and what the caps refused there. Selection, sizing and
      exits are the frozen ones — this page only re-groups their output.</p>
{_provenance(prov)}
  </header>

  <section id="standing">
    <p class="note is-warning"><strong>Nothing on this page is a finding.</strong> account_sim
      pre-registers no cut by regime. These cells were chosen after seeing the book, most of them
      hold fewer than ten positions, and no rule may be read off any of them. A cell marked
      <strong>†</strong> or <em>thin</em> is one whose numbers are too few to read qualitatively at
      all. The study prints this same cut in its own report, and every figure here was recomputed
      from the positions export and reconciled against that report before the page was written.</p>
    {arm_note}
    <p class="note">By construction the study prints no annualised figure, no Sharpe ratio and no
      time-to-recover, and this page does not add any.</p>
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
      conclusion alone. Regime cells are thinner still inside either one.</p>
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
    Rendered by <code>python -m scripts.study_charts.regime</code> from
    <code>{_esc(source['report'])}</code> and <code>{_esc(source['positions'])}</code>.
    Every figure is recomputed from the study's positions export and reconciled against the
    study's own report at build time — the build fails rather than draw a chart that disagrees
    with the study. Research tier: not a shippable rule, and this cut is not even a tested one.
  </footer>
</div>

<script>
window.__ACCOUNT_SIM_REGIME__ = {data_json};
</script>
<script>
{js}
</script>
"""
