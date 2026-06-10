"""
NAV data fetchers.

Primary source: MFApi.in  (https://api.mfapi.in/mf/<amfi_code>)
Fallback:       AMFI NAVAll.txt
Benchmark:      yfinance ^NSEI (Nifty 50 price index — TRI not on yfinance)
ISIN lookup:    parse AMFI master file to map ISIN → AMFI code
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MFAPI_BASE = "https://api.mfapi.in/mf"
AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> str:
    """Parse MFApi (DD-MM-YYYY) and AMFI (DD-MMM-YYYY) dates to YYYY-MM-DD."""
    s = s.strip()
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


# ---------------------------------------------------------------------------
# MFApi
# ---------------------------------------------------------------------------

async def fetch_nav_history(
    amfi_code: str,
    since_date: Optional[date] = None,
) -> list[dict]:
    """
    Fetch NAV history for a scheme from MFApi.
    Returns list of {"nav_date": "YYYY-MM-DD", "nav": float}.
    If since_date is given, only entries on or after that date are returned.
    Falls back to AMFI text file on error.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(f"{MFAPI_BASE}/{amfi_code}", headers=_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            rows = []
            for entry in data.get("data", []):
                try:
                    nav_date = _parse_date(entry["date"])
                    nav = float(entry["nav"])
                    if since_date and nav_date < since_date.isoformat():
                        continue
                    rows.append({"nav_date": nav_date, "nav": nav})
                except (KeyError, ValueError):
                    continue
            return rows
    except Exception as exc:
        logger.warning("MFApi failed for %s (%s) — trying AMFI fallback", amfi_code, exc)
        return await _fetch_from_amfi(amfi_code, since_date)


async def fetch_latest_nav(amfi_code: str) -> Optional[dict]:
    """Return only the most recent {"nav_date", "nav"} for a scheme."""
    rows = await fetch_nav_history(amfi_code)
    if not rows:
        return None
    return max(rows, key=lambda r: r["nav_date"])


# ---------------------------------------------------------------------------
# AMFI fallback
# ---------------------------------------------------------------------------

async def _fetch_from_amfi(
    amfi_code: str,
    since_date: Optional[date] = None,
) -> list[dict]:
    """Parse AMFI NAVAll.txt for a single scheme code (today's NAV only)."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(AMFI_NAV_URL, headers=_HEADERS)
            resp.raise_for_status()
            text = resp.text
        rows = []
        for line in text.splitlines():
            parts = line.split(";")
            if len(parts) < 8:
                continue
            if parts[0].strip() != amfi_code:
                continue
            try:
                nav_date = _parse_date(parts[7])
                nav = float(parts[4].strip())
                if since_date and nav_date < since_date.isoformat():
                    continue
                rows.append({"nav_date": nav_date, "nav": nav})
            except (IndexError, ValueError):
                continue
        return rows
    except Exception as exc:
        logger.error("AMFI fallback also failed for %s: %s", amfi_code, exc)
        return []


# ---------------------------------------------------------------------------
# ISIN → AMFI code lookup
# ---------------------------------------------------------------------------

async def build_isin_to_amfi_map() -> dict[str, str]:
    """
    Download AMFI master file and return {isin: amfi_code} for all schemes.
    Called once per sync run; not cached between runs.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(AMFI_NAV_URL, headers=_HEADERS)
            resp.raise_for_status()
            text = resp.text
        mapping: dict[str, str] = {}
        for line in text.splitlines():
            parts = line.split(";")
            if len(parts) < 4:
                continue
            code = parts[0].strip()
            if not code.isdigit():
                continue
            for col in range(1, min(3, len(parts))):
                isin = parts[col].strip()
                if isin.startswith("INF"):
                    mapping[isin] = code
        if mapping:
            logger.warning("Built ISIN→AMFI map: %d entries (sample: %s)", len(mapping), list(mapping.keys())[:3])
        else:
            logger.warning("AMFI map is EMPTY — file may have returned HTML instead of NAV data. First 200 chars: %r", text[:200])
        return mapping
    except Exception as exc:
        logger.error("Failed to build ISIN→AMFI map: %s", exc)
        return {}


async def search_amfi_code_by_name(scheme_name: str) -> str:
    """
    Search MFApi by scheme name and return the best-matching scheme code.
    Used as fallback when ISIN is absent from the AMFI master file.
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                f"{MFAPI_BASE}/search",
                params={"q": scheme_name[:60]},
                headers=_HEADERS,
            )
            resp.raise_for_status()
            results = resp.json()
        if not results:
            return ""
        # Pick the result whose name most closely matches (simple: first result)
        return str(results[0]["schemeCode"])
    except Exception as exc:
        logger.warning("MFApi name search failed for '%s': %s", scheme_name[:40], exc)
        return ""


# ---------------------------------------------------------------------------
# Benchmark (yfinance — blocking, run in thread)
# ---------------------------------------------------------------------------

async def fetch_benchmark_history(
    _symbol: str = "^NSEI",
    since_date: Optional[date] = None,
) -> list[dict]:
    """
    Fetch Nifty 50 daily close prices from Stooq.
    Stooq requires no cookies and supports Indian market indices.
    symbol "^NSEI" maps to Stooq symbol "%5Ensei".
    """
    """
    Fetch Nifty 50 benchmark via a Nifty 50 Index Fund's NAV from MFApi.

    Yahoo Finance and Stooq both block automated requests. MFApi is unrestricted.
    A Nifty 50 index fund tracks the index with <0.1% tracking error; for
    Alpha/Beta (which uses daily % returns, not absolute values) this is
    functionally identical to the raw index.

    `symbol` is kept as a parameter for API compatibility but is ignored.
    """
    amfi_code = await _find_nifty50_fund_code()
    if not amfi_code:
        logger.error("Could not find a Nifty 50 index fund on MFApi — benchmark skipped")
        return []

    rows = await fetch_nav_history(amfi_code, since_date=since_date)
    logger.warning("Fetched %d benchmark rows via Nifty 50 index fund (amfi %s)", len(rows), amfi_code)
    return [
        {"index_name": "nifty50", "price_date": r["nav_date"], "close_price": r["nav"]}
        for r in rows
    ]


async def _find_nifty50_fund_code() -> str:
    """Search MFApi for a Nifty 50 direct-growth index fund and return its scheme code."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                f"{MFAPI_BASE}/search",
                params={"q": "nifty 50 index direct growth"},
                headers=_HEADERS,
            )
            resp.raise_for_status()
            results = resp.json()
        for r in results:
            name = r.get("schemeName", "").lower()
            if (
                ("nifty 50" in name or "nifty50" in name)
                and "direct" in name
                and "growth" in name
                and "index" in name
            ):
                return str(r["schemeCode"])
        # Fallback: first result
        return str(results[0]["schemeCode"]) if results else ""
    except Exception as exc:
        logger.error("MFApi Nifty 50 search failed: %s", exc)
        return ""
