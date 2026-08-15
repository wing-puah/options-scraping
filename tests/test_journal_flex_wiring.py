"""Tests for transport selection — which source a given command line reaches for.

There is one transport (Flex) since 2026-08-15, so what these pin is narrower
and sharper than "which broker": whether an invocation FETCHES or reads only
what is on disk. Getting that wrong is expensive in a specific way — a run that
silently reads a stale export produces a journal that looks normal and describes
last month's account. They also pin that the Flex path never reaches the network
for greeks unless it was asked to.
"""

import io

import pytest

from scripts.journal import __main__ as cli
from scripts.journal import pull as pull_mod

HEADER = ("Description,UnderlyingSymbol,Open/CloseIndicator,Quantity,TradePrice,"
          "CostBasis,FifoPnlRealized,Strike,Expiry,DateTime,Put/Call,AssetClass,"
          "Symbol,TradeID,Conid,Buy/Sell")
ROW = ("NVDA 220 C,NVDA,O,1,5.00,500,0,220,2026-09-18,2026-08-14;103000,C,OPT,"
       "NVDA  260918C00220000,T1,100,BUY")


def flex_csv():
    return io.StringIO(f"{HEADER}\n{ROW}\n")


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------
def test_a_bare_run_fetches():
    """The exports on disk go stale the moment a fill lands, so the default has
    to be the live statement — this is the whole point of the 2026-08-15
    change."""
    assert cli._use_web_service(cli._parse_args([])) is True


def test_naming_files_means_offline():
    """--from-flex is an offline replay of a specific export; it must not
    quietly widen itself with a fetch."""
    assert cli._use_web_service(cli._parse_args(["--from-flex", "a.csv"])) is False
    assert cli._use_web_service(
        cli._parse_args(["--from-flex-positions", "p.csv"])) is False


def test_flex_web_re_enables_the_fetch_alongside_named_files():
    args = cli._parse_args(["--from-flex", "a.csv", "--flex-web"])
    assert cli._use_web_service(args) is True


@pytest.mark.parametrize("flag", ["--offline", "--no-flex-web"])
def test_offline_switches_the_fetch_off(flag):
    assert cli._use_web_service(cli._parse_args([flag])) is False


def test_from_flex_accepts_several_files():
    """The open book is netted across them — one year is not enough for a
    position entered in a prior year."""
    args = cli._parse_args(["--from-flex", "a.csv", "b.csv"])
    assert args.from_flex == ["a.csv", "b.csv"]


def test_net_liq_is_parsed_as_a_number():
    assert cli._parse_args(["--net-liq", "52000"]).net_liq == 52000.0


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
def _seen_kwargs(monkeypatch, argv):
    seen = {}

    def fake_flex(sources, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(pull_mod, "pull_flex", fake_flex)
    cli._fetch(cli._parse_args(argv))
    return seen


def test_the_fetch_decision_reaches_pull_flex(monkeypatch):
    assert _seen_kwargs(monkeypatch, [])["use_web_service"] is True
    assert _seen_kwargs(monkeypatch, ["--offline"])["use_web_service"] is False


def test_no_greeks_is_passed_through_as_enrich_false(monkeypatch):
    seen = _seen_kwargs(monkeypatch, ["--no-greeks", "--net-liq", "1000"])
    assert seen["enrich"] is False
    assert seen["net_liquidation"] == 1000.0


def test_a_dry_run_keeps_no_statement(monkeypatch):
    """--dry-run writes nothing, and a saved statement is still a write."""
    assert _seen_kwargs(monkeypatch, ["--dry-run"])["statement_dir"] is None
    assert _seen_kwargs(monkeypatch, [])["statement_dir"] is not None


# --------------------------------------------------------------------------
# pull_flex
# --------------------------------------------------------------------------
def test_pull_flex_without_enrichment_touches_no_network():
    raw = pull_mod.pull_flex([flex_csv()], use_web_service=False, enrich=False)
    assert raw["source"] == "ibkr-flex"
    assert raw["greeks"]["100"]["source"] == "unavailable"


def test_pull_flex_calls_the_enricher_with_the_session_date(monkeypatch):
    seen = {}

    def fake_enrich(raw, *, as_of, cache_dir=None, **_):
        seen["as_of"] = as_of
        return raw

    import scripts.journal.greeks as greeks_mod
    monkeypatch.setattr(greeks_mod, "enrich", fake_enrich)
    pull_mod.pull_flex([flex_csv()], use_web_service=False, enrich=True)
    assert seen["as_of"].isoformat() == "2026-08-14"


# --------------------------------------------------------------------------
# pull_flex — the second (OpenPositions) handshake
# --------------------------------------------------------------------------
POSITIONS_CSV = ("Conid,Quantity,AssetClass,Strike,Expiry,Put/Call,UnderlyingSymbol\n"
                 "100,1,OPT,220,2026-09-18,C,NVDA\n")


def test_from_flex_positions_is_parsed():
    args = cli._parse_args(["--from-flex-positions", "positions.csv"])
    assert args.from_flex_positions == "positions.csv"


def test_flex_web_fetches_both_queries_through_one_client(monkeypatch, tmp_path):
    """--flex-web with the OpenPositions query configured must run BOTH
    handshakes through the SAME FlexClient (one token, one session, one
    retry policy) rather than skip the second query or build a new client."""
    import lib.ibkr.flex as flex_mod

    calls = []

    class FakeClient:
        def __init__(self):
            calls.append("constructed")

        def fetch(self, query_id=None):
            calls.append(("fetch", query_id))
            return POSITIONS_CSV if query_id else f"{HEADER}\n{ROW}\n"

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: "pos-query-id")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)  # no local exports to widen with

    raw = pull_mod.pull_flex(use_web_service=True, enrich=False)

    assert calls == ["constructed", ("fetch", None), ("fetch", "pos-query-id")]
    assert raw["book_reconstructed"] is False


def test_one_query_saved_with_both_sections_costs_one_handshake(monkeypatch, tmp_path):
    """When BOTH env vars name the SAME saved query, that query carries both
    sections and the statement already in hand IS the declared book. Fetching
    it a second time would be another handshake for a byte-identical answer —
    and on one token, the thing that trips IBKR's 1018 rate limit."""
    import lib.ibkr.flex as flex_mod

    combined = f"{HEADER}\n{ROW}\n{POSITIONS_CSV}"
    calls = []

    class FakeClient:
        def __init__(self):
            self.query_id = "one-query-id"

        def fetch(self, query_id=None):
            calls.append(("fetch", query_id))
            return combined

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: "one-query-id")
    monkeypatch.setattr(flex_mod, "trades_query_id_from_env", lambda: "one-query-id")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)

    raw = pull_mod.pull_flex(use_web_service=True, enrich=False)

    assert calls == [("fetch", None)]              # ONE handshake, not two
    assert raw["book_reconstructed"] is False      # still the DECLARED book
    assert len(raw["positions"]) == 1
    assert len(raw["trades"]) == 1


def test_two_distinct_query_ids_still_run_two_handshakes(monkeypatch, tmp_path):
    """The fetch-once path must key on the ids being EQUAL, not on a positions
    query merely being configured — otherwise a real second query is skipped
    and the declared book silently becomes the trades statement."""
    import lib.ibkr.flex as flex_mod

    calls = []

    class FakeClient:
        def __init__(self):
            self.query_id = "trades-query-id"

        def fetch(self, query_id=None):
            calls.append(("fetch", query_id))
            return POSITIONS_CSV if query_id else f"{HEADER}\n{ROW}\n"

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: "pos-query-id")
    monkeypatch.setattr(flex_mod, "trades_query_id_from_env", lambda: "trades-query-id")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)

    pull_mod.pull_flex(use_web_service=True, enrich=False)

    assert calls == [("fetch", None), ("fetch", "pos-query-id")]


def test_flex_web_skips_the_second_handshake_when_no_positions_query_is_configured(
        monkeypatch, tmp_path):
    import lib.ibkr.flex as flex_mod

    calls = []

    class FakeClient:
        def __init__(self):
            pass

        def fetch(self, query_id=None):
            calls.append(("fetch", query_id))
            return f"{HEADER}\n{ROW}\n"

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: None)
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)

    raw = pull_mod.pull_flex(use_web_service=True, enrich=False)

    assert calls == [("fetch", None)]
    assert raw["book_reconstructed"] is True


def test_an_explicit_positions_source_wins_over_the_web_fetch(monkeypatch, tmp_path):
    """--from-flex-positions is the offline-replay path — it must win over the
    web-service second handshake for the same reason --from-flex wins over
    --flex-web for trades: a passed-in source is never silently overridden."""
    import io as io_mod
    import lib.ibkr.flex as flex_mod

    calls = []

    class FakeClient:
        def __init__(self):
            pass

        def fetch(self, query_id=None):
            calls.append(("fetch", query_id))
            return f"{HEADER}\n{ROW}\n"

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: "pos-query-id")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)

    raw = pull_mod.pull_flex(use_web_service=True, enrich=False,
                             positions_source=io_mod.StringIO(POSITIONS_CSV))

    # Only the trades fetch happened — the positions query was never called.
    assert calls == [("fetch", None)]
    assert raw["book_reconstructed"] is False


def test_a_fetched_statement_is_kept_verbatim(monkeypatch, tmp_path):
    """The pull records what was PARSED; when the parse is what's in doubt,
    only the statement itself settles it."""
    import lib.ibkr.flex as flex_mod

    class FakeClient:
        def fetch(self, query_id=None):
            return POSITIONS_CSV if query_id else f"{HEADER}\n{ROW}\n"

    monkeypatch.setattr(flex_mod, "FlexClient", FakeClient)
    monkeypatch.setattr(flex_mod, "positions_query_id_from_env", lambda: "pos-query-id")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path / "input")

    kept = tmp_path / "raw"
    pull_mod.pull_flex(use_web_service=True, enrich=False, statement_dir=kept)

    written = {p.name.rsplit("-", 1)[-1]: p.read_text() for p in kept.iterdir()}
    assert set(written) == {"trades.csv", "positions.csv"}
    assert written["positions.csv"] == POSITIONS_CSV


def test_flex_sources_defaults_to_every_export_not_just_the_newest(tmp_path, monkeypatch):
    for name in ("trades_2025.csv", "trades_2026.csv"):
        (tmp_path / name).write_text("x")
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)
    found = [p.name for p in pull_mod.flex_sources()]
    assert found == ["trades_2025.csv", "trades_2026.csv"]


def test_flex_sources_says_what_to_do_when_there_is_no_export(tmp_path, monkeypatch):
    monkeypatch.setattr(pull_mod, "FLEX_INPUT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="--from-flex"):
        pull_mod.flex_sources()


# --------------------------------------------------------------------------
# Source caveats reach the report
# --------------------------------------------------------------------------
def test_a_reconstructed_book_is_declared_in_the_caveats():
    raw = pull_mod.pull_flex([flex_csv()], use_web_service=False, enrich=False)
    notes = cli._source_caveats(raw)
    assert any("RECONSTRUCTED" in n for n in notes)


def test_absent_commission_is_declared_rather_than_shown_as_zero():
    raw = pull_mod.pull_flex([flex_csv()], use_web_service=False, enrich=False)
    notes = cli._source_caveats(raw)
    assert any("EXCLUDE commission" in n for n in notes)
