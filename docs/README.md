# docs/ — how the system works and how to run it

Hand-written, tracked prose. The placement rule for the whole repo, in one line:

> **machine-read → `config/`** · **how-it-works → `docs/`** · **what-we-learned → `research/`**
> · **generated → `site/`**

If code opens the file and feeds it to something (a YAML the pipeline parses, prose the code
inlines into an LLM prompt), it belongs in `config/` — including `config/prompts/`. If it
explains how a component behaves, what a column means, or what to do on a deploy morning, it
belongs here. If it records an experiment, a conclusion, or the evidence behind a rule, it
belongs in `research/`. If a `make` target writes it, it belongs in `site/` and is gitignored.
`CLAUDE.md` at the repo root is the compact always-loaded agent layer and stays there.

**Do not re-add `docs/` to `.gitignore`.** Until the reorganisation, `docs/` was the *generated
output* folder (study map, study charts, journal pages) and was gitignored — which meant the
one directory named for documentation was the one place documentation could not live. The
generated pages moved to `site/`, and `docs/` is now tracked source prose. Re-adding the old
ignore rule would silently drop every file below out of version control. The `.gitignore`
comment on the `site/` rule says the same thing; keep both.

## Contents

| File                    | Answers                                                                                | Read by                                              |
| ----------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `architecture.md`       | How does this module work? What are its per-file contracts, flag matrices, resume/idempotency semantics, journal and study internals? | Anyone editing `lib/` or `scripts/` — read the relevant section first |
| `deployment-rules.md`   | What gets real capital today? VETOs, the tier ladder, entry and exit management         | The operator on a deploy morning; encoded in code exactly once, by `ladder_tier()` |
| `conviction-score.md`   | How is the direction-agnostic conviction score computed, component by component?        | Anyone changing scoring — the model-facing condensed copy is `config/prompts/conviction-score-legend.md`, and both must change together |
| `rollup-reference.md`   | What are the per-ticker aggregation columns that feed the LLM and the scorer?            | Anyone reading the analysis markdown or the audit rollup CSV |
| `backtest-reference.md` | What does each column of `BacktestResults` / `backtests/results.csv` mean?               | Anyone interpreting backtest output or writing a study loader |
| `barchart-reference.md` | What does each Barchart flow column mean?                                                | Anyone parsing raw or compiled flow — vendor help text, copied verbatim |

## Neighbours

- `research/README.md` — the research index: tuning log, pre-registrations, study map,
  deployment evidence, replication protocol, glossary, handoff notes.
- `README.md` (repo root) — the entry point, with a "Where do I look for X?" table that maps
  questions to all of the above.
