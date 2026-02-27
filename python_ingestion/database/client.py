"""Supabase database client for grant pipeline."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from supabase import Client, create_client

from models.grant_opportunity import GrantOpportunity
from models.eligibility_result import EligibilityResult

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

    def save_eligibility_result(self, result: EligibilityResult) -> Dict[str, Any]:
        """Persist an eligibility assessment result.

        Args:
            result: EligibilityResult from the eligibility engine.

        Returns:
            The inserted row as a dict.
        """
        record = {
            "opportunity_id": result.opportunity_id,
            "is_eligible": result.is_eligible,
            "participation_path": result.participation_path,
            "entity_type_check": result.entity_type_check.model_dump(),
            "location_check": result.location_check.model_dump(),
            "sam_active_check": result.sam_active_check.model_dump(),
            "naics_match_check": result.naics_match_check.model_dump(),
            "security_posture_check": result.security_posture_check.model_dump(),
            "certification_check": result.certification_check.model_dump(),
            "blockers": result.blockers,
            "assets": result.assets,
            "warnings": result.warnings,
            "evaluated_at": result.evaluated_at.isoformat(),
            "vtkl_profile_version": result.vtkl_profile_version,
        }
        response = (
            self._client.table("eligibility_results")
            .insert(record)
            .execute()
        )
        logger.info("Saved eligibility result for %s: eligible=%s",
                     result.opportunity_id, result.is_eligible)
        return response.data[0] if response.data else {}

    def update_grant_status(self, opportunity_id: str, new_status: str) -> Dict[str, Any]:
        """Update a grant opportunity's status by source_opportunity_id.

        Args:
            opportunity_id: The source_opportunity_id of the grant.
            new_status: New status value (e.g., 'assessed').

        Returns:
            The updated row as a dict, or empty dict if not found.
        """
        response = (
            self._client.table("grant_opportunities")
            .update({"status": new_status, "last_updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("source_opportunity_id", opportunity_id)
            .execute()
        )
        logger.info("Updated grant %s status to '%s'", opportunity_id, new_status)
        return response.data[0] if response.data else {}

    def get_grants_by_status(self, status: str) -> List[GrantOpportunity]:
        """Fetch all grants with a given status.

        Args:
            status: Status to filter by (e.g., 'new').

        Returns:
            List of GrantOpportunity objects.
        """
        response = (
            self._client.table("grant_opportunities")
            .select("*")
            .eq("status", status)
            .execute()
        )
        return [GrantOpportunity(**row) for row in response.data]
