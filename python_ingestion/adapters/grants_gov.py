"""Grants.gov API adapter - POST /v1/api/search2."""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional
import httpx

from .base import BaseAdapter
from models import GrantOpportunity

logger = logging.getLogger(__name__)


class GrantsGovAdapter(BaseAdapter):
    """Adapter for Grants.gov Search API v2.
    
    API Docs: https://www.grants.gov/system/files/2021-06/GrantsGovAPITermsofUse.pdf
    Endpoint: POST https://www.grants.gov/web/grants/search-grants.html/v1/api/search2
    
    Per INTAKE BLOCK 1 acceptance criteria: requests must include attribution header per ToS.
    """
    
    API_URL = "https://www.grants.gov/web/grants/search-grants.html/v1/api/search2"
    
    def __init__(self, attribution_header: str = "VTKL Grant Pipeline"):
        """Initialize adapter.
        
        Args:
            attribution_header: Attribution string per Grants.gov ToS
        """
        self.attribution_header = attribution_header
    
    @property
    def source_name(self) -> str:
        return "grants_gov"
    
    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch opportunities from Grants.gov Search API.
        
        Per INTAKE BLOCK 1: POST /v1/api/search2
        Returns ≥1 GrantOpportunity record against live API in acceptance test.
        """
        logger.info(f"Fetching opportunities from {self.source_name}")
        
        # Search payload - open search for recent opportunities
        # Real implementation would filter by relevant NAICS/keywords
        payload = {
            "keyword": "",
            "sortBy": "openDate|desc",
            "rows": 100,
            "oppStatuses": "forecasted|posted",
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self.attribution_header,  # Attribution per ToS
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
            
            opportunities = []
            hit_count = data.get("hitCount", 0)
            logger.info(f"Grants.gov returned {hit_count} opportunities")
            
            for opp_data in data.get("oppHits", []):
                opportunity = self._normalize_opportunity(opp_data)
                if opportunity:
                    opportunities.append(opportunity)
            
            logger.info(f"Normalized {len(opportunities)} opportunities from {self.source_name}")
            return opportunities
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching from {self.source_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching from {self.source_name}: {e}")
            return []
    
    def _normalize_opportunity(self, data: dict) -> Optional[GrantOpportunity]:
        """Normalize Grants.gov response to GrantOpportunity model.
        
        Args:
            data: Raw opportunity data from Grants.gov API
            
        Returns:
            Normalized GrantOpportunity or None if invalid
        """
        try:
            source_id = data.get("number", data.get("id", ""))
            if not source_id:
                logger.warning("Grants.gov opportunity missing ID, skipping")
                return None
            
            # Deduplication hash per INTAKE BLOCK 1
            dedup_string = f"{self.source_name}:{source_id}"
            dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
            
            # Parse dates
            posted_date = self._parse_date(data.get("openDate"))
            response_deadline = self._parse_date(data.get("closeDate"))
            archive_date = self._parse_date(data.get("archiveDate"))
            
            # Build opportunity
            opportunity = GrantOpportunity(
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
                naics_codes=[],  # Grants.gov doesn't provide NAICS in search results
                set_aside_type=data.get("additionalInfoOnEligibility"),
                opportunity_type="Grant",
                description=data.get("synopsis", data.get("description")),
                raw_text=data.get("synopsis", data.get("description")),
                source_url=f"https://www.grants.gov/web/grants/view-opportunity.html?oppId={source_id}",
                status="new",
                sbir_program_active=False,  # Not SBIR source
            )
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error normalizing Grants.gov opportunity: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Grants.gov date string to datetime."""
        if not date_str:
            return None
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                # Try MM/DD/YYYY format
                return datetime.strptime(date_str, "%m/%d/%Y")
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None
    
    def _parse_amount(self, amount: Optional[any]) -> Optional[float]:
        """Parse amount to float."""
        if amount is None:
            return None
        try:
            return float(amount)
        except (ValueError, TypeError):
            return None
