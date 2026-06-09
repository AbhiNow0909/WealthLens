import httpx
import pandas as pd


MFAPI_BASE = "https://api.mfapi.in/mf"
AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


async def fetch_nav_history(amfi_code: str) -> list[dict]:
    """Fetch full NAV history for a fund from MFApi. Falls back to AMFI on error."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{MFAPI_BASE}/{amfi_code}")
            resp.raise_for_status()
            data = resp.json()
            return [
                {"nav_date": entry["date"], "nav": float(entry["nav"])}
                for entry in data.get("data", [])
            ]
    except Exception:
        return await _fetch_nav_from_amfi(amfi_code)


async def _fetch_nav_from_amfi(amfi_code: str) -> list[dict]:
    """Fallback: fetch latest NAV from AMFI text file."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(AMFI_NAV_URL)
        resp.raise_for_status()
    rows = []
    for line in resp.text.splitlines():
        parts = line.split(";")
        if len(parts) >= 5 and parts[0].strip() == amfi_code:
            rows.append({"nav_date": parts[7].strip(), "nav": float(parts[4].strip())})
    return rows
