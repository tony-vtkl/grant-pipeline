"""Tests for VTK-97: Eliminar Hardcoded Partners.

Tests verify:
1. USASpending API call returns partners (mocked)
2. Config file fallback works when API unavailable
3. Error raised when neither API nor config available
4. Engine integration with new partner source
5. No automated outreach
"""

import json
import os
import tempfile

import httpx
import pytest
import respx

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult, DimensionScore
from models.teaming_partner import TeamingPartner
from teaming.engine import generate_teaming_suggestions, ACTIONABLE_VERDICTS
from teaming.hardcoded_partners import (
    PartnerSourceError,
    get_matching_partners,
    _load_config_partners,
)
from teaming.usaspending_lookup import USAspendingPartner


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


SAMPLE_CONFIG = [
    {
        "name": "University of Hawaiʻi at Mānoa",
        "role": "Research Partner",
        "rationale": "Academic research institution",
        "agency_patterns": ["NSF", "National Science Foundation"],
        "opportunity_type_patterns": ["grant"],
    },
    {
        "name": "Farm to School Hui",
        "role": "Community Partner",
        "rationale": "Local agriculture network",
        "agency_patterns": ["USDA", "Department of Agriculture"],
        "opportunity_type_patterns": ["grant"],
    },
]

USA_SPENDING_RESPONSE = {
    "results": [
        {
            "Recipient Name": "TechCorp Inc.",
            "Award Amount": 500000,
            "NAICS Code": "541511",
            "Awarding Agency": "National Science Foundation",
        },
        {
            "Recipient Name": "DataSystems LLC",
            "Award Amount": 300000,
            "NAICS Code": "541512",
            "Awarding Agency": "National Science Foundation",
        },
    ]
}


# --- Test 1: USASpending API returns partners (mocked) ---

class TestUSASpendingAPIPartners:
    @respx.mock
    def test_api_returns_partners(self):
        """When USASpending API responds, partners come from API."""
        respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
            return_value=httpx.Response(200, json=USA_SPENDING_RESPONSE)
        )
        # Ensure no config fallback
        os.environ.pop("PARTNER_CONFIG_PATH", None)

        partners = get_matching_partners(agency="National Science Foundation")
        assert len(partners) == 2
        assert partners[0].name == "TechCorp Inc."
        assert partners[1].name == "DataSystems LLC"
        assert all(isinstance(p, USAspendingPartner) for p in partners)

    @respx.mock
    def test_api_partners_have_metadata(self):
        """API partners include NAICS codes and agency."""
        respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
            return_value=httpx.Response(200, json=USA_SPENDING_RESPONSE)
        )
        os.environ.pop("PARTNER_CONFIG_PATH", None)

        partners = get_matching_partners(agency="NSF")
        assert partners[0].naics_codes == ["541511"]
        assert partners[0].award_count == 1


# --- Test 2: Config file fallback ---

class TestConfigFallback:
    def test_config_fallback_when_api_empty(self):
        """When API returns no results, falls back to config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_CONFIG, f)
            config_path = f.name

        try:
            os.environ["PARTNER_CONFIG_PATH"] = config_path
            with respx.mock:
                respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
                    return_value=httpx.Response(200, json={"results": []})
                )
                partners = get_matching_partners(agency="NSF", opportunity_type="grant")
                assert len(partners) == 1
                assert partners[0].name == "University of Hawaiʻi at Mānoa"
        finally:
            os.environ.pop("PARTNER_CONFIG_PATH", None)
            os.unlink(config_path)

    def test_config_fallback_when_api_fails(self):
        """When API errors out, falls back to config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_CONFIG, f)
            config_path = f.name

        try:
            os.environ["PARTNER_CONFIG_PATH"] = config_path
            with respx.mock:
                respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
                    return_value=httpx.Response(500)
                )
                partners = get_matching_partners(agency="USDA", opportunity_type="grant")
                assert len(partners) == 1
                assert partners[0].name == "Farm to School Hui"
        finally:
            os.environ.pop("PARTNER_CONFIG_PATH", None)
            os.unlink(config_path)


# --- Test 3: Error when neither source available ---

class TestNoSourceAvailable:
    def test_raises_error_when_no_api_no_config(self):
        """PartnerSourceError raised when API empty and no config."""
        os.environ.pop("PARTNER_CONFIG_PATH", None)
        with respx.mock:
            respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
                return_value=httpx.Response(200, json={"results": []})
            )
            with pytest.raises(PartnerSourceError):
                get_matching_partners(agency="UnknownAgency")

    def test_raises_error_when_api_fails_no_config(self):
        """PartnerSourceError raised when API fails and no config."""
        os.environ.pop("PARTNER_CONFIG_PATH", None)
        with respx.mock:
            respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
                return_value=httpx.Response(500)
            )
            with pytest.raises(PartnerSourceError):
                get_matching_partners(agency="NSF")


# --- Test 4: Engine integration ---

class TestEngineIntegration:
    @respx.mock
    def test_go_verdict_returns_partners(self):
        """GO verdict triggers partner lookup via API."""
        respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
            return_value=httpx.Response(200, json=USA_SPENDING_RESPONSE)
        )
        os.environ.pop("PARTNER_CONFIG_PATH", None)

        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")
        partners = generate_teaming_suggestions(opp, scoring)
        assert len(partners) > 0
        for p in partners:
            assert isinstance(p, TeamingPartner)
            assert p.partner_name
            assert p.rationale
            assert p.source == "usaspending"

    def test_monitor_verdict_returns_empty(self):
        """MONITOR verdict skips teaming."""
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("MONITOR")
        partners = generate_teaming_suggestions(opp, scoring)
        assert partners == []

    def test_nogo_verdict_returns_empty(self):
        """NO-GO verdict skips teaming."""
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("NO-GO")
        partners = generate_teaming_suggestions(opp, scoring)
        assert partners == []


# --- Test 5: No automated outreach ---

class TestNoAutomatedOutreach:
    @respx.mock
    def test_teaming_output_is_informational(self):
        """Partners have no action/outreach fields."""
        respx.post("https://api.usaspending.gov/api/v2/search/spending_by_award/").mock(
            return_value=httpx.Response(200, json=USA_SPENDING_RESPONSE)
        )
        os.environ.pop("PARTNER_CONFIG_PATH", None)

        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")
        partners = generate_teaming_suggestions(opp, scoring)
        for p in partners:
            data = p.model_dump()
            assert "action" not in data
            assert "send_email" not in data
            assert "contact" not in data
            assert "outreach" not in data


# --- Test 6: No hardcoded data in production code ---

class TestNoHardcodedData:
    def test_no_seed_partners_constant(self):
        """hardcoded_partners.py should not export SEED_PARTNERS."""
        import teaming.hardcoded_partners as mod
        assert not hasattr(mod, "SEED_PARTNERS"), "SEED_PARTNERS still exists in production code"

    def test_no_hardcoded_names_in_source(self):
        """Production source file contains no hardcoded partner names."""
        from pathlib import Path
        source = Path(__file__).parent.parent / "teaming" / "hardcoded_partners.py"
        content = source.read_text()
        # These were the old hardcoded names
        hardcoded_names = [
            "University of Hawaiʻi at Mānoa",
            "Chaminade University",
            "Hawaiʻi Pacific University",
            "Hawaiʻi Department of Education",
            "Farm to School Hui",
        ]
        for name in hardcoded_names:
            assert name not in content, f"Hardcoded partner name found in production code: {name}"
