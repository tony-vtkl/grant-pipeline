"""VTKL entity profile configuration.

Defines VTKL's capabilities, certifications, and constraints for eligibility assessment.
Environment variable overrides (prefixed VTKL_) take precedence over defaults.
"""

import os
from datetime import datetime, timezone


def _env(key: str, default: str) -> str:
    """Read VTKL_ prefixed env var with fallback."""
    return os.environ.get(f"VTKL_{key}", default)


def _env_bool(key: str, default: bool) -> bool:
    """Read VTKL_ prefixed env var as boolean."""
    val = os.environ.get(f"VTKL_{key}")
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _env_list(key: str, default: list[str]) -> list[str]:
    """Read VTKL_ prefixed env var as comma-separated list."""
    val = os.environ.get(f"VTKL_{key}")
    if val is None:
        return default
    return [v.strip() for v in val.split(",") if v.strip()]


def _env_int(key: str, default: int) -> int:
    """Read VTKL_ prefixed env var as integer."""
    val = os.environ.get(f"VTKL_{key}")
    if val is None:
        return default
    return int(val)


def _build_profile() -> dict:
    """Build VTKL profile with env var overrides."""
    sam_expiry_str = os.environ.get("VTKL_SAM_EXPIRY")
    if sam_expiry_str:
        sam_expiry = datetime.fromisoformat(sam_expiry_str)
        if sam_expiry.tzinfo is None:
            sam_expiry = sam_expiry.replace(tzinfo=timezone.utc)
    else:
        sam_expiry = datetime(2026, 11, 11, tzinfo=timezone.utc)

    return {
        "entity_type": _env("ENTITY_TYPE", "for-profit_corporation"),
        "sam_registration": {
            "entity_id": _env("SAM_ENTITY_ID", "ML49GKWHGCX6"),
            "cage_code": _env("SAM_CAGE_CODE", "16RM8"),
            "expiry_date": sam_expiry,
            "status": _env("SAM_STATUS", "active"),
        },
        "naics_primary": _env_list("NAICS_PRIMARY", ["541511", "541512", "541990"]),
        "naics_optional": _env_list("NAICS_OPTIONAL", ["541715", "518210"]),
        "security_posture": _env_list("SECURITY_POSTURE", ["IL2", "IL3", "IL4"]),
        "location": {
            "state": _env("STATE", "HI"),
            "city": _env("CITY", "Honolulu"),
            "nho_eligible": _env_bool("NHO_ELIGIBLE", True),
        },
        "certifications": {
            "8a": _env_bool("CERT_8A", False),
            "8(a)": _env_bool("CERT_8A", False),
            "hubzone": _env_bool("CERT_HUBZONE", False),
            "HUBZone": _env_bool("CERT_HUBZONE", False),
            "sdvosb": _env_bool("CERT_SDVOSB", False),
            "wosb": _env_bool("CERT_WOSB", False),
        },
        "financial_capacity": {
            "min_award": _env_int("MIN_AWARD", 100_000),
            "max_award": _env_int("MAX_AWARD", 5_000_000),
            "preferred_range": (
                _env_int("PREF_AWARD_MIN", 500_000),
                _env_int("PREF_AWARD_MAX", 2_000_000),
            ),
        },
    }


VTKL_PROFILE = _build_profile()
