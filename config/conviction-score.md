# Conviction score (0–10, direction-agnostic)

A quant pre-score of how much attention a name warrants, built from normalized
inputs only — so an expensive underlying cannot buy its way up the list with raw
premium. It is **not** a direction call; bull/bear tilt stays in the
`Bull`/`Bear`/`C-P` columns.

## Components

| Part      | Range | What it measures |
| --------- | ----- | ---------------- |
| `flow`    | 0–3   | Premium rank within the day, **guarded by contract size** (`min(premium_rank, size_rank + 1)`) |
| `rep`     | 0–2   | Trade repetition — number of trades clustering on the name |
| `cross`   | 0/2   | Also appears in the unusual-activity dataset (cross-section overlap) |
| `voloi`   | 0–2   | Strength of the name's unusual Vol/OI print, if any |
| `open`    | 0/1   | ≥1 BuyToOpen / SellToOpen / ToOpen label present |
| `persist` | 0–3   | Extra days the name recurs across the window (multi-day, `--days N` only) |

The `Ctts` (contracts) and `$/ct` (premium per contract) columns expose
vol-/price-inflation: big premium + few contracts + high `$/ct` = expensive
options, not real size — and the `flow` term discounts it (size can only *cap*
premium rank, never lift it). A missing opening label scores 0, never negative.

## Buckets

| Score | Label       |
| ----- | ----------- |
| 0–2   | ignore      |
| 3–5   | watch       |
| 6–8   | candidate   |
| 9+    | high-conv   |

Single-day ceiling is 10; with `--days N` a recurrence bonus (+1 per repeat day,
capped +3) can push the persistence-adjusted score to 13.
