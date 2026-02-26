"""SBIR.gov API adapter - GET api.www.sbir.gov/public/api/solicitations."""

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


class SbirGovAdapter(BaseAdapter):
    """Adapter for SBIR.gov Public API."""

    API_URL = "https://api.www.sbir.gov/public/api/solicitations"

    @property
    def source_name(self) -> str:
        return "sbir_gov"

    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch solicitations. Returns empty list on failure for partial failure isolation."""
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

        params = {"keyword": "", "open": "true"}

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
            solicitations = data if isinstance(data, list) else data.get("solicitations", [])
            logger.info(f"SBIR.gov returned {len(solicitations)} solicitations")

            for solicitation in solicitations:
                opportunity = self._normalize_opportunity(solicitation)
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
            logger.error(f"Error normalizing SBIR.gov opportunity: {e}")
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
                logger.warning(f"Could not parse date: {date_str}")
                return None

    def _parse_amount(self, amount: Optional[any]) -> Optional[float]:
        if amount is None:
            return None
        try:
            amount_str = str(amount).replace("$", "").replace(",", "").strip()
            return float(amount_str) if amount_str else None
        except (ValueError, TypeError):
            return None
