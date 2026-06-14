"""SPX gamma exposure snapshot — gamma flip level vs current spot.

Reads the Barchart $SPX gamma-exposure page via an authenticated Playwright
session and extracts "Gamma Flip" and "Last Price" directly from the DOM chart
annotations. No CSV download or options-chain math required.

Key output fields:
  gamma_flip  — the SPX strike where net dealer gamma crosses zero
  spot        — current SPX last price
  above_flip  — True when spot > gamma_flip (dealers net long gamma)

Dealer gamma context:
  above flip → long gamma: dealers absorb flow, suppress realized vol → DP / VC
  below flip → short gamma: dealers amplify moves, chase direction → TF / GE

Caching: .cache/gex_snapshot_YYYY-MM-DD.json — same pattern as vol_snapshot.py.
Soft failure: any network/auth error returns None and never blocks a run.
Requires BARCHART_EMAIL and BARCHART_PASSWORD environment variables.
"""
import asyncio
import json
import logging
import os
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# No expiration param → aggregate gamma across all expirations.
_GEX_URL = "https://www.barchart.com/stocks/quotes/$SPX/gamma-exposure"
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def _cache_path(d: date) -> Path:
    return _CACHE_DIR / f"gex_snapshot_{d.isoformat()}.json"


def _load_cache(d: date) -> dict | None:
    p = _cache_path(d)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return None


def _save_cache(d: date, data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        _cache_path(d).write_text(json.dumps(data))
    except Exception:
        log.warning("gex_snapshot: could not write cache", exc_info=True)


def _parse_number(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"[\d,]+\.?\d*", text)
    return float(m.group().replace(",", "")) if m else None


async def _fetch_async() -> dict | None:
    email = os.environ.get("BARCHART_EMAIL")
    password = os.environ.get("BARCHART_PASSWORD")
    if not email or not password:
        log.warning("gex_snapshot: BARCHART_EMAIL/PASSWORD not set — skipping")
        return None

    cookies_path = Path(
        os.environ.get("BARCHART_COOKIES_PATH", "cookies/barchart.json")
    )

    from lib.barchart import BarchartSession  # import here to avoid circular at module load

    try:
        async with BarchartSession(email, password, cookies_path) as session:
            page = session._page
            log.info("gex_snapshot: fetching %s", _GEX_URL)
            await page.goto(_GEX_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle", timeout=20000)

            # Chart annotations render asynchronously — wait for the flip label.
            try:
                await page.wait_for_function(
                    "() => document.body.innerText.includes('Gamma Flip:')",
                    timeout=20000,
                )
            except Exception:
                log.warning("gex_snapshot: 'Gamma Flip:' not found after page load")
                return None

            # Walk all text nodes (covers both HTML and SVG <text>/<tspan> elements).
            raw = await page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null
                    );
                    let flip = null, price = null;
                    let node;
                    while ((node = walker.nextNode())) {
                        const t = node.textContent.trim();
                        if (!flip && t.startsWith('Gamma Flip:')) flip = t;
                        if (!price && t.startsWith('Last Price:'))  price = t;
                        if (flip && price) break;
                    }
                    return { flip, price };
                }
            """)

            flip = _parse_number(raw.get("flip") if raw else None)
            spot = _parse_number(raw.get("price") if raw else None)

            if flip is None:
                log.warning("gex_snapshot: could not parse Gamma Flip from DOM")
                return None

            result: dict = {"gamma_flip": flip}
            if spot is not None:
                result["spot"] = spot
                result["above_flip"] = spot > flip
            return result

    except Exception:
        log.warning("gex_snapshot: fetch failed", exc_info=True)
        return None


def fetch_gex_snapshot(date_str: str | None = None) -> dict | None:
    """Fetch SPX gamma exposure snapshot for a trading date (today if None).

    Returns a dict with keys gamma_flip, spot, above_flip, or None on failure.
    Caches to .cache/gex_snapshot_YYYY-MM-DD.json so repeated calls within the
    same day (or for any historical date) never re-fetch.
    """
    d = date.fromisoformat(date_str) if date_str else date.today()

    cached = _load_cache(d)
    if cached is not None:
        log.debug("gex_snapshot: cache hit for %s", d)
        return cached

    result = asyncio.run(_fetch_async())
    if result:
        _save_cache(d, result)
    return result


def gex_snapshot_md(snap: dict) -> str:
    """Format a GEX snapshot dict as a markdown section for the LLM prompt."""
    if not snap:
        return ""

    flip = snap.get("gamma_flip")
    spot = snap.get("spot")
    above = snap.get("above_flip")

    if flip is None:
        return ""

    lines = ["## Gamma exposure (SPX)"]

    if spot is not None and above is not None:
        direction = "ABOVE" if above else "BELOW"
        env = "dealers net long gamma" if above else "dealers net short gamma"
        lines.append(
            f"Gamma flip: {flip:,.0f}  |  Last price: {spot:,.0f}"
            f"  → spot {direction} flip ({env})"
        )
        if above:
            lines.append(
                "_Long-gamma: realized vol suppressed; DP and VC setups supported;"
                " price gravitates toward large OI clusters._"
            )
        else:
            lines.append(
                "_Short-gamma: dealers amplify directional moves; TF and GE have"
                " structural tailwind; avoid naked premium selling._"
            )
    else:
        lines.append(f"Gamma flip: {flip:,.0f}")

    return "\n".join(lines)
