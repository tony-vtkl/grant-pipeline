"""Teaming suggestion engine — generates partner recommendations.

Produces TeamingPartner records for GO and SHAPE verdicts only.
MONITOR and NO-GO are skipped.

⚠️ CRITICAL: System NEVER initiates outreach automatically.
All suggestions are informational only.

Source: BRD Section 3C, Section 5
Refactored: VTK-94 (REQ-2) — removed hardcoded partners, USASpending primary + config fallback.
"""

from __future__ import annotations

import logging

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult
from models.teaming_partner import TeamingPartner
from teaming.partner_config import get_matching_config_partners
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

    Resolution order:
      1. USASpending API (primary) — live lookup of past awardees
      2. Config file fallback (PARTNER_CONFIG_PATH) — when API unavailable
      3. Empty list — when neither source available

    Only produces suggestions for GO and SHAPE verdicts.

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

    # 1. USAspending.gov — primary source
    usaspending_succeeded = False
    if not skip_usaspending:
        try:
            usa_partners = lookup_partners_by_naics_and_agency(
                agency=opportunity.agency,
                naics_codes=opportunity.naics_codes or None,
            )
            if usa_partners:
                usaspending_succeeded = True
                for usa in usa_partners:
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
            logger.warning(
                "USAspending lookup failed for %s: %s",
                opportunity.source_opportunity_id,
                exc,
            )

    # 2. Config file fallback — only when USASpending didn't produce results
    if not usaspending_succeeded:
        config_matches = get_matching_config_partners(
            agency=opportunity.agency,
            opportunity_type=opportunity.opportunity_type,
        )
        for cp in config_matches:
            partners.append(
                TeamingPartner(
                    opportunity_id=opportunity.source_opportunity_id,
                    partner_name=cp.name,
                    partner_role=cp.role,
                    rationale=cp.rationale,
                    source="config",
                )
            )

    return partners
