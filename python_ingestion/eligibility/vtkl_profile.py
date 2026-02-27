"""VTKL entity profile configuration.

Defines VTKL's capabilities, certifications, and constraints for eligibility assessment.
All values have sensible defaults but can be overridden via environment variables.
"""

import os
from datetime import datetime, timezone


def _parse_csv(env_key: str, default: list[str]) -> list[str]:
    """Parse comma-separated env var into list, or return default."""
    val = os.environ.get(env_key)
    if val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return default


def _parse_bool(env_key: str, default: bool) -> bool:
    """Parse boolean env var (true/false/1/0)."""
    val = os.environ.get(env_key)
    if val is not None:
        return val.lower() in ("true", "1", "yes")
    return default


def _parse_datetime(env_key: str, default: datetime) -> datetime:
    """Parse ISO-format datetime env var."""
    val = os.environ.get(env_key)
    if val:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return default


VTKL_PROFILE = {
    "entity_type": os.environ.get("VTKL_ENTITY_TYPE", "for-profit_corporation"),
    "sam_registration": {
        "entity_id": os.environ.get("VTKL_SAM_ENTITY_ID", "ML49GKWHGCX6"),
        "cage_code": os.environ.get("VTKL_SAM_CAGE_CODE", "16RM8"),
        "expiry_date": _parse_datetime("VTKL_SAM_EXPIRY", datetime(2026, 11, 11, tzinfo=timezone.utc)),
        "status": "active"
    },
    "naics_primary": _parse_csv("VTKL_NAICS_PRIMARY", ["541511", "541512", "541990"]),
    "naics_optional": ["541715", "518210"],
    "security_posture": _parse_csv("VTKL_SECURITY_POSTURE", ["IL2", "IL3", "IL4"]),
    "location": {
        "state": os.environ.get("VTKL_LOCATION_STATE", "HI"),
        "city": "Honolulu",
        "nho_eligible": _parse_bool("VTKL_NHO_ELIGIBLE", True)
    },
    "certifications": {
        "8a": False,
        "8(a)": False,
        "hubzone": False,
        "HUBZone": False,
        "sdvosb": False,
        "wosb": False
    },
    "financial_capacity": {
        "min_award": 100_000,
        "max_award": 5_000_000,
        "preferred_range": (500_000, 2_000_000)
    }
}
