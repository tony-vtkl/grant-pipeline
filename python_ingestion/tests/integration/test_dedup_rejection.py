"""Integration test: Deduplication rejects duplicates.

AC-3: duplicate grant is rejected (not inserted twice).
"""

import sys
from pathlib import Path

import httpx
import pytest
import respx

_pkg = Path(__file__).resolve().parent.parent.parent
_repo = _pkg.parent
for p in [str(_repo), str(_pkg)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from python_ingestion.adapters import GrantsGovAdapter
from python_ingestion.deduplicator import Deduplicator
from tests.integration.conftest import MockDBClient, make_opportunity


@pytest.mark.asyncio
async def test_dedup_rejects_duplicate_on_second_run(grants_gov_snapshot, mock_db):
    """Run pipeline twice with same data — second run inserts zero."""

    with respx.mock:
        respx.post(GrantsGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=grants_gov_snapshot)
        )
        adapter = GrantsGovAdapter(attribution_header="test")

        # First run
        opps_run1 = await adapter.fetch_opportunities()
        assert len(opps_run1) >= 1

        existing = await mock_db.get_existing_hashes()
        dedup1 = Deduplicator(existing)
        new1 = dedup1.deduplicate(opps_run1)
        assert len(new1) == len(opps_run1)

        await mock_db.insert_opportunities(new1)
        first_count = len(mock_db.inserted)

        # Second run (same data)
        opps_run2 = await adapter.fetch_opportunities()
        existing2 = await mock_db.get_existing_hashes()
        dedup2 = Deduplicator(existing2)
        new2 = dedup2.deduplicate(opps_run2)

        assert len(new2) == 0, f"Second run should produce 0 new, got {len(new2)}"
        assert len(mock_db.inserted) == first_count


@pytest.mark.asyncio
async def test_dedup_allows_different_sources():
    """Same ID from different sources → different hashes, both pass."""
    opp_grants = make_opportunity(source="grants_gov", source_id="SHARED-001", title="Shared")
    opp_sam = make_opportunity(source="sam_gov", source_id="SHARED-001", title="Shared")

    result = Deduplicator(set()).deduplicate([opp_grants, opp_sam])
    assert len(result) == 2
    assert result[0].dedup_hash != result[1].dedup_hash


@pytest.mark.asyncio
async def test_dedup_rejects_exact_duplicate_in_same_batch():
    """Two identical opportunities in same batch — only first kept."""
    opp1 = make_opportunity(source="grants_gov", source_id="DUP-001", title="Dup")
    opp2 = make_opportunity(source="grants_gov", source_id="DUP-001", title="Dup")

    result = Deduplicator(set()).deduplicate([opp1, opp2])
    assert len(result) == 1
