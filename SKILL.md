---
name: options
description: >
  Options trading toolkit. Analyzes barchart unusual activity and flow
  data scraped to Google Sheets. Modes: analyze (Claude analysis),
  summary (show latest stored analysis), positions (cross-reference open positions).
---

# options

Options flow intelligence toolkit.

## Routing

Parse the first argument (case-insensitive):

| Argument    | Action                                                            |
| ----------- | ----------------------------------------------------------------- |
| `analyze`   | Run the analysis pipeline script — see **Analyze pipeline** below |
| `summary`   | Load and execute `modes/summary.md`                               |
| `positions` | Load and execute `modes/positions.md`                             |
| _(none)_    | Print the discovery menu below                                    |

## Analyze pipeline

`analyze` is a deterministic Python pipeline — the `scripts/analysis_pipeline`
package, run via `python3 -m scripts.analysis_pipeline`. Do NOT do the analysis
in-context and do NOT spawn a subagent. The pipeline runs the LLM step as an
isolated headless engine call, so the analysis framework, method file, and raw
flow data never enter this conversation's context. (User-tunable settings live in
`scripts/analysis_pipeline/config.py`.)

The pipeline is model-agnostic via `--engine` (currently one engine registered):

- `claude` (default) → `claude -p`, method `claude.md`, writes **AnalysisClaude**

### Steps

1. Parse args from the invocation (everything after `analyze`):
   - `claude` — engine token (default `claude`); map to `--engine`
   - `--date YYYY-MM-DD` — single date (omit for latest available)
   - `--start YYYY-MM-DD` / `--end YYYY-MM-DD` — range (weekdays only)
   - `--tickers NVDA,AMD,SPY` — ticker-focused run: narrows the per-ticker flow
     tables and returns plays only for these names (full market read retained).
     Writes to the **AnalysisTickerSpecific** tab, NOT the engine's daily tab.
   - `--days N` — persistence window
   - `--model NAME` — override the engine's model (default: claude→`opus`)
   - `--dry-run` — fetch + analyze but do not write to Sheets
   - `--yes` — skip the confirmation in step 2
2. Unless `--yes` or `--dry-run`, confirm intent with the user (this writes to
   the engine's tab — AnalysisClaude for claude; or AnalysisTickerSpecific
   when `--tickers` is given).
3. Run the pipeline and stream its report back:

   ```bash
   cd $OPTIONS_TRADING_DIR && source .venv/bin/activate && python3 -m scripts.analysis_pipeline --engine {engine} {flags}
   ```

   Where `{flags}` are the remaining parsed args (drop `--yes`, it is consumed in
   step 2 and not a script flag).

The script handles fetch → analyze → write per date, skips dates with no Drive
data, appends to the engine's tab (never clears), and prints a per-date report of
regime / signals / plays. Relay that report; do not re-derive it.

## Discovery menu

Print this when invoked with no arguments:

```
options — Options Flow Intelligence

  /options analyze
      Fetch latest barchart data from Google Sheets and run analysis via a
      headless Claude engine call (isolated context).
      Results are written to the AnalysisClaude tab.

  /options summary
      Display the latest stored analyses from AnalysisClaude
      without running new analysis. Zero token cost.

  /options positions
      Cross-reference your open positions (config/positions.yml) against
      the latest options flow data. Highlights risk and flow alignment.
```
