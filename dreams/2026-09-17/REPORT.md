# Dream options-trading — 2026-09-17

Window: 7 days (2026-09-10 to 2026-09-17), 13 parent sessions selected (+15 subagent transcripts), 27 digests written and all analysed (1 empty session skipped). This is a same-week re-run after the operator adopted six archive status lines and the writing-guide line from 2026-09-16 and committed the `ladder_overlay` close. Its purpose was to rebuild the stale `next-steps.md` and `overview.md` proposals on the committed state. It also re-sources four loose citations in `lessons.md` found by a verification pass.

## Patterns

- F01 lesson ×2: `history.py` unlinks a cache file before refetching, so an empty refetch loses the file for good. Evidence: research/archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md:410; research/next-steps.md:450. Action: new line in `lessons.md` §Standing. The code fix is still open in next-steps.md §2.11 (`scripts/` is forbidden to the dream).
- F02 lesson ×2: `cost_basis` is blank on every row while both cost knobs are 0, so it cannot split the cost-model populations. Evidence: research/current.md:120; research/next-steps.md:449. Action: new line in `lessons.md` §Standing.
- F03 + F06 + F28 + F38 repeated_mistake/drift ×4 sessions: files were edited with ad-hoc python heredoc replace scripts instead of the Edit tool, which caused retries and flake8 E127/E128 loops. Evidence: 2026-09-10-2a4f3a48.md:122; 2026-09-10-agent-ae7c6214698eab2ad.md:81; 2026-09-10-agent-a8ddbf36166ae78e1.md:41; 2026-09-15-ef8f6db1.md:27; 2026-09-16-693f8e2c.md:49. Action: the two existing session lessons in `lessons.md` were merged and re-evidenced.
- F07 inefficiency ×3: parallel subagents building one contract each re-read the same doctrine files. Evidence: 2026-09-10-agent-a0346aebc69ca172d.md:43; 2026-09-10-agent-a55fed30a6854d7ce.md:27; 2026-09-10-agent-ac3146cf394e6e9f6.md:18. Action: new session lesson in `lessons.md` §Standing.
- F17, F18, F21, F24 consolidation: four `lessons.md` citations were loose (lesson on reactive exits → archive/19; silent inputs → archive/06 addendum 7; bear debit → archive/11 item 5; what-else-moved → archive/01 Attempt 1). Evidence: research/archive/01-exit-rules-attempts-1-7.md:282; research/archive/06-mech-regime-and-shipped-exits.md:461; research/archive/11-exit-conditioning.md:236; research/current.md:45. Action: re-sourced in `lessons.md`; the dropped pointers are listed under §Retired.
- F22 repeated_mistake ×2: `rtk find` refuses `-o`, `-not` and `-exec`. Evidence: 2026-09-10-agent-a55fed30a6854d7ce.md:48; 2026-09-10-agent-a3f146261ac185766.md:17. Action: proposed one sentence for the CLAUDE.md RTK section; the `lessons.md` line now says `rtk proxy find`, because the hook rewrites a plain `find`.
- F25 consolidation: the live walk-forward Stage 1/2 figures agree between current.md:263 and next-steps.md:267. Action: none.

## Observations

- F05 lesson: a stale one-sided quote fabricated a HYG credit (next-steps.md:452). Added as an instance of the silent-input lesson.
- F20 lesson: `ladder_overlay`'s trigger cells re-wrap the deployed book (current.md:379). Now the re-wrap lesson's evidence.
- F42 lesson: two hardcoded date tables are partly no-ops (next-steps.md:56). Folded into the snapshot-constant lesson, which now covers date lists.
- F19 drift: the B5 zero-bid re-mark has no mirror in `bear_rewrap`, which blocks `hedge_structure` (next-steps.md:451). Already the operator decision filed in §2.11.
- F23, F35, F43, F31, F30, F48, F27, F29, F41, F47: one-session items, now in `lessons.md` §Recent (watcher killed by the memory guard; chained `sleep`; bare `===` in zsh; `credit_received` missing from a new engine's marks; write-up left for a later session; `mech_cell` NO_DATA on the newest date; TF-S pattern code missing from `core.py`'s allowlist; adopt has no staleness check; mislabelled fan-out ranges; abstract noun in an AskUserQuestion).
- F26 housekeeping: `scripts/analyze_bt_queue.sh` is still committed against its own THROWAWAY header (2026-09-15-ef8f6db1.md:51). Operator's call; `scripts/` is forbidden.
- F29 + F32 missing_guidance (dream skill, not this repo): `adopt.py` copies a proposal over a live file without checking that the file is unchanged since the dream, and the account-id scan before committing dream artefacts was a manual grep (2026-09-17-be43142f.md:19, :25). Both are friction for the skill; see Not done.
- F33 missing_guidance: registering a new study has no checklist of the five files it must touch (2026-09-10-agent-a1f71675abcb16c96.md:18). A later dream could propose one in docs/architecture.md.
- F37 contradiction: a CRWV short put is labelled overlay by structure but SUBSTITUTED by the journal (current.md:271). Reported only.
- F39 stale_rule: CLAUDE.md gives `option_history_cache/` as ~337MB; an exploration measured 629MB (2026-09-10-agent-abbd94cf88cb39f75.md:91). Seen once, so not proposed.
- F44 housekeeping: current.md "What was pruned from this log" grows each prune cycle (current.md:189).
- F45 repeated_mistake: an Explore subagent ran about 22 find/grep/read calls in a CodeGraph-indexed repo (2026-09-10-agent-a3f146261ac185766.md:15).
- F46 housekeeping: a dated `ladder_overlay` study-output snapshot was renamed, and a later session had to rediscover it (2026-09-16-agent-ad7ae247a65860450.md:70).
- F04, F08–F16, F34: the targets agent re-confirmed existing `lessons.md` lines. Kept as evidenced.
- F36, F40: repeated re-reads of one file inside a session. No action.

## Denied tools

- 2026-09-10-2a4f3a48.md:99: the user rejected an `AskUserQuestion` ("working-state CSVs"). This was a rejection, not an allowlist refusal, so no allowlist fix. The wording lesson is in `lessons.md` §Recent.
- No other `D` lines in any digest.

## Proposals

- `CLAUDE.md`: one sentence in the RTK section, saying `rtk find` refuses compound predicates and to run them through `rtk proxy find`. Pass (forbidden-untouched).
- `research/next-steps.md`: closed items compacted to one-line stubs, built from the COMMITTED file (so §2.13 is closed): §0 RESOLVED cache-files bullet, operator items 1–4, §2.0, §2.1, §2.7 already-run guard, §2.8, §2.12 CLOSED row, and §2.13 (anchor, heading and links kept). §2.1's deferred ARM C control moved to §2.7. 540 → 519 lines; 19 anchors and 24 headings kept. Pass (next-steps-sections, research-headings).
- `research/overview.md`: regenerated from current.md, next-steps.md and study-map.md, dated 2026-09-17. It starts from the unadopted 2026-09-16 draft and adds the `ladder_overlay` close (row, detail paragraph, moved into the closed list). 404 → 498 lines. Pass (research-headings, no-account-overview).
- All three pass `scripts/check_doc_links.py` on an overlay of HEAD plus these proposals. The one remaining broken link, archive/19:923 → `backtests/neutral_dates_v1.md`, predates this run and points at a gitignored file that exists locally.
- `UNVERIFIED-current.md`, `archive/UNVERIFIED-21-journal-replay-and-live-loop-fold.md`, `archive/UNVERIFIED-README.md`: the rotation of `current.md` (432 lines, over the 400-line trigger). It moves the two 2026-09-09 journal sections verbatim into a new archive volume 21 and adds a pruned-log bullet and two index rows. current.md 432 → 343. See Not done for why it cannot pass.

## Owned files rewritten

- `research/lessons.md`: 44 → 59 lines (cap 120). §Standing gained three research lessons (refetch-then-unlink loss, blank `cost_basis`, and date tables folded into the snapshot-constant lesson), two new instances (HYG stale quote, `ladder_overlay` re-wrap), four re-sourced citations, and one session lesson (shared doctrine context for parallel subagents). The two heredoc/Edit session lessons were merged and re-evidenced. §Recent: 13 one-session lessons. §Retired: the five dropped citation pointers, each with a reason. The H1 no longer carries the dream date, so the title stays stable across runs.

## Housekeeping applied

- Nothing configured. The manifest's `housekeeping` list is empty by design, and `housekeep.py --apply` printed "nothing configured in the manifest".

## Stats

- Sessions: 13 parent + 15 subagent transcripts selected (22.8 MB), 27 digests written (1 empty skipped), all 27 analysed. The cost guard did not trigger.
- Batches: 4 digest batches (57.6 / 54.7 / 51.4 / 48.6 KB) + 1 targets batch; 5 accepted, 0 dropped, 0 warnings. 48 findings, 11 patterns.
- Proposal work: 3 extra sonnet agents (rotation, next-steps, overview) plus 1 citation-verification agent before the run.
- Checker: 1 FAIL, on the owned file's H1 (see Not done); every proposed file passes; ibkr-tripwire pass.

## Not done

- `research-headings` FAILS on `research/lessons.md`: `missing: # Lessons: the core-lesson register (dream 2026-09-16)`. The template puts the dream date in the H1, and `headings_kept` covers `research/*.md`, so every rewrite would fail. The H1 is now undated, which fails once (this run) and passes afterwards. A manifest fix would exclude the owned file from `research-headings`; DREAM.md is operator-owned, so this is not proposed.
- The rotation is UNVERIFIED, and not from any fault in its content. Two invariants cannot pass a rotation: `research-headings` on current.md (moved `##` headings count as missing) and `archive-status-only` on a brand-new volume (no baseline status line exists). `archive/README.md` passes its own checks but links to the new volume, so it is UNVERIFIED with the other two to keep it from being adopted alone. The manifest names rotation as a proposal while its invariants refuse one; it needs a rotation exemption, or the move done by hand. The pruned bullet restates six dates that appear only in the moved text, to satisfy `current-dates`. If the rotation is adopted, repoint next-steps.md:266 to the archive/21 anchor in the same commit (the next-steps proposal deliberately keeps the `current.md` link so it adopts on its own).
- Not proposed: CLAUDE.md `option_history_cache` size (seen once); a new-study checklist in docs/architecture.md (seen once); every `scripts/`, `config/` and `docs/deployment-rules.md` action (forbidden).
- Friction for the skill: `adopt.py apply` checks only for uncommitted edits, not whether the live file changed after the dream wrote its proposal. A proposal made before a later commit silently reverts that commit's text. On 2026-09-16 this would have reopened `ladder_overlay` §2.13. `merge_findings.py` again kept the same heredoc lesson as four singletons across kinds (merged by hand above).
