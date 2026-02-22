"""Backward timeline calculator.

Calculates preparation milestones working backward from submission deadline
using per-opportunity-type lead times.

Source: BRD Section 3C (Temporal Awareness), Section 5 (Strategic Roadmap)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from timeline.lead_times import LeadTimeConfig, get_lead_time_config

logger = logging.getLogger(__name__)


@dataclass
class TimelineMilestone:
    """A single milestone in the preparation timeline.

    Attributes:
        name: Milestone name.
        date: Calculated date for this milestone.
        owner: 'human' or 'automated'.
        days_before_deadline: How many days before submission deadline.
        is_past_due: True if the milestone date is already in the past.
    """

    name: str
    date: datetime
    owner: str
    days_before_deadline: int
    is_past_due: bool = False


@dataclass
class TimelineRoadmap:
    """Complete timeline roadmap for an opportunity.

    Attributes:
        opportunity_id: Reference to the grant opportunity.
        opportunity_type: Type used for lead-time lookup.
        submission_deadline: The deadline date.
        milestones: Ordered list of milestones (earliest first).
        total_lead_days: Total preparation window in days.
        days_remaining: Days from now to submission deadline.
        feasibility: 'feasible', 'tight', or 'infeasible'.
    """

    opportunity_id: str
    opportunity_type: str
    submission_deadline: datetime
    milestones: list[TimelineMilestone]
    total_lead_days: int
    days_remaining: int
    feasibility: str


def calculate_timeline(
    opportunity_id: str,
    submission_deadline: datetime,
    opportunity_type: str = "federal",
    reference_date: Optional[datetime] = None,
) -> TimelineRoadmap:
    """Calculate backward timeline from submission deadline.

    Args:
        opportunity_id: The opportunity identifier.
        submission_deadline: Deadline for submission.
        opportunity_type: One of: federal, sbir_phase_i, sbir_phase_ii, state, private.
        reference_date: "Now" for calculating past-due. Defaults to utcnow().

    Returns:
        TimelineRoadmap with milestones ordered earliest-first.
    """
    if reference_date is None:
        reference_date = datetime.utcnow()

    config: LeadTimeConfig = get_lead_time_config(opportunity_type)

    milestones: list[TimelineMilestone] = []
    for offset in config.milestones:
        milestone_date = submission_deadline - timedelta(days=offset.days_before_deadline)
        milestones.append(
            TimelineMilestone(
                name=offset.name,
                date=milestone_date,
                owner=offset.owner,
                days_before_deadline=offset.days_before_deadline,
                is_past_due=milestone_date < reference_date,
            )
        )

    # Sort earliest first
    milestones.sort(key=lambda m: m.date)

    days_remaining = (submission_deadline - reference_date).days

    # Feasibility assessment
    if days_remaining >= config.total_lead_days:
        feasibility = "feasible"
    elif days_remaining >= config.total_lead_days * 0.5:
        feasibility = "tight"
    else:
        feasibility = "infeasible"

    return TimelineRoadmap(
        opportunity_id=opportunity_id,
        opportunity_type=opportunity_type,
        submission_deadline=submission_deadline,
        milestones=milestones,
        total_lead_days=config.total_lead_days,
        days_remaining=days_remaining,
        feasibility=feasibility,
    )
