#!/usr/bin/env python3
"""One plain-English project dashboard -> site/dashboard.html.

Reads LOCAL research/backtest/pipeline files only. No network, and nothing from
journal/ or portfolio/ (account ids, positions, P&L). Every gatherer returns a
plain dict and degrades to {"ok": False, "why": ...} when its file is missing,
so one absent file turns one card into "no data" and never stops the page.

The output starts with <title> and has no <html>/<head>/<body>, so the same file
can be published as an Artifact (the host wraps it); browsers render it as is.

    python3 scripts/dashboard.py [--today YYYY-MM-DD] [--out PATH] [--quiet]
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

FORWARD_START = "2026-09-23"   # the sealed forward period starts here
TOL = ROOT / "backtests" / "to_evaluate"
ANALYSIS_CSV = TOL / "analysis - AnalysisClaude.csv"
RESULTS_CSV = TOL / "analysis - BacktestResults.csv"
PROXY_CSV = TOL / "analysis - BacktestProxy.csv"
MECH_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
WATCH_CSV = ROOT / "backtests" / "regime_watch" / "history.csv"
LOG_DIR = ROOT / "backtests" / "run_logs"
PREREG = ROOT / "research" / "pre-registrations"
GATE_MD = PREREG / "f4_deployment" / "programme_gate.md"
DIP_MD = PREREG / "f1_selection" / "regime" / "dip_buy.md"
BENCH_MD = PREREG / "f1_selection" / "benchmark" / "mechanical_benchmark.md"
DIP_PY = ROOT / "scripts" / "backtest_study" / "f1_selection" / "regime" / "dip_buy.py"
NEXT_MD = ROOT / "research" / "next-steps.md"
OUT = ROOT / "site" / "dashboard.html"


def nodata(why: str) -> dict:
    return {"ok": False, "why": why}


# ── small helpers ─────────────────────────────────────────────────────────────
def read_rows(path: Path) -> list[dict] | None:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def num(v) -> float | None:
    try:
        x = float(str(v).strip())
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def as_date(v) -> str | None:
    s = str(v or "").strip()[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def weekday_age(d: str, today: str) -> int:
    """Weekdays between two ISO dates (holidays not modelled)."""
    return int(np.busday_count(d, today))


def state_by_age(age: int, green: int, amber: int) -> str:
    return "ok" if age <= green else "warn" if age <= amber else "bad"


def md_plain(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("`", "").replace("**", "")
    return re.sub(r"\s+", " ", s).strip()


def outcome_block(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return nodata(f"{path.name} not found")
    m = re.findall(r"<!-- outcome:start -->(.*?)<!-- outcome:end -->", text, re.S)
    if not m:
        return nodata(f"no outcome block in {path.name}")
    body = "\n".join(ln.lstrip("> ").rstrip() for ln in m[-1].strip().splitlines())
    return {"ok": True, "text": md_plain(body), "file": path.name}


# ── 2. is the data flowing ────────────────────────────────────────────────────
def analysis_dates(path: Path = ANALYSIS_CSV) -> set[str] | None:
    rows = read_rows(path)
    if rows is None:
        return None
    return {d for r in rows if (d := as_date(r.get("date"))) and r.get("ticker") != "MARKET"}


def backtested_dates(*paths: Path) -> set[str] | None:
    out, seen = set(), False
    for p in paths:
        rows = read_rows(p)
        if rows is None:
            continue
        seen = True
        out |= {d for r in rows if (d := as_date(r.get("signal_date")))}
    return out if seen else None


def last_loop_log(log_dir: Path = LOG_DIR) -> dict:
    try:
        logs = sorted(log_dir.glob("daily-loop-*.log"))
    except OSError:
        logs = []
    if not logs:
        return nodata("no daily-loop log yet")
    p = logs[-1]
    m = re.search(r"daily-loop-(\d{4})(\d{2})(\d{2})", p.name)
    d = f"{m[1]}-{m[2]}-{m[3]}" if m else None
    try:
        tail = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-40:]
    except OSError:
        return nodata("log unreadable")
    joined = "\n".join(tail)
    if re.search(r"daily-loop complete", joined):
        end = "ok"
    elif "stopping" in joined:
        end = "failed"
    else:
        end = "unfinished"
    return {"ok": True, "date": d, "end": end, "file": p.name}


def pipeline_state(today: str, root_paths: dict | None = None) -> dict:
    P = {"analysis": ANALYSIS_CSV, "results": RESULTS_CSV, "proxy": PROXY_CSV,
         "mech": MECH_CSV, "watch": WATCH_CSV, "logs": LOG_DIR}
    P.update(root_paths or {})
    items = []

    def add(label, explain, d, green, amber, extra=""):
        if not d:
            items.append({"label": label, "explain": explain, "date": None, "state": "none",
                          "note": "no data"})
            return
        age = weekday_age(d, today)
        items.append({"label": label, "explain": explain, "date": d, "age": age,
                      "state": state_by_age(age, green, amber), "note": extra})

    a = analysis_dates(P["analysis"])
    add("Newest analysis", "The newest trading day the model has written plays for.",
        max(a) if a else None, 1, 3)
    b = backtested_dates(P["results"], P["proxy"])
    add("Newest backtested day", "The newest signal day with a simulated trade. It trails the "
        "analysis because a trade needs later prices to play out.",
        max(b) if b else None, 4, 8)
    pending: list[str] = []
    if a is not None and b is not None:
        pending = sorted(d for d in a if d >= FORWARD_START and d not in b)
    mech = read_rows(P["mech"])
    add("Market regime table", "The newest day of SPY and VIX closes the regime label uses.",
        max((d for r in mech or [] if (d := as_date(r.get("date")))), default=None), 1, 3)
    w = read_rows(P["watch"])
    add("Regime watch", "The newest row of the daily regime checklist.",
        max((d for r in w or [] if (d := as_date(r.get("date")))), default=None), 1, 3)
    log = last_loop_log(P["logs"]) if isinstance(P["logs"], Path) else nodata("")
    if log["ok"]:
        age = weekday_age(log["date"], today) if log["date"] else 99
        st = state_by_age(age, 1, 3)
        if log["end"] == "failed":
            st = "bad"
        elif log["end"] == "unfinished" and st == "ok":
            st = "warn"
        items.append({"label": "Last daily loop", "explain": "The last run of the laptop's daily job.",
                      "date": log["date"], "age": age, "state": st,
                      "note": {"ok": "finished OK", "failed": "stopped on a failed step",
                               "unfinished": "did not reach its last line"}[log["end"]]})
    else:
        items.append({"label": "Last daily loop", "explain": "The last run of the laptop's daily job.",
                      "date": None, "state": "none", "note": log["why"]})
    return {"ok": True, "items": items, "pending": pending,
            "pending_known": a is not None and b is not None}


# ── 3. regime ─────────────────────────────────────────────────────────────────
CHECKS = [
    ("c1_persistence", "The market label has been bearish for 3 sessions in a row"),
    ("c2_spy_below_200", "SPY is below its 200-day average"),
    ("c3_credit_weak", "Credit is weakening (junk bonds lag Treasuries over 20 days)"),
    ("c4_iwm_below_200", "Small companies (IWM) are below their 200-day average"),
    ("c5_vix_ge_20", "The fear index (VIX) is at 20 or higher"),
]
STATUS_WORDS = {
    "CLEAR": "No bear signal. Nothing to do.",
    "WATCH": "The market has been bearish recently or some checks are met. Keep an eye on it.",
    "CONFIRMED": "A bear move looks real: three bearish sessions and at least two other checks met.",
}


def regime_state(path: Path = WATCH_CSV) -> dict:
    rows = read_rows(path)
    if not rows:
        return nodata("no regime-watch history yet")
    last = rows[-1]
    return {"ok": True, "date": as_date(last.get("date")), "status": (last.get("status") or "?").upper(),
            "checks": [(txt, truthy(last.get(k))) for k, txt in CHECKS],
            "n_confirm": last.get("n_confirm"), "streak": last.get("bear_streak"),
            "strip": [((as_date(r.get("date")) or "?"), (r.get("status") or "?").upper()) for r in rows[-30:]]}


# ── 4. book ───────────────────────────────────────────────────────────────────
def book_state(results: Path = RESULTS_CSV, proxy: Path = PROXY_CSV) -> dict:
    rr, pp = read_rows(results), read_rows(proxy)
    if rr is None and pp is None:
        return nodata("backtest exports not found")
    rows = []
    for src, rs in (("real", rr), ("proxy", pp)):
        for r in rs or []:
            d, pnl = as_date(r.get("signal_date")), num(r.get("realized_pnl_abs"))
            if d and pnl is not None:
                rows.append((d, pnl, (r.get("path_status") or "").strip(), src))
    if not rows:
        return nodata("no priced rows in the exports")
    rows.sort(key=lambda t: t[0])
    n_real = sum(1 for t in rows if t[3] == "real")
    fin = [t for t in rows if t[2] == "complete"]
    opn = [t for t in rows if t[2] == "open_at_data_end"]
    car = [t for t in rows if t[2] == "carried"]
    fwd = [t for t in rows if t[0] >= FORWARD_START]
    fwd_fin = [t for t in fwd if t[2] == "complete"]
    wins = sum(1 for t in fin if t[1] > 0)

    def curve(sel):
        by: dict[str, float] = {}
        for t in sel:
            by[t[0]] = by.get(t[0], 0.0) + t[1]
        tot, out = 0.0, []
        for d in sorted(by):
            tot += by[d]
            out.append((d, tot))
        return out
    return {"ok": True, "n": len(rows), "n_real": n_real, "n_proxy": len(rows) - n_real,
            "n_fin": len(fin), "n_open": len(opn), "n_carried": len(car),
            "win_rate": wins / len(fin) if fin else None,
            "pnl_fin": sum(t[1] for t in fin), "pnl_open": sum(t[1] for t in opn + car),
            "fwd_n": len(fwd), "fwd_fin": len(fwd_fin), "fwd_pnl": sum(t[1] for t in fwd),
            "fwd_pnl_fin": sum(t[1] for t in fwd_fin),
            "curve_fin": curve(fin), "curve_all": curve(rows),
            "first": rows[0][0], "last": rows[-1][0]}


# ── 5. flow layer ─────────────────────────────────────────────────────────────
def gate_state() -> dict:
    g, d, b = outcome_block(GATE_MD), outcome_block(DIP_MD), outcome_block(BENCH_MD)
    verdict = None
    if g["ok"]:
        m = re.search(r"\b(KEEP|WAIT|RETIRE)\b", g["text"])
        verdict = m[1] if m else None
    floor = None
    try:
        m = re.search(r"^MIN_DATES\s*=\s*(\d+)", DIP_PY.read_text(encoding="utf-8"), re.M)
        floor = int(m[1]) if m else None
    except OSError:
        pass
    n_dates = None
    pr = backtested_dates(RESULTS_CSV, PROXY_CSV)
    book = book_state()
    if book["ok"]:
        n_dates = len({d_ for d_, _ in book["curve_all"] if d_ >= FORWARD_START})
    return {"ok": g["ok"] or d["ok"] or b["ok"], "gate": g, "dip": d, "bench": b,
            "verdict": verdict, "floor": floor, "fwd_dates": n_dates, "have_exports": pr is not None}


# ── 6. studies ────────────────────────────────────────────────────────────────
def studies_state() -> dict:
    try:
        from scripts.study_map import catalog
    except Exception as e:  # noqa: BLE001  catalog is another session's file; never crash on it
        return nodata(f"study catalog unreadable ({type(e).__name__})")
    counts: dict[str, int] = {}
    open_list = []
    for name, s in catalog.STUDIES.items():
        counts[s.state] = counts.get(s.state, 0) + 1
        if s.state == "open":
            open_list.append((name, md_plain(s.question)))
    labels = dict(catalog.STATES)
    return {"ok": True, "counts": counts, "labels": labels, "open": open_list,
            "total": sum(counts.values())}


# ── 7. waiting on the operator ────────────────────────────────────────────────
DONE_WORDS = ("DONE", "RESOLVED", "DECIDED", "CLOSED")


def waiting_state(path: Path = NEXT_MD, limit: int = 8) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return nodata("research/next-steps.md not found")
    items: list[str] = []
    m = re.search(r"^### Waiting on the operator\s*\n(.*?)(?=^#{1,3} )", text, re.S | re.M)
    parsed = False
    if m:
        parsed = True
        for it in re.finditer(r"^(\d+)\. (.*?)(?=^\d+\. |\Z)", m[1], re.S | re.M):
            body = it[2]
            lead = re.match(r"\s*\*\*(.*?)\*\*", body, re.S)
            word = (lead[1].split()[0] if lead and lead[1].split() else "").upper().strip(".,—")
            if lead and word not in DONE_WORDS:
                items.append(md_plain(lead[1])[:230])
    for ln in re.findall(r"^\|\s*(P\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$", text, re.M):
        step, _who, what, blocks = ln
        if "operator" in blocks.lower():
            items.append(md_plain(f"{what.strip()} Waiting on: {blocks.strip()}")[:230])
            parsed = True
    if not parsed and not items:
        return nodata("could not find operator items in next-steps.md")
    return {"ok": True, "items": items[:limit], "extra": max(0, len(items) - limit)}


# ── rendering ─────────────────────────────────────────────────────────────────
e = html.escape
PILL = {"ok": ("ship", "Fresh"), "warn": ("open", "Slipping"), "bad": ("con", "Stale"), "none": ("null", "No data")}
REGIME_CLS = {"CLEAR": "ship", "WATCH": "open", "CONFIRMED": "con"}


def money(x: float) -> str:
    return f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def pill(cls: str, text: str) -> str:
    return f'<span class="pill {cls}">{e(text)}</span>'


def nocard(why: str) -> str:
    return f'<p class="nodata">No data. {e(why)}.</p>'


def line_chart(curves: list[tuple[str, list, str]], fwd_start: str) -> str:
    pts = [(d, v) for _, c, _ in curves for d, v in c]
    if len(pts) < 2:
        return '<p class="nodata">Not enough points to draw.</p>'
    ds = sorted({d for d, _ in pts})
    t0, t1 = datetime.fromisoformat(ds[0]).toordinal(), datetime.fromisoformat(ds[-1]).toordinal()
    vs = [v for _, v in pts] + [0.0]
    lo, hi = min(vs), max(vs)
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pad, hi + pad
    W, H, L, R, T, B = 760, 280, 64, 12, 12, 28

    def X(d):
        return L + (datetime.fromisoformat(d).toordinal() - t0) / max(1, t1 - t0) * (W - L - R)

    def Y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)
    g = []
    step = max(1, round((hi - lo) / 4 / 500) * 500) if (hi - lo) > 2000 else (hi - lo) / 4
    v = np.ceil(lo / step) * step
    while v <= hi:
        g.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                 f'<text x="{L-6}" y="{Y(v)+4:.1f}" text-anchor="end" class="tick">{money(v).replace("+", "")}</text>')
        v += step
    g.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="zero"/>')
    for d in (ds[0], ds[len(ds) // 2], ds[-1]):
        g.append(f'<text x="{min(max(X(d), L+22), W-R-22):.1f}" y="{H-8}" text-anchor="middle" class="tick">{d}</text>')
    if ds[0] < fwd_start <= ds[-1]:
        g.append(f'<line x1="{X(fwd_start):.1f}" x2="{X(fwd_start):.1f}" y1="{T}" y2="{H-B}" class="fwd"/>'
                 f'<text x="{X(fwd_start)+4:.1f}" y="{T+10}" class="tick">forward period starts</text>')
    for name, c, cls in curves:
        if len(c) > 1:
            d_ = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in c)
            g.append(f'<polyline points="{d_}" class="ln {cls}"><title>{e(name)}</title></polyline>')
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Cumulative net profit and loss '
            f'by signal date" style="min-width:560px;width:100%;height:auto">{"".join(g)}</svg></div>')


def render(today: str, flow: dict, reg: dict, book: dict, gate: dict, studies: dict, wait: dict) -> str:
    out: list[str] = []
    # status sentence
    bad = [i for i in flow["items"] if i["state"] in ("bad",)] if flow["ok"] else []
    bits = []
    bits.append("Data is flowing." if not bad else f"{len(bad)} data feed(s) look stale.")
    if reg["ok"]:
        bits.append(f"The market regime reads {reg['status']}.")
    if gate.get("verdict"):
        bits.append(f"The keep-or-kill rule reads {gate['verdict']}.")
    if wait["ok"]:
        bits.append(f"{len(wait['items']) + wait['extra']} item(s) are waiting on you.")
    cls = "con" if bad else "ship"
    out.append(f'<header><p class="eyebrow">Project dashboard</p><h1>As of {e(today)}</h1>'
               f'<p class="lede">{e(" ".join(bits))}</p></header>')

    # 2 data flowing
    s = ['<section><h2>Is the data flowing?</h2><p class="q">Each row is the newest date a stage has. '
         'Age counts weekdays behind today.</p>']
    if flow["ok"]:
        s.append('<ul class="rows">')
        for i in flow["items"]:
            c, t = PILL[i["state"]]
            when = i["date"] or "none"
            meta = " · ".join(x for x in ([f'{i["age"]} weekday(s) ago'] if i.get("age") is not None else [])
                              + ([i["note"]] if i.get("note") else []))
            s.append(f'<li><div><strong>{e(i["label"])}</strong><span class="sub">{e(i["explain"])}</span></div>'
                     f'<div class="r"><span class="mono">{e(when)}</span>{pill(c, t)}'
                     f'<span class="sub">{e(meta)}</span></div></li>')
        s.append("</ul>")
        if flow["pending_known"]:
            pend = flow["pending"]
            if pend:
                s.append(f'<p><strong>{len(pend)}</strong> analysed day(s) since {FORWARD_START} have no backtest yet: '
                         f'<span class="mono">{e(", ".join(pend))}</span>. The newest ones need later prices first.</p>')
            else:
                s.append(f'<p>Every analysed day since {FORWARD_START} has a backtest.</p>')
    else:
        s.append(nocard(flow.get("why", "")))
    s.append("</section>")
    out.append("".join(s))

    # 3 regime
    s = ['<section><h2>What is the market regime today?</h2>'
         '<p class="q">A daily checklist for whether a bear move is real. It describes the market. '
         'It changes no trade and its limits are not validated.</p>']
    if reg["ok"]:
        rc = REGIME_CLS.get(reg["status"], "null")
        s.append(f'<p class="big">{pill(rc, reg["status"])} <span class="sub">as of {e(reg["date"] or "?")}</span></p>'
                 f'<p>{e(STATUS_WORDS.get(reg["status"], ""))}</p><ul class="checks">')
        for txt, met in reg["checks"]:
            s.append(f'<li>{pill("con" if met else "null", "Met" if met else "Not met")} {e(txt)}</li>')
        s.append('</ul><p class="sub">Last 30 sessions (oldest left):</p><div class="strip">')
        for d, st in reg["strip"]:
            s.append(f'<i class="{REGIME_CLS.get(st, "null")}" title="{e(d)} {e(st)}"></i>')
        s.append('</div><p class="sub legend"><i class="ship"></i> clear <i class="open"></i> watch '
                 '<i class="con"></i> confirmed</p>')
    else:
        s.append(nocard(reg.get("why", "")))
    s.append("</section>")
    out.append("".join(s))

    # 4 book
    s = ['<section><h2>How is the backtested book doing?</h2><p class="q">Simulated trades from every '
         'analysed play. Real prices where they exist, a stand-in "proxy" where a play could not be priced '
         'directly. Profit and loss is net of costs.</p>']
    if book["ok"]:
        s.append('<div class="tiles">'
                 f'<div class="tile"><span class="k">Simulated trades</span><span class="v">{book["n"]:,}</span>'
                 f'<span class="sub">{book["n_real"]:,} real · {book["n_proxy"]:,} proxy</span></div>'
                 f'<div class="tile"><span class="k">Finished</span><span class="v">{book["n_fin"]:,}</span>'
                 f'<span class="sub">{book["win_rate"]*100:.0f}% were winners</span></div>'
                 f'<div class="tile"><span class="k">Not finished yet</span><span class="v">'
                 f'{book["n_open"] + book["n_carried"]:,}</span><span class="sub">{book["n_open"]:,} open · '
                 f'{book["n_carried"]:,} carried on a last price</span></div>'
                 f'<div class="tile"><span class="k">Net, finished trades</span><span class="v">'
                 f'{money(book["pnl_fin"])}</span><span class="sub">{money(book["pnl_open"])} more on the unfinished, '
                 'which is a paper mark only</span></div></div>')
        s.append(line_chart([("Finished trades only", book["curve_fin"], "a"),
                             ("Including unfinished trades (not final)", book["curve_all"], "b")], FORWARD_START))
        s.append('<p class="sub legend"><span class="key a"></span> finished trades only '
                 '<span class="key b"></span> adding the unfinished marks (can still change)</p>')
        s.append(f'<p><strong>Since {FORWARD_START} (the forward period):</strong> {book["fwd_n"]} simulated trades, '
                 f'{book["fwd_fin"]} finished. Net so far {money(book["fwd_pnl"])}; finished trades alone '
                 f'{money(book["fwd_pnl_fin"])}. Most of these are still open, so read the number as a first look.</p>')
    else:
        s.append(nocard(book.get("why", "")))
    s.append("</section>")
    out.append("".join(s))

    # 5 flow layer
    s = ['<section><h2>Is the flow layer earning its keep?</h2><p class="q">The "flow layer" is the model\'s daily '
         'stock picks plus the ranking that decides what to deploy. A rule written in advance says when to keep or '
         'drop it.</p>']
    if gate["ok"]:
        if gate["verdict"]:
            gc = {"KEEP": "ship", "WAIT": "open", "RETIRE": "con"}[gate["verdict"]]
            expl = {"KEEP": "The evidence supports the picks. Keep them.",
                    "WAIT": "The evidence is not strong enough either way. Keep running and collect more days.",
                    "RETIRE": "The picks failed the tests set in advance. The rule says drop them."}[gate["verdict"]]
            s.append(f'<p class="big">{pill(gc, gate["verdict"])}</p><p>{e(expl)}</p>')
        for title, key, what in (
                ("The keep-or-kill rule", "gate", "Combines the two tests below into KEEP, WAIT or RETIRE."),
                ("Dip-buying forward test", "dip", "Do the best picks do better when the market has just dipped? "
                                                    "Graded only on days after the rule was fixed."),
                ("Picks versus a mechanical rule", "bench", "Do the model's picks beat a plain rule applied to the "
                                                            "same stocks?")):
            b = gate[key]
            s.append(f'<h3>{e(title)}</h3><p class="sub">{e(what)}</p>')
            s.append(f'<blockquote>{e(b["text"])}</blockquote>' if b["ok"] else nocard(b["why"]))
        if gate["floor"] and gate["fwd_dates"] is not None:
            frac = min(1.0, gate["fwd_dates"] / gate["floor"])
            s.append(f'<h3>How much forward evidence is in</h3><p>The dip test needs at least {gate["floor"]} '
                     f'forward signal days in each group. The book has priced <strong>{gate["fwd_dates"]}</strong> '
                     f'day(s) since {FORWARD_START} in total, before splitting into groups.</p>'
                     f'<div class="bar"><b style="width:{frac*100:.0f}%"></b></div>')
    else:
        s.append(nocard("the three outcome files were not found"))
    s.append("</section>")
    out.append("".join(s))

    # 6 studies
    s = ['<section><h2>What have the studies found?</h2><p class="q">Each study asks one question of the backtest '
         'book. Most come back empty, which is a useful answer.</p>']
    if studies["ok"]:
        order = ["shipped", "null", "open", "reference"]
        cls_ = {"shipped": "ship", "null": "null", "open": "open", "reference": "pos"}
        total = studies["total"] or 1
        s.append('<div class="stack" role="img" aria-label="Studies by state">')
        for k in order:
            n = studies["counts"].get(k, 0)
            if n:
                s.append(f'<b class="{cls_[k]}" style="flex:{n}">{n}</b>')
        s.append('</div><p class="sub legend">')
        for k in order:
            s.append(f'<i class="{cls_[k]}"></i> {e(studies["labels"].get(k, k))} '
                     f'{studies["counts"].get(k, 0)} ')
        s.append(f'</p><p>{total} studies in all. "Shipped" means a rule was adopted. "Null" means no effect was '
                 'found. "Open" means it is waiting for more days of data.</p>')
        s.append(f'<details><summary>The {len(studies["open"])} open studies</summary><ul class="plain">')
        for n, q in studies["open"]:
            s.append(f'<li><strong>{e(n)}</strong> <span class="sub">{e(q[:170])}</span></li>')
        s.append("</ul></details>")
    else:
        s.append(nocard(studies.get("why", "")))
    s.append("</section>")
    out.append("".join(s))

    # 7 waiting
    s = ['<section><h2>What is waiting on you?</h2>']
    if wait["ok"]:
        s.append('<p class="q">Read from the operator list and the plan table in research/next-steps.md. This is a text match, so check the file if one looks wrong.</p>')
        if wait["items"]:
            s.append('<ol class="plain">' + "".join(f"<li>{e(i)}</li>" for i in wait["items"]) + "</ol>")
            if wait["extra"]:
                s.append(f'<p class="sub">{wait["extra"]} more in the file.</p>')
        else:
            s.append("<p>Nothing is marked as waiting on you.</p>")
    else:
        s.append(nocard(wait.get("why", "")))
    s.append("</section>")
    out.append("".join(s))

    out.append('<footer><p>Where each section comes from.</p><ul class="plain sub">'
               "<li>Data flowing: backtests/to_evaluate (analysis, BacktestResults, BacktestProxy exports), "
               "backtests/mech_regime/spy_vix_daily_full.csv, backtests/regime_watch/history.csv, "
               "backtests/run_logs/daily-loop-*.log</li>"
               "<li>Regime: backtests/regime_watch/history.csv (columns from lib/regime_watch.py)</li>"
               "<li>Book: BacktestResults and BacktestProxy exports, columns realized_pnl_abs and path_status</li>"
               "<li>Flow layer: outcome blocks in research/pre-registrations (programme_gate, dip_buy, "
               "mechanical_benchmark) and MIN_DATES in dip_buy.py</li>"
               "<li>Studies: scripts/study_map/catalog.py</li>"
               "<li>Waiting on you: research/next-steps.md</li></ul>"
               "<p class=\"sub\">Local files only. Nothing from journal/ or portfolio/.</p></footer>")
    return "".join(out)


HEAD = """<title>Project Dashboard</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Spectral:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#f4f5f7;--surface:#ffffff;--fg:#161a21;--muted:#5a6271;--line:#dde1e7;--accent:#2c56c9;--ship:#0f7a63;--ship-bg:#e1f3ee;--pos:#2c56c9;--pos-bg:#e5ecfb;--null:#646b78;--null-bg:#eceef1;--con:#b8392f;--con-bg:#fae7e5;--open:#9a6410;--open-bg:#fbf0dc;color-scheme:light}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#12151a;--surface:#1a1e25;--fg:#e8eaee;--muted:#9aa2b0;--line:#2b313b;--accent:#7f9df0;--ship:#4fc7a6;--ship-bg:#123329;--pos:#8ea9f2;--pos-bg:#1c2846;--null:#a5abb6;--null-bg:#252a33;--con:#f08a80;--con-bg:#3a1d1a;--open:#e7b55c;--open-bg:#372a12;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12151a;--surface:#1a1e25;--fg:#e8eaee;--muted:#9aa2b0;--line:#2b313b;--accent:#7f9df0;--ship:#4fc7a6;--ship-bg:#123329;--pos:#8ea9f2;--pos-bg:#1c2846;--null:#a5abb6;--null-bg:#252a33;--con:#f08a80;--con-bg:#3a1d1a;--open:#e7b55c;--open-bg:#372a12;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:24px 48px;overflow-wrap:anywhere}
.wrap,body>*{max-width:1040px;margin-inline:auto}
h1,h2,h3{font-family:Spectral,Georgia,"Times New Roman",serif;font-weight:600;line-height:1.2;margin:0}
h1{font-size:clamp(28px,5vw,40px)} h2{font-size:24px;margin-bottom:4px} h3{font-size:17px;margin:20px 0 2px}
.eyebrow{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.lede{font-size:18px;margin:8px 0 0;color:var(--fg)}
header{padding-bottom:20px;border-bottom:1px solid var(--line)}
section{padding:28px 0;border-bottom:1px solid var(--line)}
.q,.sub{color:var(--muted)} .q{margin:0 0 14px} .sub{font-size:14px}
.mono,.v,.tick,td{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace}
.mono,.v,.tick,.tile,strong{font-variant-numeric:tabular-nums}
.pill{display:inline-block;font-size:12px;font-weight:600;padding:1px 9px;border-radius:99px;margin-right:6px;white-space:nowrap}
.pill.ship{background:var(--ship-bg);color:var(--ship)} .pill.open{background:var(--open-bg);color:var(--open)}
.pill.con{background:var(--con-bg);color:var(--con)} .pill.null{background:var(--null-bg);color:var(--null)}
.pill.pos{background:var(--pos-bg);color:var(--pos)}
.big{font-size:20px;margin:0 0 6px}
ul.rows{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
ul.rows li{display:flex;flex-wrap:wrap;gap:6px 16px;justify-content:space-between;padding:12px 14px;border-top:1px solid var(--line)}
ul.rows li:first-child{border-top:0} ul.rows .r{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
ul.rows .sub{display:block}
ul.checks,ul.plain{list-style:none;padding:0;margin:8px 0}
ul.checks li{padding:5px 0} ul.plain li{padding:4px 0} ol.plain{padding-left:22px} ol.plain li{padding:4px 0}
.strip{display:flex;gap:3px;margin:6px 0}
.strip i{flex:1;height:22px;border-radius:3px;min-width:4px}
i.ship,.stack b.ship{background:var(--ship)} i.open,.stack b.open{background:var(--open)} i.con{background:var(--con)}
i.null,.stack b.null{background:var(--null)} i.pos,.stack b.pos{background:var(--pos)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column}
.tile .k{font-size:13px;color:var(--muted)} .tile .v{font-size:24px;font-weight:500}
.chart{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:8px}
.chart .grid{stroke:var(--line);stroke-width:1} .chart .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3}
.chart .fwd{stroke:var(--accent);stroke-width:1;stroke-dasharray:4 3}
.chart .tick{fill:var(--muted);font-size:11px}
.chart .ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .ln.a{stroke:var(--accent)} .chart .ln.b{stroke:var(--open);stroke-dasharray:5 4}
.key{display:inline-block;width:18px;height:0;border-top:3px solid var(--accent);vertical-align:middle;margin:0 4px 0 10px}
.key.b{border-top:3px dashed var(--open)}
blockquote{margin:6px 0 0;padding:10px 14px;background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:6px;font-size:15px}
.bar{height:10px;background:var(--null-bg);border-radius:99px;overflow:hidden}
.bar b{display:block;height:100%;background:var(--accent);border-radius:99px}
.stack{display:flex;gap:2px;height:32px;border-radius:8px;overflow:hidden}
.stack b{display:flex;align-items:center;justify-content:center;color:#fff;font:500 13px "IBM Plex Mono",monospace;min-width:24px}
details{margin-top:8px} summary{cursor:pointer;color:var(--accent);padding:4px 0}
.nodata{color:var(--muted);font-style:italic;margin:6px 0}
footer{padding-top:20px;font-size:14px;color:var(--muted)}
@media (prefers-reduced-motion:no-preference){.bar b{transition:width .4s ease}}
</style>
"""


def build(today: str) -> tuple[str, dict]:
    flow = pipeline_state(today)
    reg = regime_state()
    book = book_state()
    gate = gate_state()
    studies = studies_state()
    wait = waiting_state()
    page = HEAD + render(today, flow, reg, book, gate, studies, wait)
    return page, {"flow": flow, "reg": reg, "book": book, "gate": gate, "studies": studies, "wait": wait}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    page, d = build(a.today)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if not a.quiet:
        print(f"dashboard -> {out} ({len(page):,} bytes), as of {a.today}")
        for i in d["flow"]["items"]:
            print(f"  {i['label']:<22} {i['date'] or 'none':<11} {i['state']}  {i.get('note', '')}")
        if d["flow"]["pending_known"]:
            print(f"  analysed, not backtested since {FORWARD_START}: {len(d['flow']['pending'])}")
        if d["reg"]["ok"]:
            print(f"  regime: {d['reg']['status']} ({d['reg']['date']})")
        b = d["book"]
        if b["ok"]:
            print(f"  book: {b['n']} rows ({b['n_real']} real, {b['n_proxy']} proxy), {b['n_fin']} finished, "
                  f"{b['n_open']} open, {b['n_carried']} carried, win {b['win_rate']*100:.0f}%, "
                  f"forward {b['fwd_n']} rows")
        print(f"  gate: {d['gate'].get('verdict')}, forward dates {d['gate'].get('fwd_dates')}/{d['gate'].get('floor')}")
        if d["studies"]["ok"]:
            print(f"  studies: {d['studies']['counts']}")
        if d["wait"]["ok"]:
            print(f"  waiting: {len(d['wait']['items'])} shown (+{d['wait']['extra']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
