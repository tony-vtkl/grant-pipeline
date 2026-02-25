"""Main ingestion pipeline with APScheduler.

Per INTAKE BLOCK 1:
- 60-minute polling schedule using APScheduler within Cloud Run Job
- Each adapter normalizes to shared GrantOpportunity Pydantic model
- Deduplication via SHA256(source + source_opportunity_id)
- Writes to grant_opportunities Supabase table
"""

import asyncio
import logging
import sys
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import load_config
from .adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter
from .deduplicator import Deduplicator
from .database import SupabaseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def poll_all_sources():
    """Poll all three federal grant sources and ingest opportunities.
    
    Per INTAKE BLOCK 1 acceptance criteria:
    - All three federal source adapters return ≥1 GrantOpportunity record
    - Deduplicator prevents duplicates
    - Full polling cycle completes in <5 minutes locally
    """
    logger.info("=" * 60)
    logger.info("Starting polling cycle")
    logger.info("=" * 60)
    start_time = datetime.utcnow()
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize database client
        db_client = SupabaseClient(config.database_url)
        
        # Load existing hashes for deduplication
        existing_hashes = await db_client.get_existing_hashes()
        deduplicator = Deduplicator(existing_hashes)
        
        # Initialize adapters
        adapters = [
            GrantsGovAdapter(attribution_header=config.grants_gov_attribution),
            SamGovAdapter(api_key=config.sam_api_key),
            SbirGovAdapter(),
        ]
        
        # Fetch from all sources (partial failure isolation via safe_fetch)
        all_opportunities = []
        for adapter in adapters:
            logger.info(f"Fetching from {adapter.source_name}...")
            opportunities = await adapter.safe_fetch()
            if opportunities:
                logger.info(f"✓ {adapter.source_name}: {len(opportunities)} opportunities")
            else:
                logger.warning(f"⚠ {adapter.source_name}: 0 opportunities (may have failed)")
            all_opportunities.extend(opportunities)
        
        logger.info(f"Total opportunities fetched: {len(all_opportunities)}")
        
        # Deduplicate
        new_opportunities = deduplicator.deduplicate(all_opportunities)
        logger.info(f"New opportunities after deduplication: {len(new_opportunities)}")
        
        # Insert into database
        if new_opportunities:
            inserted_count = await db_client.insert_opportunities(new_opportunities)
            logger.info(f"✓ Inserted {inserted_count} opportunities into database")
        else:
            logger.info("No new opportunities to insert")
        
        # Log cycle completion time
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"Polling cycle completed in {duration:.2f} seconds")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Polling cycle failed: {e}", exc_info=True)
        raise


async def run_once():
    """Run polling cycle once (for testing and manual execution)."""
    await poll_all_sources()


def start_scheduler():
    """Start APScheduler for continuous polling.
    
    Per INTAKE BLOCK 1: 60-minute polling schedule.
    Runs within Cloud Run Job.
    """
    config = load_config()
    
    # Configure logging level
    logging.getLogger().setLevel(config.log_level)
    
    logger.info("Initializing Grant Ingestion Pipeline")
    logger.info(f"Polling interval: {config.polling_interval_minutes} minutes")
    
    # Create scheduler
    scheduler = AsyncIOScheduler()
    
    # Add polling job
    scheduler.add_job(
        poll_all_sources,
        trigger=IntervalTrigger(minutes=config.polling_interval_minutes),
        id="poll_grants",
        name="Poll all federal grant sources",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )
    
    # Start scheduler
    scheduler.start()
    logger.info("✓ Scheduler started")
    
    # Run first cycle immediately
    logger.info("Running initial polling cycle...")
    asyncio.create_task(poll_all_sources())
    
    # Keep running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("✓ Scheduler stopped")


if __name__ == "__main__":
    # Check if running in one-shot mode
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        asyncio.run(run_once())
    else:
        start_scheduler()
