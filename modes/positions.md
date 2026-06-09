# positions mode

Cross-reference open positions against latest options flow data.

## Steps

### 1. Sync positions from journal sheet

Pull the latest open positions from the `OpenPositions` tab in the trade journal:

```bash
cd $OPTIONS_TRADING_DIR && python3 scripts/sync_positions.py
```

If `TRADE_JOURNAL_SPREADSHEET_ID` is not set or the tab doesn't exist yet, it will print a clear error. In that case, skip to step 2 using whatever is in `config/positions.yml` already.

### 2. Load positions and latest flow

```bash
cd $OPTIONS_TRADING_DIR && python3 - <<'EOF'
import sys, json, yaml
from pathlib import Path
sys.path.insert(0, "lib")
import sheets_client

positions_path = Path("config/positions.yml")
positions = []
if positions_path.exists():
    data = yaml.safe_load(positions_path.read_text()) or {}
    positions = data.get("positions") or []

flow = sheets_client.get_recent_rows("OptionsFlow", 50)
unusual_stocks = sheets_client.get_recent_rows("UnusualStocks", 50)
unusual_etfs = sheets_client.get_recent_rows("UnusualETFs", 50)

print(json.dumps({
    "positions": positions,
    "flow": flow,
    "unusual_stocks": unusual_stocks,
    "unusual_etfs": unusual_etfs,
}))
EOF
```

### 3. Check positions exist

If `positions` is empty, say:
"No open positions found. Add rows to the `OpenPositions` tab in your trade journal sheet, or fill in `config/positions.yml` manually."
Then stop.

### 3. Analyse

Positions may be single-leg or multi-leg strategies. Handle each type accordingly:

**Single-leg positions** (no `legs` key): assess the symbol directly.

**Multi-leg positions** (has `strategy` and `legs` key): first state the overall strategy bias, then assess flow for the underlying symbol as a whole.
- Bull Call Spread / long Call → bullish bias, look for call-side flow confirmation
- Bear Put Spread / long Put → bearish bias, look for put-side flow confirmation
- Iron Condor → neutral/range bias, flag if flow shows a strong directional break toward either short strike
- Straddle/Strangle → long vol bias, note if flow suggests a directional move forming

For **each position or strategy**, search the flow and unusual activity data for the underlying symbol and report:
- **Strategy summary**: What the position is and what it needs to profit (e.g. "needs SPY above 523.20 by expiry")
- **Flow alignment**: Is current flow aligned, opposed, or neutral to the position's bias?
- **Notable activity**: Any large sweeps (ISOI), blocks (SLFT/MLFT), Buy/Sell To Open labels, or unusual Vol/OI on this symbol?
- **Risk flag** ⚠: If flow is strongly opposed to the position direction, or if a short strike is being tested by flow activity
- **DTE note**: Flag if any leg has DTE < 7

End with a brief overall summary: which positions look confirmed by flow, which look at risk, and any suggested adjustments.

This analysis is displayed inline only — nothing is written to Google Sheets.
