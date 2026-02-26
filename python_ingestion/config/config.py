"""Configuration management for ingestion pipeline."""

import sys
from typing import Optional
from pydantic_settings import BaseSettings


REQUIRED_VARS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SAM_API_KEY",
    "GRANTS_GOV_ATTRIBUTION",
]


class Config(BaseSettings):
    """Application configuration from environment variables."""

    # Required
    supabase_url: str
    supabase_key: str
    sam_api_key: str
    database_url: str = ""
    grants_gov_attribution: str = "VTKL Grant Pipeline"

    # Optional
    anthropic_api_key: Optional[str] = None
    polling_interval_minutes: int = 60
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}


def validate_config() -> Config:
    """Load and validate configuration from environment.

    Raises ValueError with descriptive message listing ALL missing
    required variables (not just the first one).
    """
    try:
        return Config()  # type: ignore[call-arg]
    except Exception as exc:
        # Collect missing fields from the pydantic error
        missing = []
        err_str = str(exc)
        for var in REQUIRED_VARS:
            if var.lower() in err_str.lower():
                missing.append(var)
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"Missing required environment variable(s): {names}. "
                "Please set them in your .env file or environment."
            ) from exc
        raise


def load_config() -> Config:
    """Load configuration from environment (startup entry point)."""
    return validate_config()
