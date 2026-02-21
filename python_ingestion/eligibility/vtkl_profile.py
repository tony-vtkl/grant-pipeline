"""VTKL entity profile configuration.

Defines VTKL's capabilities, certifications, and constraints for eligibility assessment.
"""

from datetime import datetime, timezone

VTKL_PROFILE = {
    "entity_type": "for-profit_corporation",
    "sam_registration": {
        "entity_id": "ML49GKWHGCX6",
        "cage_code": "16RM8",
        "expiry_date": datetime(2026, 11, 11, tzinfo=timezone.utc),
        "status": "active"
    },
    "naics_primary": ["541511", "541512", "541990"],
    "naics_optional": ["541715", "518210"],
    "security_posture": ["IL2", "IL3", "IL4"],
    "location": {
        "state": "HI",
        "city": "Honolulu",
        "nho_eligible": True
    },
    "certifications": {
        "8a": False,
        "8(a)": False,  # Alternative spelling
        "hubzone": False,
        "HUBZone": False,  # Alternative casing
        "sdvosb": False,
        "wosb": False
    },
    "financial_capacity": {
        "min_award": 100_000,
        "max_award": 5_000_000,
        "preferred_range": (500_000, 2_000_000)
    }
}
