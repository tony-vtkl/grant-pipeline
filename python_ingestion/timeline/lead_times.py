"""Per-type lead time configurations.

Defines milestone offsets (days before deadline) for each opportunity type:
- federal
- state
- private
- sbir_phase_i
- sbir_phase_ii

Source: BRD Section 3C (Temporal Intelligence)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadTimeConfig:
    """Lead-time offsets in days before submission deadline."""

    opportunity_type: str
    go_no_go_days: int
    partner_outreach_days: int
    draft_narrative_days: int
    human_review_days: int
    budget_compliance_days: int
    final_package_days: int


# --- Per-type configurations ---

FEDERAL = LeadTimeConfig(
    opportunity_type="federal",
    go_no_go_days=60,
    partner_outreach_days=50,
    draft_narrative_days=30,
    human_review_days=20,
    budget_compliance_days=10,
    final_package_days=3,
)

STATE = LeadTimeConfig(
    opportunity_type="state",
    go_no_go_days=45,
    partner_outreach_days=35,
    draft_narrative_days=25,
    human_review_days=15,
    budget_compliance_days=7,
    final_package_days=2,
)

PRIVATE = LeadTimeConfig(
    opportunity_type="private",
    go_no_go_days=30,
    partner_outreach_days=21,
    draft_narrative_days=14,
    human_review_days=10,
    budget_compliance_days=5,
    final_package_days=2,
)

SBIR_PHASE_I = LeadTimeConfig(
    opportunity_type="sbir_phase_i",
    go_no_go_days=45,
    partner_outreach_days=35,
    draft_narrative_days=25,
    human_review_days=15,
    budget_compliance_days=7,
    final_package_days=3,
)

SBIR_PHASE_II = LeadTimeConfig(
    opportunity_type="sbir_phase_ii",
    go_no_go_days=75,
    partner_outreach_days=60,
    draft_narrative_days=40,
    human_review_days=25,
    budget_compliance_days=14,
    final_package_days=3,
)

_CONFIGS: dict[str, LeadTimeConfig] = {
    "federal": FEDERAL,
    "state": STATE,
    "private": PRIVATE,
    "sbir_phase_i": SBIR_PHASE_I,
    "sbir_phase_ii": SBIR_PHASE_II,
}


def get_lead_time_config(opportunity_type: str) -> LeadTimeConfig:
    """Return lead-time config for the given opportunity type.

    Falls back to federal if type is unknown.
    """
    return _CONFIGS.get(opportunity_type, FEDERAL)


def list_opportunity_types() -> list[str]:
    """Return all supported opportunity types."""
    return list(_CONFIGS.keys())
