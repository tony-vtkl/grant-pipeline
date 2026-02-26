"""Integration test fixtures and mock infrastructure."""

import json
import hashlib
import sys
from pathlib import Path
from typing import List, Set

import pytest

# Ensure paths are set
_pkg_root = Path(__file__).resolve().parent.parent.parent  # python_ingestion/
_repo_root = _pkg_root.parent
for p in [str(_repo_root), str(_pkg_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from python_ingestion.models import GrantOpportunity  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockDBClient:
    """In-memory replacement for SupabaseClient."""

    def __init__(self):
        self.inserted: List[GrantOpportunity] = []
        self._hashes: Set[str] = set()

    async def get_existing_hashes(self) -> Set[str]:
        return set(self._hashes)

    async def insert_opportunities(self, opportunities: List[GrantOpportunity]) -> int:
        for opp in opportunities:
            self.inserted.append(opp)
            self._hashes.add(opp.dedup_hash)
        return len(opportunities)

    def reset(self):
        self.inserted.clear()
        self._hashes.clear()


@pytest.fixture
def mock_db():
    return MockDBClient()


def _load_json(name: str):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def grants_gov_snapshot():
    return _load_json("grants_gov_snapshots.json")


@pytest.fixture
def sam_gov_snapshot():
    return _load_json("sam_gov_snapshots.json")


@pytest.fixture
def sbir_gov_snapshot():
    return _load_json("sbir_gov_snapshots.json")


def make_opportunity(
    source: str,
    source_id: str,
    title: str,
    agency: str = "Test Agency",
    description: str = "",
    raw_text: str = "",
    naics_codes: list | None = None,
    set_aside_type: str | None = None,
    award_min: float | None = None,
    award_max: float | None = None,
    **kwargs,
) -> GrantOpportunity:
    dedup_hash = hashlib.sha256(f"{source}:{source_id}".encode()).hexdigest()
    return GrantOpportunity(
        source=source,
        source_opportunity_id=source_id,
        dedup_hash=dedup_hash,
        title=title,
        agency=agency,
        description=description,
        raw_text=raw_text,
        naics_codes=naics_codes or [],
        set_aside_type=set_aside_type,
        award_amount_min=award_min,
        award_amount_max=award_max,
        source_url=f"https://example.com/{source_id}",
        status="new",
        **kwargs,
    )
