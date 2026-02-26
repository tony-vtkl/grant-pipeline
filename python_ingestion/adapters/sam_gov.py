"""SAM.gov API adapter - authenticated API access."""

import hashlib
import logging
import time
from datetime import datetime
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from .base import BaseAdapter
try:
    from ..models import GrantOpportunity
except ImportError:
    from models import GrantOpportunity

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, connect=30.0)


class SamGovAdapter(BaseAdapter):
    """Adapter for SAM.gov Opportunities API."""

    API_URL = "https://api.sam.gov/opportunities/v2/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return "sam_gov"

    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch opportunities. Returns empty list on failure for partial failure isolation."""
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
        url = self.API_URL
        start = time.monotonic()
        status_code = None

        params = {
            "api_key": self.api_key,
            "postedFrom": self._get_recent_date(),
            "ptype": "o,g",
            "limit": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url, params=params)
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
        try:
            source_id = data.get("noticeId", "")
            if not source_id:
                logger.warning("SAM.gov opportunity missing noticeId, skipping")
                return None

            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()

            posted_date = self._parse_date(data.get("postedDate"))
            response_deadline = self._parse_date(data.get("responseDeadLine"))
            archive_date = self._parse_date(data.get("archiveDate"))

            naics_codes = []
            naics_list = data.get("naicsCode", [])
            if isinstance(naics_list, list):
                naics_codes = [str(code) for code in naics_list if code]
            elif naics_list:
                naics_codes = [str(naics_list)]

            return GrantOpportunity(
                source=self.source_name,
                source_opportunity_id=source_id,
                dedup_hash=dedup_hash,
                title=data.get("title", "Untitled"),
                agency=data.get("fullParentPathName", data.get("organizationName", "Unknown")),
                opportunity_number=data.get("solicitationNumber", source_id),
                posted_date=posted_date,
                response_deadline=response_deadline,
                archive_date=archive_date,
                award_amount_min=None,
                award_amount_max=None,
                estimated_total_program_funding=None,
                naics_codes=naics_codes,
                set_aside_type=data.get("typeOfSetAsideDescription"),
                opportunity_type=data.get("type", "Unknown"),
                description=data.get("description"),
                raw_text=data.get("description"),
                source_url=f"https://sam.gov/opp/{source_id}/view",
                status="new",
                sbir_program_active=False,
            )
        except Exception as e:
            logger.error(f"Error normalizing SAM.gov opportunity: {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except Exception:
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None

    def _get_recent_date(self) -> str:
        from datetime import timedelta
        recent_date = datetime.utcnow() - timedelta(days=30)
        return recent_date.strftime("%m/%d/%Y")
