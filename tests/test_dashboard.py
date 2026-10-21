"""scripts/dashboard.py gatherers on tiny fixtures. Missing files must degrade, never crash."""
import csv
from pathlib import Path

from scripts import dashboard as d


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_missing_files_give_no_data(tmp_path):
    ghost = tmp_path / "nope.csv"
    assert d.regime_state(ghost)["ok"] is False
    assert d.book_state(ghost, ghost)["ok"] is False
    assert d.waiting_state(ghost)["ok"] is False
    assert d.outcome_block(ghost)["ok"] is False
    assert d.last_loop_log(tmp_path)["ok"] is False
    st = d.pipeline_state("2026-10-21", {k: ghost for k in ("analysis", "results", "proxy", "mech", "watch")}
                          | {"logs": tmp_path})
    assert all(i["state"] == "none" for i in st["items"])


def test_pipeline_ages_and_pending(tmp_path):
    a, r, p = tmp_path / "a.csv", tmp_path / "r.csv", tmp_path / "p.csv"
    write_csv(a, [{"date": "2026-10-19", "ticker": "NVDA"}, {"date": "2026-10-20", "ticker": "NVDA"},
                  {"date": "2026-10-20", "ticker": "MARKET"}, {"date": "2026-10-21", "ticker": "MARKET"}])
    write_csv(r, [{"signal_date": "2026-10-19"}])
    write_csv(p, [{"signal_date": "2026-10-16"}])
    st = d.pipeline_state("2026-10-21", {"analysis": a, "results": r, "proxy": p, "logs": tmp_path})
    items = {i["label"]: i for i in st["items"]}
    assert items["Newest analysis"]["date"] == "2026-10-20"       # MARKET-only day ignored
    assert items["Newest analysis"]["state"] == "ok"
    assert items["Newest backtested day"]["date"] == "2026-10-19"
    assert st["pending"] == ["2026-10-20"]


def test_loop_log_end_states(tmp_path):
    (tmp_path / "daily-loop-20261020-1000.log").write_text("x\ndaily-loop complete in 5s\n")
    assert d.last_loop_log(tmp_path)["end"] == "ok"
    (tmp_path / "daily-loop-20261021-1000.log").write_text("!!! STEP 3 FAILED (x) exit code 1 after 2s; stopping.\n")
    r = d.last_loop_log(tmp_path)
    assert r["end"] == "failed" and r["date"] == "2026-10-21"


def test_regime_state(tmp_path):
    p = tmp_path / "h.csv"
    write_csv(p, [{"date": f"2026-10-{i:02d}", "status": "CLEAR", "n_confirm": "0", "bear_streak": "0",
                   **{k: "False" for k, _ in d.CHECKS}} for i in range(1, 4)]
              + [{"date": "2026-10-20", "status": "WATCH", "n_confirm": "2", "bear_streak": "0",
                  **{k: "True" for k, _ in d.CHECKS}}])
    r = d.regime_state(p)
    assert r["status"] == "WATCH" and all(met for _, met in r["checks"])
    assert [s for _, s in r["strip"]] == ["CLEAR"] * 3 + ["WATCH"]


def test_book_state_splits_open_and_forward(tmp_path):
    r, p = tmp_path / "r.csv", tmp_path / "p.csv"
    write_csv(r, [
        {"signal_date": "2026-09-01", "realized_pnl_abs": "100", "path_status": "complete"},
        {"signal_date": "2026-09-02", "realized_pnl_abs": "-50", "path_status": "complete"},
        {"signal_date": "2026-09-24", "realized_pnl_abs": "30", "path_status": "open_at_data_end"},
    ])
    write_csv(p, [
        {"signal_date": "2026-09-25", "realized_pnl_abs": "", "path_status": ""},          # skipped play
        {"signal_date": "2026-09-26", "realized_pnl_abs": "20", "path_status": "complete"},
    ])
    b = d.book_state(r, p)
    assert (b["n"], b["n_real"], b["n_proxy"]) == (4, 3, 1)
    assert (b["n_fin"], b["n_open"]) == (3, 1)
    assert b["pnl_fin"] == 70 and b["fwd_n"] == 2 and b["fwd_pnl"] == 50
    assert abs(b["win_rate"] - 2 / 3) < 1e-9
    assert b["curve_fin"][-1] == ("2026-09-26", 70.0)


def test_outcome_block_and_waiting(tmp_path):
    f = tmp_path / "g.md"
    f.write_text("x\n<!-- outcome:start -->\n> Latest outcome: `WAIT` ([log](a.md))\n<!-- outcome:end -->\n")
    assert d.outcome_block(f)["text"] == "Latest outcome: WAIT (log)"
    n = tmp_path / "n.md"
    n.write_text("### Waiting on the operator\n\n1. **DONE 2026-09-06** — x\n\n"
                 "2. **OPEN — decide the cap.** more\n\n## next\n")
    w = d.waiting_state(n)
    assert w["ok"] and w["items"] == ["OPEN — decide the cap."]


def test_render_survives_all_missing():
    bad = {"ok": False, "why": "gone"}
    page = d.render("2026-10-21", {"ok": False, "why": "gone"}, bad, bad, {"ok": False}, bad, bad)
    assert page.count("No data") >= 5


def test_forward_dip_days_counts_below_sma(tmp_path):
    p = tmp_path / "mech.csv"
    rows = ["date,spy_close,vix_close"]
    for i in range(60):
        rows.append(f"2026-{7 + i // 28:02d}-{i % 28 + 1:02d},100,15")
    rows.append("2026-09-24,90,20")   # below the flat 100 average
    rows.append("2026-09-25,110,20")  # above
    p.write_text("\n".join(rows) + "\n")
    from scripts import dashboard as dash
    assert dash.forward_dip_days(p) == {"days": 2, "dips": 1}
    assert dash.forward_dip_days(tmp_path / "missing.csv") is None


def test_ledger_copied_as_full_page(tmp_path):
    src = tmp_path / "ledger.html"
    src.write_text("<title>Flow Edge Ledger</title><p>hi</p>")
    out = d.write_ledger(tmp_path, src)
    page = out.read_text()
    assert out.name == d.LEDGER_NAME
    assert page.startswith("<!doctype html>") and "<title>Flow Edge Ledger</title>" in page
    assert d.write_ledger(tmp_path, tmp_path / "missing.html") is None


def test_main_writes_both_pages_and_links_the_ledger(tmp_path):
    assert d.LEDGER_SRC.exists()
    assert d.main(["--out", str(tmp_path / "dashboard.html"), "--quiet"]) == 0
    page = (tmp_path / "dashboard.html").read_text()
    assert page.startswith("<!doctype html>") and f'href="{d.LEDGER_NAME}"' in page
    assert (tmp_path / d.LEDGER_NAME).exists()
