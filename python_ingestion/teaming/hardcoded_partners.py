"""Partner source — config-driven partner lookups with USASpending API primary + config fallback.

Refactored from hardcoded seed data to dynamic sources (VTK-97).
Primary: USASpending API via usaspending_lookup module.
Fallback: JSON config file specified by PARTNER_CONFIG_PATH env var.
Fail-fast if neither source is available.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from teaming.usaspending_lookup import (
    USAspendingPartner,
    lookup_partners_by_naics_and_agency,
)

logger = logging.getLogger(__name__)


class PartnerSourceError(Exception):
    """Raised when no partner data source is available."""


@dataclass
class ConfigPartner:
    """A partner loaded from config file."""

    name: str
    role: str
    rationale: str
    agency_patterns: list[str] = field(default_factory=list)
    opportunity_type_patterns: list[str] = field(default_factory=list)


def _load_config_partners() -> list[ConfigPartner] | None:
    """Load partners from config file if PARTNER_CONFIG_PATH is set and valid.

    Returns None if env var not set or file not found/invalid.
    """
    config_path = os.environ.get("PARTNER_CONFIG_PATH")
    if not config_path:
        return None

    path = Path(config_path)
    if not path.is_file():
        logger.warning("PARTNER_CONFIG_PATH set but file not found: %s", config_path)
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        partners = []
        for entry in data:
            partners.append(
                ConfigPartner(
                    name=entry["name"],
                    role=entry["role"],
                    rationale=entry["rationale"],
                    agency_patterns=entry.get("agency_patterns", []),
                    opportunity_type_patterns=entry.get("opportunity_type_patterns", []),
                )
            )
        return partners
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse partner config at %s: %s", config_path, exc)
        return None


def _match_config_partners(
    partners: list[ConfigPartner],
    agency: str,
    opportunity_type: str | None = None,
) -> list[ConfigPartner]:
    """Filter config partners by agency and opportunity type (case-insensitive substring)."""
    agency_lower = agency.lower()
    opp_lower = (opportunity_type or "").lower()

    results: list[ConfigPartner] = []
    for partner in partners:
        agency_match = any(p.lower() in agency_lower for p in partner.agency_patterns)
        if not agency_match:
            agency_match = any(agency_lower in p.lower() for p in partner.agency_patterns)
        if not agency_match:
            continue

        if partner.opportunity_type_patterns and opp_lower:
            type_match = any(p.lower() in opp_lower for p in partner.opportunity_type_patterns)
            if not type_match:
                type_match = any(opp_lower in p.lower() for p in partner.opportunity_type_patterns)
            if not type_match:
                continue

        results.append(partner)
    return results


def get_matching_partners(
    agency: str,
    opportunity_type: str | None = None,
    naics_codes: list[str] | None = None,
    timeout: float = 15.0,
) -> list[USAspendingPartner]:
    """Return partners matching agency/opportunity, using USASpending API with config fallback.

    1. Try USASpending API lookup.
    2. If API returns empty or fails, fall back to config file (PARTNER_CONFIG_PATH).
    3. If neither source provides data, raise PartnerSourceError.

    Args:
        agency: Agency name or abbreviation.
        opportunity_type: Optional opportunity type for filtering config partners.
        naics_codes: NAICS codes for USASpending query.
        timeout: HTTP timeout for USASpending API.

    Returns:
        List of USAspendingPartner records.

    Raises:
        PartnerSourceError: If no data source is available.
    """
    # Primary: USASpending API
    api_partners = lookup_partners_by_naics_and_agency(
        agency=agency,
        naics_codes=naics_codes,
        timeout=timeout,
    )
    if api_partners:
        logger.info("Got %d partners from USASpending API for agency=%s", len(api_partners), agency)
        return api_partners

    logger.info("USASpending API returned no results for agency=%s, trying config fallback", agency)

    # Fallback: config file
    config_partners = _load_config_partners()
    if config_partners is not None:
        matched = _match_config_partners(config_partners, agency, opportunity_type)
        if matched:
            logger.info("Got %d partners from config fallback for agency=%s", len(matched), agency)
            return [
                USAspendingPartner(
                    name=p.name,
                    naics_codes=[],
                    agency=agency,
                    award_count=0,
                )
                for p in matched
            ]
        # Config loaded but no matches — still a valid source, just no matches
        logger.info("Config loaded but no matches for agency=%s", agency)
        return []

    # Neither source available
    raise PartnerSourceError(
        f"No partner data source available for agency={agency!r}. "
        "USASpending API returned no results and PARTNER_CONFIG_PATH is not set or invalid."
    )
