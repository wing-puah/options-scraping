"""`scripts/collector/fetch_substitute_legs.py` — the narrow_to_fit F3 scrape.

No network: the Barchart session is a stand-in, the cache is a temp
directory, and the book is replaced by hand-built records. Pinned here:

  * `--dry-run` prints the contract list and count and touches no session;
  * `--limit N` requests at most N contracts;
  * a fetch goes through `history.fetch_option_histories` — the cache file is
    staged and written there, and a refused (HTTP error) fetch is NEVER
    recorded as unlisted;
  * the target census drops a contract the skip-list holds ON EVIDENCE and
    keeps one it holds only as a seeded entry;
  * the run ends with the backup reminder.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from lib.barchart import options as bo  # noqa: E402
from lib.barchart import session as bs  # noqa: E402
from scripts.backtest.shared import history  # noqa: E402
from scripts.backtest.shared import unlisted  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402
from scripts.collector import fetch_substitute_legs as FSL  # noqa: E402

EXP = date(2025, 2, 21)
SIGNAL = date(2025, 1, 6)

_CSV = ('Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,Gamma,'
        "Theta,Vega,Rho,Theo,Price~,Bid,Ask\n"
        "2025-01-07,4.50,4.60,4.40,4.50,0.05,1.00%,10,100,"
        "0.30,0.40,0.01,-0.02,0.05,0.01,4.50,100.00,4.45,4.55\n")


def _target(strike, opt="Call"):
    return dict(ticker="TEST", expiration=EXP, strike=float(strike), opt_type=opt,
                category="target")


@pytest.fixture
def no_book(monkeypatch):
    targets = [_target(105), _target(107), _target(109)]
    census = {"candidates": 3, "candidate_dates": 1, "over $500": 3}
    monkeypatch.setattr(FSL, "load_book", lambda include_bs=False: ([], {}))
    monkeypatch.setattr(FSL, "budgets", lambda: (500.0, 1000.0))
    monkeypatch.setattr(FSL.NTF, "substitute_targets",
                        lambda records, budgets, scope="target_wider": (targets, census))
    return targets


def test_dry_run_prints_the_list_and_count_and_opens_no_session(no_book, monkeypatch,
                                                                capsys):
    def _boom(*a, **k):
        raise AssertionError("a dry run must not fetch")
    monkeypatch.setattr(FSL, "fetch", _boom)
    assert FSL.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "unique uncached contracts to fetch: 3" in out
    assert "105.00C" in out and "109.00C" in out
    assert "[dry-run] nothing fetched" in out
    assert "backup_research_caches.py push" in out


def test_limit_caps_the_contracts_requested(no_book, monkeypatch, capsys):
    seen = []

    async def _fake(targets, headless, timeout_ms):
        seen.extend(targets)
        return len(targets)
    monkeypatch.setattr(FSL, "fetch", _fake)
    assert FSL.main(["--limit", "2"]) == 0
    assert [t["strike"] for t in seen] == [105.0, 107.0]
    out = capsys.readouterr().out
    assert "fetched 2 of 2 requested; 1 left for a later run" in out
    assert "backup_research_caches.py push" in out


def _session(outcomes):
    """A BarchartSession stand-in: {strike: outcome}; OK returns one row."""
    class _S:
        def __init__(self, *a, **k):
            self.last_history_outcome = None
            self.last_history_logged_in = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def fetch_history_csv(self, url, timeout_ms):
            strike = float(url.split("%7C")[-1].split("/")[0][:-1])
            self.last_history_outcome = outcomes[strike]
            return _CSV if outcomes[strike] == bs.HISTORY_OK else None
    return _S


def test_a_fetch_goes_through_the_history_loop_and_a_refusal_is_not_unlisted(
        tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_CACHE", tmp_path)
    monkeypatch.setattr(history, "FETCH_PAUSE_S", 0)
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.setattr(history, "BarchartSession",
                        _session({105.0: bs.HISTORY_OK, 107.0: bs.HISTORY_HTTP_ERROR}))
    got = FSL.asyncio.run(FSL.fetch([_target(105), _target(107)], True, 1000))
    assert got == 1
    assert bo.cache_path(tmp_path, "TEST", EXP, 105.0, "Call").exists()
    assert not bo.cache_path(tmp_path, "TEST", EXP, 107.0, "Call").exists()
    # A 403/5xx-style refusal is trouble around a fetch, never evidence.
    assert unlisted.load(tmp_path / unlisted.FILENAME) == {}


# ── the target census and the skip-list ─────────────────────────────────────

def _grid_len():
    d, n = SIGNAL + timedelta(days=1), 0
    while d <= EXP:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def _pick(mlpc):
    legs = f"TEST:{EXP}:100:C +1\nTEST:{EXP}:110:C -1"
    row = {"signal_date": SIGNAL.isoformat(), "ticker": "TEST",
           "structure": "bull_call_spread", "contracts": "1",
           "dte_entry": str((EXP - SIGNAL).days - 1), "entry_option_price": "7.0",
           "entry_underlying": "104", "legs": legs,
           "entry_leg_detail": (f"TEST:{EXP}:100:C +1  px=8 iv=30% delta=0.6\n"
                                f"TEST:{EXP}:110:C -1  px=1 iv=30% delta=0.2"),
           "daily_price_csv": ",".join(["7.0"] * _grid_len())}
    return {"t": Trade(row), "credit": False, "structure": "bull_call_spread",
            "max_loss_per_contract": mlpc, "date": SIGNAL.isoformat(),
            "ticker": "TEST"}


def test_census_drops_evidence_entries_and_keeps_everything_else(monkeypatch):
    recs = [_pick(700.0), _pick(300.0)]
    monkeypatch.setattr(NTF, "candidates", lambda records: records)
    idx = {("TEST", EXP): {100.0: {"C"}, 110.0: {"C"}}}
    all_targets, census = NTF.substitute_targets(recs, (500.0,), idx=idx,
                                                 evidence=set(), scope="between")
    assert census["over $500"] == 1            # the $300 pick fits already
    strikes = sorted(t["strike"] for t in all_targets)
    assert strikes and all(100 < k < 110 for k in strikes)
    blocked = NTF.contract_stem("TEST", EXP, strikes[0], "Call")
    kept, census2 = NTF.substitute_targets(recs, (500.0,), idx=idx,
                                           evidence={blocked}, scope="between")
    assert strikes[0] not in {t["strike"] for t in kept}
    assert census2["over $500 between unlisted on evidence"] == 1


def test_target_wider_scope_fetches_the_estimate_and_its_wider_neighbour(monkeypatch):
    monkeypatch.setattr(NTF, "candidates", lambda records: records)
    idx = {("TEST", EXP): {100.0: {"C"}, 110.0: {"C"}}}
    targets, census = NTF.substitute_targets([_pick(700.0)], (500.0,), idx=idx,
                                             evidence=set())
    cats = sorted(t["category"] for t in targets)
    assert cats in (["next_wider", "target"], ["target"])
    assert all(t["opt_type"] == "Call" and 100 < t["strike"] <= 110 for t in targets)
    assert census["unique uncached contracts"] == len(targets)
