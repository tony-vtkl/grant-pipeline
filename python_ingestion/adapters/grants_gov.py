"""Grants.gov API adapter - POST /v1/api/search2."""

import hashlib
import logging
import time
from datetime import datetime
from typing import List, Optional

import httpx

from .base import BaseAdapter, ADAPTER_TIMEOUT, adapter_retry
from ..models import GrantOpportunity

logger = logging.getLogger(__name__)


class GrantsGovAdapter(BaseAdapter):
    """Adapter for Grants.gov Search API v2."""

    API_URL = "https://www.grants.gov/web/grants/search-grants.html/v1/api/search2"

    def __init__(self, attribution_header: str = "VTKL Grant Pipeline"):
        self.attribution_header = attribution_header

    @property
    def source_name(self) -> str:
        return "grants_gov"

    @adapter_retry()
    async def _do_fetch(self) -> dict:
        """HTTP call with retry + timeout."""
        payload = {
            "keyword": "",
            "sortBy": "openDate|desc",
            "rows": 100,
            "oppStatuses": "forecasted|posted",
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.attribution_header,
        }
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=ADAPTER_TIMEOUT) as client:
            response = await client.post(self.API_URL, json=payload, headers=headers)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "http_call source=grants_gov url=%s status=%d duration_ms=%.0f",
                self.API_URL,
                response.status_code,
                duration_ms,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch opportunities from Grants.gov Search API."""
        try:
            data = await self._do_fetch()
        except Exception as exc:
            logger.error(
                "adapter_error source=grants_gov error=%s",
                exc,
            )
            raise

        opportunities = []
        for opp_data in data.get("oppHits", []):
            opportunity = self._normalize_opportunity(opp_data)
            if opportunity:
                opportunities.append(opportunity)
        return opportunities

    # --- normalisation helpers (unchanged) ---

    def _normalize_opportunity(self, data: dict) -> Optional[GrantOpportunity]:
        try:
            source_id = data.get("number", data.get("id", ""))
            if not source_id:
                logger.warning("Grants.gov opportunity missing ID, skipping")
                return None
            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
            posted_date = self._parse_date(data.get("openDate"))
            response_deadline = self._parse_date(data.get("closeDate"))
            archive_date = self._parse_date(data.get("archiveDate"))
            return GrantOpportunity(
                source=self.source_name,
                source_opportunity_id=source_id,
                dedup_hash=dedup_hash,
                title=data.get("title", "Untitled"),
                agency=data.get("agencyName", data.get("agency", "Unknown")),
                opportunity_number=data.get("number"),
                posted_date=posted_date,
                response_deadline=response_deadline,
                archive_date=archive_date,
                award_amount_min=self._parse_amount(data.get("awardFloor")),
                award_amount_max=self._parse_amount(data.get("awardCeiling")),
                estimated_total_program_funding=self._parse_amount(data.get("estimatedFunding")),
                naics_codes=[],
                set_aside_type=data.get("additionalInfoOnEligibility"),
                opportunity_type="Grant",
                description=data.get("synopsis", data.get("description")),
                raw_text=data.get("synopsis", data.get("description")),
                source_url=f"https://www.grants.gov/web/grants/view-opportunity.html?oppId={source_id}",
                status="new",
                sbir_program_active=False,
            )
        except Exception as e:
            logger.error("normalise_error source=grants_gov error=%s", e)
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(date_str, "%m/%d/%Y")
            except Exception:
                logger.warning("date_parse_error source=grants_gov value=%s", date_str)
                return None

    def _parse_amount(self, amount) -> Optional[float]:
        if amount is None:
            return None
        try:
            return float(amount)
        except (ValueError, TypeError):
            return None
