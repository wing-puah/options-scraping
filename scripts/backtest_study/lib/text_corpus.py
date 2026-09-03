"""Text corpus: the analysis model's PROSE re-attached to every priced row.

RESEARCH TIER. Never imported by `scripts/journal/`, `scripts/live_loop/` or
`scripts/analysis_pipeline/`; nothing here decides a trade. It is a loader plus
a set of deterministic, regex-only text features, built so a later study can ask
whether anything in what the model *wrote* predicts what the row *did* — a
question no study in this repo has ever been able to pose, because every study
so far reads only the numeric columns.

--- The join --------------------------------------------------------------
Reused, never re-implemented: `book.norm_play` and `book._build_analysis_lookup`
are imported by identity (a test pins that), so the text a row gets here is the
text `load_book` already joined its `price_vector` / `days_to_earnings` /
`post13c` flag from. Key: ``f"{date}|{ticker}|{norm_play(play)}"``. A row whose
key does NOT resolve falls back to the results/proxy CSV's own `play` / `regime`
/ `horizon` columns (both exports carry them) with ``joined=False`` — the row
keeps its text, but `signal` / `trigger` / `invalidation` are unavailable,
because only AnalysisClaude has those columns. Count them before cutting on any
signal-derived feature: an unjoined row is not a row with no signal.

--- "Unpriced" --------------------------------------------------------------
The backtest book is a SUBSET of what the model proposed, and the missing part
is not missing at random — that is the whole reason this loader returns it
instead of dropping it. `load_corpus` returns an `unpriced` list alongside the
priced rows, one entry per analysis row that never became a record, tagged with
`reason`:

  market_row       the MARKET row (no play — it carries the market read)
  no_play          a play row whose `play` cell is blank
  bs_only          priced ONLY as a `bs_options_hist` proxy row, which
                   `include_bs=False` excludes as evidence (see book.py)
  not_backtested   no results/proxy row carries that key at all — the play was
                   never even attempted (unparseable structure, no chain, ...)
  excluded_by_book a results/proxy row EXISTS but `load_book` dropped it:
                   the proxy calibration gate, a Trade construction failure, or
                   a missing price path

These are computed by reading the era's results/proxy CSVs directly with
`csv.DictReader` and the same key function — NOT by re-running `load_book`
internals, which would couple this module to that loader's private ordering.

--- Features ----------------------------------------------------------------
`text_features` emits ONLY the list below, and the list is short on purpose. A
text feature earns a slot only if it has no numeric counterpart that a study has
already tested and found null; otherwise a "text edge" is a numeric column
wearing a wig.

DELIBERATELY EXCLUDED, with the column each one duplicates:
  - tag counts per class ([FLOW]/[VEGA]/[PRICE]/[CAT] frequencies) — a
    rescaling of `score_total` and its components, all tested null.
  - earnings / catalyst mention — `days_to_earnings` and `score_catalyst` are
    the structured, deterministic form of the same fact.
  - hedge / protection language — the play cell's own `[HEDGE]` intent bracket
    is that classification, already structured and already parsed here as
    `parsed["intent"]`.

`evidence_n` is emitted but is a REDUNDANCY CONTROL, not a candidate: it proxies
the evidence-count factor behind `score_flow` / `score_total`. It is here so a
study can show a text effect survives conditioning on it — never as a headline.

--- Network -----------------------------------------------------------------
Everything above is local-CSV only. `citation_check` is the sole exception: it
re-fetches a date's assembled analysis INPUT markdown through
`scripts/analysis_pipeline/fetch.py::fetch_data` to test whether the numbers the
model cited in its `[FLOW]` evidence were actually on the tape it was shown. The
import is lazy so this module loads without Drive credentials, and the fetch is
pointed at a cache dir of its own so the production `audit/` rollups are never
overwritten.

Run as a module for diagnostics (local CSVs only unless --citations):
    python -m scripts.backtest_study.lib.text_corpus
    python -m scripts.backtest_study.lib.text_corpus --era v3
    python -m scripts.backtest_study.lib.text_corpus --citations --limit 3
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.book import (  # noqa: E402
    load_book,
    norm_play,
    # Private on purpose in book.py, imported here on purpose: a second copy of
    # the AnalysisClaude lookup would let the text a row carries disagree with
    # the numbers load_book joined onto the same row. Pinned by identity in
    # tests/test_text_corpus.py.
    _build_analysis_lookup,
)

# Where citation_check parks the re-fetched analysis input markdown. NOT
# `audit/` — that directory holds the production rollups the live pipeline
# wrote, and fetch_data would overwrite them.
CITATION_CACHE = ROOT / "backtests" / "analysis_inputs_cache"


# ── play-cell parsing ───────────────────────────────────────────────────────
#
# The exact inverse of `scripts/analysis_pipeline/core.py::analysis_to_rows`,
# which assembles the cell as up to three lines:
#     [FLOW_INTENT]
#     pattern | structure | thesis      (" | ".join of the non-empty three)
#     Alt: alternative_interpretation
# Every part is optional there, so every part is optional here.

_INTENT_RE = re.compile(r"^\[([^\]]{1,40})\]$")
_ALT_RE = re.compile(r"^Alt:\s*(.*)$", re.IGNORECASE)
# A pattern code as the model emits it: MR / TF / TF-S / PU / GE / VC / DP.
_PATTERN_CODE_RE = re.compile(r"^[A-Z]{1,4}(?:-[A-Z]{1,3})?$")
_STRUCTURE_WORDS = (
    "spread", "call", "put", "straddle", "strangle", "condor", "butterfly",
    "calendar", "diagonal", "collar", "stock", "synthetic", "ratio",
)

_EMPTY_PLAY = dict(intent=None, pattern=None, structure_text=None,
                   thesis=None, alt=None)


def parse_play(play: str) -> dict:
    """Split an assembled play cell back into its parts.

    Returns ``{intent, pattern, structure_text, thesis, alt}``, each `None` when
    absent. Never raises: a v1/v2-era cell, a hand-edited one, or a blank comes
    back as all-None rather than an exception, because a parser that throws on
    old formatting silently truncates the corpus to the current era.

    Degradation rules for a headline with fewer than the writer's three parts
    (stated so a reader knows what a `None` means):
      3+ parts -> pattern, structure, thesis (extra parts rejoined into thesis)
      2 parts  -> pattern+structure when the first looks like a pattern CODE
                  (`TF`, `MR`, `TF-S`), else structure+thesis
      1 part   -> structure when it contains a structure word, else thesis
    """
    out = dict(_EMPTY_PLAY)
    if not isinstance(play, str) or not play.strip():
        return out

    lines = [ln.strip() for ln in play.splitlines() if ln.strip()]
    if not lines:
        return out

    m = _INTENT_RE.match(lines[0])
    if m:
        out["intent"] = m.group(1).strip().upper()
        lines = lines[1:]

    # The Alt line and anything after it (a wrapped alternative) is the alt.
    head_lines, alt_lines = [], None
    for ln in lines:
        if alt_lines is not None:
            alt_lines.append(ln)
            continue
        am = _ALT_RE.match(ln)
        if am:
            alt_lines = [am.group(1).strip()]
        else:
            head_lines.append(ln)
    if alt_lines is not None:
        alt = " ".join(x for x in alt_lines if x).strip()
        out["alt"] = alt or None

    headline = " ".join(head_lines).strip()
    if not headline:
        return out

    parts = [p.strip() for p in headline.split(" | ")]
    parts = [p for p in parts if p]
    if len(parts) >= 3:
        out["pattern"], out["structure_text"] = parts[0], parts[1]
        out["thesis"] = " | ".join(parts[2:])
    elif len(parts) == 2:
        if _PATTERN_CODE_RE.match(parts[0]):
            out["pattern"], out["structure_text"] = parts[0], parts[1]
        else:
            out["structure_text"], out["thesis"] = parts[0], parts[1]
    elif len(parts) == 1:
        low = parts[0].lower()
        if any(w in low for w in _STRUCTURE_WORDS) and len(parts[0]) < 120:
            out["structure_text"] = parts[0]
        else:
            out["thesis"] = parts[0]
    return out


# ── signal-cell parsing ─────────────────────────────────────────────────────

_SIGNAL_TAG_RE = re.compile(r"^\[([^\]]{1,40})\]\s*(.*)$", re.DOTALL)
# `_multiline_signal` splits the model's " | "-joined stream onto its own lines,
# so a pipe should not survive into the cell. Split on one anyway, but ONLY
# where it introduces a `[TAG]` — a bare pipe inside a sentence is prose.
_PIPE_SPLIT_RE = re.compile(r"\s\|\s(?=\[)")


def split_signal(signal: str) -> list[tuple[str | None, str]]:
    """`[(tag | None, text)]` for a signal cell.

    Splits on newlines (what `_multiline_signal` writes) and, defensively, on a
    ` | ` that introduces a bracketed tag. An untagged line is a WRAPPED
    continuation of the item above it — the corpus's untagged lines are all
    `counter: ...` / `red flag named: ...` riders on the preceding `[FLOW]`
    item — so it is appended to that item rather than counted as a new one;
    an untagged line with nothing above it becomes its own `(None, text)` item.
    """
    if not isinstance(signal, str) or not signal.strip():
        return []
    items: list[tuple[str | None, str]] = []
    for raw_line in signal.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for chunk in _PIPE_SPLIT_RE.split(line):
            chunk = chunk.strip()
            if not chunk:
                continue
            m = _SIGNAL_TAG_RE.match(chunk)
            if m:
                items.append((m.group(1).strip().upper(), m.group(2).strip()))
            elif items:
                tag, text = items[-1]
                items[-1] = (tag, f"{text} {chunk}".strip())
            else:
                items.append((None, chunk))
    return items


# ── numbers ─────────────────────────────────────────────────────────────────
#
# The scrubs below are the whole trick: every "which numbers are price levels"
# question in this module is answered by DELETING the spans that are provably
# something else, then reading what is left. Adding a class of non-price number
# means adding a scrub here, not a special case at each call site.

_SCRUBS = (
    # ISO dates, then month-name dates ("Nov 25", "~Nov 25, 2026", "15 Mar").
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
               r"[a-z]*\.?\s*\d{1,2}(?:\s*,?\s*(?:19|20)\d{2})?"),
    re.compile(r"(?i)\b\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"),
    # DTE / day tokens, including ranges: "120–199 DTE", "113-DTE", "10d", "56 days".
    re.compile(r"(?i)~?\d[\d.,]*(?:\s*[-–—]\s*\d[\d.,]*)?\s*-?\s*(?:DTE|days?\b|d\b)"),
    # Percentages.
    re.compile(r"\d[\d.,]*\s*%"),
    # $-magnitudes: premium, not a level.
    re.compile(r"(?i)\$\s*\d[\d.,]*\s*[MBK]\b"),
    # Contract / lot counts.
    re.compile(r"(?i)\b\d[\d,]*\s*(?:x\b|-?lots?\b|-?contracts?\b)"),
    re.compile(r"(?i)\b\d[\d,]*x\b"),
)

# The trailing lookahead rejects a number glued to a word ("10d", "4.68M") and a
# truncated decimal, but NOT a sentence-ending period — "close below 290." is a
# level, and an earlier version of this regex silently dropped every level that
# happened to end a sentence.
_NUMBER_RE = re.compile(r"(?<![\w.])\$?(\d{1,6}(?:\.\d{1,3})?)(?![\w%]|\.\d)")
_SLASH_RUN_RE = re.compile(r"(?<![\w.])(\d{1,6}(?:\.\d{1,3})?(?:/\d{1,6}(?:\.\d{1,3})?)+)(?![\w]|\.\d)")
_BARE_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")

# Plausibility band for "this number is a price level". Excludes ratios (C/P
# 0.03, IVskew), and counts above six figures. A genuine >100k strike does not
# exist in this book; if one ever does, widen it here and say so in a study.
_LEVEL_MIN, _LEVEL_MAX = 1.0, 100_000.0


def _scrub(text: str) -> str:
    """Blank out every span that is provably NOT a price level."""
    out = text
    for rx in _SCRUBS:
        out = rx.sub(lambda m: " " * len(m.group(0)), out)
    return out


def _plausible_level(tok: str, allow_year: bool = False) -> float | None:
    """A scrubbed number token as a price level, or None.

    `allow_year` suppresses the bare-year veto. Pass it wherever the CONTEXT
    already proves the number is a level — inside a `1600/1900` slash run, or
    behind a `$` — because a four-digit strike is real and "out to 2027" is not.
    """
    if "," in tok:
        return None                      # thousands separators read as counts
    if not allow_year and _BARE_YEAR_RE.match(tok):
        return None                      # "out to 2027" is a year, not a strike
    try:
        v = float(tok)
    except ValueError:
        return None
    return v if _LEVEL_MIN <= v <= _LEVEL_MAX else None


def parse_strikes(structure_text: str | None) -> list[float]:
    """Strikes out of a structure phrase — "bull put spread 145/130" -> [145, 130].

    Slash runs win outright: the writer's structure phrases put the strikes and
    only the strikes on either side of a `/`, so "bull call spread 400/430 Mar 15
    (46 DTE)" yields [400, 430] and not the expiry or the DTE. With no slash run
    (a single-leg structure), falls back to the plausible levels left after the
    scrubs. Returns [] rather than raising on anything unrecognisable.
    """
    if not isinstance(structure_text, str) or not structure_text.strip():
        return []
    scrubbed = _scrub(structure_text)
    runs = _SLASH_RUN_RE.findall(scrubbed)
    if runs:
        out: list[float] = []
        for run in runs:
            for tok in run.split("/"):
                v = _plausible_level(tok, allow_year=True)
                if v is not None:
                    out.append(v)
        if out:
            return out
    return parse_price_levels(structure_text)


def parse_price_levels(text: str | None) -> list[float]:
    """Numbers in `text` that read as PRICE LEVELS, in order of appearance.

    Not DTEs, not percentages, not calendar dates, not `$4.68M`-style premiums,
    not contract counts, not bare years, not sub-$1 ratios. A `$`-prefixed
    number is kept even when it looks like a year, because `$2025` in this
    corpus is a strike.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    scrubbed = _scrub(text)
    out: list[float] = []
    for m in _NUMBER_RE.finditer(scrubbed):
        dollar = m.group(0).startswith("$")
        v = _plausible_level(m.group(1), allow_year=dollar)
        if v is not None:
            out.append(v)
    return out


# ── features ────────────────────────────────────────────────────────────────

# Why each feature is NEW — i.e. what makes it something no already-tested
# numeric column encodes. Printed by the CLI so the justification travels with
# the coverage table rather than living only in a docstring.
FEATURE_NOTES: dict[str, str] = {
    "invalidation_type":
        "NEW: what KIND of evidence would falsify the play. No column records "
        "the falsifier's class — the book stores the outcome, never the test.",
    "invalidation_level":
        "NEW: the price the model said it would be wrong at. `delta`/`dte` "
        "describe the structure; nothing stores the model's own stop.",
    "invalidation_inside_strikes":
        "NEW: whether the stated stop sits INSIDE the structure's own strikes — "
        "a coherence check between the prose and the trade that no numeric "
        "column can express, since neither side alone is wrong.",
    "trigger_conditional":
        "NEW: whether entry was gated on a condition ('no entry before the "
        "print'). The backtest enters on the signal date unconditionally, so "
        "this is entirely un-modelled by any stored field.",
    "trigger_level":
        "NEW: the price the trigger names, which the backtest ignored — the "
        "gap between it and the entry is unrecorded anywhere else.",
    "numeric_specificity":
        "NEW: how concretely the write-up is stated. `score_*` grades evidence "
        "QUALITY on a rubric; this counts committed numbers, which the rubric "
        "does not read.",
    "thesis_len":
        "NEW: length of the case made. No column carries any measure of the "
        "prose the model produced.",
    "alt_len":
        "NEW: length of the self-argued counter-case, the model's own stated "
        "doubt. Unrepresented in every numeric column.",
    "alt_ratio":
        "NEW: doubt relative to conviction — scale-free, so it separates 'wrote "
        "more about everything' from 'hedged this one'.",
    "evidence_n":
        "REDUNDANCY CONTROL, never a candidate: a count of tagged evidence "
        "items proxies the evidence-count factor inside score_flow/score_total, "
        "already tested null. Condition on it; do not headline it.",
}

FEATURE_KEYS = tuple(FEATURE_NOTES)

_PRICE_WORDS = re.compile(
    r"(?i)\b(clos(?:e|es|ing)|below|above|break(?:s|down|ing)?|breaks?\s+down|"
    r"strike|level|support|resistance|holds?|loses?|retakes?|trades?\s+(?:below|above)|"
    r"spot|price|daily\s+close|session\s+low|session\s+high)\b")
_FLOW_WORDS = re.compile(
    r"(?i)\b(puts?|calls?|c/p|put/call|call/put|demand|flow|open\s+interest|\bOI\b|"
    r"revers(?:e|es|ing|al)|sweep|premium|selltoopen|buytoopen|toopen|"
    r"bid-side|ask-side|skew|positioning)\b")
_MACRO_WORDS = re.compile(
    r"(?i)\b(FOMC|CPI|PPI|PCE|NFP|payrolls|yields?|10-?year|VIX|dollar|DXY|"
    r"rates?|fed\b|federal\s+reserve|SPY|QQQ|SPX|NDX|IWM|index\s+complex|"
    r"macro|treasur(?:y|ies))\b")

_TRIGGER_CONDITIONAL = re.compile(
    r"(?i)(no\s+entry\s+(?:before|until)|only\s+if|only\s+on|"
    r"holds?\s+\d[\d.,]*\s+on\s+a\s+closing\s+basis|"
    r"\buntil\b|wait\s+for|\bclears?\b|provided\s+that|\bunless\b|"
    r"do\s+not\s+enter)")

# numeric_specificity counters — deliberately the RAW spans (before the level
# scrubs), because a DTE or a percentage is a committed number too.
_SPEC_DOLLARS = re.compile(r"(?i)\$\s*\d[\d.,]*\s*[MBK]?")
_SPEC_DTE = re.compile(r"(?i)~?\d[\d.,]*(?:\s*[-–—]\s*\d[\d.,]*)?\s*-?\s*(?:DTE|days?\b|d\b)")
_SPEC_PCT = re.compile(r"\d[\d.,]*\s*%")


def _words(s: str | None) -> int:
    return len(s.split()) if isinstance(s, str) and s.strip() else 0


def _classify_invalidation(text: str | None) -> str:
    """price / flow / macro / mixed / none for an invalidation clause."""
    if not isinstance(text, str) or not text.strip():
        return "none"
    hits = set()
    if _PRICE_WORDS.search(text):
        hits.add("price")
    if _FLOW_WORDS.search(text):
        hits.add("flow")
    if _MACRO_WORDS.search(text):
        hits.add("macro")
    if not hits:
        return "none"
    if len(hits) > 1:
        return "mixed"
    return hits.pop()


def text_features(text: dict, structure_text: str | None = None) -> dict:
    """Deterministic, regex-only features over one row's text.

    `text` is the corpus row's text dict (`regime`, `signal`, `play`, `trigger`,
    `invalidation`, ...). `structure_text` overrides the structure phrase parsed
    out of `play` — pass the row's own when you have a better one. Every value
    is `None` when the input needed to compute it is absent; nothing here
    guesses, and nothing raises.

    The feature list and the rationale for each entry (including the three
    features deliberately NOT here) are in `FEATURE_NOTES` and the module
    docstring. Do not extend it without a reason of the same shape: a text
    feature whose numeric counterpart has already been tested is not evidence,
    it is the same test with a longer name.
    """
    text = text or {}
    parsed = parse_play(text.get("play"))
    if structure_text is None:
        structure_text = parsed.get("structure_text")

    inval = text.get("invalidation") or ""
    trig = text.get("trigger") or ""
    sig = text.get("signal") or ""
    thesis = parsed.get("thesis") or ""
    alt = parsed.get("alt") or ""

    inval_levels = parse_price_levels(inval)
    inval_level = inval_levels[0] if inval_levels else None
    trig_levels = parse_price_levels(trig)
    trig_level = trig_levels[0] if trig_levels else None

    strikes = parse_strikes(structure_text)
    if inval_level is None or len(strikes) < 2:
        inside = None
    else:
        inside = min(strikes) < inval_level < max(strikes)

    spec_blob = "\n".join(x for x in (thesis, sig, trig, inval) if x)
    numeric_specificity = (
        len(_SPEC_DOLLARS.findall(spec_blob))
        + len(_SPEC_DTE.findall(spec_blob))
        + len(_SPEC_PCT.findall(spec_blob))
        + len(parse_price_levels(spec_blob))
    )

    thesis_len = _words(thesis)
    alt_len = _words(alt)

    return {
        "invalidation_type": _classify_invalidation(inval),
        "invalidation_level": inval_level,
        "invalidation_inside_strikes": inside,
        "trigger_conditional": bool(_TRIGGER_CONDITIONAL.search(trig)) if trig else False,
        "trigger_level": trig_level,
        "numeric_specificity": numeric_specificity,
        "thesis_len": thesis_len,
        "alt_len": alt_len,
        "alt_ratio": (alt_len / thesis_len) if thesis_len else None,
        "evidence_n": len(split_signal(sig)),
    }


# ── corpus assembly ─────────────────────────────────────────────────────────

_TEXT_FIELDS = ("regime", "signal", "play", "trigger", "invalidation",
                "horizon", "created_datetime")


def _cell(src, field: str) -> str:
    """A dict/pandas-Series cell as a stripped string ("" for None/NaN)."""
    if src is None:
        return ""
    try:
        v = src.get(field)
    except AttributeError:
        return ""
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _join_key(date: str, ticker: str, play: str) -> str:
    """The ONE key shape, shared with book._build_analysis_lookup."""
    return f"{str(date).strip()[:10]}|{str(ticker).strip()}|{norm_play(play)}"


def _text_for_record(rec: dict, ac_lookup: dict) -> dict:
    row = rec["t"].row
    jk = _join_key(rec["date"], rec["ticker"], row.get("play", ""))
    ac_row = ac_lookup.get(jk)
    if ac_row is not None:
        out = {f: _cell(ac_row, f) for f in _TEXT_FIELDS}
        out["joined"] = True
        return out
    # Fallback: BacktestResults/BacktestProxy carry play/regime/horizon but
    # never signal/trigger/invalidation. Blank there means "column absent",
    # NOT "the model said nothing" — see the module docstring.
    out = {f: "" for f in _TEXT_FIELDS}
    out["play"] = _cell(row, "play")
    out["regime"] = _cell(row, "regime")
    out["horizon"] = _cell(row, "horizon")
    out["created_datetime"] = _cell(row, "created_datetime")
    out["joined"] = False
    return out


def _csv_keys(path: Path) -> tuple[set[str], dict[str, set[str]]]:
    """(join keys in the export, {key: {proxy_method}}) — cheap, no pandas."""
    keys: set[str] = set()
    methods: dict[str, set[str]] = {}
    if path is None or not Path(path).exists():
        return keys, methods
    with Path(path).open(newline="") as fh:
        for row in csv.DictReader(fh):
            jk = _join_key(row.get("signal_date", ""), row.get("ticker", ""),
                           row.get("play", ""))
            keys.add(jk)
            m = (row.get("proxy_method") or "").strip()
            if m:
                methods.setdefault(jk, set()).add(m)
    return keys, methods


def _unpriced(analysis_csv: Path, priced_keys: set[str], results_csv: Path,
              proxy_csv: Path, include_bs: bool) -> list[dict]:
    """One entry per analysis row that never became a priced record.

    Deduplicated on the join key the same way `_build_analysis_lookup` is
    (first-written wins), so a re-analysed date does not double-count.
    """
    if analysis_csv is None or not Path(analysis_csv).exists():
        return []
    res_keys, _ = _csv_keys(results_csv)
    prox_keys, prox_methods = _csv_keys(proxy_csv)

    rows: list[dict] = []
    with Path(analysis_csv).open(newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    rows.sort(key=lambda r: (r.get("created_datetime") or ""))

    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        ticker = _cell(row, "ticker")
        play = _cell(row, "play")
        jk = _join_key(_cell(row, "date"), ticker, play)
        if jk in seen:
            continue
        seen.add(jk)
        if jk in priced_keys:
            continue
        if ticker.upper() == "MARKET":
            reason = "market_row"
        elif not play:
            reason = "no_play"
        elif jk in res_keys or jk in prox_keys:
            methods = prox_methods.get(jk, set())
            if (jk not in res_keys and methods and methods <= {"bs_options_hist"}
                    and not include_bs):
                reason = "bs_only"
            else:
                reason = "excluded_by_book"
        else:
            reason = "not_backtested"
        text = {f: _cell(row, f) for f in _TEXT_FIELDS}
        text["joined"] = True
        out.append(dict(date=_cell(row, "date")[:10], ticker=ticker,
                        reason=reason, text=text,
                        features=_features_with_parse(text)))
    return out


def _features_with_parse(text: dict, structure_text: str | None = None) -> dict:
    feats = text_features(text, structure_text)
    feats["parsed"] = parse_play(text.get("play"))
    return feats


def load_corpus(era: str | None = None, include_bs: bool = False,
                **load_book_kwargs) -> tuple[list[dict], list[dict], dict]:
    """`(rows, unpriced, diag)` — the priced book with its text re-attached.

    `rows` are `load_book` records (shallow copies; every existing key is
    untouched, because ~49 call sites read them) plus two new keys:
      `text`     — {regime, signal, play, trigger, invalidation, horizon,
                    created_datetime, joined}
      `features` — `text_features` output plus `parsed` (`parse_play` output)

    `unpriced` and `diag` are described in the module docstring. `era` and any
    `load_book` keyword (`results_csv`, `proxy_csv`, `analysis_csv`,
    `check_era`, `min_dates`, `sources`, `require_proxy_calibration`) pass
    straight through, so a test can hand it a synthetic era.
    """
    era = era or era_mod.requested_era()
    era_paths = era_mod.resolve_paths(era)
    results_csv = Path(load_book_kwargs.pop("results_csv", None) or era_paths["results"])
    proxy_csv = Path(load_book_kwargs.pop("proxy_csv", None) or era_paths["proxy"])
    analysis_csv = Path(load_book_kwargs.pop("analysis_csv", None) or era_paths["analysis"])

    records, diag = load_book(results_csv=results_csv, proxy_csv=proxy_csv,
                              analysis_csv=analysis_csv, era=era,
                              include_bs=include_bs, **load_book_kwargs)

    ac_lookup = _build_analysis_lookup(analysis_csv)

    rows: list[dict] = []
    priced_keys: set[str] = set()
    n_joined = 0
    for rec in records:
        text = _text_for_record(rec, ac_lookup)
        n_joined += bool(text["joined"])
        priced_keys.add(_join_key(rec["date"], rec["ticker"],
                                  rec["t"].row.get("play", "")))
        out = dict(rec)
        out["text"] = text
        # No structure_text override: a record's `structure` is the CANONICAL
        # name ("bull_call_spread"), not the strike-bearing phrase, so the
        # strikes have to come from the play cell.
        out["features"] = _features_with_parse(text, None)
        rows.append(out)

    unpriced = _unpriced(analysis_csv, priced_keys, results_csv, proxy_csv,
                         include_bs)

    diag = dict(diag)
    diag["n_joined"] = n_joined
    diag["n_unjoined"] = len(rows) - n_joined
    diag["unpriced_by_reason"] = Counter(u["reason"] for u in unpriced)
    diag["feature_coverage"] = feature_coverage(rows)
    return rows, unpriced, diag


def feature_coverage(rows: list[dict]) -> dict[str, float]:
    """Share of `rows` with a non-None value for each feature."""
    n = len(rows)
    if not n:
        return {k: 0.0 for k in FEATURE_KEYS}
    return {k: sum(1 for r in rows
                   if (r.get("features") or {}).get(k) is not None) / n
            for k in FEATURE_KEYS}


# ── citation check (the one network path) ───────────────────────────────────

_CITE_PREMIUM = re.compile(r"(?i)\$\s*(\d[\d,]*(?:\.\d+)?)\s*([MBK])\b")
_CITE_DTE = re.compile(r"(?i)(?<![\w.])(\d{1,4})\s*-?\s*(?:DTE|d\b|days?\b)")
_CITE_STRIKE = re.compile(r"(?<![\w.])\$(\d{1,6}(?:\.\d{1,2})?)(?![\w.]|\s*[MBKmbk]\b)")
_CITE_STRIKE_WORD = re.compile(
    r"(?i)(?<![\w.])(\d{1,6}(?:\.\d{1,2})?)[\s-]*(?:strike|calls?\b|puts?\b)")
_MD_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_UNIT = {"K": 1e3, "M": 1e6, "B": 1e9}


def _fetch_analysis_markdown(date: str, cache_dir: Path, force: bool = False) -> str:
    """The assembled analysis INPUT markdown for `date`, cached on disk.

    The ONLY network call in this module, and lazily imported so the module
    loads on a checkout with no Drive credentials. `audit_csv_path` is pointed
    INSIDE `cache_dir` so `fetch_data` cannot overwrite a production
    `audit/<date>-rollup.csv`. Monkeypatched wholesale in the tests.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{date}.md"
    if path.exists() and not force:
        return path.read_text(encoding="utf-8")
    from scripts.analysis_pipeline.fetch import fetch_data  # noqa: PLC0415
    md = fetch_data(date_str=date, audit_csv_path=cache_dir / f"{date}-rollup.csv")
    path.write_text(md, encoding="utf-8")
    return md


def _cited_tokens(signal: str) -> list[tuple[str, float, float]]:
    """`[(kind, value, tolerance)]` for the numbers cited in `[FLOW]` items.

    Only `[FLOW]` items: they are the ones that claim something about the tape
    the model was shown, so they are the only ones the input markdown can
    confirm or contradict. `tolerance` is half the last printed digit — a
    citation of `$4.68M` commits to 4.68M ± 5k, not to 4,680,000 exactly.
    """
    out: list[tuple[str, float, float]] = []
    seen: set[tuple[str, float]] = set()

    def add(kind: str, value: float, tol: float) -> None:
        if (kind, value) in seen:
            return
        seen.add((kind, value))
        out.append((kind, value, tol))

    for tag, item in split_signal(signal):
        if tag != "FLOW":
            continue
        for mant, unit in _CITE_PREMIUM.findall(item):
            clean = mant.replace(",", "")
            scale = _UNIT[unit.upper()]
            decimals = len(clean.split(".")[1]) if "." in clean else 0
            add("premium", float(clean) * scale, 0.5 * (10 ** -decimals) * scale)
        for d in _CITE_DTE.findall(item):
            add("dte", float(d), 0.0)
        for rx in (_CITE_STRIKE, _CITE_STRIKE_WORD):
            for s in rx.findall(item):
                v = float(s.replace(",", ""))
                if _LEVEL_MIN <= v <= _LEVEL_MAX:
                    add("strike", v, 0.0)
    return out


def _md_numbers(md: str) -> list[float]:
    return sorted({float(m.group(0).replace(",", "")) for m in _MD_NUMBER.finditer(md)})


def _present(kind: str, value: float, tol: float, numbers: list[float], md: str) -> bool:
    """Tolerant presence test of one cited number in the input markdown."""
    import bisect
    lo = bisect.bisect_left(numbers, value - tol - 1e-9)
    if lo < len(numbers) and numbers[lo] <= value + tol + 1e-9:
        return True
    if kind == "premium":
        # The markdown may print the same premium in the model's own shorthand
        # ("$4.68M") rather than as a raw number.
        for unit, scale in _UNIT.items():
            mant = value / scale
            if 0.001 <= mant < 10000:
                for text in (f"{mant:.2f}", f"{mant:.1f}", f"{mant:.0f}"):
                    if f"{text}{unit}" in md or f"{text}{unit.lower()}" in md:
                        return True
    return False


def citation_check(date: str, cache_dir: Path = CITATION_CACHE, force: bool = False,
                   rows: list[dict] | None = None, analysis_csv: Path | None = None,
                   era: str | None = None) -> dict:
    """Do the numbers the model cited for `date` appear in the data it was shown?

    Re-fetches (and caches) that date's assembled analysis input markdown, pulls
    the strike / DTE / $-premium tokens out of every `[FLOW]` signal item, and
    tests each one against the markdown with the rounding tolerance the citation
    itself implies.

    Returns `{date, cited_n, found_n, hallucination_rate, rows}` where `rows` is
    per-ticker `{cited_n, found_n, missing}`. `hallucination_rate` is None when
    nothing was cited — an unmeasured rate, not a clean one. A miss is EVIDENCE
    OF A MISS, not proof: the markdown is re-fetched today from a Drive that may
    have been garbage-collected since, so read a nonzero rate as a prompt to
    look, never as a verdict.
    """
    md = _fetch_analysis_markdown(date, cache_dir, force=force)
    numbers = _md_numbers(md)

    if rows is None:
        era = era or era_mod.requested_era()
        analysis_csv = Path(analysis_csv or era_mod.resolve_paths(era)["analysis"])
        rows = []
        if analysis_csv.exists():
            with analysis_csv.open(newline="") as fh:
                for r in csv.DictReader(fh):
                    if _cell(r, "date")[:10] != date:
                        continue
                    if _cell(r, "ticker").upper() == "MARKET" or not _cell(r, "play"):
                        continue
                    rows.append({"ticker": _cell(r, "ticker"),
                                 "text": {"signal": _cell(r, "signal")}})

    per: dict[str, dict] = {}
    cited_n = found_n = 0
    for r in rows:
        ticker = str(r.get("ticker") or "?")
        signal = (r.get("text") or {}).get("signal") or ""
        key = ticker
        n = 2
        while key in per:
            key, n = f"{ticker}#{n}", n + 1
        tokens = _cited_tokens(signal)
        missing = [f"{k}:{v:g}" for k, v, tol in tokens
                   if not _present(k, v, tol, numbers, md)]
        per[key] = dict(cited_n=len(tokens), found_n=len(tokens) - len(missing),
                        missing=missing)
        cited_n += len(tokens)
        found_n += len(tokens) - len(missing)

    return dict(date=date, cited_n=cited_n, found_n=found_n,
                hallucination_rate=(1 - found_n / cited_n) if cited_n else None,
                rows=per)


def citations_for_rows(rows: list[dict], cache_dir: Path = CITATION_CACHE,
                       limit: int | None = None) -> dict[str, dict]:
    """`{date: citation_check(...)}` over the dates present in `rows`.

    Dates are taken in ascending order and truncated to `limit`, so a capped run
    is deterministic and its cache is reusable rather than a different slice
    every time.
    """
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(str(r["date"])[:10], []).append(r)
    dates = sorted(by_date)
    if limit is not None:
        dates = dates[:limit]
    return {d: citation_check(d, cache_dir=cache_dir, rows=by_date[d]) for d in dates}


# ── CLI ─────────────────────────────────────────────────────────────────────

def _print_diag(rows: list[dict], unpriced: list[dict], diag: dict) -> None:
    print(f"Text corpus: {len(rows)} priced rows  "
          f"era={diag['era']}  n_dates={diag['n_dates']}  "
          f"date_range={diag['date_range']}")
    print(f"joined to AnalysisClaude: {diag['n_joined']}  "
          f"fallback (results/proxy text only): {diag['n_unjoined']}")
    print("intent: " + "  ".join(
        f"{k}={v}" for k, v in Counter(
            (r["features"]["parsed"]["intent"] or "-") for r in rows).most_common()))
    print("invalidation_type: " + "  ".join(
        f"{k}={v}" for k, v in Counter(
            r["features"]["invalidation_type"] for r in rows).most_common()))
    print(f"\nUnpriced analysis rows: {len(unpriced)}")
    for reason, n in diag["unpriced_by_reason"].most_common():
        print(f"  {reason:<18} {n}")
    print("\nFeature coverage (share non-None across priced rows):")
    for k in FEATURE_KEYS:
        print(f"  {k:<28} {diag['feature_coverage'][k]:6.1%}   {FEATURE_NOTES[k][:60]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--era", default=None, help="era to load (default: STUDY_ERA, else current)")
    ap.add_argument("--include-bs", action="store_true",
                    help="include bs_options_hist (model-priced) proxy rows")
    ap.add_argument("--citations", action="store_true",
                    help="re-fetch analysis inputs and test cited numbers (NETWORK)")
    ap.add_argument("--limit", type=int, default=None,
                    help="with --citations: check at most N dates")
    ap.add_argument("--cache-dir", default=str(CITATION_CACHE))
    args = ap.parse_args()

    # min_dates=0: like `book --validate`, this is the pre-flight diagnostic —
    # its job is to describe whatever is on disk, including a book too thin to
    # study. The era check still applies.
    rows, unpriced, diag = load_corpus(era=args.era, include_bs=args.include_bs,
                                       min_dates=0)
    _print_diag(rows, unpriced, diag)

    if args.citations:
        out = citations_for_rows(rows, cache_dir=Path(args.cache_dir), limit=args.limit)
        print("\nCitation check (cited numbers found in the model's own input):")
        for d, res in sorted(out.items()):
            rate = res["hallucination_rate"]
            rate_s = "n/a" if rate is None else f"{rate:6.1%}"
            print(f"  {d}  cited={res['cited_n']:<5} found={res['found_n']:<5} "
                  f"unmatched={rate_s}")


if __name__ == "__main__":
    main()
