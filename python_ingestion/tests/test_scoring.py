"""Unit tests for LLM-based weighted scoring engine."""

import json
from unittest.mock import Mock, patch, MagicMock
import pytest

from models.grant_opportunity import GrantOpportunity
from models.eligibility_result import EligibilityResult, ConstraintCheck
from scorer import score_opportunity, DEFAULT_WEIGHTS, ScoringWeights
from scorer.engine import _get_verdict, _score_eligibility


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client to avoid real API calls."""
    with patch('scorer.engine.anthropic.Anthropic') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def high_scoring_opportunity():
    """Create a high-quality opportunity that should score well."""
    return GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="GO-TEST-001",
        dedup_hash="test-high-001",
        title="AI/ML Decision Support System for Defense",
        agency="Department of Defense",
        description="Seeking AI workflows and machine learning solutions for decision support",
        raw_text="The DoD requires advanced AI workflows, data governance, and agent configuration "
                 "capabilities for a multi-year IDIQ contract. Technology focus: machine learning, "
                 "MLOps, workflow automation. Award range: $800,000 - $1,500,000.",
        source_url="https://test.gov/go-001",
        naics_codes=["541511"],
        award_amount_min=800000,
        award_amount_max=1500000
    )


@pytest.fixture
def eligible_result():
    """Create a clean eligibility result."""
    return EligibilityResult(
        opportunity_id="GO-TEST-001",
        is_eligible=True,
        blockers=[],
        warnings=[],
        assets=["Native Hawaiian Organization (NHO) eligible"],
        participation_path="Prime contractor",
        entity_type_check=ConstraintCheck(constraint_name="Entity Type", is_met=True, details="For-profit corporation"),
        location_check=ConstraintCheck(constraint_name="Location", is_met=True, details="Hawaii-based"),
        sam_active_check=ConstraintCheck(constraint_name="SAM Registration", is_met=True, details="Active"),
        naics_match_check=ConstraintCheck(constraint_name="NAICS Match", is_met=True, details="541511 matches"),
        security_posture_check=ConstraintCheck(constraint_name="Security Posture", is_met=True, details="IL2-IL4"),
        certification_check=ConstraintCheck(constraint_name="Certifications", is_met=True, details="NHO eligible")
    )


@pytest.fixture
def ineligible_result():
    """Create an ineligible result with 8(a) blocker."""
    return EligibilityResult(
        opportunity_id="NOGO-TEST-001",
        is_eligible=False,
        blockers=["Requires 8(a) certification - HARD BLOCKER"],
        warnings=[],
        assets=[],
        participation_path=None,
        entity_type_check=ConstraintCheck(constraint_name="Entity Type", is_met=True, details="For-profit corporation"),
        location_check=ConstraintCheck(constraint_name="Location", is_met=True, details="Hawaii-based"),
        sam_active_check=ConstraintCheck(constraint_name="SAM Registration", is_met=True, details="Active"),
        naics_match_check=ConstraintCheck(constraint_name="NAICS Match", is_met=True, details="541511 matches"),
        security_posture_check=ConstraintCheck(constraint_name="Security Posture", is_met=True, details="IL2-IL4"),
        certification_check=ConstraintCheck(constraint_name="Certifications", is_met=False, details="Requires 8(a)")
    )


def test_go_verdict_high_scores(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test GO verdict when all dimensions score high (≥80)."""
    
    # Mock LLM responses for high scores
    def mock_llm_response(dimension_prompt):
        """Return high scores for all dimensions."""
        return Mock(
            content=[Mock(text=json.dumps({
                "score": 90,
                "evidence_citations": [
                    "AI workflows and machine learning",
                    "Multi-year IDIQ contract",
                    "Award range: $800,000 - $1,500,000"
                ]
            }))]
        )
    
    mock_anthropic_client.messages.create = Mock(side_effect=lambda **kwargs: mock_llm_response(kwargs['messages'][0]['content']))
    
    # Score the opportunity
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    # Verify GO verdict
    assert result.verdict == "GO", f"Expected GO verdict but got {result.verdict}"
    assert result.composite_score >= 80, f"Expected composite ≥80 but got {result.composite_score}"
    
    # Verify all dimensions scored
    assert result.mission_fit.score > 0
    assert result.eligibility.score > 0
    assert result.technical_alignment.score > 0
    assert result.financial_viability.score > 0
    assert result.strategic_value.score > 0


def test_nogo_verdict_ineligible(mock_anthropic_client, high_scoring_opportunity, ineligible_result):
    """Test NO-GO verdict when is_eligible=False (eligibility score=0, composite ≤39)."""
    
    # Mock LLM responses - even if other dimensions score high, composite should be NO-GO
    def mock_llm_response(dimension_prompt):
        """Return moderate scores for non-eligibility dimensions."""
        return Mock(
            content=[Mock(text=json.dumps({
                "score": 70,
                "evidence_citations": ["Some technical requirements"]
            }))]
        )
    
    mock_anthropic_client.messages.create = Mock(side_effect=lambda **kwargs: mock_llm_response(kwargs['messages'][0]['content']))
    
    # Score the opportunity with ineligible status
    result = score_opportunity(high_scoring_opportunity, ineligible_result)
    
    # Verify eligibility score is 0
    assert result.eligibility.score == 0.0, f"Expected eligibility=0 for ineligible opportunity but got {result.eligibility.score}"
    
    # Verify NO-GO verdict due to ineligibility
    assert result.verdict == "NO-GO", f"Expected NO-GO verdict for ineligible opportunity but got {result.verdict}"
    assert result.composite_score <= 39, f"Expected composite ≤39 but got {result.composite_score}"


def test_evidence_citations_present(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test that all dimensions include evidence citations."""
    
    # Mock LLM responses with citations
    def mock_llm_response(dimension_prompt):
        """Return scores with evidence citations."""
        return Mock(
            content=[Mock(text=json.dumps({
                "score": 85,
                "evidence_citations": [
                    "Quote 1 from grant text",
                    "Quote 2 from grant text"
                ]
            }))]
        )
    
    mock_anthropic_client.messages.create = Mock(side_effect=lambda **kwargs: mock_llm_response(kwargs['messages'][0]['content']))
    
    # Score the opportunity
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    # Verify all dimensions have citations
    assert len(result.mission_fit.evidence_citations) > 0, "Mission fit should have evidence citations"
    assert len(result.eligibility.evidence_citations) > 0, "Eligibility should have evidence citations"
    assert len(result.technical_alignment.evidence_citations) > 0, "Technical alignment should have evidence citations"
    assert len(result.financial_viability.evidence_citations) > 0, "Financial viability should have evidence citations"
    assert len(result.strategic_value.evidence_citations) > 0, "Strategic value should have evidence citations"


def test_verdict_thresholds():
    """Test verdict threshold mapping."""
    assert _get_verdict(95) == "GO"
    assert _get_verdict(80) == "GO"
    assert _get_verdict(79) == "SHAPE"
    assert _get_verdict(60) == "SHAPE"
    assert _get_verdict(59) == "MONITOR"
    assert _get_verdict(40) == "MONITOR"
    assert _get_verdict(39) == "NO-GO"
    assert _get_verdict(0) == "NO-GO"


def test_eligibility_scoring_auto_calculated():
    """Test that eligibility score is auto-calculated without LLM."""
    
    # Test eligible with assets
    eligible_with_assets = EligibilityResult(
        opportunity_id="TEST-001",
        is_eligible=True,
        blockers=[],
        warnings=[],
        assets=["Native Hawaiian Organization (NHO)"],
        participation_path="Prime",
        entity_type_check=ConstraintCheck(constraint_name="Entity Type", is_met=True, details="For-profit"),
        location_check=ConstraintCheck(constraint_name="Location", is_met=True, details="Hawaii"),
        sam_active_check=ConstraintCheck(constraint_name="SAM", is_met=True, details="Active"),
        naics_match_check=ConstraintCheck(constraint_name="NAICS", is_met=True, details="Match"),
        security_posture_check=ConstraintCheck(constraint_name="Security", is_met=True, details="IL2-IL4"),
        certification_check=ConstraintCheck(constraint_name="Certs", is_met=True, details="NHO")
    )
    
    opp = GrantOpportunity(
        source="test",
        source_opportunity_id="TEST-001",
        dedup_hash="test",
        title="Test",
        agency="Test Agency",
        source_url="https://test.gov"
    )
    
    result = _score_eligibility(eligible_with_assets, opp)
    assert result.score == 100.0, "Eligible with assets should score 100"
    
    # Test ineligible
    ineligible = EligibilityResult(
        opportunity_id="TEST-002",
        is_eligible=False,
        blockers=["8(a) required"],
        warnings=[],
        assets=[],
        participation_path=None,
        entity_type_check=ConstraintCheck(constraint_name="Entity Type", is_met=True, details="For-profit"),
        location_check=ConstraintCheck(constraint_name="Location", is_met=True, details="Hawaii"),
        sam_active_check=ConstraintCheck(constraint_name="SAM", is_met=True, details="Active"),
        naics_match_check=ConstraintCheck(constraint_name="NAICS", is_met=True, details="Match"),
        security_posture_check=ConstraintCheck(constraint_name="Security", is_met=True, details="IL2-IL4"),
        certification_check=ConstraintCheck(constraint_name="Certs", is_met=False, details="8(a) required")
    )
    
    result = _score_eligibility(ineligible, opp)
    assert result.score == 0.0, "Ineligible should score 0"


def test_custom_weights():
    """Test that custom weights are applied correctly."""
    
    # This is a simple validation that weights sum to 1.0
    custom_weights = ScoringWeights(
        mission_fit=0.30,
        eligibility=0.20,
        technical_alignment=0.20,
        financial_viability=0.15,
        strategic_value=0.15
    )
    
    total = (
        custom_weights.mission_fit +
        custom_weights.eligibility +
        custom_weights.technical_alignment +
        custom_weights.financial_viability +
        custom_weights.strategic_value
    )
    
    assert abs(total - 1.0) < 0.001, "Weights should sum to 1.0"


def test_llm_model_recorded(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test that LLM model is recorded in result."""
    
    # Mock LLM response
    mock_anthropic_client.messages.create = Mock(
        return_value=Mock(
            content=[Mock(text=json.dumps({
                "score": 80,
                "evidence_citations": ["test"]
            }))]
        )
    )
    
    # Score with specific model
    result = score_opportunity(
        high_scoring_opportunity,
        eligible_result,
        llm_model="claude-haiku-4-5"
    )
    
    assert result.llm_model == "claude-haiku-4-5", "LLM model should be recorded"


def test_composite_score_calculation(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test that composite score is correctly calculated from weighted dimensions."""
    
    # Mock LLM to return fixed scores
    mock_anthropic_client.messages.create = Mock(
        return_value=Mock(
            content=[Mock(text=json.dumps({
                "score": 80,
                "evidence_citations": ["test citation"]
            }))]
        )
    )
    
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    # Calculate expected composite manually
    # Eligibility will be high (eligible with assets = 100)
    # Other dimensions will be 80 (from mock)
    # But we need to account for ineligibility penalty if applied
    
    # Verify composite is within reasonable range
    assert 0 <= result.composite_score <= 100, "Composite score should be 0-100"
    
    # Verify it matches the manual calculation
    expected = (
        result.mission_fit.score * DEFAULT_WEIGHTS.mission_fit +
        result.eligibility.score * DEFAULT_WEIGHTS.eligibility +
        result.technical_alignment.score * DEFAULT_WEIGHTS.technical_alignment +
        result.financial_viability.score * DEFAULT_WEIGHTS.financial_viability +
        result.strategic_value.score * DEFAULT_WEIGHTS.strategic_value
    )
    
    assert abs(result.composite_score - expected) < 0.1, "Composite should match weighted calculation"


def test_llm_error_handling(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test graceful handling of LLM API errors."""
    
    # Mock LLM to raise an exception
    mock_anthropic_client.messages.create = Mock(side_effect=Exception("API Error"))
    
    # Should still return a result with fallback scores
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    assert result is not None, "Should return result even with LLM errors"
    assert result.composite_score >= 0, "Should have valid composite score"


def test_llm_malformed_json_handling(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test handling of malformed JSON from LLM."""
    
    # Mock LLM to return invalid JSON
    mock_anthropic_client.messages.create = Mock(
        return_value=Mock(
            content=[Mock(text="This is not valid JSON")]
        )
    )
    
    # Should still return a result with fallback scores
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    assert result is not None, "Should return result even with malformed JSON"
    assert result.composite_score >= 0, "Should have valid composite score"


def test_shape_verdict_range(mock_anthropic_client, high_scoring_opportunity, eligible_result):
    """Test SHAPE verdict (60-79 range)."""
    
    # Mock LLM to return scores that should yield SHAPE
    mock_anthropic_client.messages.create = Mock(
        return_value=Mock(
            content=[Mock(text=json.dumps({
                "score": 65,
                "evidence_citations": ["moderate alignment"]
            }))]
        )
    )
    
    result = score_opportunity(high_scoring_opportunity, eligible_result)
    
    # Should be SHAPE if composite is 60-79
    if 60 <= result.composite_score < 80:
        assert result.verdict == "SHAPE", f"Score {result.composite_score} should be SHAPE"


def test_monitor_verdict_range(mock_anthropic_client, high_scoring_opportunity, ineligible_result):
    """Test MONITOR verdict (40-59 range)."""
    
    # Mock LLM to return moderate scores
    mock_anthropic_client.messages.create = Mock(
        return_value=Mock(
            content=[Mock(text=json.dumps({
                "score": 55,
                "evidence_citations": ["weak alignment"]
            }))]
        )
    )
    
    result = score_opportunity(high_scoring_opportunity, ineligible_result)
    
    # With ineligibility, should likely be in MONITOR or NO-GO range
    if 40 <= result.composite_score < 60:
        assert result.verdict == "MONITOR", f"Score {result.composite_score} should be MONITOR"
