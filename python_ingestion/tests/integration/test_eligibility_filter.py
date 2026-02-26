"""Integration test: Eligibility filters ineligible grants.

AC-4: ineligible grant is filtered out before scoring.
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

from python_ingestion.adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter
from python_ingestion.deduplicator import Deduplicator
from python_ingestion.eligibility import assess_eligibility
from python_ingestion.scorer import score_opportunity, DEFAULT_WEIGHTS
from tests.integration.conftest import MockDBClient, make_opportunity


@pytest.mark.asyncio
async def test_ineligible_grant_filtered_before_scoring(
    grants_gov_snapshot, sam_gov_snapshot, sbir_gov_snapshot, mock_db
):
    """Ineligible grants (academic-only, 8(a)) never reach scorer or DB."""

    all_opps = []

    with respx.mock:
        respx.post(GrantsGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=grants_gov_snapshot)
        )
        all_opps.extend(await GrantsGovAdapter(attribution_header="test").fetch_opportunities())

    sam = SamGovAdapter(api_key="test")
    with respx.mock:
        respx.get(SamGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=sam_gov_snapshot)
        )
        all_opps.extend(await sam.fetch_opportunities())

    sbir = SbirGovAdapter()
    with respx.mock:
        respx.get(SbirGovAdapter.API_URL).mock(
            return_value=httpx.Response(200, json=sbir_gov_snapshot)
        )
        all_opps.extend(await sbir.fetch_opportunities())

    dedup = Deduplicator(set())
    new_opps = dedup.deduplicate(all_opps)

    eligible = []
    ineligible = []
    for opp in new_opps:
        result = assess_eligibility(opp)
        if result.is_eligible:
            eligible.append((opp, result))
        else:
            ineligible.append((opp, result))

    assert len(ineligible) >= 1, "At least one grant should be ineligible"
    assert len(eligible) >= 1, "At least one grant should be eligible"

    for opp, elig_result in ineligible:
        assert not elig_result.is_eligible
        assert len(elig_result.blockers) >= 1

    scored_ids = set()
    for opp, elig_result in eligible:
        score = score_opportunity(opp, elig_result, DEFAULT_WEIGHTS)
        scored_ids.add(opp.source_opportunity_id)
        assert score.composite_score > 0

    for opp, _ in ineligible:
        assert opp.source_opportunity_id not in scored_ids

    eligible_opps = [opp for opp, _ in eligible]
    await mock_db.insert_opportunities(eligible_opps)
    assert len(mock_db.inserted) == len(eligible)
    assert len(mock_db.inserted) < len(new_opps)


@pytest.mark.asyncio
async def test_8a_certification_blocks():
    """8(a) set-aside = hard blocker for VTKL."""
    opp = make_opportunity(
        source="sam_gov", source_id="8A-BLOCK-001",
        title="8(a) Only Contract",
        description="Requires 8(a) certification. Must be 8(a) certified.",
        set_aside_type="8(a) Set-Aside",
    )
    result = assess_eligibility(opp)
    assert not result.is_eligible
    assert any("8(a)" in b or "HARD BLOCKER" in b for b in result.blockers)


@pytest.mark.asyncio
async def test_academic_only_blocks():
    """University-only grants block for-profit VTKL."""
    opp = make_opportunity(
        source="grants_gov", source_id="ACAD-001",
        title="University Research Grant",
        description="University only eligible. Academic institution required.",
    )
    result = assess_eligibility(opp)
    assert not result.is_eligible


@pytest.mark.asyncio
async def test_security_clearance_blocks():
    """Top Secret / IL6 blocks VTKL (IL2-IL4 only)."""
    opp = make_opportunity(
        source="sam_gov", source_id="TS-001",
        title="Classified System",
        description="Requires Top Secret clearance. IL6 security posture required.",
    )
    result = assess_eligibility(opp)
    assert not result.is_eligible
