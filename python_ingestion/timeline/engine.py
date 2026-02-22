"""Backward timeline planner — generates submission milestones from deadline.

Produces TimelinePlan for GO and SHAPE verdicts only.
All milestones are labeled as 'human' or 'automated'.

⚠️ INFORMATIONAL ONLY — no automated outreach or actions.

Source: BRD Section 3C, Section 5
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult
from models.timeline_plan import Milestone, TimelinePlan
from timeline.lead_times import get_lead_time_config, LeadTimeConfig

logger = logging.getLogger(__name__)

ACTIONABLE_VERDICTS = {"GO", "SHAPE"}


def classify_opportunity_type(opportunity: GrantOpportunity) -> str:
    """Classify opportunity into a lead-time category.

    Categories: federal, state, private, sbir_phase_i, sbir_phase_ii
    """
    title_lower = (opportunity.title or "").lower()
    desc_lower = (opportunity.description or "").lower()
    agency_lower = (opportunity.agency or "").lower()
    opp_type_lower = (opportunity.opportunity_type or "").lower()

    # SBIR detection
    if "sbir" in title_lower or "sbir" in desc_lower:
        if "phase ii" in title_lower or "phase ii" in desc_lower or "phase 2" in title_lower:
            return "sbir_phase_ii"
        return "sbir_phase_i"

    # State-level detection
    state_indicators = [
        "state of", "department of education", "state agency",
        "governor", "state grant", "state funding",
    ]
    if any(ind in agency_lower or ind in desc_lower for ind in state_indicators):
        return "state"

    # Private/foundation detection
    private_indicators = [
        "foundation", "private", "corporate", "philanthrop",
        "endowment", "trust fund",
    ]
    if any(ind in agency_lower or ind in desc_lower for ind in private_indicators):
        return "private"

    # Default: federal
    return "federal"


def generate_timeline(
    opportunity: GrantOpportunity,
    scoring_result: ScoringResult,
    override_deadline: Optional[date] = None,
) -> Optional[TimelinePlan]:
    """Generate a backward-planned submission timeline.

    Only produces timelines for GO and SHAPE verdicts.
    Returns None if verdict is not actionable or no deadline is available.

    Args:
        opportunity: The grant opportunity.
        scoring_result: The scoring result with verdict.
        override_deadline: Override the deadline (for testing).

    Returns:
        TimelinePlan or None.
    """
    if scoring_result.verdict not in ACTIONABLE_VERDICTS:
        logger.info(
            "Skipping timeline — verdict is %s for %s",
            scoring_result.verdict,
            opportunity.source_opportunity_id,
        )
        return None

    # Determine deadline
    deadline: Optional[date] = override_deadline
    if deadline is None and opportunity.response_deadline:
        deadline = opportunity.response_deadline.date()

    if deadline is None:
        logger.warning(
            "No deadline available for %s — cannot generate timeline",
            opportunity.source_opportunity_id,
        )
        return None

    opp_type = classify_opportunity_type(opportunity)
    config = get_lead_time_config(opp_type)

    milestones = _build_milestones(deadline, config)

    total_lead = milestones[0].days_before_deadline if milestones else 0

    return TimelinePlan(
        opportunity_id=opportunity.source_opportunity_id,
        submission_deadline=deadline,
        opportunity_type=opp_type,
        milestones=milestones,
        total_lead_time_days=total_lead,
    )


def _build_milestones(deadline: date, config: LeadTimeConfig) -> list[Milestone]:
    """Build milestone list from lead-time config, ordered earliest first."""

    raw: list[tuple[int, str, str, str]] = [
        # (days_before, name, owner_type, description)
        (
            config.go_no_go_days,
            "Internal Go/No-Go Decision",
            "human",
            "Team reviews verdict card and commits resources",
        ),
        (
            config.partner_outreach_days,
            "Partner Outreach & LOI Collection",
            "human",
            "Contact teaming partners, collect letters of intent/support",
        ),
        (
            config.draft_narrative_days,
            "Draft Narrative Generation",
            "automated",
            "AI generates first draft from opportunity requirements and VTKL profile",
        ),
        (
            config.human_review_days,
            "Human Review & Revision",
            "human",
            "Subject matter expert reviews, revises narrative, adds domain expertise",
        ),
        (
            config.budget_compliance_days,
            "Budget & Compliance Check",
            "human",
            "Financial review, compliance verification, cost documentation",
        ),
        (
            config.final_package_days,
            "Final Submission Package",
            "automated",
            "Automated formatting, attachment assembly, portal upload preparation",
        ),
    ]

    # Sort by days_before descending (earliest milestone first)
    raw.sort(key=lambda x: x[0], reverse=True)

    milestones: list[Milestone] = []
    for days_before, name, owner, desc in raw:
        due = deadline - timedelta(days=days_before)
        milestones.append(
            Milestone(
                name=name,
                due_date=due,
                days_before_deadline=days_before,
                owner_type=owner,
                description=desc,
            )
        )

    return milestones
