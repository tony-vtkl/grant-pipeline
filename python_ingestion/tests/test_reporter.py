"""Tests for VerdictReportGenerator."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from reporter import VerdictReportGenerator
from models.verdict_report import VerdictReport
from models.scoring_result import ScoringResult, DimensionScore
from models.eligibility_result import EligibilityResult, ConstraintCheck
from models.teaming_partner import TeamingPartner


@pytest.fixture
def mock_supabase_client():
    """Create mock SupabaseClient."""
    client = Mock()
    client._client = Mock()
    return client


@pytest.fixture
def go_scoring_result():
    """Sample GO verdict scoring result."""
    return {
        "opportunity_id": "TEST-GO-001",
        "mission_fit": {
            "score": 90.0,
            "evidence_citations": ["AI solutions for healthcare data analysis"]
        },
        "eligibility": {
            "score": 85.0,
            "evidence_citations": ["Small business eligible"]
        },
        "technical_alignment": {
            "score": 88.0,
            "evidence_citations": ["machine learning, data governance, automation"]
        },
        "financial_viability": {
            "score": 82.0,
            "evidence_citations": ["Award range: $1M-$2.5M"]
        },
        "strategic_value": {
            "score": 80.0,
            "evidence_citations": ["federal healthcare sector alignment"]
        },
        "composite_score": 85.0,
        "verdict": "GO",
        "scored_at": datetime.utcnow().isoformat(),
        "scoring_weights_version": "1.0",
        "llm_model": "claude-haiku-4-5"
    }


@pytest.fixture
def no_go_scoring_result():
    """Sample NO-GO verdict scoring result."""
    return {
        "opportunity_id": "TEST-NOGO-001",
        "mission_fit": {
            "score": 90.0,
            "evidence_citations": ["AI solutions for defense"]
        },
        "eligibility": {
            "score": 0.0,
            "evidence_citations": ["Requires 8(a) certification"]
        },
        "technical_alignment": {
            "score": 85.0,
            "evidence_citations": ["AI/ML capabilities"]
        },
        "financial_viability": {
            "score": 80.0,
            "evidence_citations": ["$500K award"]
        },
        "strategic_value": {
            "score": 75.0,
            "evidence_citations": ["federal sector"]
        },
        "composite_score": 39.0,
        "verdict": "NO-GO",
        "scored_at": datetime.utcnow().isoformat(),
        "scoring_weights_version": "1.0",
        "llm_model": "claude-haiku-4-5"
    }


@pytest.fixture
def eligible_result():
    """Sample eligible eligibility result."""
    return {
        "opportunity_id": "TEST-GO-001",
        "is_eligible": True,
        "participation_path": "prime",
        "entity_type_check": {
            "constraint_name": "Entity Type",
            "is_met": True,
            "details": "For-profit corporation"
        },
        "location_check": {
            "constraint_name": "Location",
            "is_met": True,
            "details": "Hawaii-based"
        },
        "sam_active_check": {
            "constraint_name": "SAM Registration",
            "is_met": True,
            "details": "Active"
        },
        "naics_match_check": {
            "constraint_name": "NAICS Match",
            "is_met": True,
            "details": "541511 matches"
        },
        "security_posture_check": {
            "constraint_name": "Security Posture",
            "is_met": True,
            "details": "IL2-IL4 capable"
        },
        "certification_check": {
            "constraint_name": "Certifications",
            "is_met": True,
            "details": "All required certifications met"
        },
        "blockers": [],
        "assets": ["Native Hawaiian Owned set-aside eligible"],
        "warnings": [],
        "evaluated_at": datetime.utcnow().isoformat(),
        "vtkl_profile_version": "1.0"
    }


@pytest.fixture
def blocked_result():
    """Sample blocked eligibility result."""
    return {
        "opportunity_id": "TEST-NOGO-001",
        "is_eligible": False,
        "participation_path": None,
        "entity_type_check": {
            "constraint_name": "Entity Type",
            "is_met": True,
            "details": "For-profit corporation"
        },
        "location_check": {
            "constraint_name": "Location",
            "is_met": True,
            "details": "Hawaii-based"
        },
        "sam_active_check": {
            "constraint_name": "SAM Registration",
            "is_met": True,
            "details": "Active"
        },
        "naics_match_check": {
            "constraint_name": "NAICS Match",
            "is_met": True,
            "details": "541511 matches"
        },
        "security_posture_check": {
            "constraint_name": "Security Posture",
            "is_met": True,
            "details": "IL2-IL4 capable"
        },
        "certification_check": {
            "constraint_name": "Certifications",
            "is_met": False,
            "details": "Requires 8(a)"
        },
        "blockers": ["Requires 8(a) certification — VTKL not currently certified"],
        "assets": [],
        "warnings": ["Tight deadline - 30 days"],
        "evaluated_at": datetime.utcnow().isoformat(),
        "vtkl_profile_version": "1.0"
    }


@pytest.fixture
def sample_teaming_partners():
    """Sample teaming partners."""
    return [
        {
            "opportunity_id": "TEST-GO-001",
            "partner_name": "University of Hawaii",
            "partner_role": "Research Partner",
            "rationale": "Academic research expertise",
            "source": "hardcoded",
            "naics_codes": [],
            "past_agency_work": None
        }
    ]


def test_go_verdict_produces_full_report(
    mock_supabase_client,
    go_scoring_result,
    eligible_result,
    sample_teaming_partners
):
    """Test that GO verdict produces full report with all 5 sections."""
    # Setup mocks
    mock_table = Mock()
    mock_supabase_client._client.table.return_value = mock_table
    
    # Mock scoring results query
    scoring_mock = Mock()
    scoring_mock.data = go_scoring_result
    
    # Mock eligibility results query
    eligibility_mock = Mock()
    eligibility_mock.data = eligible_result
    
    # Mock teaming partners query
    teaming_mock = Mock()
    teaming_mock.data = sample_teaming_partners
    
    # Mock grant opportunity query
    grant_mock = Mock()
    grant_mock.data = {"raw_text": "Sample opportunity seeking AI solutions"}
    
    # Mock insert
    insert_mock = Mock()
    insert_mock.data = [{"id": 1}]
    
    # Setup query chain
    def mock_query_chain(*args, **kwargs):
        query = Mock()
        query.select = Mock(return_value=query)
        query.eq = Mock(return_value=query)
        query.single = Mock(return_value=query)
        
        # Determine which query based on table name
        table_name = args[0] if args else None
        if table_name == "scoring_results":
            query.execute = Mock(return_value=scoring_mock)
        elif table_name == "eligibility_results":
            query.execute = Mock(return_value=eligibility_mock)
        elif table_name == "teaming_partners":
            query.execute = Mock(return_value=teaming_mock)
        elif table_name == "grant_opportunities":
            query.execute = Mock(return_value=grant_mock)
        elif table_name == "verdict_reports":
            query.insert = Mock(return_value=query)
            query.execute = Mock(return_value=insert_mock)
        
        return query
    
    mock_supabase_client._client.table = mock_query_chain
    
    # Generate report
    generator = VerdictReportGenerator(mock_supabase_client)
    report = generator.generate("TEST-GO-001")
    
    # Verify all 5 sections are present
    assert report.verdict == "GO"
    assert report.composite_score == 85.0
    assert report.verdict_rationale is not None and len(report.verdict_rationale) > 0
    assert report.executive_summary is not None and len(report.executive_summary) > 0
    assert report.risk_assessment is not None and len(report.risk_assessment) > 0
    assert report.strategic_roadmap is not None and len(report.strategic_roadmap) > 0
    assert report.one_pager_pitch is not None and len(report.one_pager_pitch) > 0
    assert report.status == "awaiting_human_approval"


def test_no_go_verdict_produces_abbreviated_report(
    mock_supabase_client,
    no_go_scoring_result,
    blocked_result
):
    """Test that NO-GO verdict produces abbreviated report."""
    # Setup mocks
    mock_table = Mock()
    mock_supabase_client._client.table.return_value = mock_table
    
    # Mock responses
    scoring_mock = Mock()
    scoring_mock.data = no_go_scoring_result
    
    eligibility_mock = Mock()
    eligibility_mock.data = blocked_result
    
    teaming_mock = Mock()
    teaming_mock.data = []
    
    grant_mock = Mock()
    grant_mock.data = {"raw_text": "Defense opportunity"}
    
    insert_mock = Mock()
    insert_mock.data = [{"id": 2}]
    
    # Setup query chain
    def mock_query_chain(*args, **kwargs):
        query = Mock()
        query.select = Mock(return_value=query)
        query.eq = Mock(return_value=query)
        query.single = Mock(return_value=query)
        
        table_name = args[0] if args else None
        if table_name == "scoring_results":
            query.execute = Mock(return_value=scoring_mock)
        elif table_name == "eligibility_results":
            query.execute = Mock(return_value=eligibility_mock)
        elif table_name == "teaming_partners":
            query.execute = Mock(return_value=teaming_mock)
        elif table_name == "grant_opportunities":
            query.execute = Mock(return_value=grant_mock)
        elif table_name == "verdict_reports":
            query.insert = Mock(return_value=query)
            query.execute = Mock(return_value=insert_mock)
        
        return query
    
    mock_supabase_client._client.table = mock_query_chain
    
    # Generate report
    generator = VerdictReportGenerator(mock_supabase_client)
    report = generator.generate("TEST-NOGO-001")
    
    # Verify abbreviated report (no roadmap, no one-pager)
    assert report.verdict == "NO-GO"
    assert report.composite_score == 39.0
    assert report.verdict_rationale is not None
    assert report.executive_summary is not None
    assert report.risk_assessment is not None
    assert report.strategic_roadmap is None
    assert report.one_pager_pitch is None
    assert report.status == "awaiting_human_approval"


def test_evidence_traceability_in_executive_summary(
    mock_supabase_client,
    go_scoring_result,
    eligible_result,
    sample_teaming_partners
):
    """Test that executive summary contains text from evidence_citations."""
    # Setup mocks (similar to test_go_verdict)
    scoring_mock = Mock()
    scoring_mock.data = go_scoring_result
    
    eligibility_mock = Mock()
    eligibility_mock.data = eligible_result
    
    teaming_mock = Mock()
    teaming_mock.data = sample_teaming_partners
    
    grant_mock = Mock()
    grant_mock.data = {"raw_text": "Sample opportunity"}
    
    insert_mock = Mock()
    insert_mock.data = [{"id": 3}]
    
    def mock_query_chain(*args, **kwargs):
        query = Mock()
        query.select = Mock(return_value=query)
        query.eq = Mock(return_value=query)
        query.single = Mock(return_value=query)
        
        table_name = args[0] if args else None
        if table_name == "scoring_results":
            query.execute = Mock(return_value=scoring_mock)
        elif table_name == "eligibility_results":
            query.execute = Mock(return_value=eligibility_mock)
        elif table_name == "teaming_partners":
            query.execute = Mock(return_value=teaming_mock)
        elif table_name == "grant_opportunities":
            query.execute = Mock(return_value=grant_mock)
        elif table_name == "verdict_reports":
            query.insert = Mock(return_value=query)
            query.execute = Mock(return_value=insert_mock)
        
        return query
    
    mock_supabase_client._client.table = mock_query_chain
    
    # Generate report
    generator = VerdictReportGenerator(mock_supabase_client)
    report = generator.generate("TEST-GO-001")
    
    # Verify evidence is cited in executive summary
    summary = report.executive_summary.lower()
    
    # Check for mission fit evidence
    assert "healthcare" in summary or "ai solutions" in summary
    
    # Check for technical alignment evidence
    assert "machine learning" in summary or "data governance" in summary or "automation" in summary
    
    # Verify it's 3 sentences (basic check for periods)
    sentence_count = report.executive_summary.count('.')
    assert sentence_count == 3, f"Expected 3 sentences, got {sentence_count}"


def test_brand_messaging_in_one_pager(
    mock_supabase_client,
    go_scoring_result,
    eligible_result,
    sample_teaming_partners
):
    """Test that one_pager_pitch contains required brand messaging."""
    # Setup mocks
    scoring_mock = Mock()
    scoring_mock.data = go_scoring_result
    
    eligibility_mock = Mock()
    eligibility_mock.data = eligible_result
    
    teaming_mock = Mock()
    teaming_mock.data = sample_teaming_partners
    
    grant_mock = Mock()
    grant_mock.data = {"raw_text": "Sample opportunity"}
    
    insert_mock = Mock()
    insert_mock.data = [{"id": 4}]
    
    def mock_query_chain(*args, **kwargs):
        query = Mock()
        query.select = Mock(return_value=query)
        query.eq = Mock(return_value=query)
        query.single = Mock(return_value=query)
        
        table_name = args[0] if args else None
        if table_name == "scoring_results":
            query.execute = Mock(return_value=scoring_mock)
        elif table_name == "eligibility_results":
            query.execute = Mock(return_value=eligibility_mock)
        elif table_name == "teaming_partners":
            query.execute = Mock(return_value=teaming_mock)
        elif table_name == "grant_opportunities":
            query.execute = Mock(return_value=grant_mock)
        elif table_name == "verdict_reports":
            query.insert = Mock(return_value=query)
            query.execute = Mock(return_value=insert_mock)
        
        return query
    
    mock_supabase_client._client.table = mock_query_chain
    
    # Generate report
    generator = VerdictReportGenerator(mock_supabase_client)
    report = generator.generate("TEST-GO-001")
    
    # Verify brand messaging is present
    pitch = report.one_pager_pitch.lower()
    assert "execution engine" in pitch, "Missing 'execution engine' brand messaging"
    assert "purpose-built solutions" in pitch, "Missing 'purpose-built solutions' brand messaging"
    
    # Verify pitch contains score
    assert "85" in report.one_pager_pitch or "85.0" in report.one_pager_pitch
