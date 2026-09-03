"""Does the model's own TEXT separate outcome within structure x tier?

PRE-REGISTERED 2026-09-02 in research/pre-registrations/f1_selection/text_features.md
BEFORE this file was written. Read that file first; nothing here may drift from
it. In brief:

  ARM A (deterministic)  six regex-only text features from
       `lib/text_corpus.text_features` plus the measured `hallucination_rate`
       from `lib/text_corpus.citation_check`, each read alone, WITHIN
       structure x tier. Continuous features are cut at terciles computed on
       the FULL era book and FROZEN before any outcome is read; binary
       features are read as their two groups. `evidence_n` is a REDUNDANCY
       CONTROL printed with a partial-on-`score_total` check and may not be
       promoted to a candidate under any outcome.
  ARM B (blind labels)   five taxonomy labels with frozen level sets, produced
       by a cheap headless model shown ONLY the text fields with TICKER and
       DATE stripped, cached on `sha256(text payload)`. Same within-structure
       x tier treatment as ARM A.
  ARM C (gate arms)      every feature reaching CANDIDATE in A or B (and,
       DESCRIPTIVELY, every feature regardless) applied as (i) a VETO or
       (ii) a one-step TIER DEMOTION under
       `protocol.top_k_per_day(rank_fn=ladder_rank, k=3)`, paired by date
       against the unmodified shipped ladder.

Nothing here builds a composite, weights a feature or fits anything: the
selection search closed 2026-08-11 and re-opens on NEW COLUMNS only. The text
fields are that new column family. Every arm is within structure AND within
tier from the first look, because three columns have already been caught
looking predictive pooled and vanishing within structure.

Nothing ships from this file. A CANDIDATE is filed into one of the two named
lists in the registration -- PROMPT-ROBUSTNESS FINDINGS (input to
`prompt_eval`) or ENTRY-GATE CANDIDATES (a written
`docs/deployment-rules.md` proposal for the operator) -- and neither is a ship.

No annualised figure, Sharpe or time-to-recover is printed anywhere. PF never
prints without mean R beside it. R is quoted, never dollars, in ARM C.

Usage (the runner sets STUDY_ERA from its own --era flag):
    python -m scripts.backtest_study run text_features -- --labels run --citations run
    python -m scripts.backtest_study run text_features --era v3 -- --labels cached
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import text_corpus as TC  # noqa: E402

# The runner promotes -latest.txt on these codes instead of deleting it. It
# finds this by AST parse, so it must stay a PLAIN SET LITERAL -- a
# frozenset(...) call is invisible to ast.literal_eval and the refusal would be
# misfiled as a failure. {2, 3} are `lib/era.py`'s two refusals (thin era /
# era mismatch); nothing else in this module is a designed refusal.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── frozen constants (registration: Power floors / Bar for CANDIDATE) ────────
MIN_AFFECTED_DATES = 25         # ARM A/B: dates the cell's comparison reads
MIN_ROWS = 60                   # ARM A/B: rows in the two compared groups
BH_Q = 0.10                     # Benjamini-Hochberg, per arm, never pooled
TOP_K = 3                       # the shipped ladder replay depth
BOOT_N = P.BOOT_N               # 10000
ALPHA = 0.05
BOOT_SEED = 20260902

OUT_DIR = ROOT / "backtests" / "study_output"
LABEL_CACHE = ROOT / "backtests" / "text_labels_cache"
LABEL_MODEL = "claude-haiku-4-5-20251001"
# Rows per labeller call. The study was specified at 25 and 25 was tried first:
# on 2026-09-02 it silently LOST 620 of 1,804 payloads (v3 220/795, v4 400/1009)
# because the labeller truncates a 25-object array on a ~39k-char prompt, and a
# dropped item is an UNLABELLED row, not a wrong one. At 10 the same prompt
# returns complete batches (0 unlabelled across the top-up pass). Overridable
# with --label-batch; the report prints the batch size it used.
LABEL_BATCH = 10
LABEL_WORKERS = 8               # concurrent `claude -p` batches; same calls, less wall clock
LABEL_TIMEOUT_S = 900

# The hand-added third cut of criterion 3: `protocol.window_cuts` drops ONE
# window at a time; the registration also requires the ex-BOTH cut, which it
# does not produce.
EX_BOTH_MONTHS = frozenset(m for months in P.DOMINANT_WINDOWS.values() for m in months)

# ── ARM A feature frame, frozen by the registration ─────────────────────────
#
# BINARY_FEATURES: (label of the "high" group, label of the "low" group, fn).
# The fn returns one of the two labels or None (NOT EVALUABLE, never imputed).
#
# `invalidation_type`'s PRIMARY cut is BINARY -- price_only vs mixed
# (everything else) -- because the 5-level split is 91% `mixed` in both eras.
# The 5-level table prints DESCRIPTIVELY and no criterion is evaluated on it.


def _f_invalidation_type(feats: dict):
    v = feats.get("invalidation_type")
    if v is None:
        return None
    return "price_only" if v == "price" else "mixed"


def _f_inside_strikes(feats: dict):
    v = feats.get("invalidation_inside_strikes")
    if v is None:
        return None
    return "inside" if v else "outside"


def _f_trigger_conditional(feats: dict):
    v = feats.get("trigger_conditional")
    if v is None:
        return None
    return "conditional" if v else "unconditional"


# (name, group_a, group_b, fn) -- the reported difference is mean R(a) - mean R(b).
BINARY_FEATURES = (
    ("invalidation_type", "price_only", "mixed", _f_invalidation_type),
    ("invalidation_inside_strikes", "inside", "outside", _f_inside_strikes),
    ("trigger_conditional", "conditional", "unconditional", _f_trigger_conditional),
)

# Continuous features: top tercile (T3) vs bottom tercile (T1), terciles cut on
# the FULL era book and FROZEN before any outcome is read. `hallucination_rate`
# is the measured quantity, not a regex feature; it is filled in by ARM A's
# citation step and is NOT EVALUABLE on a row whose date has no cached input.
CONTINUOUS_FEATURES = (
    "invalidation_level",
    "trigger_level",
    "numeric_specificity",
    "thesis_len",
    "alt_ratio",
    "hallucination_rate",
)

# Printed beside thesis_len, never tested on its own (the registration lists it
# as a companion of feature 5, not a seventh feature).
COMPANION_FEATURES = ("alt_len",)

# REDUNDANCY CONTROL. Reported for ONE purpose -- to show it adds nothing over
# `score_total` -- and may not be promoted to a candidate under any outcome.
CONTROL_FEATURE = "evidence_n"

# Everything ARM A declares, so a feature with no computable cell prints as
# NOT EVALUABLE rather than vanishing from the verdict block.
ARM_A_DECLARED = ("invalidation_type", "invalidation_inside_strikes",
                  "trigger_conditional", *CONTINUOUS_FEATURES)

# ── ARM B label frame, level sets frozen by the registration ────────────────
LABEL_LEVELS = {
    "thesis_type": ("flow-follow", "mean-reversion", "catalyst", "hedge", "vol"),
    "evidence_quality": ("1", "2", "3"),
    "confidence_language": ("hedged", "neutral", "assertive"),
    "one_sided": ("token", "substantive"),
    "invalidation_concreteness": ("1", "2", "3"),
}

# How each label is read as a two-group contrast: (group_a, group_b) or
# ONE_VS_REST for a nominal label with no ordering.
ONE_VS_REST = "__one_vs_rest__"
LABEL_CONTRASTS = {
    "thesis_type": ONE_VS_REST,
    "evidence_quality": ("3", "1"),
    "confidence_language": ("assertive", "hedged"),
    "one_sided": ("substantive", "token"),
    "invalidation_concreteness": ("3", "1"),
}

# The ONLY keys the labeller ever sees. Anything else in the payload is a
# leak; `assert_clean_payload` refuses it and the run fails.
TEXT_PAYLOAD_KEYS = ("thesis", "alt", "signal_items", "trigger", "invalidation")

# Keys that would leak an outcome, a price, a structure result, a date or a
# ticker into the labeller. Checked by name AND by the whitelist above, because
# a whitelist alone would not explain WHY a key was refused.
FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "R", "E", "R_dol", "E_dol", "mfe", "mae", "mfe_day", "mae_day",
    "pnl", "pnl_pct", "realized_pnl_pct", "pnl_at_cap_pct", "exit_reason",
    "days_held", "date", "signal_date", "month", "ticker", "structure",
    "tier", "source", "score_total", "price_vector", "entry_premium_total",
    "credit", "post13c", "iv_entry", "delta", "dte",
})


# ── printing ────────────────────────────────────────────────────────────────

def hdr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t: str) -> None:
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def fail(msg: str) -> None:
    """A REAL failure (not a designed refusal): exit non-zero, report deleted."""
    print(f"\n*** GATE FAILURE: {msg} ***")
    sys.exit(1)


def _fmt(x, w: int = 7, p: int = 4) -> str:
    if x is None:
        return "n/a".rjust(w)
    try:
        if x != x:                       # NaN
            return "nan".rjust(w)
    except TypeError:
        return str(x).rjust(w)
    return f"{x:{w}.{p}f}"


def _fmt_pf(x) -> str:
    """PF prints only beside mean R. `None` means undefined (no losers)."""
    return "undef" if x is None else ("nan" if x != x else f"{x:5.2f}")


def n_dates(rows) -> int:
    return len({str(r["date"]) for r in rows})


def _mean_R(rows) -> float:
    vals = [float(r["R"]) for r in rows if r.get("R") is not None]
    return statistics.fmean(vals) if vals else float("nan")


# ── statistics ──────────────────────────────────────────────────────────────
#
# `protocol` exposes no unpaired two-group mean-difference CI: `boot_ci_by_date`
# is a one-sample CI and `boot_ci_paired_by_date` requires both statistics to
# live on the SAME row. An ARM A/B contrast is two DISJOINT row sets, and on
# this book the two groups rarely share a date inside one structure x tier cell
# (measured 2026-09-02: 0-45 shared dates per cell against 28-126 in the union),
# so a within-date pairing would throw away most of the evidence and fail the
# power floor for reasons that have nothing to do with the effect.
#
# So the difference CI below resamples DATES over the UNION of the two groups'
# dates, each drawn date contributing its rows to whichever pool they belong to
# -- exactly the joint-resampling shape `protocol.pf_paired_by_date` already
# uses to compare two books. It is date-clustered in the same unit and for the
# same reason. `protocol.boot_ci_by_date` still prints each group's own mean CI
# beside it. See the dated wording correction at the end of the registration.

def boot_ci_diff_by_date(rows_a, rows_b, key: str = "R", n: int = BOOT_N,
                         seed: int = BOOT_SEED, alpha: float = ALPHA):
    """`(point, lo, hi, p)` for mean(a) - mean(b) under joint date resampling.

    `p` is the achieved significance level of the bootstrap distribution
    (twice the smaller tail mass at zero), used only to feed the per-arm
    Benjamini-Hochberg control; criterion 1 itself is the CI excluding zero.
    """
    def _by(rows):
        out: dict[str, list[float]] = {}
        for r in rows:
            if r.get(key) is None:
                continue
            out.setdefault(str(r["date"]), []).append(float(r[key]))
        return out

    ba, bb = _by(rows_a), _by(rows_b)
    va = [v for vs in ba.values() for v in vs]
    vb = [v for vs in bb.values() for v in vs]
    if not va or not vb:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    point = statistics.fmean(va) - statistics.fmean(vb)
    dates = sorted(set(ba) | set(bb))
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        pa, pb = [], []
        for _ in range(len(dates)):
            d = rng.choice(dates)
            pa.extend(ba.get(d, ()))
            pb.extend(bb.get(d, ()))
        if not pa or not pb:
            continue
        diffs.append(statistics.fmean(pa) - statistics.fmean(pb))
    if not diffs:
        return (point, float("nan"), float("nan"), float("nan"))
    diffs.sort()
    m = len(diffs)
    lo = diffs[int(alpha / 2 * m)]
    hi = diffs[min(m - 1, int((1 - alpha / 2) * m))]
    n_le = sum(1 for d in diffs if d <= 0)
    n_ge = m - n_le
    p = min(1.0, 2.0 * min(n_le, n_ge) / m)
    return (point, lo, hi, p)


def loo_diff_by_date(rows_a, rows_b):
    """Leave-one-DATE-out gain of mean(a) - mean(b) -- the two-group analogue of
    `protocol.loo_by_date`, which assumes both statistics live on the same rows.

    Returns `(mean_gain, share_positive, min_gain, n_folds)`, the same shape, so
    the registration's "read `min_gain`" instruction reads identically here. A
    rule SURVIVES only when EVERY fold stays positive.
    """
    gains = _loo_gains(rows_a, rows_b)
    if not gains:
        return (float("nan"), float("nan"), float("nan"), 0)
    return (statistics.fmean(gains),
            sum(1 for g in gains if g > 0) / len(gains),
            min(gains), len(gains))


def bh_reject(pvals: list[float], q: float = BH_Q) -> list[bool]:
    """Benjamini-Hochberg at level `q` over one arm's p-vector.

    Returns a boolean per input position (True = survives BH). A NaN p-value
    never survives. Applied PER ARM, never pooled across A, B and C.
    """
    idx = [i for i, p in enumerate(pvals) if p == p and p is not None]
    m = len(idx)
    out = [False] * len(pvals)
    if m == 0:
        return out
    order = sorted(idx, key=lambda i: pvals[i])
    k_max = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= q * rank / m:
            k_max = rank
    for rank, i in enumerate(order, start=1):
        if rank <= k_max:
            out[i] = True
    return out


def year_diffs(rows_a, rows_b) -> dict[str, float]:
    """Per-calendar-year mean R difference, from `protocol.by_year`."""
    ya, yb = P.by_year(rows_a), P.by_year(rows_b)
    out: dict[str, float] = {}
    for y in sorted(set(ya) | set(yb)):
        a = [float(r["R"]) for r in ya.get(y, []) if r.get("R") is not None]
        b = [float(r["R"]) for r in yb.get(y, []) if r.get("R") is not None]
        if not a or not b:
            out[y] = float("nan")
        else:
            out[y] = statistics.fmean(a) - statistics.fmean(b)
    return out


def all_same_sign(vals, sign: float | None = None) -> bool:
    """Criterion 4: positive in every calendar year present -- or, for a
    right-signed NEGATIVE effect, negative in every one (see the registration's
    wording correction 3). A year that cannot be computed (NaN) fails it.

    `sign` pins the direction to the cell's own point estimate, so a cell whose
    yearly diffs all point the OTHER way cannot pass on "consistency" alone.
    """
    vs = list(vals)
    if not vs or any(v != v for v in vs):
        return False
    if sign is not None:
        if sign == 0:
            return False
        return all(v * sign > 0 for v in vs)
    return all(v > 0 for v in vs) or all(v < 0 for v in vs)


# ── ARM B: the blind labeller ───────────────────────────────────────────────
#
# The whole leakage argument rests on two things and both are enforced here,
# not by convention:
#   1. the payload handed to the model holds ONLY the five text keys, with the
#      ticker symbol and every date-shaped token scrubbed OUT OF THE TEXT too;
#   2. the cache key is `sha256` of that exact payload, so a cache HIT cannot
#      carry an outcome in from anywhere -- there is nowhere for one to ride.
# `tests/test_text_features.py::test_label_input_carries_no_outcome_key` pins
# both. The run fails if the guard fails.

_ISO_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
_MONTH_DATE_RE = re.compile(
    r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*"
    r"\d{1,2}(?:\s*,?\s*(?:19|20)\d{2})?")
_DAY_MONTH_RE = re.compile(
    r"(?i)\b\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*")
_BARE_YEAR_RE = re.compile(r"(?<![\w.$])(?:19|20)\d{2}(?![\w.])")


def scrub_identity(text: str, ticker: str | None) -> str:
    """Remove the ticker symbol and every date-shaped token from one text field.

    The registration's binding mitigation for the labeller's own lookahead:
    date and ticker are STRIPPED, and the cache key is the stripped text. This
    reduces the recall risk, it does not eliminate it -- every label-derived
    CANDIDATE carries that caveat in the verdict block.
    """
    if not isinstance(text, str) or not text:
        return ""
    out = text
    if ticker:
        t = str(ticker).strip()
        if t:
            # The bare symbol, and the $-prefixed cashtag form.
            out = re.sub(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])",
                         "TKR", out, flags=re.IGNORECASE)
            out = re.sub(rf"\${re.escape(t)}\b", "TKR", out, flags=re.IGNORECASE)
    for rx in (_ISO_DATE_RE, _MONTH_DATE_RE, _DAY_MONTH_RE, _BARE_YEAR_RE):
        out = rx.sub("DATE", out)
    return out.strip()


def text_payload(row: dict) -> dict:
    """The ONLY thing the labeller ever sees, for one corpus row.

    Built from the text fields alone; ticker and date are scrubbed out of the
    text as well as absent from the keys. Never returns an outcome, a price, a
    structure result, a tier or a source.
    """
    text = row.get("text") or {}
    feats = row.get("features") or {}
    parsed = feats.get("parsed") or TC.parse_play(text.get("play"))
    ticker = row.get("ticker")
    items = [f"[{tag or '-'}] {body}" for tag, body in TC.split_signal(text.get("signal") or "")]
    payload = {
        "thesis": scrub_identity(parsed.get("thesis") or "", ticker),
        "alt": scrub_identity(parsed.get("alt") or "", ticker),
        "signal_items": [scrub_identity(i, ticker) for i in items],
        "trigger": scrub_identity(text.get("trigger") or "", ticker),
        "invalidation": scrub_identity(text.get("invalidation") or "", ticker),
    }
    assert_clean_payload(payload)
    return payload


def assert_clean_payload(payload: dict) -> dict:
    """The leakage guard. Raises on anything that is not one of the five text
    keys, and names the forbidden key when it recognises one."""
    if not isinstance(payload, dict):
        raise TypeError(f"labeller payload must be a dict, got {type(payload).__name__}")
    bad = sorted(set(payload) & FORBIDDEN_PAYLOAD_KEYS)
    if bad:
        raise ValueError(
            f"LEAKAGE GUARD: labeller payload carries outcome/identity key(s) {bad}. "
            f"The labeller may see the text fields {list(TEXT_PAYLOAD_KEYS)} and nothing else.")
    extra = sorted(set(payload) - set(TEXT_PAYLOAD_KEYS))
    if extra:
        raise ValueError(
            f"LEAKAGE GUARD: labeller payload carries unexpected key(s) {extra}; "
            f"allowed keys are exactly {list(TEXT_PAYLOAD_KEYS)}.")
    return payload


def payload_hash(payload: dict) -> str:
    """sha256 of the exact text payload -- the cache key, and nothing else."""
    assert_clean_payload(payload)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


LABEL_PROMPT = """You are labelling short options-trade write-ups for a research \
taxonomy. You see ONLY the text of each write-up. You are NOT told the ticker, the \
date, the structure, the price, or what happened. Do not guess any of them, and do \
not let any guess influence a label. Label ONLY what the text says.

For each numbered item, emit these five labels:

  thesis_type               one of: flow-follow | mean-reversion | catalyst | hedge | vol
                            (what KIND of case the thesis makes)
  evidence_quality          one of: 1 | 2 | 3
                            (1 = assertion with no specifics, 2 = some concrete
                             evidence, 3 = several specific, checkable facts)
  confidence_language       one of: hedged | neutral | assertive
                            (the register of the prose, not its correctness)
  one_sided                 one of: token | substantive
                            (is the "alt" counter-reading a real alternative
                             case, or a throwaway line?)
  invalidation_concreteness one of: 1 | 2 | 3
                            (1 = vague or absent, 2 = a condition without a
                             number, 3 = a specific, checkable falsifier)

Reply with ONLY a JSON array of {n} objects, in the SAME ORDER as the items, each
object exactly:
{{"i": <item number>, "thesis_type": "...", "evidence_quality": "...", \
"confidence_language": "...", "one_sided": "...", "invalidation_concreteness": "..."}}

No prose, no markdown fence, no explanation.

ITEMS:
{items}
"""


def _render_items(payloads: list[dict]) -> str:
    out = []
    for i, p in enumerate(payloads, start=1):
        assert_clean_payload(p)
        sig = "\n".join(f"    - {s}" for s in p["signal_items"]) or "    (none)"
        out.append(
            f"### item {i}\n"
            f"thesis: {p['thesis'] or '(none)'}\n"
            f"alt: {p['alt'] or '(none)'}\n"
            f"signal_items:\n{sig}\n"
            f"trigger: {p['trigger'] or '(none)'}\n"
            f"invalidation: {p['invalidation'] or '(none)'}")
    return "\n\n".join(out)


def parse_label_response(raw: str, n: int) -> dict[int, dict]:
    """`{item_index (1-based): {label: level}}` from one labeller reply.

    Tolerates a markdown fence and leading prose; validates every level against
    the FROZEN level sets and drops any item that fails, so an invalid level is
    an UNLABELLED row (counted) rather than a silently coerced one.
    """
    if not isinstance(raw, str):
        return {}
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\s*", "", txt)
        txt = re.sub(r"```\s*$", "", txt).strip()
    start, end = txt.find("["), txt.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        arr = json.loads(txt[start:end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(arr, list):
        return {}
    out: dict[int, dict] = {}
    for pos, obj in enumerate(arr, start=1):
        if not isinstance(obj, dict):
            continue
        try:
            i = int(obj.get("i", pos))
        except (TypeError, ValueError):
            i = pos
        if not (1 <= i <= n) or i in out:
            continue
        labels = {}
        ok = True
        for name, levels in LABEL_LEVELS.items():
            v = obj.get(name)
            v = str(v).strip().lower() if v is not None else ""
            if v not in levels:
                ok = False
                break
            labels[name] = v
        if ok:
            out[i] = labels
    return out


def _invoke_labeller(prompt: str, model: str) -> str:
    """One `claude -p` call. Mirrors `scripts/study_review/core.py`'s subprocess
    shape and result-event extraction, with MCP servers switched OFF: the
    labeller is a pure text-in / JSON-out classifier and must not be able to
    reach Drive, Sheets or the broker. It also triples the throughput, which is
    what makes ~75 calls a practical study step."""
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model,
         "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
        input=prompt, capture_output=True, text=True, cwd=str(ROOT),
        timeout=LABEL_TIMEOUT_S, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:400]}")
    parsed = json.loads(proc.stdout)
    if isinstance(parsed, list):
        events = [e for e in parsed if isinstance(e, dict) and e.get("type") == "result"]
        wrapper = events[-1] if events else {}
    else:
        wrapper = parsed
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {str(wrapper.get('result'))[:400]}")
    return wrapper.get("result", "")


def label_rows(rows: list[dict], model: str = LABEL_MODEL, batch: int = LABEL_BATCH,
               cache_dir: Path = LABEL_CACHE, mode: str = "run",
               invoke=None, log=print, workers: int = LABEL_WORKERS) -> dict:
    """Attach `row["labels"]` to every row it can, from cache or the labeller.

    `mode`: "run" labels everything not already cached; "cached" uses ONLY what
    is on disk and calls nothing; "skip" attaches nothing. Resumable in every
    mode -- a row whose payload hash is cached is never sent again, so an
    interrupted run resumes at the batch it stopped on.

    Returns `{calls, cached, labelled, invalid, unique, retries, failures}`.
    """
    cache_dir = Path(cache_dir)
    invoke = invoke or (lambda prompt: _invoke_labeller(prompt, model))
    stats = dict(calls=0, cached=0, labelled=0, invalid=0, unique=0,
                 retries=0, failures=0, mode=mode)
    if mode == "skip":
        for r in rows:
            r["labels"] = None
        return stats

    # One payload per row; identical text collapses onto one cache entry.
    payloads = {}
    for r in rows:
        p = text_payload(r)
        h = payload_hash(p)
        r["_label_hash"] = h
        payloads.setdefault(h, p)
    stats["unique"] = len(payloads)

    labels: dict[str, dict] = {}
    todo: list[str] = []
    for h, p in payloads.items():
        f = cache_dir / f"{h}.json"
        if f.exists():
            try:
                labels[h] = json.loads(f.read_text())
                stats["cached"] += 1
                continue
            except (ValueError, OSError):
                pass
        todo.append(h)

    if mode == "run" and todo:
        cache_dir.mkdir(parents=True, exist_ok=True)
        todo.sort()                       # deterministic batching, resumable
        chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]

        def _one_batch(chunk: list[str]) -> tuple[list[str], dict[int, dict], int, int]:
            """One batch: (chunk, parsed labels, calls made, retries). Pure —
            it touches no shared state, so the pool below needs no lock."""
            prompt = LABEL_PROMPT.format(n=len(chunk), items=_render_items(
                [payloads[h] for h in chunk]))
            calls = retries = 0
            got: dict[int, dict] = {}
            for attempt in (1, 2):        # one retry on a failed/short batch
                try:
                    calls += 1
                    got = parse_label_response(invoke(prompt), len(chunk))
                except Exception as exc:                      # noqa: BLE001
                    log(f"    labeller error ({type(exc).__name__}: {str(exc)[:120]})")
                    got = {}
                if len(got) == len(chunk):
                    break
                if attempt == 1:
                    retries += 1
            return chunk, got, calls, retries

        done = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for chunk, got, calls, retries in pool.map(_one_batch, chunks):
                stats["calls"] += calls
                stats["retries"] += retries
                for j, h in enumerate(chunk, start=1):
                    lab = got.get(j)
                    if lab is None:
                        stats["failures"] += 1
                        continue
                    labels[h] = lab
                    (cache_dir / f"{h}.json").write_text(json.dumps(lab, sort_keys=True))
                done += len(chunk)
                log(f"    labelled {done}/{len(todo)} unique payloads "
                    f"({stats['calls']} calls, {stats['failures']} unlabelled)")

    for r in rows:
        lab = labels.get(r.get("_label_hash"))
        r["labels"] = lab
        if lab is None:
            stats["invalid"] += 1
        else:
            stats["labelled"] += 1
    return stats


# ── level assignment ────────────────────────────────────────────────────────

def tercile_edges(rows, feat: str) -> tuple[float, float] | None:
    """`(t1_edge, t2_edge)` cut on the FULL era book, FROZEN before any outcome
    is read. The NaN filter is `v == v` on the RAW value, applied before the
    cut; the excluded count is printed by the caller."""
    vals = sorted(v for v in (_raw(r, feat) for r in rows)
                  if v is not None and v == v)
    n = len(vals)
    if n < 3:
        return None
    return (vals[n // 3], vals[2 * n // 3])


def _raw(row: dict, feat: str):
    if feat == "hallucination_rate":
        return row.get("hallucination_rate")
    v = (row.get("features") or {}).get(feat)
    return None if v is None else float(v)


def continuous_level(row: dict, feat: str, edges, degenerate: bool = False):
    """"T3" / "T2" / "T1" for a continuous feature, or None (NOT EVALUABLE).

    `degenerate` switches to the binary >0 / ==0 read used when the tercile
    edges collapse onto one value -- which happens on `hallucination_rate`,
    whose distribution is a spike at zero. Declared in the report where it
    fires; never applied silently.
    """
    v = _raw(row, feat)
    if v is None or v != v or edges is None:
        return None
    if degenerate:
        return "T3" if v > 0 else "T1"
    lo, hi = edges
    if v <= lo:
        return "T1"
    if v > hi:
        return "T3"
    return "T2"


def label_level(row: dict, name: str):
    labs = row.get("labels")
    if not labs:
        return None
    v = labs.get(name)
    return v if v in LABEL_LEVELS[name] else None


# ── one cell test (the shared A/B engine) ───────────────────────────────────

def cell_test(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Everything the CANDIDATE conjunction needs for one (feature, cell).

    Criteria 2-5 are only computed when the floor (criterion 6) is met -- an
    UNDERPOWERED cell publishes its census and nothing is read from it.
    """
    dates_a = {str(r["date"]) for r in rows_a}
    dates_b = {str(r["date"]) for r in rows_b}
    dates = dates_a | dates_b
    out = dict(n_a=len(rows_a), n_b=len(rows_b), n_rows=len(rows_a) + len(rows_b),
               n_dates=len(dates), dates_a=len(dates_a), dates_b=len(dates_b),
               mean_a=_mean_R(rows_a), mean_b=_mean_R(rows_b),
               pf_a=P.pf(rows_a, "R"), pf_b=P.pf(rows_b, "R"),
               diff=float("nan"), ci=(float("nan"), float("nan")), p=float("nan"),
               ci_a=(float("nan"), float("nan")), ci_b=(float("nan"), float("nan")),
               pf_diff=None, loo=None, cuts={}, cut_n={}, ex_both=float("nan"),
               years={}, tiers={},
               floor_ok=False, ci_ok=False, loo_ok=False, cuts_ok=False,
               ex_both_ok=False, year_ok=False, tier_ok=False, bh_ok=False)
    # The registration's floor is declared on "ARM A / B cells (feature LEVEL x
    # structure x tier)", so it binds on EACH LEVEL, not on the pair: a 181-vs-1
    # split has 182 rows and 82 dates between them and is not a comparison.
    # Both groups must independently clear >= MIN_ROWS rows and
    # >= MIN_AFFECTED_DATES dates.
    out["floor_ok"] = (out["n_a"] >= MIN_ROWS and out["n_b"] >= MIN_ROWS
                       and out["dates_a"] >= MIN_AFFECTED_DATES
                       and out["dates_b"] >= MIN_AFFECTED_DATES)
    if not out["floor_ok"]:
        out["diff"] = out["mean_a"] - out["mean_b"]
        return out

    point, lo, hi, p = boot_ci_diff_by_date(rows_a, rows_b)
    out.update(diff=point, ci=(lo, hi), p=p)
    out["ci_ok"] = (lo == lo and hi == hi and (lo > 0 or hi < 0))
    out["ci_a"] = P.boot_ci_by_date(rows_a, key="R")
    out["ci_b"] = P.boot_ci_by_date(rows_b, key="R")
    out["pf_diff"] = P.pf_paired_by_date(rows_a, rows_b, key="R")

    sign = 1.0 if point > 0 else (-1.0 if point < 0 else 0.0)

    # Criterion 2, read in the direction the effect points: EVERY leave-one-
    # date-out fold must keep the sign, never flip. For a positive effect that
    # is `min_gain > 0`, which is the registration's wording and what
    # `protocol.loo_by_date` exposes; for a negative one the mirror test is
    # that the LEAST negative fold is still negative.
    gains = _loo_gains(rows_a, rows_b)
    out["loo"] = loo_diff_by_date(rows_a, rows_b)
    if not gains or sign == 0:
        out["loo_ok"] = False
    elif sign > 0:
        out["loo_ok"] = min(gains) > 0
    else:
        out["loo_ok"] = max(gains) < 0

    ca, cb = P.window_cuts(rows_a), P.window_cuts(rows_b)
    for cut in ca:
        a, b = ca[cut], cb.get(cut, [])
        out["cuts"][cut] = (_mean_R(a) - _mean_R(b)) if (a and b) else float("nan")
        out["cut_n"][cut] = len(a) + len(b)
    xa = [r for r in rows_a if str(r["date"])[:7] not in EX_BOTH_MONTHS]
    xb = [r for r in rows_b if str(r["date"])[:7] not in EX_BOTH_MONTHS]
    out["ex_both"] = (_mean_R(xa) - _mean_R(xb)) if (xa and xb) else float("nan")
    out["cut_n"]["ex_BOTH"] = len(xa) + len(xb)
    out["cuts_ok"] = all(v == v and (v * sign) > 0
                         for k, v in out["cuts"].items() if k != "ALL") and sign != 0
    out["ex_both_ok"] = out["ex_both"] == out["ex_both"] and (out["ex_both"] * sign) > 0

    out["years"] = year_diffs(rows_a, rows_b)
    out["year_ok"] = all_same_sign(out["years"].values(), sign)

    for tier in ("real", "tweak"):
        ta = [r for r in rows_a if r.get("source") == tier]
        tb = [r for r in rows_b if r.get("source") == tier]
        out["tiers"][tier] = (_mean_R(ta) - _mean_R(tb)) if (ta and tb) else float("nan")
    out["tier_ok"] = all(v == v and (v * sign) > 0 for v in out["tiers"].values())
    return out


def _loo_gains(rows_a, rows_b) -> list[float]:
    """Per-fold mean-R difference with one DATE left out. Fewer than three
    dates is no fold structure at all, matching `protocol.loo_by_date`."""
    dates = sorted({str(r["date"]) for r in rows_a} | {str(r["date"]) for r in rows_b})
    if len(dates) < 3:
        return []
    gains = []
    for d in dates:
        ka = [float(r["R"]) for r in rows_a if str(r["date"]) != d and r.get("R") is not None]
        kb = [float(r["R"]) for r in rows_b if str(r["date"]) != d and r.get("R") is not None]
        if ka and kb:
            gains.append(statistics.fmean(ka) - statistics.fmean(kb))
    return gains


CRITERIA_ORDER = (("1 CI", "ci_ok"), ("2 LOO", "loo_ok"), ("3 windows", "cuts_ok"),
                  ("3b ex-BOTH", "ex_both_ok"), ("4 year-sign", "year_ok"),
                  ("5 both-tiers", "tier_ok"), ("6 floor", "floor_ok"),
                  ("BH q=0.10", "bh_ok"))


def is_candidate(t: dict) -> bool:
    """The full conjunction. Failing any one is failing."""
    return all(bool(t.get(k)) for _, k in CRITERIA_ORDER)


def criteria_vector(t: dict) -> str:
    return "  ".join(f"{name}={'PASS' if t.get(key) else 'fail'}"
                     for name, key in CRITERIA_ORDER)


def print_cell(prefix: str, t: dict) -> None:
    if not t["floor_ok"]:
        print(f"    {prefix:<34} UNDERPOWERED  n={t['n_a']}/{t['n_b']} "
              f"dates={t['dates_a']}/{t['dates_b']} "
              f"(floor {MIN_ROWS} rows AND {MIN_AFFECTED_DATES} dates PER LEVEL)")
        return
    lo, hi = t["ci"]
    print(f"    {prefix:<34} n={t['n_a']}/{t['n_b']:<5} "
          f"dates={t['dates_a']}/{t['dates_b']:<5} "
          f"meanR {_fmt(t['mean_a'])} vs {_fmt(t['mean_b'])}  "
          f"dR={_fmt(t['diff'])} CI[{_fmt(lo,7,4)},{_fmt(hi,7,4)}] p={_fmt(t['p'],5,3)}  "
          f"PF {_fmt_pf(t['pf_a'])} vs {_fmt_pf(t['pf_b'])}")


# ── ARM C: gate arms on the shipped k=3 ladder replay ───────────────────────

DEMOTE_ONE_STEP = {"A": "B", "B": "C", "C": "C", "VETO": "VETO"}


def _picked_uids(picked) -> set:
    return {p["_uid"] for p in picked}


def gate_replay(rows: list[dict], level_fn, bad_level: str, mode: str) -> dict:
    """One ARM C gate arm: the shipped top-3/day ladder vs the same with the
    feature applied as a VETO or a one-step TIER DEMOTION.

    No other selection knob moves -- tier membership, structure universe, entry
    side, sizing and exits stay shipped. A row whose level is None is NOT
    EVALUABLE and is left alone: a gate cannot fire on a value that was never
    measured.
    """
    base = P.top_k_per_day(rows, P.ladder_rank, k=TOP_K, eligible_fn=P.ladder_eligible)

    if mode == "veto":
        def eligible(r):
            return P.ladder_eligible(r) and level_fn(r) != bad_level
        gated = P.top_k_per_day(rows, P.ladder_rank, k=TOP_K, eligible_fn=eligible)
    elif mode == "demote":
        shadow = []
        for r in rows:
            if level_fn(r) == bad_level:
                c = dict(r)
                c["tier"] = DEMOTE_ONE_STEP.get(r.get("tier"), r.get("tier"))
                shadow.append(c)
            else:
                shadow.append(r)
        gated = P.top_k_per_day(shadow, P.ladder_rank, k=TOP_K,
                                eligible_fn=P.ladder_eligible)
    else:                                                    # pragma: no cover
        raise ValueError(f"unknown gate mode {mode!r}")

    by_b: dict[str, list[dict]] = defaultdict(list)
    by_g: dict[str, list[dict]] = defaultdict(list)
    for p in base:
        by_b[str(p["date"])].append(p)
    for p in gated:
        by_g[str(p["date"])].append(p)

    affected = sorted(d for d in set(by_b) | set(by_g)
                      if _picked_uids(by_b.get(d, [])) != _picked_uids(by_g.get(d, [])))
    emptied = sorted(d for d in by_b if not by_g.get(d))

    paired = []
    for d in sorted(set(by_b) & set(by_g)):
        rb, rg = _mean_R(by_b[d]), _mean_R(by_g[d])
        if rb != rb or rg != rg:
            continue
        paired.append({"date": d, "R_base": rb, "R_gate": rg, "D": rg - rb})

    out = dict(mode=mode, bad_level=bad_level,
               n_base=len(base), n_gate=len(gated),
               dates_base=len(by_b), dates_gate=len(by_g),
               n_affected_dates=len(affected), n_emptied_dates=len(emptied),
               n_paired_dates=len(paired),
               mean_base=_mean_R(base), mean_gate=_mean_R(gated),
               pf_base=P.pf(base, "R"), pf_gate=P.pf(gated, "R"),
               diff=float("nan"), ci=(float("nan"), float("nan")), p=float("nan"),
               pf_diff=None, loo=None, cuts={}, cut_n={}, ex_both=float("nan"),
               years={}, tiers={},
               floor_ok=False, ci_ok=False, loo_ok=False, cuts_ok=False,
               ex_both_ok=False, year_ok=False, tier_ok=False, bh_ok=False,
               pf_up=False)
    out["floor_ok"] = out["n_affected_dates"] >= MIN_AFFECTED_DATES and len(paired) >= 3
    if not paired:
        return out
    out["diff"] = statistics.fmean([r["D"] for r in paired])
    if not out["floor_ok"]:
        return out

    lo, hi = P.boot_ci_paired_by_date(paired, "R_gate", "R_base")
    out["ci"] = (lo, hi)
    out["ci_ok"] = (lo == lo and hi == hi and (lo > 0 or hi < 0))
    # p-value for the per-arm BH control, from the same date-clustered
    # resample as the CI (the CI itself is criterion 1).
    out["p"] = _paired_p(paired)
    out["pf_diff"] = P.pf_paired_by_date(gated, base, key="R")
    out["pf_up"] = (out["pf_gate"] is not None and out["pf_base"] is not None
                    and out["pf_gate"] > out["pf_base"])

    sign = 1.0 if out["diff"] > 0 else (-1.0 if out["diff"] < 0 else 0.0)
    loo = P.loo_by_date(paired, lambda r: r["R_gate"], lambda r: r["R_base"])
    out["loo"] = loo
    gains = _paired_loo_gains(paired)
    out["loo_ok"] = bool(gains) and ((min(gains) > 0) if sign > 0 else
                                     (max(gains) < 0) if sign < 0 else False)

    for cut, rs in P.window_cuts(paired).items():
        out["cuts"][cut] = statistics.fmean([r["D"] for r in rs]) if rs else float("nan")
        out["cut_n"][cut] = len(rs)
    xb = [r for r in paired if str(r["date"])[:7] not in EX_BOTH_MONTHS]
    out["ex_both"] = statistics.fmean([r["D"] for r in xb]) if xb else float("nan")
    out["cut_n"]["ex_BOTH"] = len(xb)
    out["cuts_ok"] = sign != 0 and all(v == v and v * sign > 0
                                       for k, v in out["cuts"].items() if k != "ALL")
    out["ex_both_ok"] = out["ex_both"] == out["ex_both"] and out["ex_both"] * sign > 0

    _, _, ymeans = P.sign_stable(paired, key="D")
    out["years"] = ymeans
    out["year_ok"] = all_same_sign(ymeans.values(), sign)

    for tier in ("real", "tweak"):
        sub_rows = [r for r in rows if r.get("source") == tier]
        if not sub_rows:
            out["tiers"][tier] = float("nan")
            continue
        t = gate_replay_point(sub_rows, level_fn, bad_level, mode)
        out["tiers"][tier] = t
    out["tier_ok"] = sign != 0 and all(v == v and v * sign > 0 for v in out["tiers"].values())
    return out


def gate_replay_point(rows, level_fn, bad_level, mode) -> float:
    """The paired mean-R difference alone, for a pricing-tier sub-book."""
    base = P.top_k_per_day(rows, P.ladder_rank, k=TOP_K, eligible_fn=P.ladder_eligible)
    if mode == "veto":
        gated = P.top_k_per_day(rows, P.ladder_rank, k=TOP_K,
                                eligible_fn=lambda r: (P.ladder_eligible(r)
                                                       and level_fn(r) != bad_level))
    else:
        shadow = []
        for r in rows:
            if level_fn(r) == bad_level:
                c = dict(r)
                c["tier"] = DEMOTE_ONE_STEP.get(r.get("tier"), r.get("tier"))
                shadow.append(c)
            else:
                shadow.append(r)
        gated = P.top_k_per_day(shadow, P.ladder_rank, k=TOP_K,
                                eligible_fn=P.ladder_eligible)
    by_b, by_g = defaultdict(list), defaultdict(list)
    for p in base:
        by_b[str(p["date"])].append(p)
    for p in gated:
        by_g[str(p["date"])].append(p)
    ds = [d for d in set(by_b) & set(by_g)]
    if not ds:
        return float("nan")
    vals = []
    for d in ds:
        rb, rg = _mean_R(by_b[d]), _mean_R(by_g[d])
        if rb == rb and rg == rg:
            vals.append(rg - rb)
    return statistics.fmean(vals) if vals else float("nan")


def _paired_p(paired, n: int = BOOT_N, seed: int = BOOT_SEED) -> float:
    rng = random.Random(seed)
    dates = [r["date"] for r in paired]
    by = {r["date"]: r["D"] for r in paired}
    diffs = []
    for _ in range(n):
        pool = [by[rng.choice(dates)] for _ in range(len(dates))]
        diffs.append(statistics.fmean(pool))
    n_le = sum(1 for d in diffs if d <= 0)
    return min(1.0, 2.0 * min(n_le, len(diffs) - n_le) / len(diffs))


def _paired_loo_gains(paired) -> list[float]:
    dates = sorted({r["date"] for r in paired})
    if len(dates) < 3:
        return []
    out = []
    for d in dates:
        kept = [r for r in paired if r["date"] != d]
        if kept:
            out.append(statistics.fmean([r["D"] for r in kept]))
    return out


def print_gate(prefix: str, g: dict) -> None:
    if not g["floor_ok"]:
        print(f"    {prefix:<40} UNDERPOWERED  affected_dates={g['n_affected_dates']} "
              f"(floor {MIN_AFFECTED_DATES})  picks {g['n_base']}->{g['n_gate']}  "
              f"dR={_fmt(g['diff'])}")
        return
    lo, hi = g["ci"]
    print(f"    {prefix:<40} affected={g['n_affected_dates']:<4} picks {g['n_base']}->"
          f"{g['n_gate']}  meanR {_fmt(g['mean_base'])} -> {_fmt(g['mean_gate'])}  "
          f"dR={_fmt(g['diff'])} CI[{_fmt(lo,7,4)},{_fmt(hi,7,4)}] p={_fmt(g['p'],5,3)}  "
          f"PF {_fmt_pf(g['pf_base'])} -> {_fmt_pf(g['pf_gate'])}")


# ── population / census ─────────────────────────────────────────────────────

def cells_of(rows) -> list[tuple[str, str]]:
    """Every (structure, tier) present, largest first. Every one is reported
    regardless of outcome; the floor decides which are READ."""
    return [c for c, _ in Counter((r["structure"], r["tier"]) for r in rows).most_common()]


def census(rows, unpriced, diag, era: str) -> None:
    hdr(f"POPULATION & CENSUS — era {era} (registration s.Population and basis)")
    n_play_unpriced = [u for u in unpriced if u["reason"] not in ("market_row", "no_play")]
    total_play = len(rows) + len(n_play_unpriced)
    print(f"  era={diag['era']}  priced rows={len(rows)}  dates={diag['n_dates']}  "
          f"range={diag['date_range']}")
    print(f"  joined to AnalysisClaude: {diag['n_joined']}   "
          f"fallback (results/proxy text only): {diag['n_unjoined']}")
    print(f"  pricing tiers returned: {dict(Counter(r['source'] for r in rows))}   "
          f"counts_by_source={diag['counts_by_source']}   include_bs={diag['include_bs']}")
    n_bs = (diag["counts_by_source"] or {}).get("bs", 0)
    bs_note = ("a NO-OP on this era (ZERO bs_options_hist rows in the proxy export)"
               if not n_bs else
               f"a BINDING exclusion here ({n_bs} bs_options_hist rows dropped)")
    print("  include_bs=False is the 2026-08-11 standing hazard: real + "
          f"strike_expiry_tweak tiers only.\n    It is {bs_note}.")
    print(f"  debit calibration: {diag['debit_calib']}")
    print(f"  credit rows admitted UNGATED (calibrated=False): {diag['n_credit_ungated']}")
    print("  CREDIT-UNGATED CAVEAT: there is no single credit PROD that calibrates this "
          "sheet\n    (Attempt 13 removed the credit stop mid-book), so credit rows carry "
          "calibrated=False\n    and every credit-side number here is unvalidated until the "
          "book is split per credit-stop era.")
    st_c = Counter(r["structure"] for r in rows).most_common()
    ti_c = Counter(r["tier"] for r in rows).most_common()
    print("  structures: " + "  ".join(f"{k}={v}" for k, v in st_c))
    print("  tiers: " + "  ".join(f"{k}={v}" for k, v in ti_c))

    sub("Unpriced analysis rows (the missing part is NOT missing at random)")
    print(f"  unpriced total: {len(unpriced)}")
    for reason, n in diag["unpriced_by_reason"].most_common():
        print(f"    {reason:<18} {n}")
    if total_play:
        print(f"  PRICEABILITY: {len(rows)}/{total_play} = {len(rows)/total_play:.1%} of "
              f"PLAY rows became priced records.")
    print("  EVERY text-feature claim below is conditioned on that priceability share. "
          "No criterion\n  is evaluated on an unpriced row; the unpriced share BY FEATURE "
          "is reported as a\n  PROMPT-ROBUSTNESS read and is the only place an unpriced row "
          "carries a number.")

    years = sorted({str(r["date"])[:4] for r in rows})
    print(f"\n  calendar years present: {years}")
    if "2026" not in years:
        print("  THE 2026 NO-OP, STATED UP FRONT: this era's book carries ZERO 2026 signal "
              "dates, so\n  `ex_2026_feb_apr` == ALL, the hand-added ex-BOTH cut == "
              "`ex_2025_mar_apr`, and criterion 4\n  ('positive in every calendar year') "
              f"reduces to {' & '.join(years)}. Every cut prints its own n\n  beside ALL's, "
              "so a reader sees a no-op rather than a passed test. Any conjunction pass\n"
              "  citing year stability inherits this until 2026 dates land.")


def coverage_table(rows, diag, terciles: dict, excluded: dict) -> None:
    hdr("FEATURE COVERAGE on priced rows (a missing feature is NOT EVALUABLE, never imputed)")
    cov = diag["feature_coverage"]
    for k in TC.FEATURE_KEYS:
        note = TC.FEATURE_NOTES[k].replace("\n", " ")
        print(f"  {k:<28} {cov[k]:6.1%}   {note[:70]}")
    sub("Frozen tercile edges (cut on the FULL era book BEFORE any outcome was read)")
    for feat in CONTINUOUS_FEATURES:
        e = terciles.get(feat)
        if e is None:
            print(f"  {feat:<28} NOT CUT — fewer than 3 non-NaN values on this book")
            continue
        deg = " [DEGENERATE tercile edges -> binary >0 vs ==0 cut, declared here]" \
            if e[0] == e[1] else ""
        print(f"  {feat:<28} T1<= {e[0]:<12g} T3> {e[1]:<12g}   "
              f"NaN-excluded={excluded.get(feat, 0)}{deg}")


def unpriced_by_feature(rows, unpriced, terciles, degenerate) -> None:
    hdr("UNPRICED SHARE BY FEATURE — does vaguer text co-occur with unpriceable plays?")
    print("  A PROMPT-ROBUSTNESS read in its own right, and the ONLY place an unpriced row "
          "carries\n  a number. No criterion is evaluated here. Denominator = PLAY rows "
          "(market rows and\n  blank-play rows excluded); `hallucination_rate` is absent "
          "because it is measured on\n  priced rows only.")
    play_unpriced = [u for u in unpriced if u["reason"] not in ("market_row", "no_play")]
    both = [dict(features=r["features"], priced=True) for r in rows] + \
           [dict(features=u["features"], priced=False) for u in play_unpriced]
    for name, ga, gb, fn in BINARY_FEATURES:
        sub(f"{name}")
        for lvl in (ga, gb):
            sel = [x for x in both if fn(x["features"]) == lvl]
            if not sel:
                continue
            up = sum(1 for x in sel if not x["priced"])
            print(f"    {lvl:<16} n={len(sel):<5} unpriced={up:<5} share={up/len(sel):6.1%}")
    for feat in CONTINUOUS_FEATURES:
        if feat == "hallucination_rate":
            continue
        e = terciles.get(feat)
        if e is None:
            continue
        sub(f"{feat}")
        for lvl in ("T1", "T2", "T3"):
            sel = [x for x in both
                   if continuous_level({"features": x["features"]}, feat, e,
                                       degenerate.get(feat, False)) == lvl]
            if not sel:
                continue
            up = sum(1 for x in sel if not x["priced"])
            print(f"    {lvl:<16} n={len(sel):<5} unpriced={up:<5} share={up/len(sel):6.1%}")


# ── citation check (the hallucination arm) ──────────────────────────────────

def attach_hallucination(rows, mode: str, cache_dir: Path, log=print) -> dict:
    """Attach `row["hallucination_rate"]` where the date's input markdown is
    available. A row whose date has no cached/fetchable input is NOT EVALUABLE
    (None), never imputed to zero."""
    stats = dict(mode=mode, dates=0, covered=0, failed=0, cited=0, found=0,
                 rows_covered=0, reason="", errors=Counter())
    for r in rows:
        r["hallucination_rate"] = None
        r["cited_n"] = None
    if mode == "skip":
        stats["reason"] = "--citations skip: the hallucination arm was NOT RUN."
        return stats

    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_date[str(r["date"])[:10]].append(r)
    stats["dates"] = len(by_date)
    cache_dir = Path(cache_dir)
    for i, d in enumerate(sorted(by_date), start=1):
        cached = (cache_dir / f"{d}.md").exists()
        if mode == "cached" and not cached:
            continue
        try:
            res = TC.citation_check(d, cache_dir=cache_dir, rows=by_date[d])
        except Exception as exc:                                   # noqa: BLE001
            stats["failed"] += 1
            stats["errors"][type(exc).__name__] += 1
            if stats["failed"] <= 3:
                log(f"    citation fetch failed for {d}: {type(exc).__name__}: "
                    f"{str(exc)[:160]}")
            continue
        stats["covered"] += 1
        stats["cited"] += res["cited_n"]
        stats["found"] += res["found_n"]
        # Re-derive the per-row key exactly as `citation_check` assigned it.
        seen: dict[str, int] = {}
        for r in by_date[d]:
            t = str(r.get("ticker") or "?")
            n = seen.get(t, 1)
            key = t if n == 1 else f"{t}#{n}"
            seen[t] = n + 1
            cell = res["rows"].get(key)
            if not cell:
                continue
            r["cited_n"] = cell["cited_n"]
            if cell["cited_n"]:
                r["hallucination_rate"] = 1 - cell["found_n"] / cell["cited_n"]
                stats["rows_covered"] += 1
        if mode == "run" and i % 25 == 0:
            log(f"    citation check {i}/{len(by_date)} dates "
                f"(covered={stats['covered']} failed={stats['failed']})")
    if stats["covered"] == 0:
        stats["reason"] = (f"no date's analysis input was available "
                           f"({dict(stats['errors']) or 'no cached markdown'})")
    return stats


def print_citations(stats: dict, rows) -> None:
    hdr("CITATION CHECK — are the [FLOW] numbers the model cited actually on its own tape?")
    if stats["mode"] == "skip":
        print("  hallucination arm: NOT RUN (--citations skip).")
        return
    if stats["covered"] == 0:
        print(f"  hallucination arm: NOT EVALUABLE — {stats['reason']}.")
        print("  Nothing is imputed and no hallucination number is printed below.")
        return
    rate = (1 - stats["found"] / stats["cited"]) if stats["cited"] else None
    print(f"  mode={stats['mode']}  dates covered={stats['covered']}/{stats['dates']}"
          f"  fetch failures={stats['failed']} {dict(stats['errors']) or ''}")
    print(f"  cited tokens={stats['cited']}  found on the tape={stats['found']}  "
          f"overall unmatched rate={'n/a' if rate is None else f'{rate:.2%}'}")
    print(f"  priced rows with a measurable rate: {stats['rows_covered']}/{len(rows)} "
          f"({stats['rows_covered']/len(rows):.1%} of the book)")
    print("  COVERAGE IS NOT RANDOM: it follows which dates still have a fetchable input "
          "markdown.\n  An uncovered row is NOT EVALUABLE, never zero. A miss is EVIDENCE "
          "OF A MISS, not proof —\n  the markdown is re-fetched today from a Drive that may "
          "have been garbage-collected since.")


# ── contrast frames ─────────────────────────────────────────────────────────

def _binary_fn(fn):
    return lambda r: fn(r.get("features") or {})


def _continuous_fn(feat, edges, degenerate):
    return lambda r: continuous_level(r, feat, edges, degenerate)


def _label_fn(name):
    return lambda r: label_level(r, name)


def _one_vs_rest_fn(name, level):
    def f(r):
        v = label_level(r, name)
        if v is None:
            return None
        return level if v == level else "rest"
    return f


def arm_a_contrasts(terciles: dict, degenerate: dict) -> list[dict]:
    out = []
    for name, ga, gb, fn in BINARY_FEATURES:
        out.append(dict(feature=name, label=f"{ga} vs {gb}", a=ga, b=gb,
                        fn=_binary_fn(fn), kind="binary"))
    for feat in CONTINUOUS_FEATURES:
        e = terciles.get(feat)
        if e is None:
            continue
        deg = degenerate.get(feat, False)
        lab = ">0 vs ==0" if deg else "T3 vs T1"
        out.append(dict(feature=feat, label=lab, a="T3", b="T1",
                        fn=_continuous_fn(feat, e, deg), kind="continuous"))
    return out


def arm_b_contrasts() -> list[dict]:
    out = []
    for name, contrast in LABEL_CONTRASTS.items():
        if contrast is ONE_VS_REST:
            for level in LABEL_LEVELS[name]:
                out.append(dict(feature=name, label=f"{level} vs rest", a=level, b="rest",
                                fn=_one_vs_rest_fn(name, level), kind="label"))
        else:
            ga, gb = contrast
            out.append(dict(feature=name, label=f"{ga} vs {gb}", a=ga, b=gb,
                            fn=_label_fn(name), kind="label"))
    return out


def run_arm(arm: str, contrasts: list[dict], rows: list[dict],
            cells: list[tuple[str, str]]) -> list[dict]:
    """Every contrast x every structure x tier cell. Floors run FIRST and block
    everything; BH q=0.10 is applied over THIS arm's powered p-vector only."""
    tests = []
    for c in contrasts:
        for cell in cells:
            sel = [r for r in rows if (r["structure"], r["tier"]) == cell]
            ra = [r for r in sel if c["fn"](r) == c["a"]]
            rb = [r for r in sel if c["fn"](r) == c["b"]]
            if not ra and not rb:
                continue
            t = cell_test(ra, rb)
            t.update(arm=arm, feature=c["feature"], contrast=c["label"],
                     cell=cell, kind=c["kind"])
            tests.append(t)

    powered = [t for t in tests if t["floor_ok"]]
    flags = bh_reject([t["p"] for t in powered], BH_Q)
    for t, ok in zip(powered, flags):
        t["bh_ok"] = bool(ok)
    for t in tests:
        t["candidate"] = is_candidate(t)

    hdr(f"ARM {arm} — within structure x tier "
        f"({len(tests)} cells, {len(powered)} powered, BH q={BH_Q} over the powered p-vector)")
    print(f"  floors run FIRST and block everything: >= {MIN_ROWS} rows AND "
          f">= {MIN_AFFECTED_DATES} dates on EACH SIDE of the\n  contrast (the "
          "registration declares the floor on a cell = feature LEVEL x structure x tier).\n"
          "  A cell under either floor is UNDERPOWERED, printed with its n, and NO "
          "criterion is\n  evaluated on it. n and dates print as level_a/level_b "
          "throughout.")
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for t in tests:
        by_feature[t["feature"]].append(t)
    for feat in dict.fromkeys(c["feature"] for c in contrasts):
        sub(f"{feat}")
        for t in by_feature[feat]:
            print_cell(f"{t['cell'][0]}/{t['cell'][1]}  {t['contrast']}", t)
        for t in by_feature[feat]:
            if not t["floor_ok"]:
                continue
            print(f"      [{t['cell'][0]}/{t['cell'][1]} {t['contrast']}] "
                  f"{criteria_vector(t)}")
            print(f"        CI(a)={_fmt(t['ci_a'][0])},{_fmt(t['ci_a'][1])}  "
                  f"CI(b)={_fmt(t['ci_b'][0])},{_fmt(t['ci_b'][1])}  "
                  f"dPF={_fmt_pf(t['pf_diff'][0]) if t['pf_diff'] else 'n/a'} "
                  f"CI[{_fmt(t['pf_diff'][1],6,2) if t['pf_diff'] else 'n/a'},"
                  f"{_fmt(t['pf_diff'][2],6,2) if t['pf_diff'] else 'n/a'}]")
            loo = t["loo"] or (float('nan'),) * 4
            print(f"        LOO mean={_fmt(loo[0])} share_pos={_fmt(loo[1],5,2)} "
                  f"min_gain={_fmt(loo[2])} folds={loo[3]}   "
                  + "cuts=" + " ".join(f"{k}:{_fmt(v,7,4)}(n={t['cut_n'].get(k,0)})"
                                       for k, v in t["cuts"].items())
                  + f" ex_BOTH:{_fmt(t['ex_both'])}(n={t['cut_n'].get('ex_BOTH',0)})")
            years_s = " ".join(f"{y}:{_fmt(v,7,4)}" for y, v in t["years"].items())
            tiers_s = " ".join(f"{k}:{_fmt(v,7,4)}" for k, v in t["tiers"].items())
            print(f"        years={years_s}   tiers={tiers_s}")
    return tests


def evidence_control(rows, cells, terciles, degenerate) -> None:
    """`evidence_n` is a REDUNDANCY CONTROL, never a candidate.

    Printed for ONE purpose -- to show it adds nothing over `score_total` --
    which is what the partial below tests: within each `score_total` tercile,
    does the evidence_n contrast still separate? If the raw contrast is carried
    by `score_total`, the partial collapses.
    """
    hdr("REDUNDANCY CONTROL — evidence_n (may NOT be promoted to a candidate "
        "under any outcome)")
    e = terciles.get(CONTROL_FEATURE)
    print("  evidence_n counts [TAG] items only: the untagged continuation lines in the "
          "signal\n  cells are attached to the item above them, not counted as separate "
          "evidence.")
    if e is None:
        print("  NOT CUT — fewer than 3 non-NaN values on this book.")
        return
    fn = _continuous_fn(CONTROL_FEATURE, e, degenerate.get(CONTROL_FEATURE, False))
    sub("raw contrast (T3 vs T1), within structure x tier")
    for cell in cells:
        sel = [r for r in rows if (r["structure"], r["tier"]) == cell]
        ra = [r for r in sel if fn(r) == "T3"]
        rb = [r for r in sel if fn(r) == "T1"]
        if not ra and not rb:
            continue
        t = cell_test(ra, rb)
        print_cell(f"{cell[0]}/{cell[1]}  T3 vs T1", t)

    sub("PARTIAL on score_total — the same contrast INSIDE each score_total tercile")
    st_vals = sorted(float(r["score_total"]) for r in rows
                     if r.get("score_total") not in (None, "")
                     and float(r["score_total"]) == float(r["score_total"]))
    if len(st_vals) < 3:
        print("    score_total unavailable on this book — the partial cannot be computed.")
        return
    lo, hi = st_vals[len(st_vals) // 3], st_vals[2 * len(st_vals) // 3]
    print(f"    score_total terciles cut on the full era book: S1<= {lo:g}  S3> {hi:g}  "
          f"(n={len(st_vals)})")

    def st_level(r):
        v = r.get("score_total")
        if v in (None, ""):
            return None
        v = float(v)
        if v != v:
            return None
        return "S1" if v <= lo else ("S3" if v > hi else "S2")

    corr = _corr([float(r["score_total"]) for r in rows
                  if r.get("score_total") not in (None, "")
                  and (r["features"] or {}).get(CONTROL_FEATURE) is not None],
                 [float(r["features"][CONTROL_FEATURE]) for r in rows
                  if r.get("score_total") not in (None, "")
                  and (r["features"] or {}).get(CONTROL_FEATURE) is not None])
    print(f"    corr(evidence_n, score_total) = {_fmt(corr)}")
    for slev in ("S1", "S2", "S3"):
        for cell in cells:
            sel = [r for r in rows if (r["structure"], r["tier"]) == cell
                   and st_level(r) == slev]
            ra = [r for r in sel if fn(r) == "T3"]
            rb = [r for r in sel if fn(r) == "T1"]
            if not ra and not rb:
                continue
            t = cell_test(ra, rb)
            print_cell(f"{slev}  {cell[0]}/{cell[1]}  T3 vs T1", t)
    print("\n    READ: evidence_n is reported to show it adds nothing over score_total. "
          "It is NOT a\n    candidate under any outcome above, by pre-registration.")


def _corr(xs, ys):
    if len(xs) < 3 or len(xs) != len(ys):
        return float("nan")
    try:
        return statistics.correlation(xs, ys)
    except (statistics.StatisticsError, ValueError):
        return float("nan")


# ── ARM C runner ────────────────────────────────────────────────────────────

def worse_level(rows, fn, ga: str, gb: str) -> tuple[str, float, float]:
    """The level a gate would remove: whichever of the two contrast groups has
    the lower pooled mean R on the era book. DESCRIPTIVE and printed -- it fixes
    the DIRECTION of the gate, never whether the gate clears anything."""
    a = [r for r in rows if fn(r) == ga]
    b = [r for r in rows if fn(r) == gb]
    ma, mb = _mean_R(a), _mean_R(b)
    if ma != ma or mb != mb:
        return (gb, ma, mb)
    return ((ga, ma, mb) if ma < mb else (gb, ma, mb))


def run_arm_c(rows, contrasts_a, contrasts_b, candidates: set[str]) -> list[dict]:
    hdr("ARM C — gate arms: shipped ladder top-3/day vs the same with the feature "
        "as a VETO / one-step TIER DEMOTION")
    base = P.top_k_per_day(rows, P.ladder_rank, k=TOP_K, eligible_fn=P.ladder_eligible)
    bs = P.replay_stats(base)
    print(f"  SHIPPED BASELINE (protocol.top_k_per_day(rank_fn=ladder_rank, k={TOP_K}), "
          f"eligible = tiers A+B):")
    print(f"    picks={bs['n']}  dates={bs['dates']}  mean R={_fmt(bs['mean_R'])}  "
          f"PF={_fmt_pf(P.pf(base,'R'))}  win={_fmt(bs['win'],5,3)}")
    print("    R is quoted, never dollars (contract counts differ across gated books).")
    print(f"  No other selection knob moves: tier membership, structure universe, entry "
          "side,\n  sizing and exits stay shipped. FLOOR: >= "
          f"{MIN_AFFECTED_DATES} dates on which the gate CHANGES\n  the picked set — a date "
          "where the gate is inert is not affected.")
    cand_s = (str(sorted(candidates)) if candidates else
              "NONE — every gate arm below is DESCRIPTIVE ONLY and proposes nothing")
    print(f"  Features reaching CANDIDATE in ARM A/B: {cand_s}")

    out = []
    for c in (*contrasts_a, *contrasts_b):
        bad, ma, mb = worse_level(rows, c["fn"], c["a"], c["b"])
        for mode in ("veto", "demote"):
            g = gate_replay(rows, c["fn"], bad, mode)
            g.update(feature=c["feature"], contrast=c["label"], kind=c["kind"],
                     mean_a=ma, mean_b=mb,
                     registered=(c["feature"] in candidates))
            out.append(g)

    powered = [g for g in out if g["floor_ok"]]
    for g, ok in zip(powered, bh_reject([g["p"] for g in powered], BH_Q)):
        g["bh_ok"] = bool(ok)
    for g in out:
        g["candidate"] = is_candidate(g)

    by_feature: dict[str, list[dict]] = defaultdict(list)
    for g in out:
        by_feature[g["feature"]].append(g)
    for feat, gs in by_feature.items():
        tag = ("CANDIDATE in A/B" if gs[0]["registered"]
               else "DESCRIPTIVE ONLY (not an A/B candidate)")
        sub(f"{feat} — gate removes level {gs[0]['bad_level']!r}  [{tag}]")
        print(f"    pooled mean R by contrast group: {gs[0]['contrast']} -> "
              f"{_fmt(gs[0]['mean_a'])} / {_fmt(gs[0]['mean_b'])}")
        for g in gs:
            print_gate(f"{g['mode'].upper():<7} {g['contrast']}", g)
            if not g["floor_ok"]:
                continue
            print(f"      {criteria_vector(g)}")
            loo = g["loo"] or (float('nan'),) * 4
            print(f"        emptied_dates={g['n_emptied_dates']} paired_dates="
                  f"{g['n_paired_dates']}  LOO mean={_fmt(loo[0])} "
                  f"share_pos={_fmt(loo[1],5,2)} min_gain={_fmt(loo[2])} folds={loo[3]}")
            print("        cuts=" + " ".join(
                f"{k}:{_fmt(v,7,4)}(n={g['cut_n'].get(k,0)})" for k, v in g["cuts"].items())
                + f" ex_BOTH:{_fmt(g['ex_both'])}(n={g['cut_n'].get('ex_BOTH',0)})")
            print("        years=" + " ".join(f"{y}:{_fmt(v,7,4)}" for y, v in g["years"].items())
                  + "   tiers=" + " ".join(f"{k}:{_fmt(v,7,4)}" for k, v in g["tiers"].items())
                  + f"   PF up={g['pf_up']}")
    print("\n  MFE/MAE give-back is DESCRIPTIVE and is NOT A CRITERION anywhere in this "
          "study; it is\n  not computed above. A PF claim must ALSO clear the mean-R "
          "criterion — PF alone is\n  gameable by fewer, larger wins.")
    return out


# ── verdicts ────────────────────────────────────────────────────────────────

def feature_verdict(tests: list[dict]) -> tuple[str, list[dict]]:
    """UNDERPOWERED / NULL / CANDIDATE for one feature, plus the passing cells."""
    powered = [t for t in tests if t["floor_ok"]]
    if not powered:
        return "UNDERPOWERED", []
    hits = [t for t in powered if t["candidate"]]
    return ("CANDIDATE" if hits else "NULL"), hits


def verdicts(a_tests, b_tests, c_tests, arm_b_ran: bool, cit_stats: dict,
             era: str, label_stats: dict) -> None:
    hdr("VERDICT — registration grammar (UNDERPOWERED / NULL / CANDIDATE, "
        "catch-all NO PRE-REGISTERED VERDICT MATCHES)")

    prompt_findings: list[str] = []
    gate_candidates: list[str] = []
    unmatched: list[str] = []

    def emit(arm_name: str, tests: list[dict], declared: tuple[str, ...]) -> dict[str, str]:
        by_feature: dict[str, list[dict]] = defaultdict(list)
        for t in tests:
            by_feature[t["feature"]].append(t)
        verds = {}
        print(f"\n  ARM {arm_name}:")
        if not by_feature:
            print("    (no cell computed)")
        for feat in declared:
            if feat not in by_feature:
                # A registered feature with no cell at all: the input it needs was
                # never available on this book. NOT EVALUABLE is not a null.
                print(f"    {feat:<28} {'NOT EVALUABLE':<14} no cell could be formed "
                      "(the feature's input was unavailable on this book)")
                verds[feat] = "NOT EVALUABLE"
        for feat, ts in by_feature.items():
            v, hits = feature_verdict(ts)
            verds[feat] = v
            powered = sum(1 for t in ts if t["floor_ok"])
            print(f"    {feat:<28} {v:<14} cells={len(ts)} powered={powered}")
            for t in hits:
                print(f"        CANDIDATE cell {t['cell'][0]}/{t['cell'][1]} "
                      f"[{t['contrast']}]: dR={_fmt(t['diff'])} "
                      f"CI[{_fmt(t['ci'][0],7,4)},{_fmt(t['ci'][1],7,4)}] "
                      f"n={t['n_a']}/{t['n_b']} dates={t['dates_a']}/{t['dates_b']}")
                print(f"        criteria: {criteria_vector(t)}")
                prompt_findings.append(
                    f"{feat} [{t['contrast']}] in {t['cell'][0]}/{t['cell'][1]} "
                    f"(ARM {arm_name}, dR={t['diff']:+.4f})")
        return verds

    emit("A (deterministic text features)", a_tests, ARM_A_DECLARED)
    if arm_b_ran:
        emit("B (blind taxonomy labels)", b_tests, tuple(LABEL_LEVELS))
    else:
        print("\n  ARM B: NOT RUN — no labels were available "
              f"({label_stats.get('mode')} mode, "
              f"{label_stats.get('labelled', 0)} rows labelled).")

    print("\n  ARM C (gate arms):")
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for g in c_tests:
        by_feature[g["feature"]].append(g)
    for feat, gs in by_feature.items():
        powered = [g for g in gs if g["floor_ok"]]
        hits = [g for g in powered if g["candidate"]]
        v = "UNDERPOWERED" if not powered else ("CANDIDATE" if hits else "NULL")
        print(f"    {feat:<28} {v:<14} arms={len(gs)} powered={len(powered)}")
        for g in hits:
            print(f"        criteria: {criteria_vector(g)}  PF {_fmt_pf(g['pf_base'])} -> "
                  f"{_fmt_pf(g['pf_gate'])} (up={g['pf_up']})")
            line = (f"{feat} as a {g['mode'].upper()} of {g['bad_level']!r} "
                    f"(dR={g['diff']:+.4f}, affected dates={g['n_affected_dates']})")
            if g["pf_up"] and g["diff"] > 0:
                gate_candidates.append(line)
            else:
                unmatched.append(
                    f"ARM C {line}: the conjunction cleared but the registration's "
                    f"ENTRY-GATE list requires the gate to raise mean R AND PF "
                    f"(mean R {'up' if g['diff'] > 0 else 'DOWN'}, PF up={g['pf_up']})")

    sub("PROMPT-ROBUSTNESS FINDINGS")
    print("  (text predicts failure independent of the numeric columns; feeds "
          "`prompt_eval`'s\n  `draft` mode, nothing more — NOT a ship)")
    if prompt_findings:
        for f in prompt_findings:
            print(f"    - {f}")
    else:
        print("    none")

    sub("ENTRY-GATE CANDIDATES")
    print("  (an ARM C gate raising mean R AND PF under the k=3 replay; would feed a "
          "written\n  `docs/deployment-rules.md` PROPOSAL for the operator — NOT a ship, "
          "and queued behind an\n  independent-window confirmation)")
    if gate_candidates:
        for f in gate_candidates:
            print(f"    - {f}")
    else:
        print("    none")

    if unmatched:
        sub("NO PRE-REGISTERED VERDICT MATCHES")
        print("  (the registration's catch-all: resolved by hand in research/current.md)")
        for u in unmatched:
            print(f"    - {u}")

    sub("Standing caveats carried by every line above")
    print(f"  - era {era}; the PRIMARY era is `current` (v4). A v3 result is reported "
          "and carries\n    nothing — a finding about v3 text is a finding about a dead "
          "prompt.")
    print("  - every claim is conditioned on the priceability share printed in the census; "
          "no\n    criterion was evaluated on an unpriced row.")
    print("  - text length is confounded with structure complexity, so `thesis_len` / "
          "`alt_ratio`\n    are never read pooled; every test above is within structure "
          "AND within tier.")
    print("  - the thesis restates the regime the ladder already conditions on, so a "
          "within-tier\n    'finding' cannot be the ladder read back.")
    if arm_b_ran:
        print("  - EVERY label-derived line inherits the labeller's own recall risk: date "
              "and ticker\n    are STRIPPED from its input and the cache key is that "
              "stripped text, which REDUCES\n    the risk and does not eliminate it.")
    if cit_stats.get("covered"):
        print(f"  - `hallucination_rate` coverage is not random ({cit_stats['covered']}/"
              f"{cit_stats['dates']} dates); an\n    uncovered row is NOT EVALUABLE, "
              "not zero.")
    print("  - `evidence_n` is a redundancy control and appears in no list above, by "
          "pre-registration.")
    print("  - no annualised figure, Sharpe or time-to-recover is printed anywhere in this "
          "report;\n    PF never prints without mean R beside it.")


# ── per-row CSV for the charts / review layer ───────────────────────────────

def write_rows_csv(rows, era: str, path: Path) -> Path:
    cols = (["date", "ticker", "structure", "tier", "source", "credit", "post13c",
             "R", "E", "mfe", "mae", "days_held", "exit_reason", "score_total",
             "joined", "cited_n", "hallucination_rate"]
            + list(TC.FEATURE_KEYS) + list(LABEL_LEVELS))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            f = r.get("features") or {}
            labs = r.get("labels") or {}
            w.writerow([
                r["date"], r["ticker"], r["structure"], r["tier"], r["source"],
                r.get("credit"), r.get("post13c"), r.get("R"), r.get("E"),
                r.get("mfe"), r.get("mae"), r.get("days_held"), r.get("exit_reason"),
                r.get("score_total"), (r.get("text") or {}).get("joined"),
                r.get("cited_n"), r.get("hallucination_rate"),
                *[f.get(k) for k in TC.FEATURE_KEYS],
                *[labs.get(k) for k in LABEL_LEVELS]])
    return path


# ── main ────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", choices=("run", "cached", "skip"), default="cached",
                    help="ARM B: 'run' labels every uncached row with the headless "
                         "labeller (NETWORK + model cost, resumable); 'cached' uses only "
                         "what is already in backtests/text_labels_cache/ (the default, so "
                         "`run --all` never spends); 'skip' prints ARM B as NOT RUN.")
    ap.add_argument("--citations", choices=("run", "cached", "skip"), default="cached",
                    help="hallucination arm: 'run' re-fetches each date's analysis INPUT "
                         "markdown through Drive (read-only, cached, resumable); 'cached' "
                         "reads only dates already cached; 'skip' does not evaluate it.")
    ap.add_argument("--label-model", default=LABEL_MODEL)
    ap.add_argument("--label-batch", type=int, default=LABEL_BATCH)
    ap.add_argument("--label-workers", type=int, default=LABEL_WORKERS,
                    help="concurrent labeller batches (same calls, less wall clock)")
    ap.add_argument("--label-cache", default=str(LABEL_CACHE))
    ap.add_argument("--citation-cache", default=str(TC.CITATION_CACHE))
    ap.add_argument("--rows-csv", default=None,
                    help="override the per-row CSV path (default "
                         "backtests/study_output/text_features-<era>-rows.csv)")
    args = ap.parse_args(argv)

    from scripts.backtest_study.lib import era as era_mod
    era = era_mod.requested_era()

    # include_bs=False: the 2026-08-11 standing hazard. A NO-OP on v4 (zero
    # bs_options_hist rows in that proxy export) and still binding on v3.
    rows, unpriced, diag = TC.load_corpus(era=era, include_bs=False)
    for i, r in enumerate(rows):
        r["_uid"] = i

    census(rows, unpriced, diag, era)

    # The hallucination arm must run BEFORE the terciles are cut: it is one of
    # the continuous features and its edges come off the full era book.
    if args.citations != "skip":
        print("\n  [citation check running — read-only Drive fetch, cached, resumable]")
    cit_stats = attach_hallucination(rows, args.citations, Path(args.citation_cache))
    print_citations(cit_stats, rows)

    terciles, excluded, degenerate = {}, {}, {}
    for feat in (*CONTINUOUS_FEATURES, CONTROL_FEATURE):
        vals = [_raw(r, feat) for r in rows]
        excluded[feat] = sum(1 for v in vals if v is None or v != v)
        e = tercile_edges(rows, feat)
        terciles[feat] = e
        degenerate[feat] = bool(e is not None and e[0] == e[1])
    coverage_table(rows, diag, terciles, excluded)

    sub("DESCRIPTIVE 5-level invalidation_type census (no criterion is evaluated on it)")
    for k, v in Counter(r["features"]["invalidation_type"] for r in rows).most_common():
        print(f"    {k:<12} {v:<5} ({v/len(rows):.1%})")
    sub("DESCRIPTIVE companion features (printed beside their feature, never tested alone)")
    for feat in COMPANION_FEATURES:
        vals = [v for v in (_raw(r, feat) for r in rows) if v is not None and v == v]
        if vals:
            print(f"    {feat:<12} n={len(vals)} mean={statistics.fmean(vals):.2f} "
                  f"median={statistics.median(vals):.2f} "
                  f"min={min(vals):g} max={max(vals):g}")

    unpriced_by_feature(rows, unpriced, terciles, degenerate)

    print("\n  [ARM B labelling — the labeller sees ONLY the five text fields, with "
          "ticker and\n   date stripped; the cache key is sha256 of that exact payload]")
    label_stats = label_rows(rows, model=args.label_model, batch=args.label_batch,
                             cache_dir=Path(args.label_cache), mode=args.labels,
                             workers=args.label_workers)
    print(f"  labeller: model={args.label_model}  batch={args.label_batch}  "
          f"workers={args.label_workers}")
    print(f"  labeller: mode={label_stats['mode']}  unique payloads="
          f"{label_stats['unique']}  cache hits={label_stats['cached']}  "
          f"claude calls={label_stats['calls']}  retries={label_stats['retries']}  "
          f"rows labelled={label_stats['labelled']}  rows UNLABELLED="
          f"{label_stats['invalid']}  batch failures={label_stats['failures']}")
    if rows:
        print(f"  ARM B label coverage: {label_stats['labelled']}/{len(rows)} priced rows "
              f"({label_stats['labelled']/len(rows):.1%}). An UNLABELLED row is NOT "
              "EVALUABLE in ARM B,\n  never imputed; label coverage is not random and every "
              "ARM B cell prints its own n.")

    cells = cells_of(rows)
    contrasts_a = arm_a_contrasts(terciles, degenerate)
    a_tests = run_arm("A", contrasts_a, rows, cells)
    evidence_control(rows, cells, terciles, degenerate)

    arm_b_ran = label_stats["labelled"] > 0
    contrasts_b = arm_b_contrasts() if arm_b_ran else []
    if arm_b_ran:
        b_tests = run_arm("B", contrasts_b, rows, cells)
        sub("ARM B label distribution (priced rows)")
        for name in LABEL_LEVELS:
            c = Counter(label_level(r, name) for r in rows)
            print(f"    {name:<28} " + "  ".join(f"{k}={v}" for k, v in c.most_common()))
    else:
        b_tests = []
        hdr("ARM B — NOT RUN")
        print(f"  --labels {args.labels}: {label_stats['labelled']} rows carry a label, so "
              "no blind-label\n  cell is computed and no criterion is evaluated. The five "
              "level sets stay as registered.")

    candidates = {t["feature"] for t in (*a_tests, *b_tests)
                  if t["candidate"] and t["feature"] != CONTROL_FEATURE}
    c_tests = run_arm_c(rows, contrasts_a, contrasts_b, candidates)

    verdicts(a_tests, b_tests, c_tests, arm_b_ran, cit_stats, era, label_stats)

    out = Path(args.rows_csv) if args.rows_csv else \
        OUT_DIR / f"text_features-{era}-rows.csv"
    write_rows_csv(rows, era, out)
    print(f"\nper-row features + labels + outcomes -> {out.relative_to(ROOT)} "
          f"({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
