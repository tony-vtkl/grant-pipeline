"""Tests for REQ-3 Temporal Intelligence Module."""

import pytest
from datetime import datetime, date, timezone, timedelta

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult, DimensionScore
from models.timeline_plan import TimelinePlan, Milestone
from timeline.engine import generate_timeline, classify_opportunity_type, ACTIONABLE_VERDICTS
from timeline.lead_times import (
    get_lead_time_config,
    list_opportunity_types,
    FEDERAL,
    STATE,
    PRIVATE,
    SBIR_PHASE_I,
    SBIR_PHASE_II,
)


# --- Fixtures ---

def _dim(score: float) -> DimensionScore:
    return DimensionScore(score=score, evidence_citations=["test"])


def _make_opportunity(**overrides) -> GrantOpportunity:
    defaults = dict(
        source="sam_gov",
        source_opportunity_id="TEST-001",
        dedup_hash="abc123",
        title="AI Research Grant",
        agency="NSF",
        source_url="https://example.com",
        response_deadline=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return GrantOpportunity(**defaults)


def _make_scoring(verdict: str = "GO") -> ScoringResult:
    d = _dim(80.0)
    return ScoringResult(
        opportunity_id="TEST-001",
        mission_fit=d,
        eligibility=d,
        technical_alignment=d,
        financial_viability=d,
        strategic_value=d,
        composite_score=80.0,
        verdict=verdict,
        llm_model="test",
    )


# --- AC4: Backward timeline from submission deadline with 4+ milestones ---

class TestBackwardTimeline:
    def test_go_verdict_generates_timeline(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        assert plan is not None
        assert len(plan.milestones) >= 4

    def test_shape_verdict_generates_timeline(self):
        opp = _make_opportunity()
        scoring = _make_scoring("SHAPE")
        plan = generate_timeline(opp, scoring)
        assert plan is not None
        assert len(plan.milestones) >= 4

    def test_monitor_returns_none(self):
        opp = _make_opportunity()
        scoring = _make_scoring("MONITOR")
        assert generate_timeline(opp, scoring) is None

    def test_nogo_returns_none(self):
        opp = _make_opportunity()
        scoring = _make_scoring("NO-GO")
        assert generate_timeline(opp, scoring) is None

    def test_no_deadline_returns_none(self):
        opp = _make_opportunity(response_deadline=None)
        scoring = _make_scoring("GO")
        assert generate_timeline(opp, scoring) is None

    def test_milestones_ordered_earliest_first(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        dates = [m.due_date for m in plan.milestones]
        assert dates == sorted(dates)

    def test_all_milestones_before_deadline(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        for m in plan.milestones:
            assert m.due_date < plan.submission_deadline

    def test_override_deadline(self):
        opp = _make_opportunity(response_deadline=None)
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring, override_deadline=date(2026, 12, 1))
        assert plan is not None
        assert plan.submission_deadline == date(2026, 12, 1)


# --- AC5: Each milestone labeled human or automated ---

class TestMilestoneLabels:
    def test_every_milestone_has_owner_type(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        for m in plan.milestones:
            assert m.owner_type in ("human", "automated"), f"{m.name} has invalid owner_type: {m.owner_type}"

    def test_has_both_human_and_automated(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        owner_types = {m.owner_type for m in plan.milestones}
        assert "human" in owner_types
        assert "automated" in owner_types


# --- AC6: Per-type lead times ---

class TestPerTypeLeadTimes:
    def test_all_five_types_exist(self):
        types = list_opportunity_types()
        assert "federal" in types
        assert "state" in types
        assert "private" in types
        assert "sbir_phase_i" in types
        assert "sbir_phase_ii" in types

    def test_federal_longer_than_private(self):
        assert FEDERAL.go_no_go_days > PRIVATE.go_no_go_days

    def test_sbir_phase_ii_longest(self):
        assert SBIR_PHASE_II.go_no_go_days >= FEDERAL.go_no_go_days

    def test_different_types_produce_different_timelines(self):
        deadline = date(2026, 8, 15)
        scoring = _make_scoring("GO")

        fed_opp = _make_opportunity(agency="NSF", title="Federal AI Grant")
        sbir_opp = _make_opportunity(
            agency="NSF",
            title="SBIR Phase II AI Grant",
            description="SBIR Phase II solicitation",
        )

        fed_plan = generate_timeline(fed_opp, scoring)
        sbir_plan = generate_timeline(sbir_opp, scoring)

        assert fed_plan.opportunity_type == "federal"
        assert sbir_plan.opportunity_type == "sbir_phase_ii"
        assert fed_plan.total_lead_time_days != sbir_plan.total_lead_time_days

    def test_classify_sbir_phase_i(self):
        opp = _make_opportunity(title="SBIR Phase I: AI Tools")
        assert classify_opportunity_type(opp) == "sbir_phase_i"

    def test_classify_sbir_phase_ii(self):
        opp = _make_opportunity(title="SBIR Phase II: Scaling AI")
        assert classify_opportunity_type(opp) == "sbir_phase_ii"

    def test_classify_state(self):
        opp = _make_opportunity(agency="State of Hawaii Department of Education")
        assert classify_opportunity_type(opp) == "state"

    def test_classify_private(self):
        opp = _make_opportunity(agency="Gates Foundation")
        assert classify_opportunity_type(opp) == "private"

    def test_classify_federal_default(self):
        opp = _make_opportunity(agency="NSF")
        assert classify_opportunity_type(opp) == "federal"

    def test_unknown_type_falls_back_to_federal(self):
        config = get_lead_time_config("unknown_type")
        assert config == FEDERAL


# --- AC7: No automated outreach (timeline) ---

class TestTimelineInformationalOnly:
    def test_milestone_has_no_action_fields(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        for m in plan.milestones:
            data = m.model_dump()
            assert "send" not in data
            assert "email" not in data
            assert "execute" not in data


# --- AC8: Integration with pipeline ---

class TestTimelinePipelineIntegration:
    def test_timeline_links_to_opportunity(self):
        opp = _make_opportunity(source_opportunity_id="INTEG-002")
        scoring = _make_scoring("GO")
        scoring.opportunity_id = "INTEG-002"
        plan = generate_timeline(opp, scoring)
        assert plan.opportunity_id == "INTEG-002"

    def test_timeline_plan_serializable(self):
        opp = _make_opportunity()
        scoring = _make_scoring("GO")
        plan = generate_timeline(opp, scoring)
        data = plan.model_dump()
        assert "milestones" in data
        assert "submission_deadline" in data
        assert "opportunity_type" in data
