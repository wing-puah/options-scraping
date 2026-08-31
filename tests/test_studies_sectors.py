"""Tests for scripts/backtest_study/lib/sectors.py — the shared sector map.

The load-bearing test is `test_map_is_verbatim_transcription_of_prereg`: it
re-parses the COMMITTED map out of
`research/pre-registrations/f4_deployment/hedge_exposure.md` and diffs it
against the module. That is not a stored expected figure — the pre-registration
is immutable by its own terms, so the file IS the specification, and a drift in
either direction (module edited, or the committed constant edited after commit)
fails here rather than silently redefining what "same sector" means for two
studies.

Everything else pins BEHAVIOUR: the residual rules (two callers, two different
ones), that an UNHEDGEABLE cluster keeps its identity, and the normalisation.
No test asserts a count read off an export.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.backtest_study.lib import sectors as S

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "research" / "pre-registrations" / "f4_deployment" / "hedge_exposure.md"

# `  - `NAME` → **PROXY**[, but UNHEDGEABLE (see below)]: T1 T2 ...`
_BULLET = re.compile(
    r"- `([A-Z]+)` → \*\*([A-Z]+)\*\*(?:, but UNHEDGEABLE \(see below\))?: (.+)"
)


def _committed_map() -> dict[str, tuple[str, str]]:
    return {
        m.group(1): (m.group(2), m.group(3).strip())
        for m in _BULLET.finditer(PREREG.read_text())
    }


# ---------------------------------------------------------------------------
# the committed constant
# ---------------------------------------------------------------------------


def test_prereg_still_parses():
    """Guard the guard: if the bullet shape ever changes, the transcription
    test must fail loudly rather than compare against an empty parse."""
    committed = _committed_map()
    assert len(committed) == 11, committed.keys()


def test_map_is_verbatim_transcription_of_prereg():
    committed = _committed_map()
    assert set(committed) == set(S.CLUSTERS)
    for name, (proxy, members) in committed.items():
        cl = S.CLUSTERS[name]
        assert cl.proxy == proxy, name
        # BROAD's membership is the residual RULE, not a ticker list.
        expected = frozenset() if name == S.BROAD else frozenset(members.split())
        assert cl.tickers == expected, name


def test_no_ticker_in_two_clusters():
    seen: dict[str, str] = {}
    for name, cl in S.CLUSTERS.items():
        for t in cl.tickers:
            assert t not in seen, f"{t} in {seen.get(t)} and {name}"
            seen[t] = name


def test_no_proxy_belongs_to_another_cluster():
    for name, cl in S.CLUSTERS.items():
        owner = S.named_cluster_for(cl.proxy)
        assert owner in (None, name), (cl.proxy, owner, name)


# ---------------------------------------------------------------------------
# lookups and the two residual rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker,cluster,proxy", [
    ("NVDA", "SEMIS", "SMH"),
    ("SMH", "SEMIS", "SMH"),
    ("GOOG", "MEGATECH", "QQQ"),
    ("GOOGL", "MEGATECH", "QQQ"),
    ("LQD", "CREDIT", "HYG"),
    ("SE", "INTL", "EEM"),
    ("IWM", "SMALL", "IWM"),
])
def test_named_tickers_resolve(ticker, cluster, proxy):
    assert S.cluster_for(ticker) == cluster
    assert S.named_cluster_for(ticker) == cluster
    assert S.proxy_for(ticker) == proxy


def test_unnamed_ticker_is_broad_for_hedge_exposure():
    """hedge_exposure's committed residual: everything unnamed is BROAD/SPY."""
    assert S.cluster_for("ZZZZ") == S.BROAD
    assert S.proxy_for("ZZZZ") == "SPY"


def test_unnamed_ticker_is_none_for_concurrency_correlation():
    """concurrency_correlation's opposite commitment: an unmapped ticker is
    its own bucket and is NEVER folded into a named sector."""
    assert S.named_cluster_for("ZZZZ") is None
    assert S.named_cluster_for("NVDA") == "SEMIS"


def test_lookup_normalises_case_and_whitespace():
    assert S.cluster_for(" nvda ") == "SEMIS"
    assert S.named_cluster_for("nvda") == "SEMIS"
    assert S.stratum(" smh ") == S.DIRECT


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_empty_ticker_refuses_rather_than_counting_into_broad(bad):
    with pytest.raises(ValueError):
        S.cluster_for(bad)


def test_unknown_cluster_name_raises():
    with pytest.raises(KeyError):
        S.cluster("SEMIS_TYPO")


# ---------------------------------------------------------------------------
# unhedgeable clusters keep their identity
# ---------------------------------------------------------------------------


def test_unhedgeable_set():
    assert S.UNHEDGEABLE == frozenset({"ENERGY", "FINL", "CRYPTO", "INTL"})


def test_unhedgeable_cluster_keeps_identity_and_proxy():
    for name in S.UNHEDGEABLE:
        assert S.proxy_of_cluster(name) != "SPY", name
        assert not S.is_hedgeable(name)
        assert S.unhedgeable_reason(name)
    # a member ticker still resolves to its own cluster, never BROAD
    assert S.cluster_for("COIN") == "CRYPTO"
    assert S.cluster_for("JPM") == "FINL"
    assert S.cluster_for("XOM") == "ENERGY"
    assert S.cluster_for("FXI") == "INTL"


def test_hedgeable_clusters_carry_no_reason():
    for name, cl in S.CLUSTERS.items():
        if name in S.UNHEDGEABLE:
            continue
        assert cl.hedgeable and cl.unhedgeable_reason is None, name


def test_unhedgeable_reasons_are_data_not_a_name_branch():
    reasons = S.unhedgeable()
    assert set(reasons) == S.UNHEDGEABLE
    assert "rescaled_tickers" in reasons["ENERGY"]
    for name in ("FINL", "CRYPTO", "INTL"):
        assert "fill gate" in reasons[name]


# ---------------------------------------------------------------------------
# stratification, census, diagnostics
# ---------------------------------------------------------------------------


def test_stratum_direct_vs_constituent():
    assert S.stratum("SMH") == S.DIRECT
    assert S.stratum("SPY") == S.DIRECT
    assert S.stratum("NVDA") == S.CONSTITUENT
    # XLE is ENERGY's proxy but not a committed ENERGY member, so an XLE
    # position falls to BROAD and is not DIRECT. Consequence of the committed
    # transcription, pinned here so it cannot be "fixed" by editing the map.
    assert S.cluster_for("XLE") == S.BROAD
    assert S.stratum("XLE") == S.CONSTITUENT


def test_census_quotes_the_whole_map():
    text = "\n".join(S.census_lines())
    assert S.MAP_SOURCE in text
    for name, cl in S.CLUSTERS.items():
        assert name in text
        assert cl.proxy in text
        for t in cl.tickers:
            assert re.search(rf"\b{t}\b", text), (name, t)
    assert text.count("[UNHEDGEABLE]") == len(S.UNHEDGEABLE)


def test_as_dict_round_trips_the_map():
    d = S.as_dict()
    assert set(d) == set(S.CLUSTERS)
    for name, cl in S.CLUSTERS.items():
        assert frozenset(d[name]["tickers"]) == cl.tickers
        assert d[name]["proxy"] == cl.proxy
        assert d[name]["hedgeable"] is cl.hedgeable


def test_clusters_preserve_committed_order():
    committed = list(_committed_map())
    assert [c.name for c in S.clusters()] == committed


def test_rescale_withheld_proxies_is_diagnostic_only(monkeypatch):
    monkeypatch.setattr(S, "rescaled_tickers", lambda: frozenset({"QQQ", "NVDA"}))
    assert S.rescale_withheld_proxies() == frozenset({"QQQ"})
    # a cache-driven diagnostic may NOT move the committed unhedgeable set
    assert S.UNHEDGEABLE == frozenset({"ENERGY", "FINL", "CRYPTO", "INTL"})
    assert S.is_hedgeable("MEGATECH")
