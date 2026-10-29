"""Assemble the studies section of the project dashboard.

Emits an HTML *fragment* — body markup only, no `<title>` or `<style>` — that
`scripts/dashboard.py` drops into its "What have the studies found?" section
and styles with its own stylesheet. The study map used to be a page of its own
(`site/study-map.html`); it was folded into the dashboard on 2026-10-29 so the
operator reads results in one place.

Everything in the section comes from one of three places, and the markup keeps
them visually separated because they carry different authority:

    catalog.py  hand-written verdicts     — what the programme concluded
    summary.py  quoted report excerpts    — what the last run printed
    tuning.py   quoted current.md headings — what was last written up

The digest pages (`digest.py`) are still pages of their own, linked from the
section; `ASSETS`, `site_name` and `wrap_standalone` exist for them.
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

from . import catalog, summary, tuning

ROOT = Path(__file__).resolve().parents[2]

ASSETS = Path(__file__).resolve().parent / "assets"

# The dashboard's pill colours, by catalog state.
STATE_CLS = {"shipped": "ship", "null": "null", "open": "open", "reference": "pos"}


def site_name(study: str) -> str:
    """site/ filename for a study's rendered digest page (hyphenated, matching
    the existing account-sim-*.html naming)."""
    return study.replace("_", "-") + "-digest.html"


_KIND_NOTE = {
    "verdict": "quoted from the report's own VERDICT block",
    "refusal": "BY DESIGN — the study declared this exit code as a pre-registered "
               "gate or guard declining to answer, not a broken run",
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


# ── study rows ────────────────────────────────────────────────────────────────
def _run_state(run: summary.RunSummary) -> str:
    if not run.ran:
        if run.retired:
            return '<span class="run-state"><span class="retired-label">retired</span></span>'
        return '<span class="run-state">never run</span>'
    when = run.run_at.split()[0] if run.run_at else ""
    if run.ok:
        mark = '<span class="good">ok</span>'
    elif run.refused:
        # A designed refusal is not "bad" — it is the study correctly
        # declining to answer. Its own visual class, not .bad's warning tone.
        mark = f'<span class="refused">{_e(run.status)}</span>'
    else:
        mark = f'<span class="bad">{_e(run.status)}</span>'
    return f'<span class="run-state">last run {_e(when)} · {mark}</span>'


def _record_path(name: str) -> str | None:
    """Repo-relative path of `name`'s per-era record, or None if it has none yet.

    Resolved through `scripts.study_results.record_path` rather than rebuilt
    from a family string here — that module derives the family from the study's
    real module directory, and a second derivation in the renderer is exactly
    how the map would start pointing at files that do not exist. Imported
    lazily for the same reason the catalog import below is: keeping module
    import side-effect-free.
    """
    try:
        from scripts.study_results import record_path
    except ImportError:
        return None
    path = record_path(name)
    return str(path.relative_to(ROOT)) if path.exists() else None


def _run_block(run: summary.RunSummary) -> str:
    if not run.ran:
        return ('      <p class="caveat">No report on disk. Run '
                f'<code>python -m scripts.backtest_study run {_e(run.name)}</code> '
                'and this block fills in.</p>')

    meta = [f"<span><b>run</b> {_e(run.run_at)}</span>"]
    # Always shown, "?" included: which population a number came from is not an
    # optional detail here. A report predating the era line (2026-08-15) cannot
    # say, and the map must show that it cannot rather than omit the field and
    # read as though the question never arose.
    meta.append(f"<span><b>era</b> {_e(run.era.split()[0] if run.era else '?')}</span>")
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
    if run.refused:
        caveats.append('<p class="caveat">This run exited non-zero BY DESIGN — '
                       f'{_e(run.name)} exited {run.exit_code} as a designed refusal '
                       '(a pre-registered gate not met, an export era that is not the one '
                       'asked for, or an era too thin to conclude from). Correct behaviour, '
                       'not a broken run — see <code>scripts/backtest_study/run.py</code>\'s '
                       '"Designed refusals" note.</p>')
        # Without this, a refused row is a dead end: it says the current era
        # cannot answer and gives no route to the era that could. The record is
        # the ONLY place a past era's numbers survive — the reports themselves
        # are gitignored and are overwritten by exactly this kind of re-run.
        rec = _record_path(run.name)
        if rec is not None:
            caveats.append('<p class="caveat">The last era that could answer is recorded in '
                           f'<code>{_e(rec)}</code> — reports are gitignored scratch, so that '
                           'file is where a past era\'s numbers survive.</p>')
    elif not run.ok:
        caveats.append('<p class="caveat is-warning">This run exited non-zero. For most '
                       'studies that is a calibration or input gate refusing to print '
                       'numbers it cannot vouch for — read it as the gate working, not '
                       'as a result.</p>')
    if run.dirty:
        caveats.append('<p class="caveat">Working tree was dirty at run time, so the git '
                       'sha does not fully identify the code that produced this.</p>')
    if run.digest_title:
        caveats.append(
            '<p class="caveat">Plain-language digest: '
            f'<a href="{_e(site_name(run.name))}">{_e(run.digest_title)}</a> '
            f'(rendered from <code>{_e(run.digest_path.name)}</code>).</p>')

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
        <div class="meta">{''.join(meta)}</div>
        <pre class="excerpt">{excerpt}</pre>
        <div class="links">{''.join(links)}</div>
{chr(10).join(caveats)}
      </details>"""


def _study(name: str, study: catalog.Study, run: summary.RunSummary) -> str:
    state = study.state
    row_cls = f"study is-{state}" + (" is-retired" if study.retired else "")
    retired_pill = ('<span class="pill is-retired">retired</span>'
                    if study.retired else "")
    retired_note = (f'      <p class="caveat is-warning">{_rich(study.retired)}</p>'
                    if study.retired else "")
    return f"""  <li class="{row_cls}" data-study="{_e(name)}"><details>
    <summary><span class="pill {STATE_CLS[state]}">{_e(catalog.STATES[state])}</span>{retired_pill}\
<span class="sname">{_e(name)}</span>{_run_state(run)}<span class="sq">{_rich(study.question)}</span></summary>
    <div class="sbody">
      <p><strong>Verdict.</strong> {_rich(study.verdict)}</p>
{retired_note}
{_run_block(run)}
    </div>
  </details></li>"""


def _family(key: str, studies: list[tuple[str, catalog.Study]],
            runs: dict[str, summary.RunSummary]) -> str:
    fam = catalog.FAMILIES[key]
    rows = "\n".join(_study(n, s, runs[n]) for n, s in studies)
    return f"""<div class="fam" id="studies-{_e(key)}">
<h3>{_e(fam['index'])} {_e(fam['title'])} <span class="sub">— {_e(fam['question'])} \
· {len(studies)} studies</span></h3>
<p class="sub">{_rich(fam['note'])}</p>
<ul class="studies">
{rows}
</ul>
</div>"""


# ── reading queue ─────────────────────────────────────────────────────────────
STUDY_OUTPUT = ROOT / "backtests" / "study_output"

# The review artifacts a study_review pass leaves behind, in reading order.
_REVIEW_FILES = (
    ("digest", "{s}-digest-latest.md"),
    ("validator", "{s}-review-validator-latest.md"),
    ("analyst A", "{s}-review-analyst-a-latest.md"),
    ("analyst B", "{s}-review-analyst-b-latest.md"),
)


def _review_artifacts(study: str) -> list[tuple[str, str, float]]:
    """(label, href relative to site/, mtime) for each review file on disk."""
    out = []
    for label, pat in _REVIEW_FILES:
        p = STUDY_OUTPUT / pat.format(s=study)
        if p.is_file():
            href = site_name(study) if label == "digest" else f"../backtests/study_output/{p.name}"
            out.append((label, href, p.stat().st_mtime))
    return out


def _art_links(arts: list[tuple[str, str, float]]) -> str:
    return " · ".join(f'<a href="{_e(href)}">{_e(label)}</a>' for label, href, _ in arts)


def flagged() -> list[str]:
    """Studies whose hand-written `attention` flag asks the operator to read them now."""
    return [n for n, s in catalog.STUDIES.items() if s.attention]


def _queue() -> str:
    """The operator's reading queue.

    The split is two sources with different authority, same as the rest of the
    section: the READ-FIRST flags are hand-written (`catalog.Study.attention` —
    set during the recording pass that created the need, cleared once the
    operator has read/decided); the artifact lists and their dates are read
    mechanically off `backtests/study_output/`. Nothing here summarises a
    review — the flag says why to open the artifacts, never what they found.
    """
    first, fyi = [], []
    for name, study in catalog.STUDIES.items():
        arts = _review_artifacts(name)
        if study.attention:
            first.append((name, study, arts))
        elif arts:
            fyi.append((name, study, arts))
    newest = lambda arts: max((m for _, _, m in arts), default=0.0)  # noqa: E731
    day = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d")  # noqa: E731

    first_html = "\n".join(
        f"""  <li><div><span class="sname">{_e(n)}</span> \
<span class="sub">{_e(day(newest(a)) if a else "no review files yet")}</span>
    <p class="why">{_rich(s.attention)}</p>
    <p class="sub">{_art_links(a) or "review files not on disk — run study_review"}</p></div></li>"""
        for n, s, a in sorted(first, key=lambda t: -newest(t[2])))
    first_block = (f'<ul class="rows queue">\n{first_html}\n</ul>' if first_html
                   else "<p>Nothing is flagged for reading.</p>")
    fyi_html = "\n".join(
        f'  <li><span class="sub mono">{_e(day(newest(a)))}</span> '
        f'<span class="sname">{_e(n)}</span> — {_art_links(a)}</li>'
        for n, _, a in sorted(fyi, key=lambda t: -newest(t[2])))
    fyi_block = (f"""<details><summary>Reviewed, nothing pending ({len(fyi)})</summary>
<ul class="plain">
{fyi_html}
</ul></details>""" if fyi else "")

    return f"""<h3 id="studies-queue">Read first</h3>
<p class="sub">Flags hand-written in <code>catalog.py</code> when a study's result changed or
a decision is pending. Each says why to open that study's review files, never what they
found. A flag is cleared once you have read it.</p>
{first_block}
{fyi_block}"""


# ── other blocks ──────────────────────────────────────────────────────────────
def _log(entries: list[tuning.LogEntry], mtime: str) -> str:
    if not entries:
        return ""
    rows = "\n".join(
        f'  <li><span class="sub mono">{_e(e.date or "undated")}</span> <strong>{_e(e.title)}</strong>'
        + (f'<br><span class="sub">{_rich(e.gist)}</span>' if e.gist else "")
        + "</li>"
        for e in entries)
    return f"""<details id="studies-log"><summary>Latest write-ups in research/current.md \
({len(entries)})</summary>
<p class="sub">The newest sections, quoted: heading and first line only. The log is the
source of truth; this only points into it. Last edited {_e(mtime or "unknown")}.</p>
<ul class="plain">
{rows}
</ul></details>"""


def _about() -> str:
    steps = "\n".join(f"  <li><strong>{_e(head)}.</strong> {_rich(body)}</li>"
                      for head, body in catalog.READING)
    traps = "\n".join(f"  <li><strong>{_e(head)}.</strong> {_rich(body)}</li>"
                      for head, body in catalog.TRAPS)
    infra = "\n".join(f'  <tr><td class="name">{_e(name)}</td><td>{_rich(desc)}</td></tr>'
                      for name, desc in catalog.INFRA.items())
    return f"""<details id="studies-about"><summary>How to read a study report</summary>
<ol class="plain">
{steps}
</ol>
<h4>Traps this research has fallen into</h4>
<ul class="plain">
{traps}
</ul>
<h4>The shared code every study runs on</h4>
<p class="sub">Not studies: these carry no verdict, and every verdict rests on them.</p>
<div class="tablewrap"><table class="infra">
{infra}
</table></div></details>"""


# ── section ───────────────────────────────────────────────────────────────────
def build(runs: dict[str, summary.RunSummary],
          log_entries: list[tuning.LogEntry],
          log_mtime: str) -> str:
    """The studies section body, below the dashboard's own heading and tally."""
    families = catalog.by_family()
    jump = " · ".join(
        ['<a href="#studies-queue">Read first</a>']
        + [f'<a href="#studies-{_e(k)}">{_e(catalog.FAMILIES[k]["index"])} '
           f'{_e(catalog.FAMILIES[k]["title"])}</a>' for k, v in families.items() if v]
        + ['<a href="#studies-about">How to read a report</a>'])
    sections = "\n".join(_family(k, v, runs) for k, v in families.items() if v)
    on_disk = sum(1 for r in runs.values() if r.ran)
    return f"""<p class="thesis"><strong>The whole programme in one sentence:</strong>
selection is not tunable from the columns we have; the money is in the exit rules and in
position management. Every selection study returns a null. Two exit rules shipped.</p>
<p class="sub prov">Verdicts are hand-written in <code>scripts/study_map/catalog.py</code>
and change only when someone edits them. Run blocks are quoted from
<code>backtests/study_output/</code> and are only as fresh as the last run
({on_disk} of {len(runs)} studies have a report on disk). Click a study to open it.</p>
<p class="sub jump">{jump}</p>
{_queue()}
{_log(log_entries, log_mtime)}
{sections}
{_about()}"""


def wrap_standalone(fragment: str) -> str:
    """Wrap a digest fragment in a minimal document for opening straight off disk."""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"</head>\n<body>\n{fragment}\n</body>\n</html>\n"
    )
