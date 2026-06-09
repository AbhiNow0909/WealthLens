import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def _sync_navs():
    logger.info("Daily NAV sync started")
    # TODO: Step 4 — fetch latest NAVs for all ISINs and recompute metrics
    logger.info("Daily NAV sync complete")


def start_scheduler():
    _scheduler.add_job(_sync_navs, CronTrigger(hour=23, minute=0))
    _scheduler.start()
    logger.info("APScheduler started — daily NAV sync at 23:00 IST")
