"""Tests for configuration validation (VTK-100)."""

import os
import pytest
from unittest.mock import patch


class TestConfigValidation:
    """Test startup config validation."""

    VALID_ENV = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key-123",
        "SAM_API_KEY": "test-sam-key",
        "GRANTS_GOV_ATTRIBUTION": "Test Pipeline",
        "POLLING_INTERVAL_MINUTES": "30",
        "LOG_LEVEL": "DEBUG",
    }

    def test_valid_config_loads_successfully(self):
        """All required vars present → Config loads without error."""
        with patch.dict(os.environ, self.VALID_ENV, clear=False):
            from python_ingestion.config.config import validate_config

            config = validate_config()
            assert config.supabase_url == "https://test.supabase.co"
            assert config.supabase_key == "test-key-123"
            assert config.sam_api_key == "test-sam-key"
            assert config.grants_gov_attribution == "Test Pipeline"
            assert config.polling_interval_minutes == 30
            assert config.log_level == "DEBUG"

    def test_missing_required_var_raises_error(self):
        """Missing required var → clear ValueError."""
        # Only provide some vars, omit SUPABASE_URL and SUPABASE_KEY
        partial_env = {
            "SAM_API_KEY": "test-sam-key",
            "GRANTS_GOV_ATTRIBUTION": "Test",
        }
        # Clear all config-related vars to ensure they're missing
        env_clear = {
            k: v for k, v in os.environ.items()
            if k not in ("SUPABASE_URL", "SUPABASE_KEY", "SAM_API_KEY",
                         "GRANTS_GOV_ATTRIBUTION", "DATABASE_URL")
        }
        env_clear.update(partial_env)

        with patch.dict(os.environ, env_clear, clear=True):
            from python_ingestion.config.config import validate_config

            with pytest.raises((ValueError, Exception)) as exc_info:
                validate_config()
            # Error should mention the missing variable
            err_msg = str(exc_info.value).lower()
            assert "supabase_url" in err_msg or "supabase_key" in err_msg or "missing" in err_msg or "required" in err_msg
