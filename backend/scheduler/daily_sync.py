"""
Daily NAV sync job — runs at 23:00 IST via APScheduler.

Workflow:
1. Download AMFI master file to build ISIN→amfi_code map.
2. Fill in any missing amfi_codes in the holdings table.
3. For each unique (isin, amfi_code), fetch NAV history from MFApi.
   - Full history if no nav_history rows exist for that ISIN.
   - Incremental (since last recorded date) otherwise.
4. Upsert rows into nav_history in batches.
5. Update current_nav and current_value in holdings.
6. Fetch Nifty 50 benchmark and upsert into benchmark_history.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.supabase_client import get_supabase
from services.nav_fetcher import (
    fetch_nav_history,
    fetch_benchmark_history,
    build_isin_to_amfi_map,
    search_amfi_code_by_name,
)

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

_BATCH = 500  # rows per Supabase upsert call


async def run_nav_sync() -> dict:
    """
    Execute the full NAV sync.  Returns a summary dict so it can also be
    called on-demand from the manual trigger endpoint.
    """
    supabase = get_supabase()
    summary = {"funds_synced": 0, "nav_rows_upserted": 0, "benchmark_rows_upserted": 0, "errors": []}

    # --- 1. Build ISIN → AMFI code map ---
    logger.info("Building ISIN→AMFI map…")
    isin_map = await build_isin_to_amfi_map()

    # --- 2. Get all unique holdings across all users ---
    result = supabase.table("holdings").select("isin,amfi_code,scheme_name").execute()
    holdings_rows = result.data or []

    # Deduplicate by ISIN; resolve amfi_code from AMFI map
    seen: dict[str, str] = {}  # isin → amfi_code
    name_by_isin: dict[str, str] = {}
    for row in holdings_rows:
        isin = row.get("isin", "").strip()
        code = row.get("amfi_code") or ""
        if not code and isin in isin_map:
            code = isin_map[isin]
        if isin and isin not in seen:
            seen[isin] = code
            name_by_isin[isin] = row.get("scheme_name", "")

    # --- 2b. Fallback: MFApi name search for ISINs still missing a code ---
    missing = [isin for isin, code in seen.items() if not code]
    if missing:
        logger.warning("AMFI map miss for %d ISINs — trying MFApi name search", len(missing))
        for isin in missing:
            name = name_by_isin.get(isin, "")
            if not name:
                continue
            code = await search_amfi_code_by_name(name)
            if code:
                seen[isin] = code
                logger.warning("Resolved %s → amfi_code %s via name search", isin, code)

    if not seen:
        logger.info("No holdings found — nothing to sync")
        return summary

    # --- 3. Fill missing amfi_codes in holdings table ---
    for isin, code in seen.items():
        if code:
            supabase.table("holdings").update({"amfi_code": code}).eq("isin", isin).is_("amfi_code", "null").execute()

    # --- 4. Fetch and upsert NAV history per fund ---
    for isin, amfi_code in seen.items():
        if not amfi_code:
            logger.warning("No AMFI code for ISIN %s — skipping NAV fetch", isin)
            summary["errors"].append(f"No AMFI code for {isin}")
            continue

        # Find the latest date we already have for this ISIN
        existing = (
            supabase.table("nav_history")
            .select("nav_date")
            .eq("isin", isin)
            .order("nav_date", desc=True)
            .limit(1)
            .execute()
        )
        since = None
        if existing.data:
            # Fetch only dates strictly after the last one we have
            since = date.fromisoformat(existing.data[0]["nav_date"]) + timedelta(days=1)

        rows = await fetch_nav_history(amfi_code, since_date=since)
        if not rows:
            summary["errors"].append(f"No NAV data returned for {isin} / {amfi_code}")
            continue

        # Attach ISIN and amfi_code to every row
        records = [{"isin": isin, "amfi_code": amfi_code, **r} for r in rows]

        # Batch upsert (ignore existing rows — unique constraint on isin+nav_date)
        for i in range(0, len(records), _BATCH):
            batch = records[i : i + _BATCH]
            try:
                supabase.table("nav_history").upsert(
                    batch, on_conflict="isin,nav_date", ignore_duplicates=True
                ).execute()
                summary["nav_rows_upserted"] += len(batch)
            except Exception as exc:
                logger.warning("nav_history upsert failed for %s batch %d: %s", isin, i, exc)

        # --- 5. Update current_nav + current_value in holdings ---
        latest = max(rows, key=lambda r: r["nav_date"])
        latest_nav = latest["nav"]
        # Get all holdings rows for this ISIN (could be multiple users)
        holdings_for_isin = (
            supabase.table("holdings")
            .select("id,units_held")
            .eq("isin", isin)
            .execute()
            .data or []
        )
        for h in holdings_for_isin:
            try:
                supabase.table("holdings").update({
                    "current_nav": latest_nav,
                    "current_value": round((h["units_held"] or 0) * latest_nav, 2),
                    "last_updated": date.today().isoformat(),
                }).eq("id", h["id"]).execute()
            except Exception as exc:
                logger.warning("Failed to update current_nav for holding %s: %s", h["id"], exc)

        summary["funds_synced"] += 1
        logger.debug("Synced %s (%s): %d rows, latest NAV %.4f", isin, amfi_code, len(rows), latest_nav)

    # --- 6. Benchmark (Nifty 50) ---
    bench_existing = (
        supabase.table("benchmark_history")
        .select("price_date")
        .eq("index_name", "nifty50")
        .order("price_date", desc=True)
        .limit(1)
        .execute()
    )
    bench_since = None
    if bench_existing.data:
        # Fetch only dates strictly after the last one we have (avoid duplicate-key)
        bench_since = date.fromisoformat(bench_existing.data[0]["price_date"]) + timedelta(days=1)

    bench_rows = await fetch_benchmark_history(since_date=bench_since)
    if bench_rows:
        for i in range(0, len(bench_rows), _BATCH):
            batch = bench_rows[i : i + _BATCH]
            try:
                supabase.table("benchmark_history").upsert(
                    batch, on_conflict="index_name,price_date", ignore_duplicates=True
                ).execute()
                summary["benchmark_rows_upserted"] += len(batch)
            except Exception as exc:
                logger.warning("benchmark_history upsert failed at batch %d: %s", i, exc)

    # --- 7. Prune old report exports from Storage ---
    try:
        from services.export_service import cleanup_old_reports
        summary["reports_deleted"] = cleanup_old_reports()
    except Exception as exc:
        logger.warning("Report cleanup failed: %s", exc)
        summary["reports_deleted"] = 0

    logger.info(
        "NAV sync complete — %d funds, %d nav rows, %d benchmark rows, %d reports pruned, %d errors",
        summary["funds_synced"],
        summary["nav_rows_upserted"],
        summary["benchmark_rows_upserted"],
        summary.get("reports_deleted", 0),
        len(summary["errors"]),
    )
    return summary


async def _sync_navs():
    try:
        await run_nav_sync()
    except Exception as exc:
        logger.exception("Daily NAV sync crashed: %s", exc)


def start_scheduler():
    _scheduler.add_job(_sync_navs, CronTrigger(hour=23, minute=0))
    _scheduler.start()
    logger.info("APScheduler started — daily NAV sync at 23:00 IST")
