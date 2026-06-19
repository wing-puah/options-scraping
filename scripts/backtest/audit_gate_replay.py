#!/usr/bin/env python3
"""Replay quality gates over an existing backtest results CSV to quantify lift.

This is a *deterministic, reproducible* alternative to re-running the full
analysis pipeline (which is non-deterministic — the LLM re-picks plays). It
joins each backtested trade back to its conviction-score audit rollup
(``audit/<date>-rollup.csv``) and reports the portfolio P&L when the
financing-penalty and IVSpread directional gates are applied.

Gates (both supported by the Mar-2025 panic window; see backtest-tuning.md):
  A. Financing gate     — drop a play whose FinancingShare > --fin-max. The flow
                          is stock-substitute positioning, not a directional bet.
  B. IVSpread dir. gate — drop a BEAR play whose IVSpread < --bear-ivspr-min.
                          Extreme put-IV inflation (panic hedging) flags an
                          overpriced crash-insurance entry that mean-reverts.

Usage:
  python3 -m scripts.backtest.audit_gate_replay \
      --results backtests/results.csv --audit-dir audit \
      --fin-max 0.6 --bear-ivspr-min -25
"""
import argparse
import glob
import os
import re

import pandas as pd


def _parse_conf(play: str) -> str | None:
    m = re.search(r"\[([^\]|]+)\|", str(play))
    return m.group(1).strip() if m else None


def load(results_path: str, audit_dir: str) -> pd.DataFrame:
    df = pd.read_csv(results_path)
    df["win"] = df["realized_pnl_pct"] > 0
    df["is_bear"] = df["structure"].str.startswith("bear")
    df["conf"] = df["play"].apply(_parse_conf)

    rolls = []
    for f in glob.glob(os.path.join(audit_dir, "*-rollup.csv")):
        r = pd.read_csv(f)
        r["signal_date"] = os.path.basename(f)[:10]
        rolls.append(r)
    if not rolls:
        raise SystemExit(f"no *-rollup.csv files in {audit_dir}")
    R = pd.concat(rolls)
    keep = ["signal_date", "Symbol", "Score", "FinancingShare", "IVSpread"]
    M = df.merge(R[keep], left_on=["signal_date", "ticker"],
                 right_on=["signal_date", "Symbol"], how="left")
    M["IVSpread"] = pd.to_numeric(M["IVSpread"], errors="coerce")
    return M


def book(s: pd.DataFrame) -> dict:
    return {
        "n": len(s),
        "win%": round(100 * float(s["win"].mean()), 1) if len(s) else 0.0,
        "avg_pnl%": round(100 * float(s["realized_pnl_pct"].mean()), 1) if len(s) else 0.0,
        "total_$": int(round(float(s["realized_pnl_abs"].sum()))),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="backtests/results.csv")
    ap.add_argument("--audit-dir", default="audit")
    ap.add_argument("--fin-max", type=float, default=0.6,
                    help="drop plays with FinancingShare above this (0 disables)")
    ap.add_argument("--bear-ivspr-min", type=float, default=-25.0,
                    help="drop BEAR plays with IVSpread below this")
    args = ap.parse_args()

    M = load(args.results, args.audit_dir)
    keep_fin = M["FinancingShare"] <= args.fin_max
    keep_ivspr = ~(M["is_bear"] & (M["IVSpread"] < args.bear_ivspr_min))
    keep = keep_fin & keep_ivspr

    print(f"Replay over {args.results} ({len(M)} trades)\n")
    print(f"  Baseline (trade all)                  : {book(M)}")
    print(f"  + financing gate (fin<= {args.fin_max})        : {book(M[keep_fin])}")
    print(f"  + bear IVspr gate (>= {args.bear_ivspr_min})       : {book(M[keep_ivspr])}")
    print(f"  + COMBINED                            : {book(M[keep])}\n")

    dropped = M[~keep]
    if len(dropped):
        print("Dropped by combined gate:")
        cols = ["signal_date", "ticker", "structure", "FinancingShare",
                "IVSpread", "realized_pnl_pct", "realized_pnl_abs"]
        print(dropped[cols].to_string(index=False))


if __name__ == "__main__":
    main()
