"""Daily digest cron — posts verdict summary at 8:00 AM HST daily."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from supabase import create_client

from .formatters import format_digest_blocks
from .poster import SlackPoster

logger = logging.getLogger(__name__)

# HST = UTC-10
HST = timezone(timedelta(hours=-10))


def _fetch_unposted_verdicts(db) -> list[dict]:
    """Fetch verdict reports not yet posted to Slack."""
    resp = (
        db.table("verdict_reports")
        .select("*")
        .is_("posted_to_slack_at", "null")
        .execute()
    )
    return resp.data or []


def _fetch_recent_verdicts(db, hours: int = 24) -> list[dict]:
    """Fetch verdicts generated in the last N hours (for digest)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        db.table("verdict_reports")
        .select("*")
        .gte("generated_at", since)
        .execute()
    )
    return resp.data or []


def run_digest_job() -> None:
    """Execute one digest run: post unposted verdicts + daily summary."""
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_KEY"]
    db = create_client(supabase_url, supabase_key)

    poster = SlackPoster(supabase_client=db)

    # 1. Post any unposted individual verdicts
    unposted = _fetch_unposted_verdicts(db)
    for report in unposted:
        poster.post_verdict(report)

    # 2. Build and post daily digest
    recent = _fetch_recent_verdicts(db, hours=24)
    if recent:
        today_str = datetime.now(HST).strftime("%b %d, %Y")
        blocks = format_digest_blocks(recent, date_str=today_str)
        try:
            poster.post_blocks(blocks)
            logger.info("Daily digest posted: %d verdicts", len(recent))
        except Exception as exc:
            logger.error("Failed to post daily digest: %s", exc)
    else:
        logger.info("No recent verdicts for daily digest.")


def start_digest_cron() -> None:
    """Start the blocking scheduler. 8:00 AM HST = 18:00 UTC."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_digest_job,
        trigger=CronTrigger(hour=18, minute=0),  # 18:00 UTC = 08:00 HST
        id="daily_verdict_digest",
        name="Daily Verdict Digest (8:00 AM HST)",
    )
    logger.info("Digest cron scheduled for 18:00 UTC (8:00 AM HST)")
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_digest_cron()
