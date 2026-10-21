"""DRAFT, untested, not wired into the journal CLI — next-steps.md §2.14.

Three-way read of the operator's closed trades: what was traded (journal/trades.csv)
vs the card's play as backtested (BacktestResults/Proxy exports) vs the mechanical
ATM/+5% call spread (mechanical_benchmark-pairs.csv, ARM M1). Reads only gitignored
inputs and writes only journal/_compare_positions.csv; prints to stdout.

Run from the repo root after restoring journal/ from Drive and running
`python3 -m scripts.backtest_study run mechanical_benchmark`:
    python3 scripts/journal/draft_compare_card.py
Signal dates on or after the holdout seal are excluded from the card comparison.
"""
import sys; sys.path[:0] = [".", "scripts"]
import re, pandas as pd, numpy as np
from scripts.backtest_study.lib.era import SEAL_START as SEAL
t = pd.read_csv("journal/trades.csv").reset_index(drop=True)
LEG = re.compile(r"(\S+:\S+:[\d.]+:[CP]) ([+-]\d+)")
t["legset"] = t.legs.fillna("").map(lambda s: [(c, int(q)) for c, q in LEG.findall(s)])

# union-find over fills sharing a contract = one position
parent = list(range(len(t)))
def find(i):
    while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
    return i
owner = {}
for i, ls in enumerate(t.legset):
    for c, _ in ls:
        if c in owner: parent[find(i)] = find(owner[c])
        owner[c] = i
t["pos"] = [find(i) for i in range(len(t))]

LINKED = {"EXACT", "STRUCTURE", "SUBSTITUTED", "CORE"}
rows = []
for pid, g in t.sort_values("trade_datetime_utc").groupby("pos"):
    qty = {}
    for ls, n in zip(g.legset, g.contracts):
        for c, q in ls: qty[c] = qty.get(c, 0) + q * (n if abs(q) == 1 else 1)
    opens = g[g.action == "OPEN"]
    first = opens.iloc[0] if len(opens) else g.iloc[0]
    link = opens[opens.match_confidence.isin(LINKED)]
    lead = link.iloc[0] if len(link) else first
    debit = -opens.net_cash[opens.net_cash < 0].sum()
    rows.append(dict(
        ticker=first.ticker, opened=first.date if len(opens) else None, last=g.date.max(),
        structure=lead.structure, match=lead.match_confidence, ac_play=lead.ac_play, signal_date=lead.signal_date,
        tier=lead.tier, closed=all(v == 0 for v in qty.values()) and len(opens) > 0,
        orphan=len(opens) == 0, pnl=g.realized_pnl.fillna(0).sum(), debit=debit,
        credit=opens.net_cash[opens.net_cash > 0].sum(), fills=len(g)))
P = pd.DataFrame(rows)
P["linked"] = P.match.isin(LINKED)
P["R_you"] = np.where(P.debit > 0, P.pnl / P.debit.replace(0, np.nan), np.nan)
P.to_csv("journal/_compare_positions.csv", index=False)

print("== Your realized P&L by position kind (all dates, net of commission) ==")
c = P[P.closed]
print(c.groupby("linked").agg(positions=("pnl", "size"), pnl=("pnl", "sum"),
      win_rate=("pnl", lambda s: (s > 0).mean()), mean_pnl=("pnl", "mean")).round(2).to_string())
print("by match label:"); print(c.groupby("match").agg(n=("pnl","size"), pnl=("pnl","sum")).round(0).to_string())
print(f"still open: {(~P.closed & ~P.orphan).sum()}   closes with no open in journal: {P.orphan.sum()} (pnl {P[P.orphan].pnl.sum():.0f})")

# three-way on linked, closed, debit positions with a priced pair (pre-seal only)
pairs = pd.read_csv("backtests/study_output/mechanical_benchmark-pairs.csv")
m1 = pairs[pairs.arm == "M1"].groupby(["date", "ticker"]).agg(R_card=("R_T", "mean"), R_mech=("R_C", "mean")).reset_index()
L = c[c.linked & (c.signal_date < SEAL)].merge(m1, left_on=["signal_date", "ticker"], right_on=["date", "ticker"], how="left")
print(f"\n== Linked closed positions, signal before {SEAL}: {len(L)}; with a priced card/mechanical pair: {L.R_card.notna().sum()} ==")
T = L[L.R_card.notna() & L.R_you.notna()]
if len(T):
    print(T[["signal_date","ticker","structure","match","tier","pnl","debit","R_you","R_card","R_mech"]].round(3).to_string(index=False))
    print("\nmean R:", T[["R_you","R_card","R_mech"]].mean().round(3).to_dict())
    rng = np.random.default_rng(0)
    for a, b in [("R_you","R_card"),("R_you","R_mech"),("R_card","R_mech")]:
        d = (T[a]-T[b]).values; bs = [rng.choice(d, len(d)).mean() for _ in range(5000)]
        print(f"  {a} - {b}: {d.mean():+.3f}  CI95 [{np.percentile(bs,2.5):+.3f}, {np.percentile(bs,97.5):+.3f}]  you-better share {(d>0).mean():.2f}")

# card R for every linked play, from the backtest exports themselves (net of cost)

from scripts.backtest.shared.identity import identity_key
bt = pd.concat([pd.read_csv("backtests/to_evaluate/analysis - BacktestResults.csv").assign(src="real"),
                pd.read_csv("backtests/to_evaluate/analysis - BacktestProxy.csv").assign(src="proxy")])
bt["key"] = [identity_key(d, k, p) for d, k, p in zip(bt.signal_date, bt.ticker, bt.play)]
bt = bt.drop_duplicates("key")  # real first
card = bt.set_index("key")[["pnl_on_risk_pct", "src", "exit_reason", "days_held"]]
L = c[c.linked & (c.signal_date < SEAL)].copy()
L["key"] = [identity_key(d, k, p) for d, k, p in zip(L.signal_date, L.ticker, L.ac_play)]
L = L.join(card, on="key").rename(columns={"pnl_on_risk_pct": "R_card"})
# fallback: same signal date + ticker, one backtested play only (or the one whose structure matches)
def side(s): s = str(s).lower(); return "call" if "call" in s else ("put" if "put" in s else "")
bt["kind"] = bt.structure.map(side)
for i, p in L[L.R_card.isna()].iterrows():
    m = bt[(bt.signal_date == p.signal_date) & (bt.ticker == p.ticker)]
    if len(m) > 1: m = m[m.play.str.lower().str.contains(str(p.ac_play).split("|")[2].strip()[:12].lower(), regex=False)] if str(p.ac_play).count("|") >= 2 else m
    if len(m) == 1:
        L.loc[i, ["R_card", "src"]] = [m.pnl_on_risk_pct.iloc[0], m.src.iloc[0] + "~"]
L = L.merge(m1, left_on=["signal_date", "ticker"], right_on=["date", "ticker"], how="left", suffixes=("", "_p"))
print(f"\n== Card R from the backtest tabs: {L.R_card.notna().sum()} of {len(L)} linked positions priced ==")
L["dir"] = np.where(L.structure.str.contains("bear|put", case=False), "bear/hedge", "bull")
print(L[["signal_date","ticker","structure","match","tier","pnl","debit","R_you","R_card","src","R_mech_p" if "R_mech_p" in L else "R_mech"]].round(3).sort_values("signal_date").to_string(index=False))
T = L[L.R_card.notna() & L.R_you.notna()]
print("\nmean R by direction:"); print(T.groupby("dir").agg(n=("R_you","size"), R_you=("R_you","mean"), R_card=("R_card","mean"), pnl=("pnl","sum")).round(3).to_string())
d = (T.R_you - T.R_card).values; rng = np.random.default_rng(0)
bs = [rng.choice(d, len(d)).mean() for _ in range(5000)]
print(f"R_you - R_card over {len(d)}: {d.mean():+.3f} CI95 [{np.percentile(bs,2.5):+.3f}, {np.percentile(bs,97.5):+.3f}], you better on {(d>0).mean():.0%}")
print(f"card-style $ on your debits: {(T.R_card*T.debit).sum():+.0f} vs yours {T.pnl.sum():+.0f}")
