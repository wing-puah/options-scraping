import csv
import io
from datetime import date


def parse_csv(raw: str) -> list[dict]:
    """Parse a Barchart-exported CSV, stopping at the 'Downloaded from' footer row."""
    rows = []
    reader = csv.DictReader(io.StringIO(raw))
    for row in reader:
        first_val = (next(iter(row.values()), "") if row else "") or ""
        if first_val.startswith("Downloaded from"):
            break
        if not any(row.values()):
            continue
        rows.append(dict(row))
    return rows


def normalize_flow_rows(rows: list[dict], trade_date: date) -> list[dict]:
    """Backfill Expires/DTE from Barchart's newer 'Exp Date' column, in place.

    Barchart's flow-CSV export switched from separate Expires + DTE columns to a
    single Exp Date column (same ISO-datetime content as the old Expires) around
    2026-07-14, dropping DTE entirely. Every downstream consumer keys off
    Expires/DTE (lib/flow_summary/_helpers.py, compile_flow.py's DEDUP_KEY,
    enrich_oi.py, lib/baseline.py), so normalize once at compile time: copy
    Exp Date -> Expires when Expires is blank, and (re)compute DTE from
    Expires - trade_date when DTE is blank. trade_date is the compiled file's
    date (from its filename) — the same reference the original Barchart DTE
    was relative to.
    """
    for row in rows:
        if not (row.get("Expires") or "").strip():
            exp_date = (row.get("Exp Date") or "").strip()
            if exp_date:
                row["Expires"] = exp_date
        if not (row.get("DTE") or "").strip():
            expires = (row.get("Expires") or "").strip()[:10]
            if expires:
                try:
                    row["DTE"] = str(max((date.fromisoformat(expires) - trade_date).days, 0))
                except ValueError:
                    pass
        row.pop("Exp Date", None)
    return rows
