"""SBIR.gov API adapter - GET api.www.sbir.gov/public/api/solicitations."""

import hashlib
import logging
import time
from datetime import datetime
from typing import List, Optional

import httpx

from .base import BaseAdapter, ADAPTER_TIMEOUT, adapter_retry
from ..models import GrantOpportunity

logger = logging.getLogger(__name__)


class SbirGovAdapter(BaseAdapter):
    """Adapter for SBIR.gov Public API."""

    API_URL = "https://api.www.sbir.gov/public/api/solicitations"

    @property
    def source_name(self) -> str:
        return "sbir_gov"

    @adapter_retry()
    async def _do_fetch(self) -> any:
        """HTTP call with retry + timeout."""
        params = {"keyword": "", "open": "true"}
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=ADAPTER_TIMEOUT) as client:
            response = await client.get(self.API_URL, params=params)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "http_call source=sbir_gov url=%s status=%d duration_ms=%.0f",
                self.API_URL,
                response.status_code,
                duration_ms,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch solicitations from SBIR.gov API."""
        try:
            data = await self._do_fetch()
        except Exception as exc:
            logger.error("adapter_error source=sbir_gov error=%s", exc)
            raise

        solicitations = data if isinstance(data, list) else data.get("solicitations", [])
        opportunities = []
        for solicitation in solicitations:
            opportunity = self._normalize_opportunity(solicitation)
            if opportunity:
                opportunities.append(opportunity)
        return opportunities

    # --- normalisation helpers ---

    def _normalize_opportunity(self, data: dict) -> Optional[GrantOpportunity]:
        try:
            source_id = data.get("solicitation_number", data.get("solicitation_id", ""))
            if not source_id:
                logger.warning("SBIR.gov solicitation missing ID, skipping")
                return None
            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
            posted_date = self._parse_date(data.get("open_date", data.get("release_date")))
            response_deadline = self._parse_date(data.get("close_date"))
            agency = data.get("agency", data.get("agency_name", "Unknown"))
            title = data.get("topic_title", data.get("solicitation_title", "Untitled SBIR"))
            description = data.get("description", data.get("topic_description"))
            naics_codes = []
            naics_str = data.get("naics", "")
            if naics_str:
                naics_codes = [n.strip() for n in str(naics_str).split(",") if n.strip()]
            return GrantOpportunity(
                source=self.source_name,
                source_opportunity_id=source_id,
                dedup_hash=dedup_hash,
                title=title,
                agency=agency,
                opportunity_number=source_id,
                posted_date=posted_date,
                response_deadline=response_deadline,
                archive_date=None,
                award_amount_min=self._parse_amount(data.get("award_amount_min")),
                award_amount_max=self._parse_amount(data.get("award_amount_max", data.get("award_amount"))),
                estimated_total_program_funding=None,
                naics_codes=naics_codes,
                set_aside_type="Small Business (SBIR/STTR)",
                opportunity_type="SBIR/STTR",
                description=description,
                raw_text=description,
                source_url=data.get("solicitation_url", f"https://www.sbir.gov/sbirsearch/detail/{source_id}"),
                status="new",
                sbir_program_active=False,
            )
        except Exception as e:
            logger.error("normalise_error source=sbir_gov error=%s", e)
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                logger.warning("date_parse_error source=sbir_gov value=%s", date_str)
                return None

    def _parse_amount(self, amount) -> Optional[float]:
        if amount is None:
            return None
        try:
            amount_str = str(amount).replace("$", "").replace(",", "").strip()
            return float(amount_str) if amount_str else None
        except (ValueError, TypeError):
            return None
