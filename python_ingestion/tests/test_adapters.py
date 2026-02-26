"""Unit tests for source adapters with mocked httpx responses (respx).

Per INTAKE BLOCK 1 DoD:
- Unit tests for each source adapter with mocked httpx responses (respx)
- All acceptance criteria validated

VTK-96: Added error handling tests (timeout, retry exhaustion, malformed response,
partial failure isolation).
"""

import pytest
import respx
import httpx
from adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

GRANTS_GOV_URL = "https://www.grants.gov/web/grants/search-grants.html/v1/api/search2"
SAM_GOV_URL = "https://api.sam.gov/opportunities/v2/search"
SBIR_GOV_URL = "https://api.www.sbir.gov/public/api/solicitations"

GRANTS_GOV_MOCK = {
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

SAM_GOV_MOCK = {
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

SBIR_GOV_MOCK = [
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


def _mock_all_sources_success():
    """Set up respx mocks for all three sources returning valid data."""
    respx.post(GRANTS_GOV_URL).mock(return_value=httpx.Response(200, json=GRANTS_GOV_MOCK))
    respx.get(SAM_GOV_URL).mock(return_value=httpx.Response(200, json=SAM_GOV_MOCK))
    respx.get(SBIR_GOV_URL).mock(return_value=httpx.Response(200, json=SBIR_GOV_MOCK))


# ---------------------------------------------------------------------------
# Existing tests (preserved from INTAKE BLOCK 1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_grants_gov_adapter_returns_opportunities():
    """AC #1: Grants.gov adapter returns ≥1 GrantOpportunity record.
    AC #6: Grants.gov requests include attribution header per ToS.
    """
    route = respx.post(GRANTS_GOV_URL)
    route.return_value = httpx.Response(200, json=GRANTS_GOV_MOCK)

    adapter = GrantsGovAdapter(attribution_header="VTKL Test")
    opportunities = await adapter.fetch_opportunities()

    assert len(opportunities) >= 1, "Should return at least 1 opportunity"
    assert len(opportunities) == 2, "Should return 2 opportunities from mock"

    opp = opportunities[0]
    assert opp.source == "grants_gov"
    # number field takes priority over id in _normalize_opportunity
    assert opp.source_opportunity_id == "HHS-2024-001"
    assert opp.title == "AI for Healthcare"
    assert opp.agency == "Health and Human Services"
    assert opp.dedup_hash is not None
    assert len(opp.dedup_hash) == 64  # SHA256
    assert opp.sbir_program_active is False  # AC #5

    # Verify attribution header (AC #6)
    request = route.calls.last.request
    assert request.headers.get("User-Agent") == "VTKL Test"


@pytest.mark.asyncio
@respx.mock
async def test_sam_gov_adapter_returns_opportunities():
    """AC #1: SAM.gov adapter returns ≥1 GrantOpportunity record."""
    route = respx.get(SAM_GOV_URL)
    route.return_value = httpx.Response(200, json=SAM_GOV_MOCK)

    adapter = SamGovAdapter(api_key="test-key")
    opportunities = await adapter.fetch_opportunities()

    assert len(opportunities) >= 1
    opp = opportunities[0]
    assert opp.source == "sam_gov"
    assert opp.source_opportunity_id == "SAM-001"
    assert opp.title == "Army Research Lab AI/ML"
    assert opp.naics_codes == ["541511", "541512"]
    assert opp.sbir_program_active is False


@pytest.mark.asyncio
@respx.mock
async def test_sbir_gov_adapter_returns_opportunities():
    """AC #1 & AC #5: SBIR.gov adapter returns ≥1 GrantOpportunity, sbir_program_active=False."""
    route = respx.get(SBIR_GOV_URL)
    route.return_value = httpx.Response(200, json=SBIR_GOV_MOCK)

    adapter = SbirGovAdapter()
    opportunities = await adapter.fetch_opportunities()

    assert len(opportunities) >= 1
    opp = opportunities[0]
    assert opp.source == "sbir_gov"
    assert opp.source_opportunity_id == "N241-001"
    assert opp.title == "Navy SBIR: AI for Ship Systems"
    assert opp.sbir_program_active is False


@pytest.mark.asyncio
@respx.mock
async def test_all_pydantic_fields_populated_or_none():
    """AC #3: All GrantOpportunity fields populated or explicitly None."""
    mock_response = {
        "hitCount": 1,
        "oppHits": [{"id": "MINIMAL-001", "title": "Minimal Opportunity", "agencyName": "Test Agency"}]
    }
    respx.post(GRANTS_GOV_URL).mock(return_value=httpx.Response(200, json=mock_response))

    adapter = GrantsGovAdapter()
    opportunities = await adapter.fetch_opportunities()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.source is not None
    assert opp.source_opportunity_id is not None
    assert opp.dedup_hash is not None
    assert opp.title is not None
    assert opp.agency is not None
    assert opp.source_url is not None


@pytest.mark.asyncio
@respx.mock
async def test_polling_cycle_completes_under_5_minutes():
    """AC #4: Full polling cycle across all three sources completes quickly."""
    import time

    _mock_all_sources_success()

    adapters = [GrantsGovAdapter(), SamGovAdapter(api_key="test-key"), SbirGovAdapter()]

    start_time = time.time()
    for adapter in adapters:
        await adapter.fetch_opportunities()
    duration = time.time() - start_time

    assert duration < 10


# ---------------------------------------------------------------------------
# VTK-96: Error handling tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_adapter_timeout_returns_empty_list():
    """VTK-96: Adapter returns [] on timeout instead of raising."""
    respx.post(GRANTS_GOV_URL).mock(side_effect=httpx.ConnectTimeout("connect timed out"))

    adapter = GrantsGovAdapter()
    result = await adapter.fetch_opportunities()
    assert result == [], "Adapter must return empty list on timeout"


@pytest.mark.asyncio
@respx.mock
async def test_adapter_timeout_returns_empty_list_sam():
    """VTK-96: SAM.gov adapter returns [] on timeout."""
    respx.get(SAM_GOV_URL).mock(side_effect=httpx.ConnectTimeout("connect timed out"))

    adapter = SamGovAdapter(api_key="test-key")
    result = await adapter.fetch_opportunities()
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_adapter_timeout_returns_empty_list_sbir():
    """VTK-96: SBIR.gov adapter returns [] on timeout."""
    respx.get(SBIR_GOV_URL).mock(side_effect=httpx.ConnectTimeout("connect timed out"))

    adapter = SbirGovAdapter()
    result = await adapter.fetch_opportunities()
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_adapter_retry_exhaustion():
    """VTK-96: After 3 consecutive failures (500s), adapter returns [] after retries."""
    respx.post(GRANTS_GOV_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    adapter = GrantsGovAdapter()
    result = await adapter.fetch_opportunities()
    assert result == [], "Adapter must return empty list after retry exhaustion"


@pytest.mark.asyncio
@respx.mock
async def test_adapter_malformed_response():
    """VTK-96: Adapter returns [] gracefully on malformed JSON response."""
    respx.post(GRANTS_GOV_URL).mock(
        return_value=httpx.Response(200, content=b"not json at all", headers={"content-type": "application/json"})
    )

    adapter = GrantsGovAdapter()
    result = await adapter.fetch_opportunities()
    assert result == [], "Adapter must return empty list on malformed response"


@pytest.mark.asyncio
@respx.mock
async def test_adapter_malformed_response_sam():
    """VTK-96: SAM.gov adapter returns [] on malformed JSON."""
    respx.get(SAM_GOV_URL).mock(
        return_value=httpx.Response(200, content=b"<<<garbage>>>", headers={"content-type": "application/json"})
    )

    adapter = SamGovAdapter(api_key="test-key")
    result = await adapter.fetch_opportunities()
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_partial_failure_pipeline_continues():
    """VTK-96: When 1 adapter fails, the other 2 still return results."""
    # Grants.gov fails
    respx.post(GRANTS_GOV_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
    # SAM.gov and SBIR.gov succeed
    respx.get(SAM_GOV_URL).mock(return_value=httpx.Response(200, json=SAM_GOV_MOCK))
    respx.get(SBIR_GOV_URL).mock(return_value=httpx.Response(200, json=SBIR_GOV_MOCK))

    adapters = [GrantsGovAdapter(), SamGovAdapter(api_key="test-key"), SbirGovAdapter()]

    all_opportunities = []
    for adapter in adapters:
        try:
            opportunities = await adapter.fetch_opportunities()
            all_opportunities.extend(opportunities)
        except Exception:
            pass  # Pipeline continues

    # SAM returns 1, SBIR returns 1 = 2 total (Grants.gov returned [])
    assert len(all_opportunities) == 2, f"Expected 2 from surviving adapters, got {len(all_opportunities)}"
    sources = {opp.source for opp in all_opportunities}
    assert "sam_gov" in sources
    assert "sbir_gov" in sources
    assert "grants_gov" not in sources
