import csv
import hashlib
import io
import statistics
from datetime import date

from lib.parsing import to_float

# Columns identifying a unique flow trade. compile_flow.py dedups on these and
# flow_fingerprint() hashes them, so both agree on what "the same row" means.
DEDUP_KEY = ["Symbol", "Type", "Strike", "Expires", "Trade", "Size", "Side", "Premium", "Time"]

# ── Trap A thresholds (see flow_staleness_report) ─────────────────────────────
# Barchart serves a fallback payload past the options-flow retention window:
# HTTP 200, correct schema, ~500 rows, content anchored to the RUN date rather
# than the requested historicalDate. Nothing errors, so it has to be caught here.
#
# The horizon bounds key off that anchoring: a genuine day's flow is dominated by
# near-dated contracts, while the fallback's expiries sit years out.
#
# MEASURED 2026-08-14 (etfs-flow). The floor sits between 2023-12-27 and
# 2024-01-02: every probed date from 2023-11-01 through 2023-12-27 returned the
# BYTE-IDENTICAL payload (sha256 prefix 26fc63189d6d182f, exactly 500 rows,
# median DTE ~1000-1060, SPY Price~ 777.86 — i.e. that day's SPY, against real
# closes of 422.66/459.10). Every date from 2024-01-02 on came back genuine
# (median DTE 38-51, SPY drift <=0.004). The window ROLLS, so re-probe before
# trusting these bounds for a date near the edge.
_MAX_MEDIAN_DTE = 400     # a real session's median DTE is far below this
_MAX_DTE = 1100           # ~3y; LEAPS exist, but not beyond this on flow tape
_SPY_TOLERANCE = 0.03     # SPY Price~ vs that date's close
_FALLBACK_ROWS = 500      # the fallback's row count — corroborating only


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


def _row_expiry(row: dict) -> date | None:
    """Expiry of a flow row, tolerating the 2026-07-14 Expires -> Exp Date rename.

    Read-only: unlike normalize_flow_rows this never mutates, because the
    staleness check runs BEFORE a payload is trusted enough to normalize.
    """
    for col in ("Expires", "Exp Date"):
        raw = (row.get(col) or "").strip()[:10]
        if raw:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                continue
    return None


def flow_fingerprint(rows: list[dict]) -> str:
    """SHA-256 of rows projected onto DEDUP_KEY — a payload's content identity.

    Two different requested dates returning this same digest means Barchart
    served one of them a cached/fallback payload.
    """
    digest = hashlib.sha256()
    for row in rows:
        digest.update("\x1f".join(str(row.get(c, "")) for c in DEDUP_KEY).encode())
        digest.update(b"\x1e")
    return digest.hexdigest()


def flow_staleness_report(rows: list[dict], target: date,
                          spy_close: float | None = None) -> dict:
    """Decide whether a downloaded flow CSV really is `target`'s data.

    Barchart's options-flow feed silently serves a fallback payload for dates
    past its retention window: HTTP 200, correct schema, no error. The CSV
    carries no trade-date column (``Time`` is time-of-day only), so identity has
    to be established indirectly.

    Returns a report dict; ``verdict`` is ``"ok"`` or ``"reject"`` and
    ``reasons`` lists every check that failed. The caller owns the cross-date
    fingerprint check — that needs a manifest of other dates, which lives with
    the caller, not here.

    Strength varies by feed, deliberately. The ``options-flow`` CSVs carry
    expiries (and SPY carries ``Price~``), so all checks apply — which is what
    matters, since that feed is the one with the short retention window. The
    ``unusual-activity`` CSVs have neither, so ``expiries_parsed`` is 0 and this
    degrades to fingerprint-plus-row-count; acceptable, because that feed serves
    genuine content back to 2022 and is not the trap being guarded against.
    """
    expiries = [e for e in (_row_expiry(r) for r in rows) if e is not None]
    dtes = sorted((e - target).days for e in expiries)

    report: dict = {
        "verdict": "ok",
        "reasons": [],
        "flags": [],
        "rows": len(rows),
        "sha256": flow_fingerprint(rows),
        "expiries_parsed": len(expiries),
        "median_dte": statistics.median(dtes) if dtes else None,
        "max_dte": dtes[-1] if dtes else None,
    }

    # (a) An option cannot trade after it expires. Any row expiring before the
    #     requested date means this is not that date's tape.
    if dtes and dtes[0] < 0:
        report["reasons"].append(
            f"expiry_before_target (min DTE {dtes[0]}, {sum(d < 0 for d in dtes)} rows)")

    # (b) The fallback is anchored to the RUN date, so its expiries sit years past
    #     `target`. Decisive for 2022-23 requests; weakens as target nears today.
    if report["median_dte"] is not None and report["median_dte"] > _MAX_MEDIAN_DTE:
        report["reasons"].append(
            f"median_dte {report['median_dte']:.0f} > {_MAX_MEDIAN_DTE}")
    if report["max_dte"] is not None and report["max_dte"] > _MAX_DTE:
        report["reasons"].append(f"max_dte {report['max_dte']} > {_MAX_DTE}")

    # (e) True date identity for the ETF feed: SPY's traded underlying price must
    #     match that session's close. No equivalent anchor exists for stocks.
    if spy_close:
        spy_px = [
            px for px in (
                to_float(r.get("Price~")) for r in rows
                if (r.get("Symbol") or "").strip().upper() == "SPY"
            ) if px
        ]
        if spy_px:
            observed = statistics.median(spy_px)
            drift = abs(observed / spy_close - 1)
            report["spy_observed"] = observed
            report["spy_drift"] = round(drift, 4)
            if drift > _SPY_TOLERANCE:
                report["reasons"].append(
                    f"spy_price_drift {drift:.1%} (saw {observed:.2f}, "
                    f"close {spy_close:.2f})")

    # (d) The fallback returned exactly 500 rows — but so can a legitimate page
    #     cap, so this corroborates a rejection and never causes one.
    if len(rows) == _FALLBACK_ROWS:
        report["flags"].append(f"row_count == {_FALLBACK_ROWS}")

    if report["reasons"]:
        report["verdict"] = "reject"
    return report
