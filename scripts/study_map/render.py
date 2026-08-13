"""Assemble the page.

Emits an HTML *fragment* — `<title>`, inline `<style>`, body markup — matching
what `scripts/study_charts/render.py` produces, so the same bytes can be
published as an Artifact or, via `wrap_standalone`, opened straight off disk.

Everything on the page comes from one of three places, and the markup keeps
them visually separated because they carry different authority:

    catalog.py  hand-written verdicts     — what the programme concluded
    summary.py  quoted report excerpts    — what the last run printed
    tuning.py   quoted current.md headings — what was last written up
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from . import catalog, summary, tuning

ASSETS = Path(__file__).resolve().parent / "assets"
TITLE = "Backtest Study Map"

_KIND_NOTE = {
    "verdict": "quoted from the report's own VERDICT block",
    "failure": "the run did not finish — this is where it stopped",
    "matched": "lines stating a pre-registered criterion, quoted in order",
    "tail": "no verdict block in this report — this is its last few lines, "
            "not a conclusion it drew",
}


def _e(text: object) -> str:
    return html.escape(str(text), quote=False)


_CODE = re.compile(r"`([^`]+)`")


def _rich(text: object) -> str:
    """Escape, then honour `backticks` — the catalog is written in prose+idents."""
    return _CODE.sub(r"<code>\1</code>", _e(text))


# ── diagram ───────────────────────────────────────────────────────────────────
def _svg_box(x: int, y: int, w: int, h: int, title: str, subs: list[str],
             tag: str = "", accent: bool = False) -> str:
    cls = "d-box-accent" if accent else "d-box"
    parts = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>']
    ty = y + 20
    if tag:
        parts.append(f'<text class="d-tag" x="{x + 12}" y="{ty}">{_e(tag)}</text>')
        ty += 16
    parts.append(f'<text class="d-title" x="{x + 12}" y="{ty}">{_e(title)}</text>')
    for i, sub in enumerate(subs):
        parts.append(
            f'<text class="d-sub" x="{x + 12}" y="{ty + 16 + i * 14}">{_e(sub)}</text>')
    return "".join(parts)


def _diagram(counts: dict[str, int]) -> str:
    fam = catalog.FAMILIES
    # Short labels, not truncated catalog text — a diagram that clips a word
    # mid-way reads as a bug rather than as shorthand.
    lanes = [
        ("selection", "what to trade", "mostly null", "0/496 subsets · 0/15 cells"),
        ("management", "when to get out", "the edge is here", "2 rules shipped"),
        ("structure", "which wrapper", "one +0.085", "dies out of sample"),
        ("deployment", "can I run it", "feasibility only", "delta binds, not cash"),
    ]
    xs = [70, 265, 460, 655]
    boxes = "".join(
        _svg_box(x, 300, 175, 108,
                 f"{fam[key]['index']} {fam[key]['title'].upper()}",
                 [label, "", line1, line2],
                 tag=f"{counts.get(key, 0)} STUDIES")
        for x, (key, label, line1, line2) in zip(xs, lanes))
    drops = "".join(
        f'<path class="d-line" d="M {x + 87} 276 V 300"/>'
        f'<path class="d-line" d="M {x + 87} 408 V 432"/>' for x in xs)
    return f"""    <div class="diagram">
      <svg viewBox="0 0 900 500" role="img" aria-label="Flow from the analysis engine
        through the pooled book and the frozen harness into four study families and
        out to the operator card.">
        {_svg_box(300, 8, 300, 46, "ANALYSIS ENGINE", ["v3 frozen · v4 live"])}
        <path class="d-line" d="M 450 54 V 82"/>
        {_svg_box(190, 82, 520, 68, "THE BOOK", [
            "real rows + real-priced proxy rows, calibration-gated",
            "n is the ~118 SIGNAL DATES, not the ~1,100 rows"], tag="BOOK.PY")}
        <path class="d-line" d="M 450 150 V 178"/>
        {_svg_box(190, 178, 520, 68, "HARNESS · PROTOCOL", [
            "frozen replay of stored marks — prices nothing",
            "purged walk-forward · date-clustered CIs · LOO · window re-cuts"],
            tag="HARNESS.PY / PROTOCOL.PY")}
        <path class="d-line" d="M 450 246 V 276"/>
        <path class="d-line" d="M 157 276 H 742"/>
        {drops}
        {boxes}
        <path class="d-line" d="M 157 432 H 742"/>
        {_svg_box(300, 432, 300, 52, "config/deployment-rules.md",
                  ["the operator card — top 3/day, tiers A/B"], accent=True)}
      </svg>
    </div>"""


# ── cards ─────────────────────────────────────────────────────────────────────
def _run_state(run: summary.RunSummary) -> str:
    if not run.ran:
        return '<span class="run-state">never run</span>'
    when = run.run_at.split()[0] if run.run_at else ""
    if run.ok:
        mark = '<span class="good">ok</span>'
    else:
        mark = f'<span class="bad">{_e(run.status)}</span>'
    return f'<span class="run-state">last run {_e(when)} · {mark}</span>'


def _run_block(run: summary.RunSummary) -> str:
    if not run.ran:
        return ('      <p class="caveat">No report on disk. Run '
                f'<code>python -m scripts.backtest_study run {_e(run.name)}</code> '
                'and this block fills in.</p>')

    meta = [f"<span><b>run</b> {_e(run.run_at)}</span>"]
    if run.git:
        meta.append(f"<span><b>git</b> {_e(run.git)}</span>")
    if run.elapsed:
        meta.append(f"<span><b>took</b> {_e(run.elapsed)}</span>")
    if run.inputs:
        inputs = " · ".join(f"{rows} {Path(path).name}" for rows, _, path in run.inputs)
        meta.append(f"<span><b>inputs</b> {_e(inputs)}</span>")
    if run.missing_inputs:
        meta.append(f'<span><b>MISSING</b> {_e(", ".join(run.missing_inputs))}</span>')

    caveats = []
    if not run.ok:
        caveats.append('<p class="caveat is-warning">This run exited non-zero. For most '
                       'studies that is a calibration or input gate refusing to print '
                       'numbers it cannot vouch for — read it as the gate working, not '
                       'as a result.</p>')
    if run.dirty:
        caveats.append('<p class="caveat">Working tree was dirty at run time, so the git '
                       'sha does not fully identify the code that produced this.</p>')
    if run.digest_title:
        caveats.append(
            '<p class="caveat">Graded write-up on disk: '
            f'<code>{_e(run.digest_path.name)}</code> — “{_e(run.digest_title)}”.</p>')

    links = []
    if run.report:
        links.append(f'<span>report: <code>{_e(run.report.name)}</code></span>')
    if run.charts_path:
        links.append(f'<span>charts: <code>{_e(run.charts_path.name)}</code></span>')
    if run.regime_path:
        links.append(f'<span>by regime: <code>{_e(run.regime_path.name)}</code></span>')

    excerpt = "\n".join(_e(line) for line in run.excerpt) or "(empty report)"
    kind_note = _KIND_NOTE.get(run.excerpt_kind, "")

    return f"""      <details class="run">
        <summary>what the last run printed <span class="kind">— {_e(kind_note)}</span></summary>
        <div class="run-body">
          <div class="meta">{''.join(meta)}</div>
          <pre class="excerpt">{excerpt}</pre>
          <div class="links">{''.join(links)}</div>
{chr(10).join(caveats)}
        </div>
      </details>"""


def _card(name: str, study: catalog.Study, run: summary.RunSummary) -> str:
    state = study.state
    return f"""    <article class="card is-{state}">
      <div class="card-head">
        <h3>{_e(name)}.py</h3>
        <span class="pill is-{state}">{_e(catalog.STATES[state])}</span>
        {_run_state(run)}
      </div>
      <div class="qa">
        <p class="q"><span class="label">Asks</span>{_rich(study.question)}</p>
        <p class="v"><span class="label">Verdict</span>{_rich(study.verdict)}</p>
      </div>
{_run_block(run)}
    </article>"""


def _family(key: str, studies: list[tuple[str, catalog.Study]],
            runs: dict[str, summary.RunSummary]) -> str:
    fam = catalog.FAMILIES[key]
    cards = "\n".join(_card(n, s, runs[n]) for n, s in studies)
    return f"""  <section id="{_e(key)}">
    <div class="family-head">
      <div class="line">
        <h2>{_e(fam['index'])} {_e(fam['title'])}</h2>
        <span class="ask">{_e(fam['question'])}</span>
        <span class="count">{len(studies)} studies</span>
      </div>
      <p class="note">{_rich(fam['note'])}</p>
    </div>
    <div class="cards">
{cards}
    </div>
  </section>"""


# ── other sections ────────────────────────────────────────────────────────────
def _scoreboard(runs: dict[str, summary.RunSummary]) -> str:
    cells = [
        (str(len(catalog.STUDIES)), "studies", ""),
        *((str(n), catalog.STATES[state], f" is-{state}")
          for state, n in catalog.scoreboard().items()),
        (f"{sum(1 for r in runs.values() if r.ran)}/{len(runs)}", "reports on disk", ""),
    ]
    return ('  <div class="scoreboard">\n'
            + "\n".join(f'    <div class="score{cls}"><span class="n">{_e(n)}</span>'
                        f'<span class="k">{_e(k)}</span></div>' for n, k, cls in cells)
            + "\n  </div>")


def _log(entries: list[tuning.LogEntry], mtime: str) -> str:
    if not entries:
        return ""
    rows = "\n".join(
        f'      <div class="log-row">'
        f'<span class="when">{_e(e.date or "undated")}</span>'
        f'<p class="what">{_e(e.title)}</p>'
        + (f'<p class="gist">{_rich(e.gist)}</p>' if e.gist else "")
        + "</div>"
        for e in entries)
    return f"""  <section id="log">
    <div class="section-head">
      <h2>Latest from the tuning log</h2>
      <p>The newest sections of <code>config/backtest-tuning/current.md</code>, quoted —
        headings and first line only. The log is the source of truth; this is a pointer
        into it, not a second copy. Last edited {_e(mtime or "unknown")}.</p>
    </div>
    <div class="log">
{rows}
    </div>
  </section>"""


def _infra() -> str:
    rows = "\n".join(
        f'          <tr><td class="name">{_e(name)}</td><td><p>{_rich(desc)}</p></td></tr>'
        for name, desc in catalog.INFRA.items())
    return f"""  <section id="infra">
    <div class="section-head">
      <h2>Infrastructure</h2>
      <p>Not studies — these carry no verdict, and every verdict rests on them.</p>
    </div>
    <div class="table-view">
      <table>
        <thead><tr><th>File</th><th>Role</th></tr></thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
  </section>"""


def _reading() -> str:
    items = "\n".join(
        f"      <li><div><b>{_e(head)}</b><p>{_rich(body)}</p></div></li>"
        for head, body in catalog.READING)
    traps = "\n".join(
        f"      <li><b>{_e(head)}</b><p>{_rich(body)}</p></li>"
        for head, body in catalog.TRAPS)
    return f"""  <section id="reading">
    <div class="section-head">
      <h2>How to read any one report</h2>
    </div>
    <ol class="steps">
{items}
    </ol>
  </section>

  <section id="traps">
    <div class="section-head">
      <h2>Traps this log has actually fallen into</h2>
    </div>
    <ul class="traps">
{traps}
    </ul>
  </section>"""


# ── page ──────────────────────────────────────────────────────────────────────
def build(runs: dict[str, summary.RunSummary],
          log_entries: list[tuning.LogEntry],
          log_mtime: str,
          built_at: str | None = None) -> str:
    """The full page fragment."""
    built_at = built_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    css = (ASSETS / "page.css").read_text()
    families = catalog.by_family()
    counts = {k: len(v) for k, v in families.items()}
    sections = "\n\n".join(_family(k, v, runs) for k, v in families.items() if v)

    return f"""<title>{TITLE}</title>
<style>
{css}
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">scripts/backtest_study · research tier · never scheduled</p>
    <h1>Study map</h1>
    <p class="standfirst"><code>scripts/backtest/</code> <strong>prices</strong> the book.
      <code>scripts/backtest_study/</code> <strong>argues</strong> about it. Nothing here is
      imported by production, nothing runs on a schedule, and no study writes config — a study
      ends in a plain-text report that becomes an addendum in <code>current.md</code>, and a
      human decides whether anything ships.</p>
    <p class="thesis"><strong>The result of the whole programme, in one sentence:</strong>
      selection is not tunable from the columns we have; the money is in the exit rules and in
      position management. Every selection study returns a null. Two exit rules shipped.</p>
    <p class="built">
      <span>built {_e(built_at)}</span>
      <span>verdicts: hand-written, from current.md</span>
      <span>run blocks: quoted from backtests/study_output/</span>
    </p>
  </header>

{_scoreboard(runs)}

  <section id="shape">
    <div class="section-head">
      <h2>The shape of the whole thing</h2>
      <p>A play is picked, managed, wrapped and funded. The four families are those four
        decisions, and each one is a question somebody tried to answer with a study.</p>
    </div>
{_diagram(counts)}
  </section>

{_log(log_entries, log_mtime)}

{sections}

{_infra()}

{_reading()}

  <footer>
    Rendered by <code>python -m scripts.study_map</code>, and re-rendered automatically after
    every <code>python -m scripts.backtest_study run …</code>. The <em>verdict</em> lines are
    hand-written in <code>scripts/study_map/catalog.py</code> and change only when someone edits
    them; the <em>last run</em> blocks are quoted verbatim out of
    <code>backtests/study_output/</code> and are only as current as the last run. Nothing on this
    page states a conclusion a study did not print — an excerpt with no verdict block in it is
    labelled as the tail of the report, and a study nobody has run says so.
  </footer>
</div>
"""


def wrap_standalone(fragment: str) -> str:
    """Wrap the fragment in a minimal document for opening straight off disk."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"</head>\n<body>\n{fragment}\n</body>\n</html>\n"
    )
