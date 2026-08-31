"""The ticker -> correlated-cluster map: the repo's SINGLE encoding.

Transcribed verbatim from the COMMITTED constant in
`research/pre-registrations/f4_deployment/hedge_exposure.md` §"Population and
basis, fixed here" — 11 clusters, one proxy instrument each, residual BROAD ->
SPY, and four clusters marked UNHEDGEABLE. That file fixed the map before any
concentration or outcome column was computed and forbids editing it after
commit; this module may therefore be re-formatted but its ticker membership,
proxies and unhedgeable set may NOT change.

Shared, not study-local, per the same section's commitment: *"Two maps would
let two studies disagree about what 'same sector' means, which is the failure
mode `mapping.CONFIDENCES` and `ladder_tier()` exist to prevent."*
`hedge_exposure` (f4) uses it for the concentration trigger and the proxy
instrument; `concurrency_correlation`'s ARM K (registered 2026-08-22) imports
it rather than restating it.

The two callers need DIFFERENT residual behaviour and both are provided, so
neither has to re-encode the map to get it:

- `cluster_for()` applies `hedge_exposure`'s committed residual rule — every
  ticker not named in a cluster is BROAD, hedged with SPY.
- `named_cluster_for()` returns None for exactly those tickers, which is what
  `concurrency_correlation` commits to instead: an unmapped ticker "is its own
  bucket — never folded into a named sector".

An UNHEDGEABLE cluster (ENERGY, FINL, CRYPTO, INTL) KEEPS its identity here.
It is never folded into BROAD/SPY — folding would inflate BROAD's measured
concentration with exposure SPY does not track, corrupting the trigger itself.
The reason each is unhedgeable is carried as DATA on the cluster
(`Cluster.unhedgeable_reason`) so a caller branches on the map, not on a
hardcoded cluster name.

`lib/` placement is deliberate: no catalog entry, no verdict, and per repo
layering this module MUST NOT import from any study module (`f1_*`..`f4_*`).
It holds no outcome data and reads nothing at import beyond its own literals.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.underlying import rescaled_tickers  # noqa: E402

# Where the map is committed. Quoted in report censuses so a reader can find
# the immutable source rather than trusting this file.
MAP_SOURCE = "research/pre-registrations/f4_deployment/hedge_exposure.md"

BROAD = "BROAD"

# DIRECT  = the position IS the cluster's proxy instrument (an ETF the book
#           already holds).
# CONSTITUENT = a single name inside the proxy — the operator's literally
#           described practice. The two are never pooled in a verdict
#           (hedge_exposure's binding asymmetric reading rule).
DIRECT = "DIRECT"
CONSTITUENT = "CONSTITUENT"


@dataclass(frozen=True)
class Cluster:
    """One correlated cluster: its name, its single proxy instrument, the
    tickers committed to it, and — when it cannot be hedged — WHY.

    `tickers` is empty for BROAD alone, whose membership is the residual rule
    ("every ticker not named above") rather than a list.
    """
    name: str
    proxy: str
    tickers: frozenset[str]
    unhedgeable_reason: str | None = None

    @property
    def hedgeable(self) -> bool:
        """False for the four clusters whose proxy the pre-registration
        withheld. Such a session is carried at f=0 and counted against the
        fill gate — never dropped, never re-pointed at SPY."""
        return self.unhedgeable_reason is None


# --- the committed map --------------------------------------------------------
# Order is the pre-registration's order and is preserved for the census.
# Ticker strings are transcribed verbatim; do not add, remove or re-assign one.

# Line-broken after ARM on purpose: `tests/test_arm_index.py` reads a literal
# "ARM <TOKEN>" as an arm label, and the ticker ARM followed by MRVL trips it.
# The break is whitespace only — `split()` sees the committed order unchanged.
_SEMIS = (
    "NVDA AMD MU TSM AVGO SMCI AMAT ARM\n"
    "MRVL INTC QCOM CRDO SMH"
)
_MEGATECH = (
    "AAPL MSFT META GOOGL GOOG AMZN NFLX TSLA ADBE CRM ORCL PLTR APP INTU "
    "CSCO IBM U SNOW NTNX AKAM DELL SHOP UBER DIS TMUS QQQ"
)
_CRYPTO = "COIN MSTR MARA IBIT BITO ETHA HOOD IREN"
_RATES = "TLT"
_CREDIT = "HYG LQD"
_METALS = "GLD SLV GDX AGI"
_ENERGY = "XOM CVX HES VLO USO OIH OKLO CCJ VST CEG DUK RUN BE FSLR GEV MP X"
_FINL = "JPM GS WFC COF DFS AXP BX CMA KRE GPN SOFI NU UPST AFRM XLF"
_INTL = "EEM EFA FXI KWEB EWZ BABA PDD SE"
_SMALL = "IWM"

# The withholding reasons, verbatim from the pre-registration's fill-coverage
# and rescale disclosures. Held as data so no caller branches on a name.
_XLF_REASON = "fails the fill gate (15.0% band / 40.7% nearest)"
_XLE_REASON = (
    "on underlying.rescaled_tickers() at a 0.5000 median relative difference "
    "over 267 overlaps; the repo's own convention withholds it"
)
_IBIT_REASON = "fails the fill gate (22.9% band / 38.6% nearest)"
_EEM_REASON = "fails the fill gate (41.4% band / 67.9% nearest)"


def _cl(name: str, proxy: str, tickers: str, reason: str | None = None) -> Cluster:
    return Cluster(name, proxy, frozenset(tickers.split()), reason)


CLUSTERS: dict[str, Cluster] = {
    c.name: c
    for c in (
        _cl("SEMIS", "SMH", _SEMIS),
        _cl("MEGATECH", "QQQ", _MEGATECH),
        _cl("CRYPTO", "IBIT", _CRYPTO, _IBIT_REASON),
        _cl("RATES", "TLT", _RATES),
        _cl("CREDIT", "HYG", _CREDIT),
        _cl("METALS", "GLD", _METALS),
        _cl("ENERGY", "XLE", _ENERGY, _XLE_REASON),
        _cl("FINL", "XLF", _FINL, _XLF_REASON),
        _cl("INTL", "EEM", _INTL, _EEM_REASON),
        _cl("SMALL", "IWM", _SMALL),
        _cl(BROAD, "SPY", ""),
    )
}

# ticker -> cluster name, for every EXPLICITLY named ticker. BROAD contributes
# nothing: its membership is the residual rule, not a list.
_BY_TICKER: dict[str, str] = {}
for _c in CLUSTERS.values():
    for _t in _c.tickers:
        # Import-time cross-check: a ticker in two clusters would make the
        # concentration measure depend on dict order.
        assert _t not in _BY_TICKER, (
            f"sector map defect: {_t} is in both {_BY_TICKER[_t]} and {_c.name}"
        )
        _BY_TICKER[_t] = _c.name

# A proxy may only be claimed by its own cluster: SMH is SEMIS's proxy AND a
# SEMIS member, but no proxy may sit inside a DIFFERENT cluster's list, which
# would make `stratum` and the instrument choice disagree.
for _c in CLUSTERS.values():
    _owner = _BY_TICKER.get(_c.proxy)
    assert _owner in (None, _c.name), (
        f"sector map defect: proxy {_c.proxy} of {_c.name} is mapped to {_owner}"
    )
del _c, _t, _owner

UNHEDGEABLE: frozenset[str] = frozenset(
    name for name, c in CLUSTERS.items() if not c.hedgeable
)


# --- lookups ------------------------------------------------------------------


def _norm(ticker: str) -> str:
    """Upper-cased, stripped ticker. Raises on an empty/None ticker rather
    than silently returning BROAD: a blank underlying is a data defect, and
    counting it into BROAD would move the concentration measure."""
    if ticker is None or not str(ticker).strip():
        raise ValueError("sectors: empty ticker has no cluster")
    return str(ticker).strip().upper()


def named_cluster_for(ticker: str) -> str | None:
    """The cluster `ticker` is EXPLICITLY named in, or None when it is not
    named anywhere in the map.

    This is `concurrency_correlation`'s residual rule — an unmapped ticker is
    its own bucket and is never folded into a named sector. Callers wanting
    `hedge_exposure`'s residual (BROAD) want `cluster_for` instead.
    """
    return _BY_TICKER.get(_norm(ticker))


def cluster_for(ticker: str) -> str:
    """The cluster name for `ticker`, applying `hedge_exposure`'s committed
    residual rule: every ticker not named in the map is BROAD (proxy SPY)."""
    return _BY_TICKER.get(_norm(ticker), BROAD)


def cluster(name: str) -> Cluster:
    """The `Cluster` record by name. KeyError on an unknown name — a typo'd
    cluster must not read as an empty bucket."""
    return CLUSTERS[name]


def proxy_of_cluster(name: str) -> str:
    """The single proxy instrument for a cluster name, hedgeable or not: an
    UNHEDGEABLE cluster keeps its proxy identity (ENERGY is XLE, not SPY);
    what it loses is the ability to be filled. Check `is_hedgeable` before
    placing anything."""
    return CLUSTERS[name].proxy


def proxy_for(ticker: str) -> str:
    """The proxy instrument of `ticker`'s cluster, under the BROAD residual."""
    return proxy_of_cluster(cluster_for(ticker))


def is_hedgeable(name: str) -> bool:
    """False for ENERGY, FINL, CRYPTO, INTL — the four clusters whose proxy
    the pre-registration withheld."""
    return CLUSTERS[name].hedgeable


def unhedgeable_reason(name: str) -> str | None:
    """Why a cluster cannot be hedged, or None when it can. The reason is
    committed data, so a report quotes it instead of restating it."""
    return CLUSTERS[name].unhedgeable_reason


def unhedgeable() -> dict[str, str]:
    """`{cluster: reason}` for every withheld cluster, in committed order."""
    return {
        n: c.unhedgeable_reason
        for n, c in CLUSTERS.items()
        if c.unhedgeable_reason is not None
    }


def stratum(ticker: str) -> str:
    """DIRECT when the position IS its cluster's proxy instrument, else
    CONSTITUENT — the split every hedge_exposure result must be stratified on.

    Derived from the map, never stored: a DIRECT position is one whose ticker
    equals the proxy of the cluster it resolves to. Note that a proxy NOT
    named in its own cluster's list resolves to BROAD and is therefore
    CONSTITUENT-of-BROAD, not DIRECT (see `census_lines`' ENERGY footnote).
    """
    t = _norm(ticker)
    return DIRECT if t == proxy_for(t) else CONSTITUENT


def clusters() -> tuple[Cluster, ...]:
    """Every cluster in the pre-registration's committed order."""
    return tuple(CLUSTERS.values())


def as_dict() -> dict[str, dict]:
    """The whole map as plain data, for a report or a test to walk without
    touching module internals."""
    return {
        name: {
            "proxy": c.proxy,
            "tickers": sorted(c.tickers),
            "hedgeable": c.hedgeable,
            "unhedgeable_reason": c.unhedgeable_reason,
        }
        for name, c in CLUSTERS.items()
    }


def rescale_withheld_proxies() -> frozenset[str]:
    """Proxies that are on `underlying.rescaled_tickers()` in THIS checkout.

    Diagnostic only — a report can confirm at run time that the committed
    withholding still matches the cache (the pre-registration withheld XLE for
    exactly this reason). It does NOT change `UNHEDGEABLE`, which is a
    committed constant and is not recomputed from a cache file.
    """
    rescaled = rescaled_tickers()
    return frozenset(c.proxy for c in CLUSTERS.values() if c.proxy in rescaled)


def census_lines() -> list[str]:
    """The map as report lines, so a study prints the map it actually ran
    under (the pre-registration requires the map be quoted in the census)."""
    width = max(len(n) for n in CLUSTERS)
    lines = [f"SECTOR MAP (committed in {MAP_SOURCE}; encoded in lib/sectors.py)"]
    for name, c in CLUSTERS.items():
        flag = "" if c.hedgeable else "  [UNHEDGEABLE]"
        members = (
            "every ticker not named above (residual)"
            if not c.tickers
            else " ".join(sorted(c.tickers))
        )
        lines.append(f"  {name:<{width}} -> {c.proxy:<4}{flag}: {members}")
    lines.append("  UNHEDGEABLE clusters keep their identity; never folded into BROAD/SPY:")
    for name, reason in unhedgeable().items():
        lines.append(f"    {name} ({CLUSTERS[name].proxy}): {reason}")
    lines.append(
        "  NOTE: XLE is ENERGY's proxy but is not a committed ENERGY member, so an "
        "XLE POSITION resolves to BROAD under the residual rule (consistent with the "
        "pre-registration's disclosed ENERGY direct% = 0.0)."
    )
    return lines
