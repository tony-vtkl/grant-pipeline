"""Tests for configuration validation (VTK-100 AC5)."""

import os
import pytest
from unittest.mock import patch

from python_ingestion.config.config import Config, validate_config


class TestConfigValidation:
    """Dedicated tests for config validation – AC5."""

    VALID_ENV = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key-123",
        "SAM_API_KEY": "test-sam-key",
        "GRANTS_GOV_ATTRIBUTION": "Test Pipeline",
        "POLLING_INTERVAL_MINUTES": "30",
        "LOG_LEVEL": "DEBUG",
    }

    def test_valid_env_vars_load_config_successfully(self):
        """All required env vars present → config loads with correct values."""
        with patch.dict(os.environ, self.VALID_ENV, clear=True):
            config = validate_config()
            assert config.supabase_url == "https://test.supabase.co"
            assert config.supabase_key == "test-key-123"
            assert config.sam_api_key == "test-sam-key"
            assert config.grants_gov_attribution == "Test Pipeline"
            assert config.polling_interval_minutes == 30
            assert config.log_level == "DEBUG"

    def test_missing_supabase_url_and_key_raises_valueerror(self):
        """Missing SUPABASE_URL and SUPABASE_KEY → ValueError with clear message."""
        env = {"SAM_API_KEY": "key", "GRANTS_GOV_ATTRIBUTION": "Test"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="(?i)missing required"):
                validate_config()

    def test_missing_supabase_url_only_raises_valueerror(self):
        """Missing just SUPABASE_URL → ValueError mentioning SUPABASE_URL."""
        env = {
            "SUPABASE_KEY": "key",
            "SAM_API_KEY": "key",
            "GRANTS_GOV_ATTRIBUTION": "Test",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                validate_config()
            assert "SUPABASE_URL" in str(exc_info.value)

    def test_missing_supabase_key_only_raises_valueerror(self):
        """Missing just SUPABASE_KEY → ValueError mentioning SUPABASE_KEY."""
        env = {
            "SUPABASE_URL": "https://x.supabase.co",
            "SAM_API_KEY": "key",
            "GRANTS_GOV_ATTRIBUTION": "Test",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                validate_config()
            assert "SUPABASE_KEY" in str(exc_info.value)

    def test_defaults_applied_for_optional_fields(self):
        """Optional fields get sensible defaults when not set."""
        env = {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_KEY": "k",
            "SAM_API_KEY": "k",
        }
        with patch.dict(os.environ, env, clear=True):
            config = validate_config()
            assert config.grants_gov_attribution == "VTKL Grant Pipeline"
            assert config.polling_interval_minutes == 60
            assert config.log_level == "INFO"
            assert config.anthropic_api_key is None
