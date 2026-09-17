# Dream options-trading — 2026-09-16

Window: 7 days (2026-09-09 to 2026-09-16), 9 parent sessions selected (+10 subagent transcripts), 19 digests analysed, all of them. The week was one long `ladder_overlay` build session fanned out over five subagents, a Drive mirror for the journal, two journal fixes, and the first dream: the register `research/lessons.md` is written from the archive's core lessons.

## Patterns

- F01 lesson ×4 — An input that fails silently gives a clean-looking wrong answer (stale fallback payload behind HTTP 200, a `frozenset` invisible to `ast.literal_eval`, a bar hole anchoring a fill late, a naked fill pooled as STRUCTURE). Evidence: research/archive/06-mech-regime-and-shipped-exits.md:373, :461; research/archive/09-v3-closeout.md:599; research/archive/11-exit-conditioning.md:417; research/archive/16-first-runs-on-v3.md:195. Action: written into `research/lessons.md` §Standing.
- F02 lesson ×3 — A study delta measured against `DEBIT_PROD` overstates production impact wherever a regime cell already ships a rule converting the same rows; quote both baselines. Evidence: research/archive/09-v3-closeout.md:574; research/archive/11-exit-conditioning.md:184, :262; research/deployment-evidence.md:235. Action: in `lessons.md` §Standing.
- F03 consolidation ×8 — Every "core lesson" across archive/01, 04, 05, 06, 09, 11, 16 and deployment-evidence.md is one trap in a new costume: a read that was really the baseline, the composition, the hold length or the export state. Evidence: research/archive/01-exit-rules-attempts-1-7.md:69; research/archive/04-pooled-evals-and-ladder.md:246; research/archive/05-pooled-evals-762-and-regime-labels.md:235; research/archive/06-mech-regime-and-shipped-exits.md:373; research/archive/09-v3-closeout.md:574; research/archive/11-exit-conditioning.md:184; research/archive/16-first-runs-on-v3.md:532; research/deployment-evidence.md:235. Action: one cross-referencing line at the end of `lessons.md` §Standing; the concrete lessons carry the evidence.
- F04 consolidation ×3 — Three independent reads converge: bear debit has no standalone selection edge, hedge value only. Evidence: research/archive/09-v3-closeout.md:499; research/archive/11-exit-conditioning.md:346; research/deployment-evidence.md:273. Action: in `lessons.md` §Standing as a standing conclusion; already doctrine in next-steps.md §3 (bear debit selection-vetoed).
- F05 lesson ×3 — A feature's apparent signal can be pure structure or hold-length composition; test at full joined coverage and within structure. Evidence: research/archive/04-pooled-evals-and-ladder.md:246; research/archive/05-pooled-evals-762-and-regime-labels.md:101; research/archive/16-first-runs-on-v3.md:288. Action: in `lessons.md` §Standing; already a trap in study-map.md §Recurring traps.
- F06 lesson ×2 — Reactive and threshold exit rules sell continuation on normal option noise; scheduling the switch does not fix it. Evidence: research/archive/01-exit-rules-attempts-1-7.md:69, :206; research/archive/16-first-runs-on-v3.md:295. Action: in `lessons.md` §Standing; already doctrine in next-steps.md §3 (`staged_exit` null).
- F07 lesson ×2 — Any input change is a new analysis version writing to new `vN_` tabs; never append changed-input rows or pool across versions. Evidence: research/archive/05-pooled-evals-762-and-regime-labels.md:235; research/archive/09-v3-closeout.md:655. Action: in `lessons.md` §Standing, citing CLAUDE.md §Prompt versions, which already codifies the mechanics.
- F08 repeated_mistake ×2 — flake8 E127/E128 continuation-indent errors recur when subagents write multi-line code via heredoc or string-patch edits, costing fix-rerun cycles. Evidence: 2026-09-10-agent-ab1ef6eccb734a66a.md:83; 2026-09-10-agent-ae7c6214698eab2ad.md:81, :102. Action: in `lessons.md` §Standing (session lessons); a CLAUDE.md line is a candidate for a later dream, not proposed on a first run.
- F14 housekeeping ×2 — `scripts/analyze_bt_queue.sh` was noticed as untracked by two sessions on 2026-09-10 and then committed on 2026-09-15 despite its own "THROWAWAY, deliberately uncommitted" header (F21). Evidence: 2026-09-10-2a4f3a48.md:118; 2026-09-10-agent-a1f71675abcb16c96.md:98; 2026-09-15-ef8f6db1.md:73. Action: operator decides whether to fold it into `scrape_and_enrich.sh` or delete it; `scripts/` is forbidden to the dream, so this is a REPORT line only.
- F17 repeated_mistake ×2 — Read tool called on a bare directory path (EISDIR) in two Explore subagents. Evidence: 2026-09-10-agent-a0346aebc69ca172d.md:22; 2026-09-10-agent-a3f146261ac185766.md:30. Action: in `lessons.md` §Standing (session lessons).
- F25 + F29 (merged by hand; the merger kept them apart as `lesson` and `inefficiency`) ×2 — `rtk find` refuses compound predicates (`-o`, `-not`, `-exec`); plain `find` is needed. Evidence: 2026-09-10-agent-a55fed30a6854d7ce.md:48; 2026-09-10-agent-a3f146261ac185766.md:17. Action: in `lessons.md` §Standing (session lessons); a CLAUDE.md RTK-section line is a candidate for a later dream.
- F16 + F24 (merged by hand) ×2 — One-off python heredoc replace scripts used instead of the Edit tool, failing on a changed anchor and costing retries. Evidence: 2026-09-10-2a4f3a48.md:112; 2026-09-10-agent-a8ddbf36166ae78e1.md:55. Action: in `lessons.md` §Standing (session lessons).

## Observations

- F09 lesson — A minimum-dates floor is not a density floor (archive/16, two entries). research/archive/16-first-runs-on-v3.md:43, :689. In `lessons.md` §Standing (two dated entries of one volume).
- F10 lesson — A rollback census that barely clears its floor on a backfilling book is not a decision; three exports, three answers. research/deployment-evidence.md:139, :650. In `lessons.md` §Standing (two sections, plus current.md and next-steps.md §2.4 say it).
- F11 lesson — A gate keyed to a hand-transcribed snapshot constant breaks silently as the cache grows. research/archive/16-first-runs-on-v3.md:60, :91. In `lessons.md` §Standing with next-steps.md §3 "never hardcode a figure off one export" as the second file.
- F19 lesson — `trailing_stop_trigger` is dead code below `profit_target`. research/archive/01-exit-rules-attempts-1-7.md:133, :220. In `lessons.md` §Standing (two attempts of one volume).
- F12 stale_rule — `config/pipeline-health.yml` `enrich_oi` `lag_sessions=1` encoded a stale D+1 rationale; fixed in session a972e0e3 (commit 505f5a6). 2026-09-15-a972e0e3.md:26. `config/` is forbidden; `lessons.md` §Recent carries the lesson.
- F13 repeated_mistake — Background scrape watchers re-armed four times and killed by the low-memory guard before manual polling was used. 2026-09-10-aa312feb.md:119. `lessons.md` §Recent.
- F15, F23 inefficiency — Explore subagents re-read `lib/barchart/session.py` 4×, `config/backtest.yml` 3×, `financed_spread.py` and archive/16 3× each. 2026-09-10-agent-abbd94cf88cb39f75.md:74; 2026-09-10-agent-a55fed30a6854d7ce.md:54. No action.
- F18 missing_guidance — The `ladder_overlay` plan was written on an estimated contract count; the collector's dry run then found 11,502 targets (next-steps.md §2.13). 2026-09-10-aa312feb.md:43. `lessons.md` §Recent.
- F20 housekeeping — A doc-order fix, docstring and test for `--net-liq` precedence were written in fd1d8b02 and left uncommitted. 2026-09-11-fd1d8b02.md:47. Operator's call; not a dream target.
- F22 inefficiency — An AskUserQuestion used the abstract word "state" for three CSVs and the user rejected it. 2026-09-10-2a4f3a48.md:101. `lessons.md` §Recent.
- F26 missing_guidance — Globbing `backtests/option_history_cache/*.csv` overflowed the shell arg list. 2026-09-10-agent-ab498abf5112fd010.md:68. `lessons.md` §Recent.
- F27 consolidation — An episodic memory note (`project_ladder_overlay_study.md`, outside the repo) tracks the open `ladder_overlay` study; fold into `lessons.md` after its review and write-up. 2026-09-10-aa312feb.md:151. Next dream.
- F28 housekeeping — Digest 2026-09-15-047f8a6e.md is empty (8 records, no prompt, no tools, no final text). 2026-09-15-047f8a6e.md:29. A selector/digester friction item, see Not done.
- Session b7a0b5bf (daily-journal-review) made 8 MCP calls through its own connector; none to IBKR (tripwire pass). Not a repo finding.

## Denied tools

- 2026-09-10-2a4f3a48.md:99 — `AskUserQuestion` marked `D`: the user rejected the question ("where should the three working-state CSVs live"), not an allowlist refusal. Fix: none in `scheduled/tasks.json`; the wording lesson is in `lessons.md` §Recent (F22).
- No other `D` lines in any digest.

## Proposals

- `research/archive/10-post-closeout-ops-and-live-evals.md` — status line gains a `current.md §2026-09-09 journal` qualification: the live loop promoted here was deleted, its rules module is `scripts/journal/lib/mapping.py`, the daily journal is the Stage 1 fill mapping — pass (archive-status-only, research-headings).
- `research/archive/12-wrappers-and-vol-sleeve.md` — status line: `vol_sleeve` retired into `hedge_structure` gate R4, its files deleted 2026-09-08 (git `44bbfb2`), `calendar_hedge` renamed — pass.
- `research/archive/13-account-sim-and-calendar-hedge.md` — status line: `calendar_hedge` is `hedge_structure` since 2026-09-08, still stops at R2 on the grown export — pass.
- `research/archive/16-first-runs-on-v3.md` — status line: the 2026-09-04 re-run moved `financed_spread` (F3 off1 RE-WRAP, held) and gave `staged_exit`'s null a measured cost (six HARMFUL cells); `calendar_hedge` rename — pass.
- `research/archive/17-v4-refresh-bear-deploy-and-vocabulary.md` — status line: `concurrency_correlation` built and first-run 2026-09-04, NOISE on both eras, closed; `bear_deploy`/`hedge_exposure` renames — pass.
- `research/archive/18-hedge-programme-exit-basis-and-text-loop.md` — status line: the §4 gap-up prohibition drafted here was ACCEPTED 2026-09-06; `hedge_exposure` rename; `hedge_concentration` merged into `hedge_portfolio --admitted` and its files deleted — pass.
- `research/next-steps.md` — closed items compacted to one-line stubs (§0 cache-files RESOLVED bullet, operator items 1-4, §2.0, §2.1, §2.7 already-run guard, §2.8, §2.12 CLOSED row); §2.1's deferred ARM C control moved to §2.7; one clause names the B5 mirror decision as the item owed now; 540 → 473 lines; 19 section labels and 24 headings kept — pass (next-steps-sections, research-headings).
- `research/overview.md` — regenerated from current.md §State of play, next-steps.md and study-map.md, dated 2026-09-16, 15 headings kept; fixes the stale "prohibition still held", "no live-loop progress since 2026-08-13", "§2.8 still open", "ceiling 1.50 candidate" and the 2026-08-24 rollback table; adds the studies and queue items that postdate 2026-09-05; drops figures absent from the three sources — pass (research-headings, no-account-overview).
- `research/writing-guide.md` — one bullet under "What to cut": read `lessons.md` before writing a core lesson; if the line is there, cite it — pass (research-headings). `research/README.md` already carries its line (uncommitted, from the wiring pass), so it is not proposed.
- Not proposed: `research/current.md` rotation. It is 314 lines, under the 400-line threshold the manifest sets.
- All 9 proposals also pass the repo's own `scripts/check_doc_links.py` on an overlay copy (0 broken, 0 warnings).

## Owned files rewritten

- `research/lessons.md` — 14 → 44 lines (cap 120); 0 lines retired (first run; the previous version was a stub with "(none yet)"). §Standing: 15 research lessons from archive/01, 04, 05, 06, 09, 11, 12, 13, 16, 19, deployment-evidence.md, current.md and next-steps.md, each citing every section that learned it, plus 4 session lessons seen in ≥ 2 sessions; §Recent: 5 lessons seen once; §Retired: empty. No account ids, no balances; every number in a line appears in the cited file.

## Housekeeping applied

- The manifest's `housekeeping` list is empty by design (DREAM.md: "Housekeeping is empty on purpose"). `housekeep.py --apply` ran, printed nothing, and left `housekeeping.log` with no lines.

## Stats

- Sessions: 9 parent + 10 subagent transcripts selected (16.3 MB of JSONL), 19 digests written and all 19 analysed (cost guard not triggered; the cap is 40).
- Digest bytes: 166,218 across 19 files; largest 24.7 KB (aa312feb).
- Denials: 1 (a user-rejected AskUserQuestion). Tool errors: 31 across the 19 digests. MCP calls: 8, all in b7a0b5bf, none IBKR.
- Batches: 3 digest batches (54.8 / 57.7 / 53.6 KB) + 1 targets batch; 4 accepted, 0 dropped. 29 findings, 10 patterns by the merger (12 after two hand-merges noted above), 19 observations.
- Checker: `OK: 10 files, 0 failures`; `checks.json` `"ok": true`; ibkr-tripwire pass.
- Dream cost: not reported by the runner; sub-agent usage roughly 94k + 97k + 98k + 131k tokens.

## Not done

- No UNVERIFIED proposals, no dropped batches, nothing cut by the cost guard.
- Skipped on purpose: `research/README.md` line (already present, uncommitted); `current.md` rotation (314 lines < 400); every CLAUDE.md, `config/`, `scripts/` and `docs/deployment-rules.md` action named by a finding (forbidden or not a first-run target; F08, F12, F13, F14, F20, F21, F26, F29 are REPORT lines only).
- Friction for the skill: `select_sessions.py` picked an empty session (047f8a6e: 8 records, no prompt, no tool calls) and `transcript_digest.py` wrote a 602-byte digest for it; the selector could skip sessions with zero assistant turns. `merge_findings.py` dedups on (kind, summary) only, so the same lesson filed as `lesson` by one batch and `inefficiency` by another stays two singletons (F25/F29, F16/F24). `housekeep.py` writes no log line when the manifest has zero entries, so the REPORT section has nothing to copy.
