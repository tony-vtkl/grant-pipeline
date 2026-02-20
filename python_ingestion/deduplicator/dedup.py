"""Deduplication logic for grant opportunities."""

import logging
from typing import List, Set
from ..models import GrantOpportunity

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicates opportunities by SHA256(source + source_opportunity_id).
    
    Per INTAKE BLOCK 1: prevents duplicate records across polling cycles.
    Acceptance criteria #2: second run within 5min produces 0 new records for existing opportunities.
    """
    
    def __init__(self, existing_hashes: Set[str] = None):
        """Initialize deduplicator.
        
        Args:
            existing_hashes: Set of existing dedup_hash values from database
        """
        self.existing_hashes = existing_hashes or set()
    
    def deduplicate(self, opportunities: List[GrantOpportunity]) -> List[GrantOpportunity]:
        """Filter out opportunities that already exist.
        
        Args:
            opportunities: List of opportunities to deduplicate
            
        Returns:
            List of new (non-duplicate) opportunities
        """
        new_opportunities = []
        duplicate_count = 0
        
        for opp in opportunities:
            if opp.dedup_hash in self.existing_hashes:
                duplicate_count += 1
                logger.debug(f"Duplicate found: {opp.source}:{opp.source_opportunity_id}")
            else:
                new_opportunities.append(opp)
                self.existing_hashes.add(opp.dedup_hash)
        
        logger.info(f"Deduplication: {len(new_opportunities)} new, {duplicate_count} duplicates")
        return new_opportunities
    
    def add_hash(self, dedup_hash: str):
        """Add a hash to the existing set (for after DB insert)."""
        self.existing_hashes.add(dedup_hash)
    
    def add_hashes(self, hashes: Set[str]):
        """Add multiple hashes to the existing set."""
        self.existing_hashes.update(hashes)
