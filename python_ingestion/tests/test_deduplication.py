"""Unit tests for deduplication logic with fixture data.

Per INTAKE BLOCK 1 DoD:
- Deduplication logic has dedicated unit test with fixture data
"""

import pytest
import hashlib
from deduplicator import Deduplicator
from models import GrantOpportunity


def create_test_opportunity(source: str, source_id: str, title: str) -> GrantOpportunity:
    """Helper to create test opportunity."""
    dedup_string = f"{source}:{source_id}"
    dedup_hash = hashlib.sha256(dedup_string.encode()).hexdigest()
    
    return GrantOpportunity(
        source=source,
        source_opportunity_id=source_id,
        dedup_hash=dedup_hash,
        title=title,
        agency="Test Agency",
        source_url=f"https://example.com/{source_id}",
    )


def test_deduplicator_prevents_duplicates():
    """AC #2: Deduplicator prevents duplicates - second run within 5min produces 0 new records."""
    
    # Create test opportunities
    opp1 = create_test_opportunity("grants_gov", "GRANTS-001", "First Opportunity")
    opp2 = create_test_opportunity("sam_gov", "SAM-001", "Second Opportunity")
    opp3_duplicate = create_test_opportunity("grants_gov", "GRANTS-001", "First Opportunity (duplicate)")
    
    # First run - all new
    deduplicator = Deduplicator()
    first_run = deduplicator.deduplicate([opp1, opp2])
    
    assert len(first_run) == 2, "First run should return all opportunities as new"
    assert opp1 in first_run
    assert opp2 in first_run
    
    # Second run - with duplicate
    second_run = deduplicator.deduplicate([opp3_duplicate, opp2])
    
    # AC #2: second run produces 0 new records for existing opportunities
    assert len(second_run) == 0, "Second run should return 0 new opportunities (all duplicates)"


def test_deduplicator_with_existing_hashes():
    """Test deduplicator initialized with existing hashes from database."""
    
    opp1 = create_test_opportunity("grants_gov", "GRANTS-001", "First Opportunity")
    opp2 = create_test_opportunity("sam_gov", "SAM-001", "Second Opportunity")
    
    # Simulate existing hashes from database
    existing_hashes = {opp1.dedup_hash}
    
    deduplicator = Deduplicator(existing_hashes=existing_hashes)
    new_opps = deduplicator.deduplicate([opp1, opp2])
    
    # Only opp2 should be new
    assert len(new_opps) == 1
    assert new_opps[0] == opp2


def test_deduplicator_fixture_data():
    """Test deduplication with realistic fixture data."""
    
    # Fixture: First polling cycle
    first_cycle = [
        create_test_opportunity("grants_gov", "HHS-2024-001", "AI for Healthcare"),
        create_test_opportunity("sam_gov", "W911NF-24-001", "Army AI Research"),
        create_test_opportunity("sbir_gov", "N241-001", "Navy SBIR"),
    ]
    
    # Fixture: Second polling cycle (5 minutes later) with 2 duplicates + 1 new
    second_cycle = [
        create_test_opportunity("grants_gov", "HHS-2024-001", "AI for Healthcare"),  # duplicate
        create_test_opportunity("sam_gov", "W911NF-24-001", "Army AI Research"),     # duplicate
        create_test_opportunity("grants_gov", "NSF-2024-002", "Cyberinfrastructure"),  # new
    ]
    
    deduplicator = Deduplicator()
    
    # First cycle
    first_new = deduplicator.deduplicate(first_cycle)
    assert len(first_new) == 3, "All opportunities new in first cycle"
    
    # Second cycle (per AC #2)
    second_new = deduplicator.deduplicate(second_cycle)
    assert len(second_new) == 1, "Only 1 new opportunity in second cycle"
    assert second_new[0].source_opportunity_id == "NSF-2024-002"


def test_dedup_hash_consistency():
    """Verify dedup hash is consistent across identical opportunities."""
    
    opp1 = create_test_opportunity("grants_gov", "TEST-001", "Test Opportunity")
    opp2 = create_test_opportunity("grants_gov", "TEST-001", "Test Opportunity")
    
    assert opp1.dedup_hash == opp2.dedup_hash, "Same source+ID must produce same hash"


def test_dedup_hash_unique_per_source():
    """Verify dedup hash differs for same ID from different sources."""
    
    opp1 = create_test_opportunity("grants_gov", "001", "Test")
    opp2 = create_test_opportunity("sam_gov", "001", "Test")
    
    assert opp1.dedup_hash != opp2.dedup_hash, "Same ID from different sources must produce different hashes"
