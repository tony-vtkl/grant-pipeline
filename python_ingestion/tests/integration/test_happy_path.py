"""Integration test: Happy path — full pipeline end-to-end.

AC-2: adapter fetch → normalize → dedup → eligibility → score → DB insert succeeds.
"""

import hashlib
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

from python_ingestion.adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter
from python_ingestion.deduplicator import Deduplicator
from python_ingestion.eligibility import assess_eligibility
from python_ingestion.scorer import score_opportunity, DEFAULT_WEIGHTS
from tests.integration.conftest import MockDBClient


@pytest.mark.asyncio
async def test_full_pipeline_happy_path(grants_gov_snapshot, sam_gov_snapshot, sbir_gov_snapshot, mock_db):
    """Full end-to-end: fetch → normalize → dedup → eligibility → score → DB insert."""

    all_opportunities = []

    # Grants.gov
    with respx.mock:
        respx.post(GrantsGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=grants_gov_snapshot)
        )
        opps = await GrantsGovAdapter(attribution_header="test").fetch_opportunities()
        assert len(opps) >= 1
        all_opportunities.extend(opps)

    # SAM.gov
    sam_adapter = SamGovAdapter(api_key="test-key")
    with respx.mock:
        respx.get(SamGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=sam_gov_snapshot)
        )
        opps = await sam_adapter.fetch_opportunities()
        assert len(opps) >= 1
        all_opportunities.extend(opps)

    # SBIR.gov
    with respx.mock:
        respx.get(SbirGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=sbir_gov_snapshot)
        )
        opps = await SbirGovAdapter().fetch_opportunities()
        assert len(opps) >= 1
        all_opportunities.extend(opps)

    total_fetched = len(all_opportunities)
    assert total_fetched >= 3

    # Dedup
    existing_hashes = await mock_db.get_existing_hashes()
    deduplicator = Deduplicator(existing_hashes)
    new_opps = deduplicator.deduplicate(all_opportunities)
    assert len(new_opps) == total_fetched

    # Eligibility
    eligible_opps = []
    for opp in new_opps:
        result = assess_eligibility(opp)
        if result.is_eligible:
            eligible_opps.append((opp, result))

    assert len(eligible_opps) >= 1

    # Score
    scored = []
    for opp, elig in eligible_opps:
        score_result = score_opportunity(opp, elig, DEFAULT_WEIGHTS)
        scored.append((opp, score_result))
        assert score_result.composite_score >= 0
        assert score_result.verdict in ("GO", "SHAPE", "MONITOR", "NO-GO")

    assert len(scored) >= 1

    # DB insert
    opps_to_insert = [opp for opp, _ in scored]
    count = await mock_db.insert_opportunities(opps_to_insert)
    assert count == len(opps_to_insert)
    assert len(mock_db.inserted) == count

    for opp in mock_db.inserted:
        expected = hashlib.sha256(f"{opp.source}:{opp.source_opportunity_id}".encode()).hexdigest()
        assert opp.dedup_hash == expected


@pytest.mark.asyncio
async def test_pipeline_produces_valid_models(grants_gov_snapshot):
    """Pipeline output are valid Pydantic models with required fields."""
    with respx.mock:
        respx.post(GrantsGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=grants_gov_snapshot)
        )
        opps = await GrantsGovAdapter(attribution_header="test").fetch_opportunities()

    for opp in opps:
        assert opp.source == "grants_gov"
        assert opp.source_opportunity_id
        assert opp.dedup_hash
        assert opp.title
        assert opp.source_url
