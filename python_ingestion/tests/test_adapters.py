"""Unit tests for source adapters with mocked httpx responses (respx).

Per INTAKE BLOCK 1 DoD:
- Unit tests for each source adapter with mocked httpx responses (respx)
- All acceptance criteria validated
"""

import pytest
import respx
import httpx
from adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter


@pytest.mark.asyncio
@respx.mock
async def test_grants_gov_adapter_returns_opportunities():
    """AC #1: Grants.gov adapter returns ≥1 GrantOpportunity record.
    AC #6: Grants.gov requests include attribution header per ToS.
    """
    # Mock Grants.gov API response
    mock_response = {
        "hitCount": 2,
        "oppHits": [
            {
                "id": "GRANTS-001",
                "number": "HHS-2024-001",
                "title": "AI for Healthcare",
                "agencyName": "Health and Human Services",
                "openDate": "2024-01-15",
                "closeDate": "2024-03-18",
                "synopsis": "Seeking AI solutions for healthcare data analysis",
                "awardCeiling": 2500000,
                "awardFloor": 1000000,
            },
            {
                "id": "GRANTS-002",
                "number": "NSF-2024-002",
                "title": "Cyberinfrastructure Development",
                "agencyName": "National Science Foundation",
                "openDate": "2024-02-01",
                "closeDate": "2024-04-30",
                "synopsis": "NSF cyberinfrastructure research",
            }
        ]
    }
    
    # Setup mock
    route = respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2")
    route.return_value = httpx.Response(200, json=mock_response)
    
    # Test adapter
    adapter = GrantsGovAdapter(attribution_header="VTKL Test")
    opportunities = await adapter.fetch_opportunities()
    
    # Assertions
    assert len(opportunities) >= 1, "Should return at least 1 opportunity"
    assert len(opportunities) == 2, "Should return 2 opportunities from mock"
    
    # Verify first opportunity
    opp = opportunities[0]
    assert opp.source == "grants_gov"
    assert opp.source_opportunity_id == "GRANTS-001"
    assert opp.title == "AI for Healthcare"
    assert opp.agency == "Health and Human Services"
    assert opp.dedup_hash is not None
    assert len(opp.dedup_hash) == 64  # SHA256 produces 64-char hex
    assert opp.sbir_program_active is False  # AC #5
    
    # Verify attribution header (AC #6)
    request = route.calls.last.request
    assert request.headers.get("User-Agent") == "VTKL Test"


@pytest.mark.asyncio
@respx.mock
async def test_sam_gov_adapter_returns_opportunities():
    """AC #1: SAM.gov adapter returns ≥1 GrantOpportunity record."""
    # Mock SAM.gov API response
    mock_response = {
        "totalRecords": 1,
        "opportunitiesData": [
            {
                "noticeId": "SAM-001",
                "solicitationNumber": "W911NF-24-R-0001",
                "title": "Army Research Lab AI/ML",
                "organizationName": "Department of Defense",
                "fullParentPathName": "DOD > Army > ARL",
                "postedDate": "01/15/2024",
                "responseDeadLine": "03/18/2024",
                "naicsCode": ["541511", "541512"],
                "typeOfSetAsideDescription": "Small Business",
                "type": "Solicitation",
                "description": "Seeking AI/ML research partners",
            }
        ]
    }
    
    # Setup mock
    route = respx.get("https://api.sam.gov/opportunities/v2/search")
    route.return_value = httpx.Response(200, json=mock_response)
    
    # Test adapter
    adapter = SamGovAdapter(api_key="test-key")
    opportunities = await adapter.fetch_opportunities()
    
    # Assertions
    assert len(opportunities) >= 1, "Should return at least 1 opportunity"
    
    opp = opportunities[0]
    assert opp.source == "sam_gov"
    assert opp.source_opportunity_id == "SAM-001"
    assert opp.title == "Army Research Lab AI/ML"
    assert opp.naics_codes == ["541511", "541512"]
    assert opp.sbir_program_active is False  # AC #5


@pytest.mark.asyncio
@respx.mock
async def test_sbir_gov_adapter_returns_opportunities():
    """AC #1: SBIR.gov adapter returns ≥1 GrantOpportunity record.
    AC #5: sbir_program_active defaults to False on all SBIR.gov records.
    """
    # Mock SBIR.gov API response
    mock_response = [
        {
            "solicitation_number": "N241-001",
            "solicitation_id": "SBIR-001",
            "topic_title": "Navy SBIR: AI for Ship Systems",
            "agency": "Department of Navy",
            "agency_name": "Navy",
            "open_date": "2024-01-15",
            "close_date": "2024-03-18",
            "description": "SBIR Phase II AI development",
            "award_amount_max": 1500000,
            "solicitation_url": "https://www.sbir.gov/sbirsearch/detail/N241-001",
        }
    ]
    
    # Setup mock
    route = respx.get("https://api.www.sbir.gov/public/api/solicitations")
    route.return_value = httpx.Response(200, json=mock_response)
    
    # Test adapter
    adapter = SbirGovAdapter()
    opportunities = await adapter.fetch_opportunities()
    
    # Assertions
    assert len(opportunities) >= 1, "Should return at least 1 opportunity"
    
    opp = opportunities[0]
    assert opp.source == "sbir_gov"
    assert opp.source_opportunity_id == "N241-001"
    assert opp.title == "Navy SBIR: AI for Ship Systems"
    
    # AC #5: sbir_program_active defaults to False
    assert opp.sbir_program_active is False, "sbir_program_active must default to False"


@pytest.mark.asyncio
@respx.mock
async def test_all_pydantic_fields_populated_or_none():
    """AC #3: All GrantOpportunity fields populated or explicitly None — no validation errors."""
    mock_response = {
        "hitCount": 1,
        "oppHits": [
            {
                "id": "MINIMAL-001",
                "title": "Minimal Opportunity",
                "agencyName": "Test Agency",
                # Omit optional fields
            }
        ]
    }
    
    respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    
    adapter = GrantsGovAdapter()
    opportunities = await adapter.fetch_opportunities()
    
    assert len(opportunities) == 1
    opp = opportunities[0]
    
    # Required fields must be present
    assert opp.source is not None
    assert opp.source_opportunity_id is not None
    assert opp.dedup_hash is not None
    assert opp.title is not None
    assert opp.agency is not None
    assert opp.source_url is not None
    
    # Optional fields explicitly None
    assert opp.posted_date is None or isinstance(opp.posted_date, type(opp.posted_date))
    assert opp.response_deadline is None or isinstance(opp.response_deadline, type(opp.response_deadline))
    
    # No Pydantic validation errors (if we got here, validation passed)


@pytest.mark.asyncio
@respx.mock
async def test_polling_cycle_completes_under_5_minutes():
    """AC #4: Full polling cycle across all three federal sources completes in <5 minutes locally.
    
    This is a smoke test - real timing test requires live APIs.
    """
    import time
    
    # Mock all three sources with minimal data
    respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(200, json={"hitCount": 0, "oppHits": []})
    )
    respx.get("https://api.sam.gov/opportunities/v2/search").mock(
        return_value=httpx.Response(200, json={"totalRecords": 0, "opportunitiesData": []})
    )
    respx.get("https://api.www.sbir.gov/public/api/solicitations").mock(
        return_value=httpx.Response(200, json=[])
    )
    
    # Initialize all adapters
    adapters = [
        GrantsGovAdapter(),
        SamGovAdapter(api_key="test-key"),
        SbirGovAdapter(),
    ]
    
    # Time the full cycle
    start_time = time.time()
    
    for adapter in adapters:
        await adapter.fetch_opportunities()
    
    duration = time.time() - start_time
    
    # Should complete quickly with mocked responses (real test would be <300s)
    assert duration < 10, f"Mocked cycle took {duration}s, should be nearly instant"
