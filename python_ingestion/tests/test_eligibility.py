"""Unit tests for eligibility assessment engine."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from models.grant_opportunity import GrantOpportunity
from eligibility import assess_eligibility, VTKL_PROFILE


@pytest.fixture
def test_opportunities():
    """Load test opportunities from fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "test_opportunities.json"
    with open(fixture_path, 'r') as f:
        data = json.load(f)
    return data


def test_vtkl_profile_loaded():
    """Test that VTKL profile is properly configured."""
    assert VTKL_PROFILE is not None
    assert VTKL_PROFILE["entity_type"] == "for-profit_corporation"
    assert "541511" in VTKL_PROFILE["naics_primary"]
    assert VTKL_PROFILE["certifications"]["8(a)"] is False
    assert VTKL_PROFILE["certifications"]["HUBZone"] is False


def test_8a_blocker(test_opportunities):
    """Test that 8(a) certification requirement is hard blocked."""
    # Find 8(a) test case
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.is_eligible is False
    assert result.certification_check.is_met is False
    assert "8(a)" in result.certification_check.details
    assert any("8(a)" in blocker for blocker in result.blockers)


def test_hubzone_blocker(test_opportunities):
    """Test that HUBZone certification requirement is hard blocked."""
    # Find HUBZone test case
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-002")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.is_eligible is False
    assert result.certification_check.is_met is False
    assert "HUBZone" in result.certification_check.details or "hubzone" in result.certification_check.details.lower()
    assert any("HUBZone" in blocker or "hubzone" in blocker.lower() for blocker in result.blockers)


def test_nho_set_aside_favorable(test_opportunities):
    """Test that NHO set-aside is recognized as favorable."""
    # Find NHO test case
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-002")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.is_eligible is True
    assert result.location_check.is_met is True
    assert any("NHO" in asset or "Native Hawaiian" in asset for asset in result.assets)


def test_naics_match_primary(test_opportunities):
    """Test NAICS matching with primary codes."""
    # Find test case with primary NAICS match
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.naics_match_check.is_met is True
    assert "541511" in result.naics_match_check.details or "541512" in result.naics_match_check.details


def test_naics_mismatch(test_opportunities):
    """Test NAICS mismatch blocks eligibility."""
    # Find test case with wrong NAICS
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-004")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.naics_match_check.is_met is False


def test_entity_type_academic_blocked(test_opportunities):
    """Test that academic-only opportunities are blocked."""
    # Find academic test case
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-003")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.is_eligible is False
    assert result.entity_type_check.is_met is False


def test_security_posture_il3_compatible(test_opportunities):
    """Test that IL2-IL4 requirements are compatible."""
    # Find test case with IL3 requirement
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-004")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.security_posture_check.is_met is True


def test_security_posture_ts_blocked(test_opportunities):
    """Test that TS clearance requirement is blocked."""
    # Find TS test case
    test_case = next(tc for tc in test_opportunities if tc["id"] == "NOGO-005")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.security_posture_check.is_met is False


def test_sam_registration_valid():
    """Test SAM registration validity check."""
    from datetime import timezone
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-SAM-001",
        dedup_hash="test123",
        title="Test Opportunity",
        agency="Test Agency",
        response_deadline=datetime(2026, 6, 1, tzinfo=timezone.utc),  # Before SAM expiry (Nov 11, 2026)
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    assert result.sam_active_check.is_met is True


def test_sam_registration_expired():
    """Test SAM registration expired check."""
    from datetime import timezone
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-SAM-002",
        dedup_hash="test456",
        title="Test Opportunity",
        agency="Test Agency",
        response_deadline=datetime(2027, 1, 1, tzinfo=timezone.utc),  # After SAM expiry (Nov 11, 2026)
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    assert result.sam_active_check.is_met is False


def test_participation_path_prime(test_opportunities):
    """Test prime participation path for well-matched opportunities."""
    # Find ideal match opportunity
    test_case = next(tc for tc in test_opportunities if tc["id"] == "GO-001")
    opp = GrantOpportunity(**test_case["opportunity"])
    
    result = assess_eligibility(opp)
    
    assert result.is_eligible is True
    assert result.participation_path in ["prime", "subawardee"]


def test_financial_warning_large_award():
    """Test that oversized awards trigger warning."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-LARGE-001",
        dedup_hash="test789",
        title="Large Award Test",
        agency="Test Agency",
        award_amount_max=10_000_000,  # Exceeds $5M capacity
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    assert len(result.warnings) > 0
    assert any("capacity" in w.lower() for w in result.warnings)


def test_small_business_set_aside_passes():
    """Test that small business set-asides pass certification check."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-SB-001",
        dedup_hash="test012",
        title="Small Business Test",
        agency="Test Agency",
        set_aside_type="Small Business",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    assert result.certification_check.is_met is True


def test_all_constraints_checked():
    """Test that all six constraints are checked."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-ALL-001",
        dedup_hash="test345",
        title="All Constraints Test",
        agency="Test Agency",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    # All six checks should be present
    assert result.entity_type_check is not None
    assert result.location_check is not None
    assert result.sam_active_check is not None
    assert result.naics_match_check is not None
    assert result.security_posture_check is not None
    assert result.certification_check is not None


def test_eligibility_result_model_valid():
    """Test that EligibilityResult model is properly populated."""
    opp = GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="TEST-MODEL-001",
        dedup_hash="test678",
        title="Model Test",
        agency="Test Agency",
        source_url="https://test.gov",
        naics_codes=["541511"]
    )
    
    result = assess_eligibility(opp)
    
    assert result.opportunity_id == "TEST-MODEL-001"
    assert isinstance(result.is_eligible, bool)
    assert isinstance(result.blockers, list)
    assert isinstance(result.assets, list)
    assert isinstance(result.warnings, list)
    assert result.vtkl_profile_version == "1.0"
    assert isinstance(result.evaluated_at, datetime)
