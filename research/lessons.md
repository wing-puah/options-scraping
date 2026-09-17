# Lessons: the core-lesson register (dream 2026-09-16)

_The deduplicated register of lessons this research programme learned, one line each, with every archive volume or `deployment-evidence.md` section that learned or re-learned it. Written whole by the weekly dream (`../DREAM.md`), never appended, capped at 120 lines. Read it before writing a core lesson in `current.md`; if the line is here, cite it. It never overrides doctrine: the rules live in `next-steps.md` §3, `docs/deployment-rules.md` and `CLAUDE.md`._

## Standing

Research lessons, from the archive corpus and `deployment-evidence.md`.

- Reactive exit rules read normal option noise as a reversal and sell continuation. The null extends from drawdown-from-peak trails to scheduled day-X switches, and on the first book with 2026 dates it carries a measured cost. [evidence: archive/01 §Attempt 1, archive/01 §Attempt 4, archive/16 §staged_exit first run, archive/19 §2026-09-04 (late), next-steps.md §3]
- A trailing stop gives back what a hard profit target locks in, because option spreads gap; trailing-on-profit-target only pays in a sustained trend. [evidence: archive/01 §Attempt 2, archive/01 §Attempt 4]
- `trailing_stop_trigger` is dead code whenever `profit_target` sits below it: the target fires first. [evidence: archive/01 §Attempt 3, archive/01 §Attempt 5]
- A study delta measured against `DEBIT_PROD` overstates production impact wherever a regime cell already ships a rule that converts the same rows. Quote both baselines; it is the test, not hygiene, and it changed a decision twice. [evidence: archive/09 §v3 CLOSE-OUT item 1, archive/11 §bear MFE give-back item 4, archive/11 §be_after grid RUN item 2, deployment-evidence.md §The production delta is a third of the study delta]
- A feature that separates outcomes may only be re-sorting structures or hold lengths. Test it at full joined coverage and within structure, and condition on any variable mechanically coupled to hold length before queueing follow-ups. [evidence: archive/04 §07-19 follow-ups (cpir), archive/05 §Queue-item verdicts, archive/16 §macro_event_study addendum 3]
- One window can carry a whole effect. Re-cut every headline without the Mar to Apr 2025 and the Feb to Apr 2026 windows before believing it; a correlated backfill window holds a rule and promotes nothing. [evidence: archive/11 §be_after grid RUN item 2, current.md §Two firsts that hold rather than ship, next-steps.md §0]
- An input that fails silently gives a clean-looking wrong answer: a stale fallback payload behind HTTP 200, a `frozenset` invisible to `ast.literal_eval`, a hole in the bars that anchors a fill late, a family branch that pools a naked fill as STRUCTURE. Make the failure loud at the boundary and test the negative path. [evidence: archive/06 §addendum 6 Barchart coverage floor, archive/06 §addendum 7, archive/09 §v3 CLOSE-OUT item 3, archive/11 §day-0 underlying move item 1, archive/16 §macro_event_study first run]
- A gate keyed to a hand-transcribed snapshot constant fails once the cache grows, and re-baselining it is circular. Compare two live outputs of the same run instead, and never hardcode a figure off one export. [evidence: archive/16 §calendar_hedge R4, next-steps.md §3 Vocabulary and process]
- A minimum-dates floor is not a density floor. A backfilled era clears the date count with no consecutive sessions, and a dense-episode study stays starved however many dates accumulate. [evidence: archive/16 §account_sim on v4, archive/16 §portfolio_delta first run]
- Fix the verdict grammar before a run, never after a number. An outcome the registration left unnamed is assigned at build time to an existing label with a printed qualification, not to a label invented after the fact. [evidence: archive/13 §account_sim RUN (the verdict grammar had a hole), archive/16 §portfolio_delta first run]
- A rollback census that barely clears its row floor on a still-backfilling book is not a decision: the same trigger fired, un-fired and fired again on three consecutive exports. Read a trigger only at its gate, and read the census, not the absence of an alarm. [evidence: deployment-evidence.md §The bear-debit peak-triggered breakeven stop, deployment-evidence.md §Open pre-registered rollback triggers, current.md §Where the 2026 column bit, next-steps.md §2.6]
- Any input change is a new analysis version: rename the live tabs `vN_` in place and let the pipeline recreate fresh ones. Never append changed-input rows to an existing tab, and never pool across versions (codified in CLAUDE.md §Prompt versions). [evidence: archive/05 §addendum 3 versioning rule, archive/09 §v3 CLOSE-OUT item 5]
- Bear debit has no standalone selection edge; its only value is as a hedge sleeve, and no better stop rescues it. Do not re-test the selection question. [evidence: archive/09 §DEPLOY arm item 6, archive/11 §be_after grid RUN item 5, deployment-evidence.md §The bear hedge sleeve, in full]
- A synthetic built on the engine's own signal dates adds no exposure; it re-wraps the exposure already deployed. A positive correlation with the deployed book means RE-WRAP regardless of the gain. [evidence: archive/12 §vol_sleeve RUN, archive/16 §financed_spread first run, archive/19 §2026-09-04 (late)]
- Before a delta or a monotone table is called a finding, ask what else moved with it: the baseline it was graded against, the structure mix, the hold length, the export state it ran on. Every line above is one of those in a different costume. [evidence: archive/01 §Attempt 1, archive/04 §07-19 follow-ups, archive/09 §v3 CLOSE-OUT item 1, archive/16 §financed_spread first run, deployment-evidence.md §The production delta is a third of the study delta]

Session lessons, seen in two or more sessions of this window.

- `rtk`'s `find` wrapper refuses compound predicates; use plain `find` for `-o`, `-not` or `-exec`. [evidence: session 2026-09-10 (digests 2026-09-10-agent-a55fed30a6854d7ce.md:48, 2026-09-10-agent-a3f146261ac185766.md:17)]
- Writing multi-line Python through a heredoc or a string-patch script lands in a flake8 E127/E128 fix loop; use hanging indents or the Edit tool. [evidence: session 2026-09-10 (digests 2026-09-10-agent-ae7c6214698eab2ad.md:81, 2026-09-10-agent-ab1ef6eccb734a66a.md:83)]
- Prefer the Edit tool to a one-off python heredoc replace for a file already on disk; a changed anchor fails silently and costs a retry cycle. [evidence: session 2026-09-10 (digests 2026-09-10-2a4f3a48.md:112, 2026-09-10-agent-a8ddbf36166ae78e1.md:55)]
- List a directory before reading it; the Read tool on a bare directory path errors. [evidence: session 2026-09-10 (digests 2026-09-10-agent-a0346aebc69ca172d.md:22, 2026-09-10-agent-a3f146261ac185766.md:30)]

## Recent

Seen once in this window's sessions. Promoted to Standing if a later run sees it again.

- A multi-hour scrape is checked by manual polling, not a long-lived background watcher; the low-memory guard kills the watcher. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:119)]
- Run the collector's dry run for real target counts before a study's plan and pre-registration are written, not after. [evidence: session 2026-09-10 (digest 2026-09-10-aa312feb.md:43)]
- A shell glob over `backtests/option_history_cache/*.csv` overflows the argument list; list it with `find`. [evidence: session 2026-09-10 (digest 2026-09-10-agent-ab498abf5112fd010.md:68)]
- A watchdog stage's `lag_sessions` must match the actual run order, not the data's D+1 semantics; the stale value hid the newest session as "not due". [evidence: session 2026-09-15 (digest 2026-09-15-a972e0e3.md:26)]
- When asking the operator where a file belongs, name the concrete files, not an abstract noun. [evidence: session 2026-09-10 (digest 2026-09-10-2a4f3a48.md:101)]

## Retired

(none: first run)
