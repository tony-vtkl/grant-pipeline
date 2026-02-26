"""SBIR.gov API adapter - GET api.www.sbir.gov/public/api/solicitations."""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional
import httpx

from .base import BaseAdapter
from models import GrantOpportunity

logger = logging.getLogger(__name__)


class SbirGovAdapter(BaseAdapter):
    """Adapter for SBIR.gov Public API.
    
    API Endpoint: GET https://api.www.sbir.gov/public/api/solicitations
    Per INTAKE BLOCK 1: SBIR.gov records must include sbir_program_active flag (default False)
    """
    
    API_URL = "https://api.www.sbir.gov/public/api/solicitations"
    
    @property
    def source_name(self) -> str:
        return "sbir_gov"
    
    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch solicitations from SBIR.gov API.
        
        Per INTAKE BLOCK 1: GET api.www.sbir.gov/public/api/solicitations
        Returns ≥1 GrantOpportunity record against live API in acceptance test.
        sbir_program_active defaults to False per acceptance criteria.
        """
        logger.info(f"Fetching opportunities from {self.source_name}")
        
        params = {
            "keyword": "",
            "open": "true",  # Only open solicitations
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.API_URL,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
            
            opportunities = []
            
            # Handle both list and dict responses
            solicitations = data if isinstance(data, list) else data.get("solicitations", [])
            logger.info(f"SBIR.gov returned {len(solicitations)} solicitations")
            
            for solicitation in solicitations:
                opportunity = self._normalize_opportunity(solicitation)
                if opportunity:
                    opportunities.append(opportunity)
            
            logger.info(f"Normalized {len(opportunities)} opportunities from {self.source_name}")
            return opportunities
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching from {self.source_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching from {self.source_name}: {e}")
            raise
    
    def _normalize_opportunity(self, data: dict) -> Optional[GrantOpportunity]:
        """Normalize SBIR.gov response to GrantOpportunity model.
        
        Args:
            data: Raw solicitation data from SBIR.gov API
            
        Returns:
            Normalized GrantOpportunity or None if invalid
        """
        try:
            # SBIR solicitation number (e.g., "N241-123")
            source_id = data.get("solicitation_number", data.get("solicitation_id", ""))
            if not source_id:
                logger.warning("SBIR.gov solicitation missing ID, skipping")
                return None
            
            # Deduplication hash per INTAKE BLOCK 1
            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
            
            # Parse dates
            posted_date = self._parse_date(data.get("open_date", data.get("release_date")))
            response_deadline = self._parse_date(data.get("close_date"))
            
            # Agency (DoD, NASA, etc.)
            agency = data.get("agency", data.get("agency_name", "Unknown"))
            
            # Topic/solicitation details
            title = data.get("topic_title", data.get("solicitation_title", "Untitled SBIR"))
            description = data.get("description", data.get("topic_description"))
            
            # NAICS codes (if provided)
            naics_codes = []
            naics_str = data.get("naics", "")
            if naics_str:
                naics_codes = [n.strip() for n in str(naics_str).split(",") if n.strip()]
            
            # Build opportunity
            # Per INTAKE BLOCK 1 acceptance criteria #5: sbir_program_active defaults to False
            opportunity = GrantOpportunity(
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
                sbir_program_active=False,  # Per acceptance criteria #5
            )
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error normalizing SBIR.gov opportunity: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse SBIR.gov date string to datetime."""
        if not date_str:
            return None
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                # Try YYYY-MM-DD format
                return datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None
    
    def _parse_amount(self, amount: Optional[any]) -> Optional[float]:
        """Parse amount to float."""
        if amount is None:
            return None
        try:
            # Remove currency symbols and commas
            amount_str = str(amount).replace("$", "").replace(",", "").strip()
            return float(amount_str) if amount_str else None
        except (ValueError, TypeError):
            return None
