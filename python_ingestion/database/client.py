"""Supabase database client for grant pipeline."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from supabase import Client, create_client

from models.grant_opportunity import GrantOpportunity

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Client for interacting with Supabase grant_opportunities and pipeline_runs tables."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:
        """Initialize Supabase client from explicit args or env vars.

        Args:
            url: Supabase project URL (falls back to SUPABASE_URL env var).
            key: Supabase anon/service key (falls back to SUPABASE_KEY env var).
        """
        self._url = url or os.environ["SUPABASE_URL"]
        self._key = key or os.environ["SUPABASE_KEY"]
        self._client: Client = create_client(self._url, self._key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_existing_hashes(self) -> Set[str]:
        """Return all dedup_hash values currently stored in grant_opportunities.

        Returns:
            Set of dedup_hash strings.
        """
        response = (
            self._client.table("grant_opportunities")
            .select("dedup_hash")
            .execute()
        )
        return {row["dedup_hash"] for row in response.data}

    def upsert_grant(self, grant: GrantOpportunity) -> Dict[str, Any]:
        """Insert or update a grant record keyed by dedup_hash.

        Args:
            grant: A GrantOpportunity instance.

        Returns:
            The upserted row as a dict.
        """
        record = grant.model_dump(mode="json")
        response = (
            self._client.table("grant_opportunities")
            .upsert(record, on_conflict="dedup_hash")
            .execute()
        )
        logger.info("Upserted grant %s", grant.dedup_hash)
        return response.data[0] if response.data else {}

    def save_pipeline_run(
        self,
        started_at: datetime,
        completed_at: datetime,
        grants_processed: int,
        grants_new: int,
        grants_updated: int,
        errors: Optional[List[str]] = None,
        status: str = "completed",
    ) -> Dict[str, Any]:
        """Persist pipeline run metadata.

        Args:
            started_at: Run start timestamp.
            completed_at: Run completion timestamp.
            grants_processed: Total grants seen.
            grants_new: Newly inserted grants.
            grants_updated: Updated existing grants.
            errors: List of error messages (if any).
            status: Run status string.

        Returns:
            The inserted row as a dict.
        """
        record = {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "grants_processed": grants_processed,
            "grants_new": grants_new,
            "grants_updated": grants_updated,
            "errors": errors or [],
            "status": status,
        }
        response = (
            self._client.table("pipeline_runs")
            .insert(record)
            .execute()
        )
        logger.info("Saved pipeline run: %d processed, %d new, %d updated",
                     grants_processed, grants_new, grants_updated)
        return response.data[0] if response.data else {}
