"""Smoke test: full pipeline flow (ingest → dedup → store) with mocked externals.

VTK-101 / REQ-6: Validates the end-to-end polling cycle using mocked
HTTP responses, database client, and environment configuration.
"""

import hashlib
import importlib
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import GrantOpportunity


def _make_opportunity(source: str, opp_id: str, title: str) -> GrantOpportunity:
    """Build a minimal GrantOpportunity for testing."""
    dedup_hash = hashlib.sha256(f"{source}{opp_id}".encode()).hexdigest()
    return GrantOpportunity(
        source=source,
        source_opportunity_id=opp_id,
        dedup_hash=dedup_hash,
        title=title,
        agency="Test Agency",
        source_url=f"https://example.com/{opp_id}",
    )


GRANTS_GOV_OPP = _make_opportunity("grants.gov", "GG-001", "Grants.gov Opp")
SAM_GOV_OPP = _make_opportunity("sam.gov", "SAM-001", "SAM.gov Opp")
SBIR_GOV_OPP = _make_opportunity("sbir.gov", "SBIR-001", "SBIR.gov Opp")


@pytest.mark.asyncio
async def test_full_pipeline_smoke():
    """End-to-end smoke: adapters → dedup → db insert, all external deps mocked."""

    fake_config = MagicMock()
    fake_config.sam_api_key = "fake-key"
    fake_config.database_url = "postgresql://fake:fake@localhost/fake"
    fake_config.grants_gov_attribution = "test"
    fake_config.polling_interval_minutes = 60
    fake_config.log_level = "WARNING"

    mock_db = AsyncMock()
    mock_db.get_existing_hashes = AsyncMock(return_value=set())
    mock_db.insert_opportunities = AsyncMock(return_value=3)

    mock_grants = AsyncMock()
    mock_grants.source_name = "grants.gov"
    mock_grants.fetch_opportunities = AsyncMock(return_value=[GRANTS_GOV_OPP])

    mock_sam = AsyncMock()
    mock_sam.source_name = "sam.gov"
    mock_sam.fetch_opportunities = AsyncMock(return_value=[SAM_GOV_OPP])

    mock_sbir = AsyncMock()
    mock_sbir.source_name = "sbir.gov"
    mock_sbir.fetch_opportunities = AsyncMock(return_value=[SBIR_GOV_OPP])

    # python_ingestion.main uses relative imports, so we patch via package path
    # First ensure the package is importable
    import python_ingestion.main as _main_mod

    with (
        patch.object(_main_mod, "load_config", return_value=fake_config),
        patch.object(_main_mod, "SupabaseClient", return_value=mock_db),
        patch.object(_main_mod, "GrantsGovAdapter", return_value=mock_grants),
        patch.object(_main_mod, "SamGovAdapter", return_value=mock_sam),
        patch.object(_main_mod, "SbirGovAdapter", return_value=mock_sbir),
    ):
        await _main_mod.poll_all_sources()

    # DB was queried for existing hashes
    mock_db.get_existing_hashes.assert_awaited_once()

    # All three adapters fetched
    mock_grants.fetch_opportunities.assert_awaited_once()
    mock_sam.fetch_opportunities.assert_awaited_once()
    mock_sbir.fetch_opportunities.assert_awaited_once()

    # 3 new opportunities inserted (none deduped since hash set was empty)
    mock_db.insert_opportunities.assert_awaited_once()
    inserted = mock_db.insert_opportunities.call_args[0][0]
    assert len(inserted) == 3, f"Expected 3, got {len(inserted)}"
    assert {opp.source for opp in inserted} == {"grants.gov", "sam.gov", "sbir.gov"}
