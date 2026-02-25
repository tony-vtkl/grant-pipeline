"""Configurable partner fallback — loads partners from a JSON config file.

Used when USASpending API is unavailable.
Config file path set via PARTNER_CONFIG_PATH env var.

Source: VTK-94 (REQ-2: Eliminar Hardcoded Partners)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConfigPartner:
    """A partner loaded from config file."""

    name: str
    role: str
    rationale: str
    agency_patterns: list[str] = field(default_factory=list)
    opportunity_type_patterns: list[str] = field(default_factory=list)


def _get_config_path() -> Path | None:
    """Return partner config file path from env, or None."""
    path_str = os.environ.get("PARTNER_CONFIG_PATH")
    if not path_str:
        return None
    p = Path(path_str)
    if not p.exists():
        logger.warning("PARTNER_CONFIG_PATH=%s does not exist", path_str)
        return None
    return p


def load_partners_from_config() -> list[ConfigPartner]:
    """Load partner list from JSON config file.

    Expected JSON format:
    {
      "partners": [
        {
          "name": "Org Name",
          "role": "Research Partner",
          "rationale": "Why this partner",
          "agency_patterns": ["NSF"],
          "opportunity_type_patterns": ["grant"]
        }
      ]
    }

    Returns empty list if PARTNER_CONFIG_PATH not set or file invalid.
    """
    config_path = _get_config_path()
    if config_path is None:
        return []

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read partner config %s: %s", config_path, exc)
        return []

    partners: list[ConfigPartner] = []
    for entry in data.get("partners", []):
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        partners.append(
            ConfigPartner(
                name=entry["name"],
                role=entry.get("role", "Partner"),
                rationale=entry.get("rationale", ""),
                agency_patterns=entry.get("agency_patterns", []),
                opportunity_type_patterns=entry.get("opportunity_type_patterns", []),
            )
        )

    return partners


def get_matching_config_partners(
    agency: str, opportunity_type: str | None = None
) -> list[ConfigPartner]:
    """Return config partners matching agency/opportunity type.

    Matching logic mirrors the old hardcoded_partners module.
    """
    all_partners = load_partners_from_config()
    if not all_partners:
        return []

    agency_lower = agency.lower()
    opp_lower = (opportunity_type or "").lower()

    results: list[ConfigPartner] = []
    for partner in all_partners:
        agency_match = any(p.lower() in agency_lower for p in partner.agency_patterns)
        if not agency_match:
            agency_match = any(agency_lower in p.lower() for p in partner.agency_patterns)
        if not agency_match:
            continue

        if partner.opportunity_type_patterns and opp_lower:
            type_match = any(p.lower() in opp_lower for p in partner.opportunity_type_patterns)
            if not type_match:
                type_match = any(opp_lower in p.lower() for p in partner.opportunity_type_patterns)
            if not type_match:
                continue

        results.append(partner)

    return results
