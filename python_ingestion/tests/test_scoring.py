"""Unit tests for weighted scoring engine."""

import pytest
import json
from pathlib import Path
from models.grant_opportunity import GrantOpportunity
from eligibility import assess_eligibility
from scorer import score_opportunity, DEFAULT_WEIGHTS, ScoringWeights


@pytest.fixture
def test_opportunities():
    """Load test opportunities from fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "test_opportunities.json"
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    return data


def test_default_weights_valid():
    """Test that default weights are properly configured."""
    assert DEFAULT_WEIGHTS.mission_fit == 0.25
    assert DEFAULT_WEIGHTS.eligibility == 0.25
    assert DEFAULT_WEIGHTS.technical_alignment == 0.20
    assert DEFAULT_WEIGHTS.financial_viability == 0.15
    assert DEFAULT_WEIGHTS.strategic_value == 0.15
    
    # Weights should sum to 1.0
    total = (
        DEFAULT_WEIGHTS.mission_fit +
        DEFAULT_WEIGHTS.eligibility +
        DEFAULT_WEIGHTS.technical_alignment +
        DEFAULT_WEIGHTS.financial_viability +
        DEFAULT_WEIGHTS.strategic_value
    )
    assert abs(total - 1.0) < 0.001


def test_custom_weights_validation():
    """Test that custom weights are validated."""
    # Valid weights should work
    valid_weights = ScoringWeights(
        mission_fit=0.30,
        eligibility=0.20,
        technical_alignment=0.20,
        financial_viability=0.15,
        strategic_value=0.15
    )
    assert valid_weights is not None
    
    # Invalid weights (don't sum to 1.0) should fail
    with pytest.raises(ValueError):
        ScoringWeights(
            mission_fit=0.50,
            eligibility=0.50,  # Sum = 1.5, should fail
            technical_alignment=0.20,
            financial_viability=0.15,
            strategic_value=0.15
        )


def test_verdict_thresholds_go(test_opportunities):
    """Test GO verdict (score 80-100)."""
    # Test all GO opportunities
    go_cases = [tc for tc in test_opportunities if tc["expected_verdict"] == "GO"]
    
    for test_case in go_cases:
        opp = GrantOpportunity(**test_case["opportunity"])
        eligibility = assess_eligibility(opp)
        result = score_opportunity(opp, eligibility)
        
        assert result.verdict == "GO", f"Failed for {test_case['id']}"
        assert 80 <= result.composite_score <= 100, f"Score {result.composite_score} out of range for {test_case['id']}"


def test_verdict_thresholds_shape(test_opportunities):
    """Test SHAPE verdict (score 60-79)."""
    # Test all SHAPE opportunities
    shape_cases = [tc for tc in test_opportunities if tc["expected_verdict"] == "SHAPE"]
    
    for test_case in shape_cases:
        opp = GrantOpportunity(**test_case["opportunity"])
        eligibility = assess_eligibility(opp)
        result = score_opportunity(opp, eligibility)
        
        assert result.verdict == "SHAPE", f"Failed for {test_case['id']}"
        assert 60 <= result.composite_score < 80, f"Score {result.composite_score} out of range for {test_case['id']}"


def test_verdict_thresholds_monitor(test_opportunities):
    """Test MONITOR verdict (score 40-59)."""
    # Test all MONITOR opportunities
    monitor_cases = [tc for tc in test_opportunities if tc["expected_verdict"] == "MONITOR"]
    
    for test_case in monitor_cases:
        opp = GrantOpportunity(**test_case["opportunity"])
        eligibility = assess_eligibility(opp)
        result = score_opportunity(opp, eligibility)
        
        assert result.verdict == "MONITOR", f"Failed for {test_case['id']}"
        assert 40 <= result.composite_score < 60, f"Score {result.composite_score} out of range for {test_case['id']}"


def test_verdict_thresholds_nogo(test_opportunities):
    """Test NO-GO verdict (score 0-39)."""
    # Test all NO-GO opportunities
    nogo_cases = [tc for tc in test_opportunities if tc["expected_verdict"] == "NO-GO"]
    
    for test_case in nogo_cases:
        opp = GrantOpportunity(**test_case["opportunity"])
        eligibility = assess_eligibility(opp)
        result = score_opportunity(opp, eligibility)
        
        assert result.verdict == "NO-GO", f"Failed for {test_case['id']}"
        assert 0 <= result.composite_score < 40, f"Score {result.composite_score} out of range for {test_case['id']}"


def test_8a_blocker_zero_eligibility_score(test_opportunities):
    """Test that 8(a) blocker results in zero eligibility score."""
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.eligibility.score == 0.0


def test_hubzone_blocker_zero_eligibility_score(test_opportunities):
    """Test that HUBZone blocker results in zero eligibility score."""
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-002")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.eligibility.score == 0.0


def test_mission_fit_ai_opportunities(test_opportunities):
    """Test that AI/ML opportunities score high on mission fit."""
    # Test DOD AI opportunity
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.mission_fit.score >= 70.0


def test_semantic_mapping_applied(test_opportunities):
    """Test that semantic mapping is applied to technical scoring."""
    # Test opportunity with cyberinfrastructure mention
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-004")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    # Should have technical alignment score
    assert result.technical_alignment.score > 0
    # Should have evidence citations
    assert len(result.technical_alignment.evidence_citations) > 0


def test_financial_viability_preferred_range(test_opportunities):
    """Test financial scoring for preferred award range ($500K-$2M)."""
    # GO-001 has award $800K-$1.5M (in preferred range)
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.financial_viability.score >= 80.0


def test_financial_viability_too_large(test_opportunities):
    """Test financial scoring for oversized awards."""
    # NOGO-005 has award >$3M (too large)
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-005")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.financial_viability.score < 50.0


def test_financial_viability_too_small(test_opportunities):
    """Test financial scoring for undersized awards."""
    # MONITOR-001 has award <$200K (small)
    test_case = next(tc for tc in test_opportunities if tc["id"] == "MONITOR-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    # Small awards should score lower on financial viability
    assert result.financial_viability.score < 80.0


def test_strategic_value_multi_year(test_opportunities):
    """Test strategic value boost for multi-year opportunities."""
    # GO-001 mentions IDIQ (multi-year)
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.strategic_value.score >= 60.0


def test_strategic_value_high_value_agency(test_opportunities):
    """Test strategic value boost for high-value agencies (DOD, Navy, etc.)."""
    # GO-005 is Navy opportunity
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-005")
    opp = GrantOpportunity(**test_case["opportunity"])
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.strategic_value.score >= 65.0


def test_dimension_evidence_citations():
    """Test that all dimensions include evidence citations."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-EVIDENCE-001",
        dedup_hash="test123",
        title="AI Workflow System",
        agency="Test Agency",
        description="AI workflows and machine learning for decision support",
        raw_text="Requires expertise in AI workflows, data governance, and agent configuration",
        source_url="https://test.gov",
        naics_codes=["541511"],
        award_amount_min=500000,
        award_amount_max=1000000
    )
    
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert len(result.mission_fit.evidence_citations) > 0
    assert len(result.eligibility.evidence_citations) > 0
    assert len(result.technical_alignment.evidence_citations) > 0
    assert len(result.financial_viability.evidence_citations) > 0
    assert len(result.strategic_value.evidence_citations) > 0


def test_composite_score_calculation():
    """Test that composite score is correctly weighted."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-COMPOSITE-001",
        dedup_hash="test456",
        title="Test Opportunity",
        agency="Test Agency",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    # Manual calculation
    expected_composite = (
        result.mission_fit.score * DEFAULT_WEIGHTS.mission_fit +
        result.eligibility.score * DEFAULT_WEIGHTS.eligibility +
        result.technical_alignment.score * DEFAULT_WEIGHTS.technical_alignment +
        result.financial_viability.score * DEFAULT_WEIGHTS.financial_viability +
        result.strategic_value.score * DEFAULT_WEIGHTS.strategic_value
    )
    
    assert abs(result.composite_score - expected_composite) < 0.1


def test_custom_weights_affect_scoring():
    """Test that custom weights change composite score appropriately."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-WEIGHTS-001",
        dedup_hash="test789",
        title="Test Opportunity",
        agency="Test Agency",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    eligibility = assess_eligibility(opp)
    
    # Score with default weights
    result_default = score_opportunity(opp, eligibility, weights=DEFAULT_WEIGHTS)
    
    # Score with mission-focused weights
    mission_focused = ScoringWeights(
        mission_fit=0.40,
        eligibility=0.20,
        technical_alignment=0.20,
        financial_viability=0.10,
        strategic_value=0.10
    )
    result_mission = score_opportunity(opp, eligibility, weights=mission_focused)
    
    # Results should differ
    assert result_default.composite_score != result_mission.composite_score


def test_baseline_accuracy_90_percent(test_opportunities):
    """Test 90%+ accuracy vs human baseline (±5 point variance)."""
    # This test validates acceptance criterion #7
    
    accurate_scores = 0
    total_scores = 0
    
    for test_case in test_opportunities:
        opp = GrantOpportunity(**test_case["opportunity"])
        eligibility = assess_eligibility(opp)
        result = score_opportunity(opp, eligibility)
        
        expected_min, expected_max = test_case["expected_score_range"]
        actual_score = result.composite_score
        
        # Allow ±5 point variance
        tolerance = 5
        if (expected_min - tolerance) <= actual_score <= (expected_max + tolerance):
            accurate_scores += 1
        
        total_scores += 1
    
    accuracy = (accurate_scores / total_scores) * 100
    
    # Must achieve 90%+ accuracy
    assert accuracy >= 90.0, f"Accuracy {accuracy:.1f}% is below 90% threshold"


def test_scoring_result_model_valid():
    """Test that ScoringResult model is properly populated."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-MODEL-001",
        dedup_hash="test012",
        title="Model Test",
        agency="Test Agency",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    eligibility = assess_eligibility(opp)
    result = score_opportunity(opp, eligibility)
    
    assert result.opportunity_id == "TEST-MODEL-001"
    assert 0 <= result.composite_score <= 100
    assert result.verdict in ["GO", "SHAPE", "MONITOR", "NO-GO"]
    assert result.scoring_weights_version == "1.0"
    assert result.llm_model is not None
    assert result.mission_fit is not None
    assert result.eligibility is not None
    assert result.technical_alignment is not None
    assert result.financial_viability is not None
    assert result.strategic_value is not None


def test_end_to_end_processing(test_opportunities):
    """Test end-to-end processing of REQ-1 opportunity records."""
    # This validates acceptance criterion #6
    
    for test_case in test_opportunities[:5]:  # Test first 5 cases
        opp = GrantOpportunity(**test_case["opportunity"])
        
        # Step 1: Eligibility assessment
        eligibility = assess_eligibility(opp)
        assert eligibility is not None
        
        # Step 2: Scoring
        result = score_opportunity(opp, eligibility)
        assert result is not None
        
        # Step 3: Verify all fields populated
        assert result.opportunity_id == opp.source_opportunity_id
        assert result.composite_score is not None
        assert result.verdict is not None
