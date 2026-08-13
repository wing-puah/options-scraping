# summary mode

Display the latest stored analysis from Google Sheets without running new LLM analysis.

## Steps

### 1. Fetch the analysis tab

```bash
cd $OPTIONS_TRADING_DIR && python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, "lib")
import sheets_client

claude_rows = sheets_client.get_all_rows("AnalysisClaude")
print(json.dumps({"claude": claude_rows}))
EOF
```

### 2. Check freshness

If the tab is empty, say: "No analysis found. Run `/options analyze` to generate one."

Report when the analysis was last run using the `analyzed_at` field from the first row.

If the analysis is more than 24 hours old, add a warning: "⚠ Analysis is older than 24 hours. Consider running `/options analyze`."

### 3. Display

Present the sections, clearly labeled:

**Claude Analysis** _(analyzed_at)_
1. Summary
2. Flow Sentiment
3. Unusual Patterns
4. Top Movers
5. Watchlist
6. Position Review
