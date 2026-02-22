"""Tests for REQ-3 Teaming Intelligence Module."""

import pytest
from datetime import datetime, timezone

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult, DimensionScore
from models.teaming_partner import TeamingPartner
from teaming.engine import generate_teaming_suggestions, ACTIONABLE_VERDICTS
from teaming.hardcoded_partners import get_matching_partners, SEED_PARTNERS
from teaming.usaspending_lookup import USAspendingPartner, lookup_partners_by_naics_and_agency


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


# --- AC1: Partner suggestion engine returns named orgs with role rationale for GO/SHAPE ---

class TestPartnerSuggestionEngine:
    def test_go_verdict_returns_partners(self):
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        assert len(partners) > 0
        for p in partners:
            assert p.partner_name  # named org
            assert p.partner_role  # role
            assert p.rationale  # rationale

    def test_shape_verdict_returns_partners(self):
        opp = _make_opportunity(agency="USDA")
        scoring = _make_scoring("SHAPE")
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        assert len(partners) > 0
        for p in partners:
            assert p.partner_name
            assert p.rationale

    def test_monitor_verdict_returns_empty(self):
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("MONITOR")
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        assert partners == []

    def test_nogo_verdict_returns_empty(self):
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("NO-GO")
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        assert partners == []


# --- AC2: Partner DB seeded with BRD examples ---

class TestPartnerDBSeed:
    REQUIRED_PARTNERS = [
        "University of Hawaiʻi at Mānoa",
        "Chaminade University",
        "Hawaiʻi Pacific University",
        "Hawaiʻi Department of Education",
        "Farm to School Hui",
    ]

    def test_all_brd_partners_present(self):
        seed_names = [p.name for p in SEED_PARTNERS]
        for required in self.REQUIRED_PARTNERS:
            assert required in seed_names, f"Missing BRD partner: {required}"

    def test_nsf_returns_academic_partners(self):
        matches = get_matching_partners(agency="NSF", opportunity_type="grant")
        names = [m.name for m in matches]
        assert "University of Hawaiʻi at Mānoa" in names
        assert "Chaminade University" in names
        assert "Hawaiʻi Pacific University" in names

    def test_usda_returns_community_partners(self):
        matches = get_matching_partners(agency="USDA", opportunity_type="grant")
        names = [m.name for m in matches]
        assert "Hawaiʻi Department of Education" in names
        assert "Farm to School Hui" in names

    def test_unrelated_agency_returns_empty(self):
        matches = get_matching_partners(agency="SEC", opportunity_type="grant")
        assert matches == []

    def test_each_partner_has_role_and_rationale(self):
        for p in SEED_PARTNERS:
            assert p.role, f"{p.name} missing role"
            assert p.rationale, f"{p.name} missing rationale"


# --- AC3: USAspending.gov API integration ---

class TestUSAspendingIntegration:
    def test_partner_model_structure(self):
        """USAspendingPartner has expected fields."""
        p = USAspendingPartner(
            name="Test Corp",
            naics_codes=["541511"],
            agency="NSF",
            award_count=3,
        )
        assert p.name == "Test Corp"
        assert p.naics_codes == ["541511"]
        assert p.agency == "NSF"

    def test_lookup_returns_list(self):
        """lookup function signature returns list (may be empty if API unreachable)."""
        # We call with a short timeout to avoid hanging in CI
        result = lookup_partners_by_naics_and_agency(
            agency="National Science Foundation",
            naics_codes=["541511"],
            limit=2,
            timeout=5.0,
        )
        assert isinstance(result, list)
        # Each item should be USAspendingPartner
        for r in result:
            assert isinstance(r, USAspendingPartner)


# --- AC7: No automated outreach ---

class TestNoAutomatedOutreach:
    def test_teaming_output_is_informational(self):
        """Partners have no 'send', 'email', 'contact' action fields."""
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        for p in partners:
            data = p.model_dump()
            # No action/outreach fields
            assert "action" not in data
            assert "send_email" not in data
            assert "contact" not in data
            assert "outreach" not in data


# --- AC8: Output integrates with existing pipeline ---

class TestPipelineIntegration:
    def test_teaming_partner_links_to_opportunity(self):
        opp = _make_opportunity(
            source_opportunity_id="INTEG-001",
            agency="NSF",
        )
        scoring = _make_scoring("GO")
        scoring.opportunity_id = "INTEG-001"
        partners = generate_teaming_suggestions(opp, scoring, skip_usaspending=True)
        for p in partners:
            assert p.opportunity_id == "INTEG-001"
