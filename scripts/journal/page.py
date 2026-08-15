"""
Step 4b — render the day's journal as a self-contained HTML page.

PRODUCTION TIER. Same inputs as report.py (`list[PositionEvent]`, `BookRisk`,
`meta`) plus an output path, and it writes a standalone HTML document with
every CSS/JS rule inlined — no external request of any kind, so it opens
straight from `docs/` with no server. Theme-aware exactly as
`scripts/study_charts/assets/page.css` is: the CSS carries the tokens, this page
adds none of its own.

`scripts/study_charts/assets/kit.js` and `.../page.css` are read from disk and
inlined VERBATIM at build time — reused as assets, the way the brief asks, not
imported as a dependency (`scripts/study_charts` is research tier; this package
is production and must not depend on it at import time).

RECONCILE-OR-WRITE-NOTHING, the same discipline `scripts/study_charts/series.py`
applies to the study pages: `compute_figures()` derives the headline numbers
independently from `events`/`book` (summing `book.positions` itself rather than
trusting `BookRisk.net_delta_notional` verbatim, recomputing the breach count
from the caps rather than reading `book.breaches`'s length), `report.build()`
renders the markdown, and `extract_report_figures()` parses the SAME numbers
back out of that markdown text. Any disagreement raises `ReconcileError` and
writes nothing — a half-drawn or silently-diverging page is worse than no page.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import report
from .config import MATCH_CONFIDENCES, PositionEvent
from .risk import BookRisk

STUDY_CHARTS_ASSETS = Path(__file__).resolve().parents[1] / "study_charts" / "assets"

EM_DASH = report.EM_DASH


class ReconcileError(RuntimeError):
    """A page-computed figure disagrees with the markdown report it was built
    from. Raised instead of writing a page that would silently diverge."""


# --------------------------------------------------------------------------
# compute_figures() — the headline numbers, derived independently of report.py
# --------------------------------------------------------------------------
def _confidence_counts(events: list[PositionEvent]) -> dict[str, int]:
    return {c: sum(1 for e in events if e.match_confidence == c) for c in MATCH_CONFIDENCES}


def _breach_count(book: BookRisk) -> int:
    """Recomputed from caps + priced positions — NOT read off `book.breaches` —
    so a bug that let `assess()`'s own breach list drift from its own totals
    would show up as a mismatch instead of hiding behind a shared number.

    This is a DELIBERATE SECOND IMPLEMENTATION of the per-TICKER cap rule that
    `risk.py::assess` applies. It must NOT be refactored to call
    `risk.per_ticker_delta_notional` — sharing the aggregation is precisely what
    would stop a bug in it from ever surfacing here. If the cap rule changes in
    `risk.py::assess`, change it here too, BY HAND.
    """
    caps = book.caps
    if caps is None:
        return 0
    by_ticker: dict[str, float] = {}
    for p in book.positions:
        if p.delta_notional is None:
            continue
        by_ticker[p.ticker] = by_ticker.get(p.ticker, 0.0) + p.delta_notional
    n = sum(1 for total in by_ticker.values()
            if abs(total) > caps.per_position_dollars)
    net = sum(p.delta_notional for p in book.positions if p.delta_notional is not None)
    if abs(net) > caps.net_dollars:
        n += 1
    return n


def compute_figures(events: list[PositionEvent], book: BookRisk) -> dict:
    """Every figure the page's charts draw, computed straight from `events`/
    `book` — never by reading `report.build()`'s output back."""
    priced = book.positions
    net_dn = round(sum(p.delta_notional for p in priced if p.delta_notional is not None), 2)
    gross_dn = round(sum(abs(p.delta_notional) for p in priced
                         if p.delta_notional is not None), 2)
    figs: dict = {
        "net_dn": net_dn,
        "gross_dn": gross_dn,
        "unpriced_n": len(book.unpriced),
        "breach_n": _breach_count(book),
    }
    caps = book.caps
    if caps is not None:
        figs["per_pos_cap"] = round(caps.per_position_dollars, 2)
        figs["net_cap"] = round(caps.net_dollars, 2)
        figs["net_util_pct"] = (round(100 * abs(net_dn) / caps.net_dollars, 1)
                                if caps.net_dollars else None)
    for c, n in _confidence_counts(events).items():
        figs[f"conf_{c}"] = n
    return figs


# --------------------------------------------------------------------------
# extract_report_figures() — parse the SAME numbers back out of the markdown
# --------------------------------------------------------------------------
def _money_to_float(token: str | None) -> float | None:
    if token is None:
        return None
    token = token.strip()
    if token == EM_DASH or not token:
        return None
    return float(token.replace(",", "").replace("$", ""))


def extract_report_figures(text: str) -> dict:
    figs: dict = {}

    m = re.search(r"Net delta-notional:\s*([^\n|]+)", text)
    if m:
        figs["net_dn"] = _money_to_float(m.group(1))
    m = re.search(r"Gross delta-notional:\s*([^\n|]+)", text)
    if m:
        figs["gross_dn"] = _money_to_float(m.group(1))
    m = re.search(r"Positions excluded \(no delta\):\s*(\d+)", text)
    if m:
        figs["unpriced_n"] = int(m.group(1))
    m = re.search(r"\*\*(\d+) breach\(es\)\.\*\*", text)
    if m:
        figs["breach_n"] = int(m.group(1))
    m = re.search(r"Per-position cap:\s*([^(]+)\(", text)
    if m:
        figs["per_pos_cap"] = _money_to_float(m.group(1))
    m = re.search(r"Net cap:\s*([^(]+)\(", text)
    if m:
        figs["net_cap"] = _money_to_float(m.group(1))
    m = re.search(r"Net utilisation:\s*([\d.]+)%", text)
    if m:
        figs["net_util_pct"] = float(m.group(1))
    m = re.search(r"Confidence tally:\*\*\s*(.+?)\.", text)
    if m:
        for pair in m.group(1).split(","):
            key, _, val = pair.strip().partition("=")
            key = key.strip()
            if key and val.strip().lstrip("-").isdigit():
                figs[f"conf_{key}"] = int(val.strip())
    return figs


def reconcile(computed: dict, extracted: dict) -> list[str]:
    """Compare page-computed numbers against the report text's own. Returns a
    list of human-readable disagreements; empty means they agree."""
    problems: list[str] = []
    for key, want in computed.items():
        if want is None:
            continue
        got = extracted.get(key)
        if got is None:
            problems.append(f"{key}: absent from the report text (computed={want!r})")
            continue
        tol = 0.02 if isinstance(want, float) else 0
        if abs(got - want) > tol + 1e-9:
            problems.append(f"{key}: computed={want!r} report={got!r}")
    return problems


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _tiles(meta: dict, computed: dict) -> str:
    util = computed.get("net_util_pct")
    util_str = f"{util:.1f}%" if util is not None else EM_DASH
    rows = [
        ("NetLiq", report.money(meta.get("net_liquidation"))),
        ("Net Δ$", report.money(computed["net_dn"], signed=True)),
        ("Gross Δ$", report.money(computed["gross_dn"])),
        ("Utilisation", util_str),
        ("Breaches", str(computed["breach_n"])),
        ("Unpriced", str(computed["unpriced_n"])),
    ]
    return "".join(
        f'<div class="tile"><span class="label">{html.escape(label)}</span>'
        f'<span class="value">{html.escape(value)}</span></div>'
        for label, value in rows
    )


def _payload(events: list[PositionEvent], book: BookRisk, computed: dict) -> dict:
    return {
        "computed": computed,
        "positions": [
            {"ticker": p.ticker, "structure": p.structure, "dn": p.delta_notional}
            for p in book.positions
        ],
        "confidence": _confidence_counts(events),
    }


_PAGE_SCRIPT = """
(function () {
  "use strict";
  var K = window.__STUDY_KIT__;
  var DATA = window.__JOURNAL__;
  var dummy = document.createElement("div");

  var dnHost = document.getElementById("chart-dn");
  var dnRows = DATA.positions
    .filter(function (p) { return p.dn !== null && p.dn !== undefined; })
    .map(function (p) { return { label: p.ticker + " " + p.structure, value: p.dn }; });
  if (dnRows.length) {
    K.divergingBars(dnHost, dummy, {
      rows: dnRows,
      valueFmt: function (v) { return K.money(v); },
      valueName: "delta-notional",
      axisTitle: "delta-notional ($)"
    });
  } else {
    dnHost.textContent = "No priced positions.";
  }

  var utilHost = document.getElementById("chart-util");
  var c = DATA.computed;
  var utilRows = [
    { label: "Net |Δ$|", value: Math.abs(c.net_dn || 0) },
    { label: "Gross |Δ$|", value: c.gross_dn || 0 }
  ];
  var refLine = (c.net_cap !== undefined && c.net_cap !== null)
    ? { v: c.net_cap, label: "net cap" } : null;
  K.columnChart(utilHost, dummy, {
    rows: utilRows,
    valueFmt: function (v) { return K.money(v); },
    axisTitle: "delta-notional ($)",
    refLine: refLine
  });

  var confHost = document.getElementById("chart-conf");
  var confRows = Object.keys(DATA.confidence).map(function (k) {
    return { label: k, value: DATA.confidence[k] };
  });
  K.columnChart(confHost, dummy, {
    rows: confRows,
    valueFmt: function (v) { return String(v); },
    axisTitle: "count"
  });
})();
"""


def _render(events: list[PositionEvent], book: BookRisk, meta: dict, computed: dict) -> str:
    date = meta.get("date") or ""
    css = (STUDY_CHARTS_ASSETS / "page.css").read_text()
    kit_js = (STUDY_CHARTS_ASSETS / "kit.js").read_text().replace("</script", "<\\/script")

    payload = _payload(events, book, computed)
    data_json = json.dumps(payload, allow_nan=False).replace("</", "<\\/")

    title = f"Trade Journal — {date}" if date else "Trade Journal"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">trade journal &middot; production</p>
    <h1>{html.escape(title)}</h1>
    <p class="standfirst">Rendered from the day's reconciled fills and open-book
      risk mark. Every figure here is independently recomputed from the same
      records the markdown report reads and checked against that report's own
      text at build time; a disagreement stops the page from being written at
      all rather than shipping a chart that quietly disagrees with it.</p>
  </header>

  <section id="tiles">
    <div class="tiles">
{_tiles(meta, computed)}
    </div>
  </section>

  <section id="charts">
    <div class="grid-2">
      <figure class="panel">
        <div class="panel-head"><h3>Delta-notional by position</h3></div>
        <div id="chart-dn" class="chart"></div>
      </figure>
      <figure class="panel">
        <div class="panel-head"><h3>Cap utilisation</h3></div>
        <div id="chart-util" class="chart"></div>
      </figure>
    </div>
    <figure class="panel" style="margin-top:18px">
      <div class="panel-head"><h3>Match confidence</h3></div>
      <div id="chart-conf" class="chart"></div>
    </figure>
  </section>

  <footer>
    Rendered by <code>python -m scripts.journal.page</code>. Every figure is
    recomputed from the same events/book records the markdown report reads and
    reconciled against <code>journal/reports/{html.escape(date)}.md</code> at
    build time.
  </footer>
</div>
<script>
window.__JOURNAL__ = {data_json};
</script>
<script>
{kit_js}
</script>
<script>
{_PAGE_SCRIPT}
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# build()
# --------------------------------------------------------------------------
def build(events: list[PositionEvent], book: BookRisk, meta: dict, out_path: Path) -> Path:
    """Render, reconcile against the markdown report, and write both the dated
    file and `journal-latest.html` alongside it. Raises `ReconcileError` and
    writes nothing on any mismatch."""
    text = report.build(events, book, meta)
    computed = compute_figures(events, book)
    extracted = extract_report_figures(text)
    problems = reconcile(computed, extracted)
    if problems:
        raise ReconcileError(
            f"page/report mismatch — refusing to write {out_path}:\n"
            + "\n".join(f"  {p}" for p in problems)
        )

    page = _render(events, book, meta, computed)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")

    latest = out_path.parent / "journal-latest.html"
    latest.write_text(page, encoding="utf-8")

    return out_path
