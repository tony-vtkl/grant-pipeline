"""DEPRECATED — hardcoded partner data removed per VTK-94 (REQ-2).

Partners now resolved via:
  1. USASpending API (primary) — teaming/usaspending_lookup.py
  2. Config file fallback — teaming/partner_config.py (PARTNER_CONFIG_PATH env var)

This module is kept as a tombstone to prevent silent import errors.
"""

raise ImportError(
    "hardcoded_partners has been removed (VTK-94). "
    "Use teaming.partner_config for config-based partners "
    "or teaming.usaspending_lookup for API-based partners."
)
