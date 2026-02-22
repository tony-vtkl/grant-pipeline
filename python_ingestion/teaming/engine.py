"""Teaming suggestion engine — generates partner recommendations.

Produces TeamingPartner records for GO and SHAPE verdicts only.
MONITOR and NO-GO are skipped.

⚠️ CRITICAL: System NEVER initiates outreach automatically.
All suggestions are informational only.

Source: BRD Section 3C, Section 5
"""

from __future__ import annotations

import logging
from typing import Optional

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult
from models.teaming_partner import TeamingPartner
from teaming.hardcoded_partners import get_matching_partners
from teaming.usaspending_lookup import lookup_partners_by_naics_and_agency

logger = logging.getLogger(__name__)

# Verdicts that trigger teaming suggestions
ACTIONABLE_VERDICTS = {"GO", "SHAPE"}


def generate_teaming_suggestions(
    opportunity: GrantOpportunity,
    scoring_result: ScoringResult,
    skip_usaspending: bool = False,
) -> list[TeamingPartner]:
    """Generate teaming partner suggestions for an opportunity.

    Only produces suggestions for GO and SHAPE verdicts.
    MONITOR and NO-GO are skipped with a log message.

    Args:
        opportunity: The grant opportunity.
        scoring_result: The scoring result with verdict.
        skip_usaspending: If True, skip live API call (for testing).

    Returns:
        List of TeamingPartner suggestions. Empty for non-actionable verdicts.
    """
    if scoring_result.verdict not in ACTIONABLE_VERDICTS:
        logger.info(
            "Skipping teaming — verdict is %s for %s",
            scoring_result.verdict,
            opportunity.source_opportunity_id,
        )
        return []

    partners: list[TeamingPartner] = []

    # 1. Hardcoded partner lookup (BRD seed data)
    seed_matches = get_matching_partners(
        agency=opportunity.agency,
        opportunity_type=opportunity.opportunity_type,
    )
    for seed in seed_matches:
        partners.append(
            TeamingPartner(
                opportunity_id=opportunity.source_opportunity_id,
                partner_name=seed.name,
                partner_role=seed.role,
                rationale=seed.rationale,
                source="hardcoded",
            )
        )

    # 2. USAspending.gov enrichment
    if not skip_usaspending:
        try:
            usa_partners = lookup_partners_by_naics_and_agency(
                agency=opportunity.agency,
                naics_codes=opportunity.naics_codes or None,
            )
            for usa in usa_partners:
                # Don't duplicate names already from seed data
                if any(p.partner_name.upper() == usa.name.upper() for p in partners):
                    continue
                partners.append(
                    TeamingPartner(
                        opportunity_id=opportunity.source_opportunity_id,
                        partner_name=usa.name,
                        partner_role="Potential Teaming Partner",
                        rationale=f"Past awardee in NAICS {', '.join(usa.naics_codes)} with {usa.agency}",
                        source="usaspending",
                        naics_codes=usa.naics_codes,
                        past_agency_work=f"Prior awards from {usa.agency}",
                    )
                )
        except Exception as exc:
            logger.warning("USAspending lookup failed for %s: %s", opportunity.source_opportunity_id, exc)

    return partners
