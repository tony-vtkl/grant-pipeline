"""SAM.gov API adapter - authenticated API access."""

import hashlib
import logging
import time
from datetime import datetime
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from .base import BaseAdapter
from models import GrantOpportunity

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, connect=30.0)


class SamGovAdapter(BaseAdapter):
    """Adapter for SAM.gov Opportunities API.
    
    API Docs: https://open.gsa.gov/api/opportunities-api/
    Requires API key: SAM-4bd94da0-aa58-4422-a387-93f954c86e40 (per INTAKE BLOCK 1)
    """
    
    API_URL = "https://api.sam.gov/prod/opportunities/v2/search"
    
    def __init__(self, api_key: str):
        """Initialize adapter.
        
        Args:
            api_key: SAM.gov API key (from env: SAM_API_KEY)
        """
        self.api_key = api_key
    
    @property
    def source_name(self) -> str:
        return "sam_gov"
    
    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch opportunities from SAM.gov API.
        
        Per INTAKE BLOCK 1: authenticated API with provided key.
        Returns ≥1 GrantOpportunity record against live API in acceptance test.
        Returns empty list on failure for partial failure isolation.
        """
        logger.info(f"Fetching opportunities from {self.source_name}")
        try:
            return await self._fetch_with_retry()
        except Exception as e:
            logger.error(f"[{self.source_name}] All retries exhausted: {e}")
            return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch_with_retry(self) -> List[GrantOpportunity]:
        """Internal fetch method with retry logic."""
        url = self.API_URL
        start = time.monotonic()
        status_code = None
        
        params = {
            "api_key": self.api_key,
            "postedFrom": self._get_recent_date(),  # Last 30 days
            "postedTo": datetime.utcnow().strftime("%m/%d/%Y"),
            "limit": 100,
        }
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(
                    url,
                    params=params
                )
                status_code = response.status_code
                response.raise_for_status()
                data = response.json()
            
            duration = time.monotonic() - start
            logger.info(
                f"[{self.source_name}] url={url} status={status_code} "
                f"duration={duration:.2f}s result=success"
            )
            
            opportunities = []
            total_records = data.get("totalRecords", 0)
            logger.info(f"SAM.gov returned {total_records} opportunities")
            
            for opp_data in data.get("opportunitiesData", []):
                opportunity = self._normalize_opportunity(opp_data)
                if opportunity:
                    opportunities.append(opportunity)
            
            logger.info(f"Normalized {len(opportunities)} opportunities from {self.source_name}")
            return opportunities
            
        except httpx.TimeoutException as e:
            duration = time.monotonic() - start
            logger.error(
                f"[{self.source_name}] url={url} status=timeout "
                f"duration={duration:.2f}s result=failure error='{e}'"
            )
            raise
        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                f"[{self.source_name}] url={url} status={status_code} "
                f"duration={duration:.2f}s result=failure error='{e}'"
            )
            raise
        except Exception as e:
            duration = time.monotonic() - start
            logger.error(
                f"[{self.source_name}] url={url} status={status_code} "
                f"duration={duration:.2f}s result=failure error='{e}'"
            )
            raise
    
    def _normalize_opportunity(self, data: dict) -> Optional[GrantOpportunity]:
        """Normalize SAM.gov response to GrantOpportunity model.
        
        Args:
            data: Raw opportunity data from SAM.gov API
            
        Returns:
            Normalized GrantOpportunity or None if invalid
        """
        try:
            source_id = data.get("noticeId", "")
            if not source_id:
                logger.warning("SAM.gov opportunity missing noticeId, skipping")
                return None
            
            # Deduplication hash per INTAKE BLOCK 1
            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
            
            # Parse dates
            posted_date = self._parse_date(data.get("postedDate"))
            response_deadline = self._parse_date(data.get("responseDeadLine"))
            archive_date = self._parse_date(data.get("archiveDate"))
            
            # NAICS codes
            naics_codes = []
            naics_list = data.get("naicsCode", [])
            if isinstance(naics_list, list):
                naics_codes = [str(code) for code in naics_list if code]
            elif naics_list:
                naics_codes = [str(naics_list)]
            
            # Build opportunity
            opportunity = GrantOpportunity(
                source=self.source_name,
                source_opportunity_id=source_id,
                dedup_hash=dedup_hash,
                title=data.get("title", "Untitled"),
                agency=data.get("fullParentPathName", data.get("organizationName", "Unknown")),
                opportunity_number=data.get("solicitationNumber", source_id),
                posted_date=posted_date,
                response_deadline=response_deadline,
                archive_date=archive_date,
                award_amount_min=None,  # SAM.gov doesn't always provide award amounts in search
                award_amount_max=None,
                estimated_total_program_funding=None,
                naics_codes=naics_codes,
                set_aside_type=data.get("typeOfSetAsideDescription"),
                opportunity_type=data.get("type", "Unknown"),
                description=data.get("description"),
                raw_text=data.get("description"),
                source_url=f"https://sam.gov/opp/{source_id}/view",
                status="new",
                sbir_program_active=False,  # Not SBIR source
            )
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error normalizing SAM.gov opportunity: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse SAM.gov date string to datetime."""
        if not date_str:
            return None
        try:
            # SAM.gov uses MM/DD/YYYY format
            return datetime.strptime(date_str, "%m/%d/%Y")
        except Exception:
            try:
                # Try ISO format
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None
    
    def _get_recent_date(self) -> str:
        """Get date string for 30 days ago (MM/DD/YYYY format)."""
        from datetime import timedelta
        recent_date = datetime.utcnow() - timedelta(days=30)
        return recent_date.strftime("%m/%d/%Y")
