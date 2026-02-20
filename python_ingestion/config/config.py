"""Configuration management for ingestion pipeline."""

import os
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Application configuration from environment variables.
    
    Per INTAKE BLOCK 1 DoD: README documents env vars:
    - SAM_API_KEY
    - DATABASE_URL
    - ANTHROPIC_API_KEY
    """
    
    # Required
    sam_api_key: str
    database_url: str
    
    # Optional
    anthropic_api_key: Optional[str] = None  # For future REQs
    grants_gov_attribution: str = "VTKL Grant Pipeline"
    
    # Polling schedule (minutes)
    polling_interval_minutes: int = 60  # Per INTAKE BLOCK 1: 60-minute polling
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def load_config() -> Config:
    """Load configuration from environment."""
    return Config()
