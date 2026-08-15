"""
Prompt + response contract for the ONE judgment call in the daily trade
journal — "does today's context still support the deploy card's survivors?"

PRODUCTION TIER, no network of its own. `recommend.py` is the only caller and
it owns the actual `claude -p` subprocess (mirrors `run_engine()` /
`_invoke_claude()` in `scripts/analysis_pipeline/core.py`); this module only
builds the prompt text and parses the response shape.

STRICT JSON CONTRACT. The model is asked exactly THREE things —
`docs/deployment-rules.md` leaves no fourth to ask:
  1. has each candidate's `trigger` fired, given the supplied context?
  2. is each candidate's `alternative_interpretation` now more likely than the
     thesis it was scored against?
  3. among the hedge-sleeve candidates (already ordered by |delta| desc), which
     to take if one is wanted — breaking a genuine tie only, never re-ranking.

The model never sees a rejected (VETO / Tier-C) play. `recommend.judge()`
builds this prompt only from Part A's survivor lists, and independently drops
any ticker in the response that is not one of those survivors — this module
has no opinion on tiers or vetoes, it just describes the shape of the ask and
the shape of the answer.
"""
from __future__ import annotations

import json

CONTRACT = """
## Your task

You are given today's SURVIVING deploy candidates from a deterministic ranker
(already tiered and ordered — do not re-rank, re-tier, or add tickers) plus a
short block of hedge-sleeve candidates (already ordered by |delta| descending
— do not re-rank those either). Given the CONTEXT below, answer three
questions and return ONLY the JSON object described here — no prose before or
after it.

For EVERY candidate you are given (deploy set AND hedge sleeve), decide:
  - `trigger_fired`: "yes" | "no" | "unknown" — has the candidate's `trigger`
    condition happened, given the context? Use "unknown" when the context
    does not say either way — never guess.
  - `trigger_note`: one line, why.
  - `alt_more_likely`: "yes" | "no" — is the candidate's
    `alternative_interpretation` now a more likely read of the flow than the
    directional thesis it was scored against?
  - `alt_note`: one line, why.

Then, ONLY among the hedge-sleeve candidates (if more than one is given), pick
which to take if a hedge is wanted this session. Break a genuine |delta| TIE
only — the sleeve is already ordered by |delta| descending, and you must not
overrule that ordering for any other reason (never on `score_total`, never on
which one "feels" cheaper). If the sleeve has zero or one candidate,
`hedge_pick` is that one candidate's ticker, or null.

Return exactly this shape and nothing else:

{
  "candidates": [
    {"ticker": "...", "trigger_fired": "yes|no|unknown", "trigger_note": "...",
     "alt_more_likely": "yes|no", "alt_note": "..."}
  ],
  "hedge": [
    {"ticker": "...", "trigger_fired": "yes|no|unknown", "trigger_note": "...",
     "alt_more_likely": "yes|no", "alt_note": "..."}
  ],
  "hedge_pick": "TICKER or null",
  "hedge_pick_note": "one line, or empty string"
}

Every ticker you return MUST be one of the tickers given to you below — you
are shown the complete survivor set. Do not invent a ticker, do not include
one that was not given to you, and do not include a tier, score, or ranking
field on any entry: you are not being asked to re-rank, promote, demote a play
into or out of a tier, or resurrect anything that is not in the lists below.
""".strip()


def _candidate_block(rec: dict) -> str:
    lines = [
        f"- {rec.get('ticker', '')} ({rec.get('tier', '')}) — {rec.get('structure', '')}",
        f"  play: {rec.get('play', '') or '(none given)'}",
        f"  trigger: {rec.get('trigger', '') or '(none given)'}",
        f"  invalidation: {rec.get('invalidation', '') or '(none given)'}",
        "  alternative_interpretation: "
        f"{rec.get('alternative_interpretation', '') or '(none given)'}",
    ]
    delta = rec.get("delta")
    if delta is not None:
        lines.append(f"  |delta|: {abs(delta):.3f}")
    return "\n".join(lines)


def build_prompt(candidates: list[dict], hedge_candidates: list[dict], context: str) -> str:
    """Assemble the full judgment prompt.

    `candidates` / `hedge_candidates` are plain dicts (see
    `recommend.Candidate.to_prompt_dict()`) — this module has no dependency on
    recommend.py's dataclasses or tier logic, only on the field names above.
    """
    cand_text = "\n".join(_candidate_block(c) for c in candidates) or "(none)"
    hedge_text = "\n".join(_candidate_block(c) for c in hedge_candidates) or "(none)"
    return "\n\n".join([
        "# Daily deploy-card judgment call",
        "Work only from what is in this prompt — do not run commands or read "
        "files, and do not use any outside knowledge of these tickers.",
        "## Context\n\n" + (context.strip() if context else "(no context supplied)"),
        "## Deploy-set candidates (already tiered/ordered — do not re-rank)\n\n" + cand_text,
        "## Hedge-sleeve candidates (already ordered by |delta| desc — do not re-rank)\n\n"
        + hedge_text,
        CONTRACT,
    ])


def _extract_json(text: str) -> dict:
    """Tolerant JSON-object extraction — same approach as
    `scripts/analysis_pipeline/core.py::_extract_json`, kept as a private copy
    here rather than a cross-package import so this module has no dependency
    on the analysis pipeline."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in judgment model output")
    return json.loads(s[start:end + 1])


def parse_response(text: str) -> dict:
    """Extract and shape-validate the model's JSON.

    Only checks the CONTRACT's shape (right keys, right types) — ticker/
    survivor validation is `recommend.judge()`'s job, not this module's, so
    this stays a pure format layer.
    """
    data = _extract_json(text)
    if "candidates" not in data or "hedge" not in data:
        raise ValueError("judgment response missing 'candidates' or 'hedge' key")
    if not isinstance(data["candidates"], list) or not isinstance(data["hedge"], list):
        raise ValueError("'candidates' and 'hedge' must be JSON arrays")
    data.setdefault("hedge_pick", None)
    data.setdefault("hedge_pick_note", "")
    return data
