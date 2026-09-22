# Lessons: the core-lesson register

_Dream 2026-09-17. The deduplicated register of lessons this research programme learned, one line each, with every archive volume or `deployment-evidence.md` section that learned or re-learned it. Written whole by the weekly dream (`../DREAM.md`), never appended, capped at 120 lines. Read it before writing a core lesson in `current.md`; if the line is here, cite it. It never overrides doctrine: the rules live in `next-steps.md` §3, `docs/deployment-rules.md` and `CLAUDE.md`._

## Standing

Research lessons, from the archive corpus and `deployment-evidence.md`.

- Reactive exit rules read normal option noise as a reversal and sell continuation. The null extends from drawdown-from-peak trails to scheduled day-X switches, and on the first book with 2026 dates it carries a measured cost. [evidence: archive/01 §Attempt 1, archive/01 §Attempt 4, archive/16 §staged_exit first run, current.md §Where the 2026 column bit, next-steps.md §3]
- A trailing stop gives back what a hard profit target locks in, because option spreads gap; trailing-on-profit-target only pays in a sustained trend. [evidence: archive/01 §Attempt 2, archive/01 §Attempt 4]
- `trailing_stop_trigger` is dead code whenever `profit_target` sits below it: the target fires first. [evidence: archive/01 §Attempt 3, archive/01 §Attempt 5]
- A study delta measured against `DEBIT_PROD` overstates production impact wherever a regime cell already ships a rule that converts the same rows. Quote both baselines; it is the test, not hygiene, and it changed a decision twice. [evidence: archive/09 §v3 CLOSE-OUT item 1, archive/11 §be_after grid RUN item 4, archive/11 §be_after grid RUN item 2, deployment-evidence.md §The production delta is a third of the study delta]
- A feature that separates outcomes may only be re-sorting structures or hold lengths. Test it at full joined coverage and within structure, and condition on any variable mechanically coupled to hold length before queueing follow-ups. [evidence: archive/04 §07-19 follow-ups (cpir), archive/05 §Queue-item verdicts, archive/16 §macro_event_study addendum 3]
- One window can carry a whole effect. Re-cut every headline without the Mar to Apr 2025 and the Feb to Apr 2026 windows before believing it; a correlated backfill window holds a rule and promotes nothing. [evidence: archive/11 §be_after grid RUN item 2, current.md §Two firsts that hold rather than ship, next-steps.md §0]
- An input that fails silently gives a clean-looking wrong answer: a stale fallback payload behind HTTP 200, a `frozenset` invisible to `ast.literal_eval`, a hole in the bars that anchors a fill late, a family branch that pools a naked fill as STRUCTURE, a stale one-sided quote marked into a fabricated credit. Make the failure loud at the boundary and test the negative path. [evidence: archive/06 §addendum 6 Barchart coverage floor, archive/09 §v3 CLOSE-OUT item 3, archive/11 §day-0 underlying move item 1, archive/16 §macro_event_study first run, next-steps.md §2.11 (B5 on a stale one-sided quote)]
- A refetch that deletes the cached copy before the new fetch succeeds turns an empty response into permanent data loss. Write to a temporary file and replace only on success. [evidence: archive/20 §2026-09-08 (eighth), next-steps.md §2.11 (`history.py` unlinks a cache file)]
- A gate or a date table keyed to a hand-transcribed snapshot goes stale once the cache or the book grows, and re-baselining it is circular. Compare two live outputs of the same run instead, and never hardcode a figure or a date list off one export. [evidence: archive/16 §calendar_hedge R4, next-steps.md §0 (two hardcoded date tables), next-steps.md §3 Vocabulary and process]
- A blank column is not a population label. `cost_basis` is empty whenever both cost knobs are 0, so it cannot split pre- from post-cost-model rows; split on `cost_total` or `pct_stale_days` being non-blank. [evidence: current.md §Known defects in this export, not repaired, next-steps.md §2.11 (The split is not readable on `cost_basis`)]
- A minimum-dates floor is not a density floor. A backfilled era clears the date count with no consecutive sessions, and a dense-episode study stays starved however many dates accumulate. [evidence: archive/16 §account_sim on v4, archive/16 §portfolio_delta first run]
- A drawdown trigger keyed to a periodic reference — an annual reset, a running peak — can miss a drawdown that never crosses it in absolute terms, even when the same stretch is deep by another measure. Check what the reference can and cannot see before trusting a trigger's silence. [evidence: current.md §2026-09-22 account_sim Turtle throttle, account-sim-feasibility-plan.md §What is ruled out, and why]
- Fix the verdict grammar before a run, never after a number. An outcome the registration left unnamed is assigned at build time to an existing label with a printed qualification, not to a label invented after the fact. [evidence: archive/13 §account_sim RUN (the verdict grammar had a hole), archive/16 §portfolio_delta first run]
- A rollback census that barely clears its row floor on a still-backfilling book is not a decision: the same trigger fired, un-fired and fired again on three consecutive exports. Read a trigger only at its gate, and read the census, not the absence of an alarm. [evidence: deployment-evidence.md §The bear-debit peak-triggered breakeven stop, deployment-evidence.md §Open pre-registered rollback triggers, current.md §Where the 2026 column bit, next-steps.md §2.6]
- Any input change is a new analysis version: rename the live tabs `vN_` in place and let the pipeline recreate fresh ones. Never append changed-input rows to an existing tab, and never pool across versions (codified in CLAUDE.md §Prompt versions). [evidence: archive/05 §addendum 3 versioning rule, archive/09 §v3 CLOSE-OUT item 5]
- Bear debit has no standalone selection edge; its only value is as a hedge sleeve, and no better stop rescues it. Do not re-test the selection question. [evidence: archive/09 §DEPLOY arm item 6, archive/11 §be_after grid RUN item 2, deployment-evidence.md §The bear hedge sleeve, in full]
- A synthetic built on the engine's own signal dates adds no exposure; it re-wraps the exposure already deployed. A positive correlation with the deployed book means RE-WRAP regardless of the gain. [evidence: archive/12 §vol_sleeve RUN, archive/16 §financed_spread first run, current.md §2026-09-16 ladder_overlay]
- Before a delta or a monotone table is called a finding, ask what else moved with it: the baseline it was graded against, the structure mix, the hold length, the export state it ran on. Every line above is one of those in a different costume. [evidence: archive/01 §What actually drives losses — confidence level, not regime, archive/04 §07-19 follow-ups, archive/09 §v3 CLOSE-OUT item 1, archive/16 §financed_spread first run, deployment-evidence.md §The production delta is a third of the study delta]

Session lessons, seen in two or more sessions.

- Edit an existing file with the Edit tool, not a one-off python heredoc replace script: a changed anchor fails and costs a retry cycle, and the diff is not visible. [evidence: sessions 2026-09-10, 2026-09-15, 2026-09-16 (digests 2026-09-10-2a4f3a48.md:122, 2026-09-10-agent-a8ddbf36166ae78e1.md:41, 2026-09-15-ef8f6db1.md:27, 2026-09-16-693f8e2c.md:49)]
- Multi-line Python written through a heredoc or a string patch lands in a flake8 E127/E128 loop; use hanging indents, and fix every line flake8 reports from one run. [evidence: session 2026-09-10 (digests 2026-09-10-agent-ae7c6214698eab2ad.md:81, 2026-09-10-agent-ab1ef6eccb734a66a.md:117)]
- `rtk`'s `find` wrapper refuses compound predicates; run `-o`, `-not` or `-exec` searches through `rtk proxy find`, since the hook rewrites a plain `find`. [evidence: session 2026-09-10 (digests 2026-09-10-agent-a55fed30a6854d7ce.md:48, 2026-09-10-agent-a3f146261ac185766.md:17)]
- List a directory before reading it; the Read tool on a bare directory path errors. [evidence: session 2026-09-10 (digests 2026-09-10-agent-a0346aebc69ca172d.md:22, 2026-09-10-agent-a3f146261ac185766.md:30)]
- Parallel subagents building one contract each re-read the same doctrine files; gather the shared context once and pass it in the brief. [evidence: session 2026-09-10 (digests 2026-09-10-agent-a0346aebc69ca172d.md:43, 2026-09-10-agent-a55fed30a6854d7ce.md:27, 2026-09-10-agent-ac3146cf394e6e9f6.md:18)]

## Recent

Seen once in the window's sessions. Promoted to Standing if a later run sees it again.

- A multi-hour scrape is checked by manual polling, not a long-lived background watcher; the low-memory guard kills the watcher. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:119)]
- Never chain `sleep` with a following command in one Bash call; the tool blocks it. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:114)]
- Run the collector's dry run for real target counts before a study's plan and pre-registration are written, not after. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:43)]
- A new multi-tranche pricing engine needs a test that `credit_received` reaches its mark series before the first study run. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:75)]
- Write up a study and close its queue item in the session the run finishes; a later session otherwise reconciles stale references before it can answer anything. [evidence: session 2026-09-16 (digest 2026-09-16-693f8e2c.md:33)]
- A shell glob over `backtests/option_history_cache/*.csv` overflows the argument list; list it with `find`. [evidence: session 2026-09-10 (digest 2026-09-10-agent-ab498abf5112fd010.md:68)]
- Quote a separator in chained shell commands (`echo '==='`); a bare `===` is a zsh error. [evidence: session 2026-09-10 (digest 2026-09-10-agent-ab498abf5112fd010.md:66)]
- A watchdog stage's `lag_sessions` must match the actual run order, not the data's D+1 semantics; the stale value hid the newest session as "not due". [evidence: session 2026-09-15 (digest 2026-09-15-a972e0e3.md:26)]
- `mech_cell` NO_DATA on the newest date means the upstream close had not posted yet; the nightly backfill fills it. [evidence: session 2026-09-11 (digest 2026-09-11-ee66ff4b.md:22)]
- A play-pattern code added to the framework prose must also be added to the pipeline's allowlist in `core.py`, or the run rejects it. [evidence: session 2026-09-17 (digest 2026-09-17-a7951712.md:20)]
- Before adopting a dream proposal, check the live file has not changed since the proposal was written; adopt copies the whole file over it. [evidence: session 2026-09-17 (digest 2026-09-17-be43142f.md:19)]
- When fanning a numbered list out to parallel subagents, print each one's item range and confirm the ranges cover the list before dispatch. [evidence: session 2026-09-17 (digest 2026-09-17-agent-af1b90db8b20a8b6b.md:19)]
- When asking the operator where a file belongs, name the concrete files, not an abstract noun. [evidence: session 2026-09-10 (digest 2026-09-10-2a4f3a48.md:101)]

## Retired

- Citation `archive/19 §2026-09-04 (late)` on the reactive-exit lesson (why: an undifferentiated re-run recap; `current.md §Where the 2026 column bit` states the measured cost).
- Citation `archive/06 §addendum 7` on the silent-input lesson (why: it back-references addendum 6 rather than being its own instance).
- Citation `archive/11 §be_after grid RUN item 5` on the bear-debit lesson (why: item 5 reads a ratchet that was never built; item 2 is the settled result).
- Citation `archive/01 §Attempt 1` on the what-else-moved lesson (why: that section is about exit mechanics, not a confound).
- Citation `archive/19 §2026-09-04 (late)` on the re-wrap lesson (why: replaced by the more direct `current.md §2026-09-16 ladder_overlay` instance).
