"""Tests for teaming module — VTK-94 (REQ-2: Eliminar Hardcoded Partners).

Tests verify:
  AC1: No hardcoded partner data in production code
  AC2: USASpending API used as primary partner source
  AC3: Configurable fallback via env var / config file
  AC4: Mocks only in test files (DoD 3.1)
  AC5: Minimum 3 tests — API mock, fallback to config, rejection when neither available
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from models.grant_opportunity import GrantOpportunity
from models.scoring_result import ScoringResult, DimensionScore
from models.teaming_partner import TeamingPartner
from teaming.engine import generate_teaming_suggestions, ACTIONABLE_VERDICTS
from teaming.partner_config import (
    ConfigPartner,
    load_partners_from_config,
    get_matching_config_partners,
)
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


SAMPLE_CONFIG = {
    "partners": [
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
            "agency_patterns": ["USDA"],
            "opportunity_type_patterns": ["grant"],
        },
    ]
}


# --- AC1: No hardcoded partner data in production code ---

class TestNoHardcodedPartners:
    def test_hardcoded_partners_module_raises_on_import(self):
        """Importing hardcoded_partners raises ImportError — no hardcoded data in prod."""
        with pytest.raises(ImportError, match="hardcoded_partners has been removed"):
            # Force reimport
            import importlib
            import teaming.hardcoded_partners
            importlib.reload(teaming.hardcoded_partners)

    def test_engine_does_not_import_hardcoded_partners(self):
        """engine.py does not reference hardcoded_partners."""
        import inspect
        import teaming.engine as eng
        source = inspect.getsource(eng)
        assert "hardcoded_partners" not in source


# --- AC2: USASpending API as primary source (mocked in test) ---

class TestUSASpendingPrimary:
    def test_usaspending_results_used_as_primary(self):
        """When USASpending returns results, they become the partner list."""
        mock_partners = [
            USAspendingPartner(
                name="Mock Research Corp",
                naics_codes=["541511"],
                agency="NSF",
                award_count=5,
            ),
        ]
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")

        with patch(
            "teaming.engine.lookup_partners_by_naics_and_agency",
            return_value=mock_partners,
        ):
            results = generate_teaming_suggestions(opp, scoring)

        assert len(results) >= 1
        assert results[0].partner_name == "Mock Research Corp"
        assert results[0].source == "usaspending"

    def test_usaspending_model_structure(self):
        """USAspendingPartner has expected fields."""
        p = USAspendingPartner(
            name="Test Corp", naics_codes=["541511"], agency="NSF", award_count=3
        )
        assert p.name == "Test Corp"
        assert p.naics_codes == ["541511"]

    def test_lookup_returns_list(self):
        """lookup function returns list (may be empty if API unreachable)."""
        result = lookup_partners_by_naics_and_agency(
            agency="National Science Foundation",
            naics_codes=["541511"],
            limit=2,
            timeout=5.0,
        )
        assert isinstance(result, list)


# --- AC3: Configurable fallback via env var / config file ---

class TestConfigFallback:
    def test_fallback_loads_from_config_file(self):
        """When PARTNER_CONFIG_PATH is set, partners load from JSON file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(SAMPLE_CONFIG, f)
            f.flush()
            config_path = f.name

        try:
            with patch.dict(os.environ, {"PARTNER_CONFIG_PATH": config_path}):
                partners = load_partners_from_config()
            assert len(partners) == 2
            assert partners[0].name == "University of Hawaiʻi at Mānoa"
            assert isinstance(partners[0], ConfigPartner)
        finally:
            os.unlink(config_path)

    def test_fallback_matching_filters_by_agency(self):
        """Config partners are filtered by agency pattern."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(SAMPLE_CONFIG, f)
            f.flush()
            config_path = f.name

        try:
            with patch.dict(os.environ, {"PARTNER_CONFIG_PATH": config_path}):
                matches = get_matching_config_partners("NSF", "grant")
            assert len(matches) == 1
            assert matches[0].name == "University of Hawaiʻi at Mānoa"
        finally:
            os.unlink(config_path)

    def test_engine_uses_config_fallback_when_api_fails(self):
        """When USASpending returns empty, engine falls back to config partners."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(SAMPLE_CONFIG, f)
            f.flush()
            config_path = f.name

        try:
            opp = _make_opportunity(agency="NSF")
            scoring = _make_scoring("GO")

            with (
                patch(
                    "teaming.engine.lookup_partners_by_naics_and_agency",
                    return_value=[],  # API returns nothing
                ),
                patch.dict(os.environ, {"PARTNER_CONFIG_PATH": config_path}),
            ):
                results = generate_teaming_suggestions(opp, scoring)

            assert len(results) >= 1
            assert results[0].source == "config"
            assert results[0].partner_name == "University of Hawaiʻi at Mānoa"
        finally:
            os.unlink(config_path)


# --- AC5: Rejection when neither API nor config available ---

class TestRejectionWhenNeitherAvailable:
    def test_empty_when_no_api_and_no_config(self):
        """Returns empty list when USASpending fails and no config file set."""
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")

        with (
            patch(
                "teaming.engine.lookup_partners_by_naics_and_agency",
                return_value=[],
            ),
            patch.dict(os.environ, {}, clear=True),
        ):
            # Ensure PARTNER_CONFIG_PATH is not set
            os.environ.pop("PARTNER_CONFIG_PATH", None)
            results = generate_teaming_suggestions(opp, scoring)

        assert results == []

    def test_empty_config_returns_no_partners(self):
        """Config file with no matching partners returns empty."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PARTNER_CONFIG_PATH", None)
            partners = load_partners_from_config()
        assert partners == []


# --- Verdict filtering (preserved from original tests) ---

class TestVerdictFiltering:
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


# --- AC4: No mocks in core code (DoD 3.1) ---

class TestNoMocksInCoreCode:
    def test_production_modules_have_no_mock_imports(self):
        """Verify production teaming modules don't import unittest.mock."""
        import inspect
        import teaming.engine as eng
        import teaming.partner_config as pc
        import teaming.usaspending_lookup as usa

        for mod in [eng, pc, usa]:
            source = inspect.getsource(mod)
            assert "unittest.mock" not in source, f"{mod.__name__} imports mock!"
            assert "from mock " not in source, f"{mod.__name__} imports mock!"


# --- No automated outreach (preserved) ---

class TestNoAutomatedOutreach:
    def test_teaming_output_is_informational(self):
        """Partners have no action/outreach fields."""
        mock_partners = [
            USAspendingPartner(name="Test Corp", naics_codes=["541511"], agency="NSF", award_count=1)
        ]
        opp = _make_opportunity(agency="NSF")
        scoring = _make_scoring("GO")

        with patch(
            "teaming.engine.lookup_partners_by_naics_and_agency",
            return_value=mock_partners,
        ):
            partners = generate_teaming_suggestions(opp, scoring)

        for p in partners:
            data = p.model_dump()
            assert "action" not in data
            assert "send_email" not in data
            assert "contact" not in data
