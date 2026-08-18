# Recommendations column reference

Column definitions for the **Recommendations** Google Sheet tab (in
`TRADE_JOURNAL_SPREADSHEET_ID`, the same workbook as TradeJournal) and its local mirror
`journal/recommendations.csv`, both written by
[`scripts/journal/s07_recwriter.py`](../scripts/journal/s07_recwriter.py) from the deploy card
that [`s06_recommend.py`](../scripts/journal/s06_recommend.py) builds. The schema is
`RECOMMENDATION_COLUMNS` in [`scripts/journal/config.py`](../scripts/journal/config.py) — 44
columns, written positionally, so the tab header must gain any new column at the end.

Produced by `python3 -m scripts.journal recommend`. TradeJournal records what was *traded*;
this tab records what was *recommended* — one loop, two halves.

## What one row is

**One candidate the ranker evaluated on one run — including the ones it threw away.** A card
that emitted 3 deploy picks, 1 hedge and 6 rejects writes 10 rows, not 3. The columns answer
four questions in order:

1. **Which run produced this?** (§1)
2. **What did the deterministic ranker decide?** (§2–§4)
3. **What did the model say about it afterwards?** (§5)
4. **What context did the whole card stand on?** (§6)

The record is **append-only and generational**. Nothing is ever overwritten: an unchanged re-run
appends nothing at all, and a re-run whose content changed appends a *new* row at
`generation = n+1` beside the old one. So one `(session_date, ticker)` can legitimately appear
several times.

Provenance below is given as `file::function`, not `file:line` — line numbers rot.

## §1 Run identity and timing

Set once per run, identical on every row of the card. Source:
`s07_recwriter.py::to_rows` (the `common` dict).

| Column | Definition | Blank when |
|---|---|---|
| `session_date` | ISO date of the **analysis session** the card ranked — the AnalysisClaude rows it read. Chosen by `lib/analysis.py::latest_date_on_or_before()`, never the unbounded `latest_date()`. | never |
| `as_of_date` | ISO date the card was built **for** — `--as-of`, defaulting to today. The card may look at nothing dated after this. | never |
| `generated_at_utc` | ISO-8601 UTC wall clock of the run. Excluded from the content hash, so re-running at a different time does not by itself make a new row. | never |
| `staleness_days` | `as_of_date − session_date` in days. Bounded by `RECOMMENDATION_MAX_AGE_DAYS`; see the note below. | never |
| `rec_id` | Row identity — see below. | never |
| `generation` | How many times this play has been recorded for this session — see below. | never |

**The two refusals are not the same thing.** `s06_recommend.py::check_freshness` raises on
analysis older than `RECOMMENDATION_MAX_AGE_DAYS` (overridable with `--allow-stale`, which
stamps `stale_override=True`), and raises **unconditionally** on analysis dated *after*
`as_of_date`. The second is lookahead, not staleness, and `--allow-stale` never reaches it. A
row therefore always has `staleness_days >= 0`.

### `rec_id`

```
session_date | as_of_date | role | ticker | structure | <sha256 of the row's content>[:12]
```

Readable at the front so the tab can be eyeballed, hashed at the back so an unchanged re-run
collides with itself and is dropped before the append. `s07_recwriter.py::content_hash` iterates
`RECOMMENDATION_COLUMNS` in order (not the dict, so it is stable across processes) and skips
`REC_IDENTITY_EXCLUDED` = (`rec_id`, `generation`, `generated_at_utc`) — the row's identity and
its wall clock are not part of its content.

### `generation`

A 1-based counter within `_GEN_KEY = (session_date, role, ticker, structure)`, stamped by
`s07_recwriter.py::_assign_generations` **after** the duplicate drop and excluded from the hash,
so it can never make a duplicate look new.

- `generation = 1` — the first time this play was recorded for this session.
- `generation = 2` — the card was re-run and **something in the content changed**: a judge
  verdict, a cap-headroom result, a duplicate-exposure flag, a rank. The earlier row is left
  exactly as it was.

It does **not** mean "the second play", and it does not increment merely because time passed.
Append-only was chosen over replace-on-change deliberately: if the 07:00 card said DEPLOY and
the 15:00 re-run says RESERVE, both are true statements about their own moment, and overwriting
the first would destroy the only record of what was actually acted on.

## §2 What the deterministic ranker decided

Source: `s06_recommend.py::rank`, serialised by `s07_recwriter.py::_candidate_row` (candidates)
and `::_rejected_row` (rejects). This half of the row is produced **before** the model is called
and is never re-sorted afterwards.

| Column         | Definition                                                                                                                                                                                                                                 | Blank when                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `role`         | Which set the play landed in: `deploy` · `hedge` · `veto` · `tier_c`. See below.                                                                                                                                                           | never                                                         |
| `rank`         | 1-based position **within its own role**, in the deterministic order `rank()` produced. There is a rank 1 deploy *and* a rank 1 hedge.                                                                                                     | on `veto`/`tier_c` rows — the rejected sets carry no ordering |
| `deploy`       | `True` for the top `DEPLOY_BUDGET` (= 3) `deploy`-role candidates. `False` on a `deploy`-role row means **reserve** (budget exceeded), not rejected.                                                                                       | never                                                         |
| `tier`         | `ladder_tier()`'s own label: `A` · `B` · `C` · `VETO`.                                                                                                                                                                                     | never                                                         |
| `tier_partial` | `True` when the tier gate was not fully verified — see below.                                                                                                                                                                              | never                                                         |
| `tier_reason`  | `ladder_tier()`'s own sentence, e.g. `other bull_call_spread` or `bull_put delta 0.15 in [0.08,0.20] and DTE 45<=59`. On a rejected row this is `Rejected.reason`, which prefixes `capital-constrained:` for Tier C.                       | never                                                         |
| `reasons`      | The semicolon-joined audit chain `rank()` built for the candidate: `structure=…`; `market regime=…`; `ladder_tier=…`; any §1.4 hedge-only override; the duplicate-exposure line if any; the headroom note; and the deploy/reserve verdict. | never on a candidate row; always on a rejected row            |

### `role` — the four values, and where each comes from

| Value | Branch in `rank()` | Meaning |
|---|---|---|
| `deploy` | Tier A or B, survived §1's vetoes, not a bear debit | A selection play. Ordered Tier A before Tier B, with `score_total` a tie-break **within** a tier only — it can never move a play between tiers. |
| `hedge` | structure in `_HEDGE_ONLY_STRUCTURES` = `bear_put_spread`, `long_put` | A §4 hedge-sleeve candidate. `docs/deployment-rules.md` §1.4 makes bear debit hedge-only — never a selection play, however thin the day's A/B supply. Ordered by `|delta|` descending, **never** by `score_total`. |
| `veto` | `ladder_tier()` returned `VETO` | Excluded from **both** the deploy set and the hedge sleeve. Fires on the `bear_call_spread` intake veto, a `BEAR + H-VOL` regime, or a credit play in `RANGE + L-VOL`. |
| `tier_c` | Tier C **on the deploy path** | Capital-constrained; dropped from the card but kept as the record of what was considered. |

**`role` and `tier` are independent — filter rejects on `role`, never on `tier`.** The §1.4
hedge-only branch runs *before* the Tier-C rejection, so a hedge candidate that `ladder_tier()`
labelled `C` is still `role=hedge`: a live hedge pick, not a reject. `role=tier_c` only ever
means "Tier C on the deploy path". A query that treats `tier == "C"` as "rejected" silently
throws away the hedge sleeve.

### `tier_partial`

`ladder_tier()`'s second return value. **`True` means the tier gate was not fully verified — read
the tier as provisional.**

Only `bull_put_spread` can ever be partial, because it is the only structure whose gate
(`docs/deployment-rules.md` §3) has two conditions: short-leg `0.08 <= |delta| <= 0.20` **and**
`DTE <= 59`. Three cases:

- **no `short_leg_delta` on the analysis row** — the normal case today, since §3 says delta and
  DTE are read at IBKR order entry rather than off the row. The DTE proxy alone decides, the
  result is `partial=True`, and `tier_reason` says `delta UNVERIFIED`.
- **delta supplied and DTE known** — both conditions checked for real, `partial=False`, and
  `tier_reason` names which one failed if either did.
- **delta supplied but DTE is NaN** — Tier `C` with `partial=True`. An unknown DTE is never
  silently treated as passing.

Every other structure returns `partial=False` unconditionally, so `tier_partial=False` on a
`bull_call_spread` means **"not applicable"**, not "verified".

## §3 The play itself

Copied off the analysis row, with two reshaping steps noted below. Source: `rank()`'s read of
the AnalysisClaude row.

| Column | Definition | Blank when |
|---|---|---|
| `ticker` | Underlying symbol, uppercased. | never |
| `structure` | Canonical structure name from `mapping.play_structure()` — `bull_call_spread`, `bull_put_spread`, `bear_put_spread`, `long_put`, … The single canonicalisation lives in `lib/structure_names.py`. | never |
| `market_regime` | The regime **label only** — `BULL + C-VOL + RISK-ON` — with its justification paragraph stripped by `s06_recommend.py::_regime_label`. Identical on every row of a session. `ladder_tier()` still receives the untruncated string; this is display. | never (renders `(none)` if the analysis had none) |
| `score_total` | The conviction score off the analysis row. **A within-tier tie-break and nothing else.** | the analysis row had no score |
| `horizon` | The play's horizon as the analysis wrote it (days). | not present on the row |
| `play` | One-line headline, ≤160 chars, from `s06_recommend.py::_play_headline`: the play cell's lines joined, stopping at the `Alt:` block, ellipsised if long. | never (renders `(none given)`) |
| `trigger` | The condition to check at the open before entering. | not present on the row |
| `invalidation` | When to abandon the thesis. | not present on the row |
| `alternative_interpretation` | The `Alt:` block `_play_headline` removed, recovered by `s06_recommend.py::_extract_alt`. There is no dedicated sheet column — `analysis_pipeline/core.py::analysis_to_rows` folds it into the play cell, and this is that operation's inverse. | the play cell had no `Alt:` line |
| `delta` | Per-contract delta, if the analysis row carried one. | **normally** — `delta` is not in `ROW_COLUMNS`, so `_optional_float` returns `None` and nothing invents one. §3 reads delta at IBKR order entry. |

> **`score_total` does not compare across prompt versions.** v3 ran 0–100; v4 runs 0–50 (0–55
> for VOLATILITY-intent plays) after `score_flow`/`score_dealer` were dropped. A card built on
> v3 rows and one built on v4 rows carry numbers on different scales. Within one card it is a
> tie-break inside a tier; it carries no other signal. See `docs/conviction-score.md`.

## §4 Book checks — advisory, never filters

Source: `s06_recommend.py::_headroom` and the `open_tickers` set in `rank()`, serialised through
`s07_recwriter.py::_book_derived`.

> **`rank()` prints these; it filters on neither.** A row with `duplicate_exposure=True` or
> `headroom_ok=False` can still be `deploy=True`. The card surfaces the conflict for the
> operator; the enforcer is IBKR at order entry (`docs/deployment-rules.md` §3).

| Column | Definition | Blank when |
|---|---|---|
| `duplicate_exposure` | `True` if the ticker is already open in the book (priced or unpriced positions both count). | `book_evaluable` is `False` |
| `headroom_ok` | `True` the candidate's estimated delta-notional fits under the caps in `config/account-sim.yml` (bound to live `net_liq`, netted against that ticker's existing exposure); `False` it would breach one. | `book_evaluable` is `False`, **or** headroom could not be evaluated at all |
| `headroom_note` | The sentence explaining the verdict — `fits under caps (est. delta-notional $…)`, `would breach the <binding> cap …`, `delta-notional not estimable from the analysis row — verify cap headroom in IBKR at order entry (§3)`, or `no caps loaded (net_liq unavailable) — cap headroom not checked`. | never |

**Two different blank rules, and both matter:**

1. **`book_evaluable = False` blanks both.** Handed an empty book, `rank()` stamps
   `duplicate_exposure=False` on every candidate — which means "not checked" but reads as
   "checked, clear". `_book_derived()` resolves that at serialisation: with no evaluable book,
   both verdicts write as an **empty cell, never `False`**. Same missing-vs-zero discipline the
   greeks get, one layer up.
2. **`headroom_ok` can be blank even with an evaluable book.** `_headroom()` returns `None` —
   not `False` — whenever headroom cannot be evaluated: no `delta_notional` estimate on the
   analysis row, or no caps loaded. That is the normal case today, and `headroom_note` says
   which of the two it was.

So: blank `headroom_ok` + `book_evaluable=True` means *"the book was read, but this play's
exposure could not be estimated"* — go check it in IBKR.

## §5 Judge annotations

Source: `s06_recommend.py::judge`, the **only** model call in the whole journal pipeline. Run
unless `--no-llm`. The run-level fields are set in `s07_recwriter.py::to_rows`; the per-candidate
verdicts are written onto the existing `Candidate` objects by `judge()` itself.

> **The model may annotate the card; it may never promote a play.** `rank()` produced the
> ordering in §2 before `judge()` was called, and nothing re-sorts on a verdict. A verdict naming
> a ticker outside the survivor set is dropped, never trusted.

| Column | Definition | Blank when |
|---|---|---|
| `judge_ran` | `True` iff `judge_status == "ran"`. | never |
| `judge_status` | `not_run` (`--no-llm`, or never attempted) · `ran` · `failed`. `failed` means the call blew up or returned unusable JSON — the deterministic card still stands, only the annotation was lost. | never |
| `judge_model` | `JUDGMENT_MODEL` when the judge ran. | judge did not run |
| `trigger_verdict` | Has the candidate's `trigger` condition happened, given the context? `yes` · `no` · `unknown` (`unknown` when the context does not say). | judge did not run, or returned no verdict for this ticker |
| `trigger_note` | The model's one-line reasoning for `trigger_verdict`. | as above, or no note given |
| `alt_verdict` | Is `alternative_interpretation` now more likely than the thesis? `yes` · `no`. | judge did not run, or returned no verdict for this ticker |
| `alt_note` | The model's one-line reasoning for `alt_verdict`. | as above, or no note given |
| `demoted` | `True` iff `trigger_verdict == "no"` **or** `alt_verdict == "yes"`. A flag for human reconsideration — it does **not** change `rank` or `deploy`. | never |
| `demote_reasons` | Semicolon-joined: `trigger has not fired` and/or `alternative interpretation now more likely than the thesis`. | not demoted |
| `hedge_pick` | `True` on the one hedge candidate the model picked as its tie-break. Ignored (and warned about) if the model names a non-survivor. | never |
| `judge_lookahead_risk` | `JUDGE_LOOKAHEAD_NOTE`, verbatim, whenever the judge ran — see below. | judge did not run; always blank on `veto`/`tier_c` rows |

**The one thing that cannot be bounded by `as_of_date`.** Every other input to the card is
date-bounded, but `JUDGMENT_MODEL`'s training cutoff overlaps the analysis dates, so a verdict on
a *historical* session may be recall rather than reasoning. Hence the standing note:

> model cutoff may postdate session_date — verdicts on historical sessions are not evidence

Every row carries `judge_status` and `judge_lookahead_risk` precisely so a later reader can
**segregate judge-touched rows** rather than discovering the contamination after building on
them. `scripts/backtest_study/lib/live_select.py` documents the same concern for its own judge
layer.

## §6 Provenance and context

Set once per run from `RecContext` (`scripts/journal/config.py`), identical on every row.

| Column | Definition | Blank when |
|---|---|---|
| `analysis_source` | Where the analysis rows came from (e.g. `sheets`, or a local path). | source unknown |
| `book_source` | Basename of the broker pull the book was built from. | no pull qualified |
| `book_as_of` | That pull's **own** `trade_date` — read from the field, not trusted from the filename. The book is marked AT the analysis session, never at `date.today()`. | no pull qualified |
| `book_evaluable` | `True` if a broker pull dated on or before the session was found and read. `False` means the card ranked against an **empty** book — which is why §4's verdicts blank out. | never |
| `net_liq` | Live account NetLiquidation the caps were bound against. Note the exposure caps come from `config/account-sim.yml` but bind against **this**, not the study's $25k. | unavailable |
| `stale_override` | `True` iff `--allow-stale` was passed, i.e. analysis older than `RECOMMENDATION_MAX_AGE_DAYS` was accepted. It can **never** mean lookahead was accepted — that refusal has no override. | never |
| `notes` | Run-level warnings joined into one cell: the staleness note and the book-provenance note, when either fired. | nothing to say |

## §7 Reading rules

1. **Blank is not `False`.** Blank means "not known / not checked"; `False` is a checked
   negative. This applies to `duplicate_exposure`, `headroom_ok`, and every verdict in §5.
2. **`role` is the reject filter, not `tier`.** `tier == "C"` includes live hedge candidates.
3. **Ordering is deterministic and predates the model.** `rank` and `deploy` come from §2; no
   §5 column moved them.
4. **The book checks are advisory.** The card is not an enforcer; IBKR at order entry is.
5. **Rows accumulate.** For "what the card finally said", take the highest `generation` per
   `(session_date, role, ticker, structure)`. For "what it said over the course of the day",
   take them all.
6. **Never pool across prompt versions on `score_total`.** See §3.

## See also

- [`architecture.md`](architecture.md) § Daily trade journal → *Recommendation record* — why the
  writer is built this way (CSV-first, append-only, deliberately not shared with `s05_writer.py`).
- [`deployment-rules.md`](deployment-rules.md) — the §1–§4 rules `ladder_tier()` encodes, and the
  order-entry checks the card defers to.
- [`conviction-score.md`](conviction-score.md) — how `score_total` is computed, and the v3/v4 split.
- [`backtest-reference.md`](backtest-reference.md) — the sibling dictionary for `BacktestResults`.
