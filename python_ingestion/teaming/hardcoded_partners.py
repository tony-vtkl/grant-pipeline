"""Seed partner database from BRD Section 3C.

Partners are keyed by agency/opportunity-type patterns.
Schema supports expansion via additional entries.

Source: BRD Section 3C (Teaming Intelligence)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SeedPartner:
    """A seeded partner entry."""

    name: str
    role: str
    rationale: str
    agency_patterns: list[str] = field(default_factory=list)
    opportunity_type_patterns: list[str] = field(default_factory=list)


# BRD-specified seed partners
SEED_PARTNERS: list[SeedPartner] = [
    # NSF grants → academic research partners
    SeedPartner(
        name="University of Hawaiʻi at Mānoa",
        role="Research Partner",
        rationale="NSF CSSI pattern — academic research institution with cyberinfrastructure and AI expertise; eligible as prime on NSF grants where VTKL can sub",
        agency_patterns=["NSF", "National Science Foundation"],
        opportunity_type_patterns=["grant", "cooperative agreement"],
    ),
    SeedPartner(
        name="Chaminade University",
        role="Research Partner",
        rationale="Private university with STEM programs; minority-serving institution status enhances NSF/NIH proposals",
        agency_patterns=["NSF", "National Science Foundation", "NIH", "National Institutes of Health"],
        opportunity_type_patterns=["grant", "cooperative agreement"],
    ),
    SeedPartner(
        name="Hawaiʻi Pacific University",
        role="Research Partner",
        rationale="Applied research focus; cybersecurity and data science programs align with VTKL technical domains",
        agency_patterns=["NSF", "National Science Foundation", "DOD", "Department of Defense"],
        opportunity_type_patterns=["grant", "cooperative agreement"],
    ),
    # USDA grants → community partners
    SeedPartner(
        name="Hawaiʻi Department of Education",
        role="Implementation Partner",
        rationale="State education agency; required partner for USDA education and nutrition grants in Hawaiʻi",
        agency_patterns=["USDA", "Department of Agriculture"],
        opportunity_type_patterns=["grant", "cooperative agreement"],
    ),
    SeedPartner(
        name="Farm to School Hui",
        role="Community Partner",
        rationale="Hawaiʻi-based farm-to-school network; established USDA grant recipient with local agriculture expertise",
        agency_patterns=["USDA", "Department of Agriculture"],
        opportunity_type_patterns=["grant", "cooperative agreement"],
    ),
]


def get_matching_partners(agency: str, opportunity_type: str | None = None) -> list[SeedPartner]:
    """Return seed partners matching the given agency and optional opportunity type.

    Matching is case-insensitive substring match against agency_patterns
    and opportunity_type_patterns.
    """
    agency_lower = agency.lower()
    opp_lower = (opportunity_type or "").lower()

    results: list[SeedPartner] = []
    for partner in SEED_PARTNERS:
        agency_match = any(p.lower() in agency_lower for p in partner.agency_patterns)
        if not agency_match:
            # Also check if agency_lower is contained in any pattern
            agency_match = any(agency_lower in p.lower() for p in partner.agency_patterns)

        if not agency_match:
            continue

        # If opportunity_type_patterns specified, check those too
        if partner.opportunity_type_patterns and opp_lower:
            type_match = any(p.lower() in opp_lower for p in partner.opportunity_type_patterns)
            if not type_match:
                type_match = any(opp_lower in p.lower() for p in partner.opportunity_type_patterns)
            if not type_match:
                continue

        results.append(partner)

    return results
