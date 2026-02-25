"""Tests for VTK-93: Error handling in adapters.

AC coverage:
  1. try/except with source-specific error messages
  2. Retry with exponential backoff (3 attempts)
  3. Timeout config (30s connect, 60s read)
  4. Structured logging (source, URL, status, duration, result)
  5. Partial failure isolation (1 source fails, others continue)
  6. This file provides the minimum 5 tests required
"""

import logging
import pytest
import respx
import httpx

from python_ingestion.adapters import GrantsGovAdapter, SamGovAdapter, SbirGovAdapter
from python_ingestion.adapters.base import ADAPTER_TIMEOUT


# ---------------------------------------------------------------------------
# Test 1: Success path — adapter returns results with structured logging
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_success_path_with_structured_logging(caplog):
    """AC 1,4: Successful fetch logs source, URL, status, duration, result."""
    mock_response = {
        "hitCount": 1,
        "oppHits": [
            {
                "number": "HHS-2024-001",
                "title": "Test Grant",
                "agencyName": "HHS",
                "openDate": "2024-01-15",
                "closeDate": "2024-03-18",
                "synopsis": "Test",
            }
        ],
    }
    respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    adapter = GrantsGovAdapter()
    with caplog.at_level(logging.INFO):
        results = await adapter.safe_fetch()

    assert len(results) == 1
    assert results[0].source == "grants_gov"

    # Verify structured logging fields (AC 4)
    log_text = " ".join(caplog.text.split())
    assert "source=grants_gov" in log_text
    assert "status=200" in log_text
    assert "duration_ms=" in log_text
    assert "result=success" in log_text


# ---------------------------------------------------------------------------
# Test 2: Timeout — adapter handles connect/read timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_timeout_returns_empty_list(caplog):
    """AC 3: Timeout config exercised; adapter returns [] on timeout."""
    respx.get("https://api.sam.gov/opportunities/v2/search").mock(
        side_effect=httpx.ReadTimeout("read timed out")
    )

    adapter = SamGovAdapter(api_key="test-key")
    with caplog.at_level(logging.WARNING):
        results = await adapter.safe_fetch()

    assert results == []
    # Verify error was logged
    assert "result=failure" in caplog.text


# ---------------------------------------------------------------------------
# Test 3: Retry exhaustion — 3 attempts then gives up
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_retry_exhaustion(caplog):
    """AC 2: Retry 3 times with backoff, then fail gracefully."""
    route = respx.get("https://api.www.sbir.gov/public/api/solicitations").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    adapter = SbirGovAdapter()
    with caplog.at_level(logging.WARNING):
        results = await adapter.safe_fetch()

    assert results == []
    # tenacity retries 3 times total (1 initial + 2 retries)
    assert route.call_count == 3


# ---------------------------------------------------------------------------
# Test 4: Malformed response — adapter handles bad JSON gracefully
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_malformed_response():
    """AC 1: Malformed response handled, returns empty or partial results."""
    # Return valid JSON but missing expected keys
    respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(200, json={"unexpected": "data"})
    )

    adapter = GrantsGovAdapter()
    results = await adapter.safe_fetch()

    # Should return empty list (no oppHits key)
    assert results == []


# ---------------------------------------------------------------------------
# Test 5: Partial failure — 1 of 3 sources fails, others continue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_partial_failure_isolation():
    """AC 5: If 1 source fails, others still return results."""
    # grants_gov succeeds
    respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(
            200,
            json={
                "hitCount": 1,
                "oppHits": [
                    {
                        "number": "HHS-001",
                        "title": "Good Grant",
                        "agencyName": "HHS",
                    }
                ],
            },
        )
    )

    # sam_gov fails with 500
    respx.get("https://api.sam.gov/opportunities/v2/search").mock(
        side_effect=httpx.ConnectError("server down")
    )

    # sbir_gov succeeds
    respx.get("https://api.www.sbir.gov/public/api/solicitations").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "solicitation_number": "N241-001",
                    "topic_title": "Good SBIR",
                    "agency": "Navy",
                }
            ],
        )
    )

    adapters = [
        GrantsGovAdapter(),
        SamGovAdapter(api_key="test"),
        SbirGovAdapter(),
    ]

    all_results = []
    for adapter in adapters:
        all_results.extend(await adapter.safe_fetch())

    # 2 of 3 succeeded
    assert len(all_results) == 2
    sources = {r.source for r in all_results}
    assert "grants_gov" in sources
    assert "sbir_gov" in sources
    assert "sam_gov" not in sources


# ---------------------------------------------------------------------------
# Test 6: Timeout config is correct
# ---------------------------------------------------------------------------
def test_timeout_configuration():
    """AC 3: Verify timeout values are 30s connect, 60s read."""
    assert ADAPTER_TIMEOUT.connect == 30.0
    assert ADAPTER_TIMEOUT.read == 60.0


# ---------------------------------------------------------------------------
# Test 7: HTTP 500 triggers retry then safe_fetch returns []
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_http_500_retries_then_empty():
    """AC 1,2: HTTP errors get retried, ultimately return [] via safe_fetch."""
    route = respx.post("https://www.grants.gov/web/grants/search-grants.html/v1/api/search2").mock(
        return_value=httpx.Response(500, json={"error": "internal"})
    )

    adapter = GrantsGovAdapter()
    results = await adapter.safe_fetch()

    assert results == []
    assert route.call_count == 3  # 3 retry attempts
