"""Teaming suggestion engine — generates partner recommendations.

Produces TeamingPartner records for GO and SHAPE verdicts only.
MONITOR and NO-GO are skipped.

⚠️ CRITICAL: System NEVER initiates outreach automatically.
All suggestions are informational only.

Source: BRD Section 3C, Section 5
"""

from __future__ import annotations

import logging

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult
from models.teaming_partner import TeamingPartner
from teaming.hardcoded_partners import PartnerSourceError, get_matching_partners

logger = logging.getLogger(__name__)

# Verdicts that trigger teaming suggestions
ACTIONABLE_VERDICTS = {"GO", "SHAPE"}


def generate_teaming_suggestions(
    opportunity: GrantOpportunity,
    scoring_result: ScoringResult,
) -> list[TeamingPartner]:
    """Generate teaming partner suggestions for an opportunity.

    Only produces suggestions for GO and SHAPE verdicts.
    MONITOR and NO-GO are skipped with a log message.

    Uses USASpending API as primary source with config file fallback.

    Args:
        opportunity: The grant opportunity.
        scoring_result: The scoring result with verdict.

    Returns:
        List of TeamingPartner suggestions. Empty for non-actionable verdicts.

    Raises:
        PartnerSourceError: If no partner data source is available.
    """
    if scoring_result.verdict not in ACTIONABLE_VERDICTS:
        logger.info(
            "Skipping teaming — verdict is %s for %s",
            scoring_result.verdict,
            opportunity.source_opportunity_id,
        )
        return []

    partners: list[TeamingPartner] = []

    try:
        matched = get_matching_partners(
            agency=opportunity.agency,
            opportunity_type=opportunity.opportunity_type,
            naics_codes=opportunity.naics_codes or None,
        )
        for p in matched:
            source = "usaspending" if p.award_count > 0 else "config"
            partners.append(
                TeamingPartner(
                    opportunity_id=opportunity.source_opportunity_id,
                    partner_name=p.name,
                    partner_role="Potential Teaming Partner",
                    rationale=(
                        f"Past awardee in NAICS {', '.join(p.naics_codes)} with {p.agency}"
                        if p.naics_codes
                        else f"Config-sourced partner for {p.agency}"
                    ),
                    source=source,
                    naics_codes=p.naics_codes,
                    past_agency_work=f"Prior awards from {p.agency}" if p.award_count > 0 else None,
                )
            )
    except PartnerSourceError:
        logger.warning(
            "No partner source available for %s (agency=%s)",
            opportunity.source_opportunity_id,
            opportunity.agency,
        )
        raise

    return partners
