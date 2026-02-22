"""TimelinePlan - Output model for REQ-3 (Temporal Intelligence Module).

Backward-planned timeline from submission deadline with labeled milestones.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class Milestone(BaseModel):
    """A single milestone in the submission timeline."""

    name: str = Field(..., description="Milestone name")
    due_date: date = Field(..., description="Target completion date")
    days_before_deadline: int = Field(..., description="Days before submission deadline")
    owner_type: str = Field(..., description="'human' or 'automated'")
    description: str = Field(default="", description="What needs to happen")


class TimelinePlan(BaseModel):
    """Backward-planned submission timeline.

    Generated for GO and SHAPE verdicts only.
    """

    opportunity_id: str = Field(..., description="Links to GrantOpportunity.source_opportunity_id")
    submission_deadline: date = Field(..., description="Final submission deadline")
    opportunity_type: str = Field(
        ..., description="federal, state, private, sbir_phase_i, sbir_phase_ii"
    )
    milestones: list[Milestone] = Field(..., description="Ordered milestones (earliest first)")
    total_lead_time_days: int = Field(..., description="Total days from first milestone to deadline")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "opportunity_id": "NSF-25-001",
                "submission_deadline": "2026-06-15",
                "opportunity_type": "federal",
                "milestones": [
                    {
                        "name": "Internal Go/No-Go Decision",
                        "due_date": "2026-04-16",
                        "days_before_deadline": 60,
                        "owner_type": "human",
                        "description": "Team reviews verdict card and commits resources",
                    },
                    {
                        "name": "Partner Outreach & LOI Collection",
                        "due_date": "2026-04-26",
                        "days_before_deadline": 50,
                        "owner_type": "human",
                        "description": "Contact teaming partners, collect letters of intent",
                    },
                    {
                        "name": "Draft Narrative Generation",
                        "due_date": "2026-05-16",
                        "days_before_deadline": 30,
                        "owner_type": "automated",
                        "description": "AI generates first draft from opportunity requirements",
                    },
                    {
                        "name": "Human Review & Revision",
                        "due_date": "2026-05-26",
                        "days_before_deadline": 20,
                        "owner_type": "human",
                        "description": "Subject matter expert reviews and revises narrative",
                    },
                    {
                        "name": "Budget & Compliance Check",
                        "due_date": "2026-06-05",
                        "days_before_deadline": 10,
                        "owner_type": "human",
                        "description": "Financial review, compliance verification",
                    },
                    {
                        "name": "Final Submission Package",
                        "due_date": "2026-06-12",
                        "days_before_deadline": 3,
                        "owner_type": "automated",
                        "description": "Automated formatting, attachment assembly, portal upload prep",
                    },
                ],
                "total_lead_time_days": 60,
            }
        }
