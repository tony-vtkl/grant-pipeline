"""SAM.gov API adapter - authenticated API access."""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from .base import BaseAdapter, ADAPTER_TIMEOUT, adapter_retry
from ..models import GrantOpportunity

logger = logging.getLogger(__name__)


class SamGovAdapter(BaseAdapter):
    """Adapter for SAM.gov Opportunities API."""

    API_URL = "https://api.sam.gov/opportunities/v2/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def source_name(self) -> str:
        return "sam_gov"

    @adapter_retry()
    async def _do_fetch(self) -> dict:
        """HTTP call with retry + timeout."""
        params = {
            "api_key": self.api_key,
            "postedFrom": self._get_recent_date(),
            "ptype": "o,g",
            "limit": 100,
        }
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=ADAPTER_TIMEOUT) as client:
            response = await client.get(self.API_URL, params=params)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "http_call source=sam_gov url=%s status=%d duration_ms=%.0f",
                self.API_URL,
                response.status_code,
                duration_ms,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch opportunities from SAM.gov API."""
        try:
            data = await self._do_fetch()
        except Exception as exc:
            logger.error("adapter_error source=sam_gov error=%s", exc)
            raise

        opportunities = []
        for opp_data in data.get("opportunitiesData", []):
            opportunity = self._normalize_opportunity(opp_data)
            if opportunity:
                opportunities.append(opportunity)
        return opportunities

    # --- normalisation helpers ---

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
            logger.error("normalise_error source=sam_gov error=%s", e)
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
                logger.warning("date_parse_error source=sam_gov value=%s", date_str)
                return None

    def _get_recent_date(self) -> str:
        recent_date = datetime.utcnow() - timedelta(days=30)
        return recent_date.strftime("%m/%d/%Y")
