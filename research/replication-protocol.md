# Two-analyst independent-replication protocol

Operator-facing. Two Claude Code agent definitions implement this:
[`research-analyst.md`](../.claude/agents/research-analyst.md) (spawned
twice, as A and B) and
[`research-validator.md`](../.claude/agents/research-validator.md)
(spawned once, after both analysts finish). This document is the
orchestration layer that sits above them — what the main session runs, in
what order, and what it does with the result.

## When it runs

- **Mode 1 (replication grading)** — after any study report the operator
  wants graded before it gets written up in `current.md`. Runs on the
  finished, stamped report under `backtests/study_output/`, never on the
  raw data or the study code. If a study hasn't been pre-registered, there
  is nothing for Mode 1 to grade against — pre-register first.
- **Mode 2 (independent exploration)** — only for NEW questions, and only
  on a TRAIN-split export (`protocol.walk_forward_splits` or
  `year_epoch_split` output), never the pooled book. Not a substitute for
  pre-registration — a Mode 2 candidate still needs its own
  pre-registered study before it can ship.

## Orchestration

1. Main session spawns **analyst A** and **analyst B** in a single message
   — two `Agent` tool calls, both `subagent_type: research-analyst`, in the
   same message so they run in parallel. **Both get an IDENTICAL prompt**
   naming the exact input file(s) (see worked example below). Neither is
   told anything the other isn't.
2. Neither analyst sees the other's output. Neither analyst sees the
   validator's output. This is enforced by never routing one analyst's
   result into the other's prompt — the main session is the only thing that
   holds both.
3. Once both return, main session spawns the **validator**
   (`subagent_type: research-validator`) with both analysts' full outputs
   plus the same underlying artifact(s) pasted or named in its prompt.
4. Once the validator returns, the **main session** — not the validator —
   makes the ship/no-ship or accept/reject call, and records a
   **Disagreement log** subsection in the `current.md` write-up:

   | Criterion | A | B | Resolution |
   |---|---|---|---|

   Even when the validator found zero disagreements, the subsection is
   still written, stating "no disagreements" — its absence is not allowed
   to read as "we didn't check."

## The four rules that make it real

1. **Runs on the finished REPORT, never the raw data, in Mode 1.** The
   analysts grade what the study printed, not what they could compute
   themselves from `backtests/to_evaluate/` — re-deriving numbers defeats
   the point of grading a specific, stamped, provenance-headed artifact.
2. **Both agents get the same artifacts and nothing else.** Same
   pre-registration section, same report path (Mode 1); same TRAIN-split
   file (Mode 2). Mode 1 optionally carries a THIRD named artifact — the
   study's positions CSV (`backtests/study_output/<study>-positions-latest.csv`),
   when the study exports one (today only `account_sim`) — passed identically
   to both analysts alongside the report. No agent gets extra context the
   other lacks.
3. **Fixed verdict schema, no prose.** Analysts output a table:
   `MET`/`NOT MET`/`NOT EVALUABLE` per criterion, the exact number, one
   sentence on what would flip it. No recommendations, no synthesis — that
   is deliberately withheld from the analyst step.
4. **The validator adjudicates only.** It checks numbers against source,
   flags disagreements and methodology violations, and stops. It does not
   introduce new claims and does not make the ship call — that stays with
   the main session, which is the only party that saw both analysts' raw
   output plus the validator's adjudication plus everything else in
   context (prior `current.md` history, the operator's actual question).

## Worked example invocation

Mode 1, replication grading. Two placeholders: `<pre-registration section>`
(the study's file under `research/pre-registrations/`, e.g.
`pre-registrations/f3_structure/calendar_hedge.md`, read whole — see
[`pre-registrations/README.md`](pre-registrations/README.md)) and
`<report path>` (e.g. `backtests/study_output/<name>-latest.txt`).

**Step 1 — spawn A and B in one message, identical prompts:**

```
Agent({
  description: "Replication grading — analyst A",
  subagent_type: "research-analyst",
  prompt: "Mode 1 (replication grading). Read the pre-registration at
    research/<pre-registration section> whole, and the report
    at <report path>. Grade every gate and criterion the pre-registration
    lists against that report only. You are analyst A; you will not see
    analyst B's output. Follow the schema in your system prompt exactly."
})
Agent({
  description: "Replication grading — analyst B",
  subagent_type: "research-analyst",
  prompt: "Mode 1 (replication grading). Read the pre-registration at
    research/<pre-registration section> whole, and the report
    at <report path>. Grade every gate and criterion the pre-registration
    lists against that report only. You are analyst B; you will not see
    analyst A's output. Follow the schema in your system prompt exactly."
})
```

(Both calls go in the same message so they run in parallel — see the
Agent tool's guidance on parallel spawns.)

**Step 2 — once both return, spawn the validator:**

```
Agent({
  description: "Replication grading — validator",
  subagent_type: "research-validator",
  prompt: "Validate the two analyst outputs below against the same
    pre-registration (research/<pre-registration section>,
    read whole) and report (<report path>).

    ANALYST A OUTPUT:
    <paste A's full output>

    ANALYST B OUTPUT:
    <paste B's full output>

    Produce the adjudication table and violations list per your system
    prompt."
})
```

**Step 3 — main session** reads the validator's adjudication, makes the
call, and writes the Disagreement log subsection into the `current.md`
entry for this study.

Mode 2 follows the same three-step shape, with the prompt instead naming a
TRAIN-split CSV path and instructing "Mode 2 (independent exploration)."

## Automated invocation

`python -m scripts.study_review <study>` (or `make study-review ARGS="<study>"`)
is the deterministic, headless path through Mode 1, modeled on
`scripts/analysis_pipeline`: it optionally runs the study
(`python -m scripts.backtest_study run <study>`) first, then makes headless
`claude -p` calls — isolated sessions, with the `research-analyst` and
`research-validator` personas inlined from `.claude/agents/research-{analyst,
validator}.md` rather than spawned as Agent-tool subagents — for analyst A and
B in parallel, then the validator, then a plain-language digest grounded in
`research/glossary.md`. Inputs to the analysts are the same as
the worked example above: the pre-registration section, the stamped report,
and (when present) the study's positions CSV, all inlined into the prompt
text.

This is a deliberate trade-off, not a lesser version of the manual path:
because everything the analysts and validator see is inlined text rather
than a live session with tool access, the validator's source-check step
means re-reading the inlined artifact text passed to it, not re-opening
files on disk. That is sufficient for Mode 1 (grading a finished, stamped
report against a finished pre-registration) but is why this path is not
offered for Mode 2 exploration, where an analyst may need to look beyond
the two named artifacts.

Outputs land in `backtests/study_output/`:
`<study>-review-analyst-a-latest.md`, `<study>-review-analyst-b-latest.md`,
`<study>-review-validator-latest.md`, and `<study>-digest-latest.md`. Flags:
`--skip-run` (reuse the existing `-latest.txt` instead of re-running the
study), `--run-args "…"` (forwarded to `backtest_study run`),
`--pre-reg PATH` (grade against a pre-registration file other than the
study's own `research/pre-registrations/<family>/<study>.md` — e.g. a
renamed study or an archived copy), `--positions-csv PATH` / `--no-positions-csv`
(override or suppress the third artifact), `--model M`, `--skip-digest`,
`--dry-run` (exercises the pipeline with placeholder outputs, no `claude`
calls).

The interactive worked example above — spawning `research-analyst` /
`research-validator` via the `Agent` tool from a live session — remains the
manual alternative: use it when Mode 2 exploration is needed, when an
analyst may need to read beyond the named artifacts, or when running the
protocol from inside an existing session is more convenient than shelling
out.

The digest is a plain-language explanation of the graded report for the
operator — it is not an input to any verdict or adjudication. The
ship/no-ship call is made from the analysts' and validator's output only;
the digest exists purely to make that output legible, and is written last,
after the call has already been reached.

## First applications

- **`account_sim`** — the protocol's **dry run**. Pre-registered
  2026-08-13 (see `current.md`); nothing ships from this study under any
  outcome regardless of what the protocol finds, so it is a safe first use
  to shake out the mechanics (schema drift, an analyst going out of scope,
  a validator missing a mismatch) before anything with stakes runs through
  it.
- **`calendar_hedge`** — the protocol's **first real use**. Pre-registered
  2026-08-13 alongside `account_sim`; its H2 gate is the primary criterion
  that decides whether the calendar candidate becomes a shippable second
  hedge sleeve, and its ARM S structure sweep is exactly the kind of
  multiple-comparisons-heavy output this protocol exists to grade honestly.
