"""USAspending.gov API integration for partner enrichment.

Public API — no key required (DATA Act mandated).
Docs: https://api.usaspending.gov

Source: BRD Section 3C
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.usaspending.gov/api/v2"

# VTKL-relevant NAICS codes
VTKL_NAICS = ["541511", "541512", "541990"]


@dataclass
class USAspendingPartner:
    """A partner found via USAspending.gov past award data."""

    name: str
    naics_codes: list[str] = field(default_factory=list)
    agency: str = ""
    award_count: int = 0


def lookup_partners_by_naics_and_agency(
    agency: str,
    naics_codes: list[str] | None = None,
    limit: int = 5,
    timeout: float = 15.0,
) -> list[USAspendingPartner]:
    """Query USAspending.gov for past awardees matching NAICS + agency.

    Uses the /search/spending_by_award/ endpoint to find organizations
    that have received awards in relevant NAICS codes from the specified agency.

    Args:
        agency: Agency name or abbreviation to search.
        naics_codes: NAICS codes to filter by. Defaults to VTKL_NAICS.
        limit: Max results to return.
        timeout: HTTP request timeout in seconds.

    Returns:
        List of USAspendingPartner with name and metadata.
    """
    if naics_codes is None:
        naics_codes = VTKL_NAICS

    payload: dict[str, Any] = {
        "filters": {
            "naics_codes": naics_codes,
            "agencies": [
                {
                    "type": "awarding",
                    "tier": "toptier",
                    "name": agency,
                }
            ],
            "time_period": [
                {
                    "start_date": "2020-01-01",
                    "end_date": "2026-12-31",
                }
            ],
        },
        "fields": [
            "Recipient Name",
            "Award Amount",
            "NAICS Code",
            "Awarding Agency",
        ],
        "limit": limit,
        "page": 1,
        "sort": "Award Amount",
        "order": "desc",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{BASE_URL}/search/spending_by_award/", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("USAspending API HTTP error %s: %s", exc.response.status_code, exc)
        return []
    except (httpx.RequestError, Exception) as exc:
        logger.warning("USAspending API request error: %s", exc)
        return []

    results: list[USAspendingPartner] = []
    seen_names: set[str] = set()

    for row in data.get("results", []):
        name = row.get("Recipient Name", "").strip()
        if not name or name.upper() in seen_names:
            continue
        seen_names.add(name.upper())

        naics = row.get("NAICS Code", "")
        results.append(
            USAspendingPartner(
                name=name,
                naics_codes=[naics] if naics else [],
                agency=row.get("Awarding Agency", ""),
                award_count=1,
            )
        )

    return results
