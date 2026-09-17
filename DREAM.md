# DREAM.md — what the weekly dream may read, own and propose here

This repo is a target of the `dream` skill (`~/claude_playground/dreaming/`). Once a week it
reads the last seven days of session transcripts and the research prose, looks for lessons that
were learned more than once, and writes one owned file directly. Everything else it wants to
change lands as a proposal under `dreams/<date>/proposed/`, checked by the invariants below and
copied in only by `dream adopt`. The fenced block is the machine-read manifest; the prose is the
part a dream reads before it decides anything.

## Owned: `research/lessons.md`

The one file the dream rewrites whole, every run, capped at 120 lines. One line per lesson, each
citing the archive volume or `deployment-evidence.md` section that learned it. The same core lesson
is stated in archive volumes 01, 04, 05, 06, 09, 11 and 16 and again in `deployment-evidence.md`;
volume 16 calls it "the lesson arriving again in a different costume". A write-up that grep-hits
`lessons.md` cites the line instead of restating it. The file is never appended to. A lesson that
leaves goes under `## Retired` with the reason, and the cap keeps the file readable.

## First-run proposals

Only these, until a dream has been adopted once:

1. `research/lessons.md`, built from the "Core lesson" and "Generalisable lesson" lines across
   `archive/01,04,05,06,09,11,16` and `deployment-evidence.md`, merged where they are one lesson.
2. Status lines of `research/archive/NN-*.md`, where a later volume or `current.md` qualifies the
   volume's conclusion. The status line is the only line that may differ; the check enforces it.
3. `research/next-steps.md` with closed items compacted to one-line stubs. Every section number
   survives, because code, tests and the archive cite them.
4. `research/overview.md` regenerated from `current.md` "State of play", `next-steps.md` and
   `study-map.md`. It admits it is a derived summary. If Wing adopts it, move it to `owned` so it
   is regenerated weekly and stops going stale.
5. One line each in `research/README.md` and `research/writing-guide.md`: read `lessons.md`
   before writing a core lesson; if the line is there, cite it.

`current.md` rotation into a new archive volume only when it passes 400 lines; the REPORT reports
the count and does not propose the move before then.

## What a dream must respect here

From `research/writing-guide.md` "What not to rewrite": `archive/` is history and only its status
line changes; `pre-registrations/` hold every number, arm label, gate id, verdict token and quote
verbatim; `study-results/` is machine-written and never hand-edited. From
`research/archive/README.md`: "The status stamp is the only thing in `archive/` that is meant to
change." From `CLAUDE.md`: the model may annotate the deploy card; it may never promote a play, so
`docs/deployment-rules.md` is forbidden and a finding about it is a REPORT line. `/journal/` is the
live trade record with real account ids and sizes; nothing from it enters a versioned file, and
the `no_pattern` checks fail an adopt that carries an account id or a balance. `config/prompts/`
are code inputs and `scripts/backtest_study/lib/harness.py` is frozen; neither is touched.

Housekeeping is empty on purpose. The only mechanical move here, rotating `current.md`, touches
three files (the new volume, the index row in `archive/README.md`, the status line), so it goes
through a proposal. Nothing else is safe to write without eyes on it.

`.github/workflows/pipeline-health.yml` disables every schedule after 60 days without a commit.
An adopt commits, which keeps the pipeline alive; a dream that only writes `dreams/` does not.

```json
{
  "repo": "options-trading",
  "root": "/Users/wing/claude_playground/options-trading",
  "proposals_dir": "dreams",

  "owned": [
    {"path": "research/lessons.md", "max_lines": 120,
     "purpose": "the deduplicated core-lesson register: one line per lesson, each citing the archive volume(s) and deployment-evidence.md sections that learned or re-learned it, so a write-up cites the line instead of restating it"}
  ],

  "transcripts": {
    "days": 7,
    "max_sessions": 40,
    "cwd_filter": "/Users/wing/claude_playground/options-trading",
    "dirs": [
      {"path": "~/.claude/projects/-Users-wing-claude-playground-options-trading", "format": "projects", "include_subagents": true}
    ]
  },

  "tiers": {
    "doctrine": [
      "CLAUDE.md", "README.md",
      "research/current.md", "research/next-steps.md", "research/overview.md",
      "research/deployment-evidence.md", "research/study-map.md", "research/arm-index.md",
      "research/glossary.md", "research/robustness-review.md", "research/writing-guide.md",
      "research/README.md", "research/archive/README.md", "research/archive/*.md",
      "docs/README.md", "docs/architecture.md", "docs/backtest-reference.md",
      "docs/barchart-reference.md", "docs/rollup-reference.md", "docs/conviction-score.md",
      "docs/recommendations-reference.md"
    ],
    "episodic": [
      "research/study-results/**",
      "backtests/study_output/*-latest.txt", "backtests/study_output/*-digest-latest.md",
      "logs/options.log"
    ],
    "derived": ["site/**", "audit/**", "backtests/*_cache/**", ".cache/**"],
    "forbidden": [
      "journal/**", ".env", "credentials/**", "config/**", "scripts/**",
      "research/pre-registrations/**", "docs/deployment-rules.md", ".github/**", ".gitignore",
      "portfolio/**", "cookies/**", "*-key.json", "*_secret_*"
    ]
  },

  "dream_targets": [
    "research/current.md", "research/next-steps.md", "research/archive/*.md",
    "research/deployment-evidence.md"
  ],
  "context_for_subagents": ["CLAUDE.md", "research/writing-guide.md"],

  "invariants": [
    {"id": "forbidden-untouched", "type": "paths_untouched",
     "paths": ["journal/**", ".env", "credentials/**", "config/**", "scripts/**",
               "research/pre-registrations/**", "research/study-results/**", "docs/deployment-rules.md",
               ".github/**", ".gitignore", "portfolio/**", "cookies/**", "*-key.json", "*_secret_*"]},
    {"id": "research-headings", "type": "headings_kept", "file": "research/*.md"},
    {"id": "docs-headings", "type": "headings_kept", "file": "docs/*.md"},
    {"id": "next-steps-sections", "type": "custom", "file": "research/next-steps.md", "script": "section_ids_kept.py"},
    {"id": "archive-status-only", "type": "custom", "file": "research/archive/[0-9][0-9]-*.md", "script": "archive_status_only.py"},
    {"id": "current-dates", "type": "token_set_subset", "file": "research/current.md", "pattern": "\\b20\\d\\d-\\d\\d-\\d\\d\\b"},
    {"id": "lessons-cap", "type": "max_lines", "file": "research/lessons.md", "max": 120},
    {"id": "no-account-lessons", "type": "no_pattern", "file": "research/lessons.md", "pattern": "\\bU\\d{6,8}\\b|NetLiq|\\$\\d{2,3},\\d{3}"},
    {"id": "no-account-overview", "type": "no_pattern", "file": "research/overview.md", "pattern": "\\bU\\d{6,8}\\b|NetLiq|\\$\\d{2,3},\\d{3}"}
  ],

  "post_adopt": [
    "make check-doc-links",
    "python3 -m pytest -q tests/test_doc_links.py"
  ],

  "housekeeping": []
}
```
