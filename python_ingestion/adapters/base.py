"""Base adapter interface for grant sources."""

from abc import ABC, abstractmethod
from typing import List
from ..models import GrantOpportunity


class BaseAdapter(ABC):
    """Abstract base class for grant source adapters."""
    
    @abstractmethod
    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch and normalize opportunities from source.
        
        Returns:
            List of normalized GrantOpportunity records
        """
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier (grants_gov, sam_gov, sbir_gov)."""
        pass
