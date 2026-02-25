"""Base adapter interface for grant sources."""

import logging
import time
from abc import ABC, abstractmethod
from typing import List

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from ..models import GrantOpportunity

logger = logging.getLogger(__name__)

# Standard timeout for all adapters: 30s connect, 60s read
ADAPTER_TIMEOUT = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)


class BaseAdapter(ABC):
    """Abstract base class for grant source adapters."""

    @abstractmethod
    async def fetch_opportunities(self) -> List[GrantOpportunity]:
        """Fetch and normalize opportunities from source.

        Returns:
            List of normalized GrantOpportunity records.
            Returns empty list on failure (never raises).
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier (grants_gov, sam_gov, sbir_gov)."""
        pass

    async def safe_fetch(self) -> List[GrantOpportunity]:
        """Fetch with full error handling — returns [] on any failure.

        This is the entry point callers should use for partial-failure isolation.
        """
        start = time.monotonic()
        try:
            results = await self.fetch_opportunities()
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "fetch_complete source=%s result=success count=%d duration_ms=%.0f",
                self.source_name,
                len(results),
                duration_ms,
            )
            return results
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "fetch_complete source=%s result=failure error=%s duration_ms=%.0f",
                self.source_name,
                exc,
                duration_ms,
            )
            return []


def adapter_retry():
    """Retry decorator for adapter HTTP calls: 3 attempts, exponential backoff."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
