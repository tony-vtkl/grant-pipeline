"""Tests for database.client (SupabaseClient).

Mocks are used here in tests only — production code uses real Supabase calls (DoD 3.1).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from database.client import SupabaseClient
from models.grant_opportunity import GrantOpportunity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase_client():
    """Patch create_client so no real network call is made."""
    with patch("database.client.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        client = SupabaseClient(url="https://fake.supabase.co", key="fake-key")
        yield client, mock_client


@pytest.fixture
def sample_grant() -> GrantOpportunity:
    return GrantOpportunity(
        source="sam_gov",
        source_opportunity_id="SAM-001",
        dedup_hash="abc123hash",
        title="Test Grant",
        agency="Test Agency",
        source_url="https://example.com/grant",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetExistingHashes:
    def test_returns_set_of_hashes(self, mock_supabase_client):
        client, mock_sb = mock_supabase_client
        mock_response = MagicMock()
        mock_response.data = [
            {"dedup_hash": "hash1"},
            {"dedup_hash": "hash2"},
            {"dedup_hash": "hash3"},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_response

        result = client.get_existing_hashes()

        assert isinstance(result, set)
        assert result == {"hash1", "hash2", "hash3"}
        mock_sb.table.assert_called_with("grant_opportunities")

    def test_returns_empty_set_when_no_rows(self, mock_supabase_client):
        client, mock_sb = mock_supabase_client
        mock_response = MagicMock()
        mock_response.data = []
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_response

        result = client.get_existing_hashes()

        assert result == set()


class TestUpsertGrant:
    def test_upserts_grant_record(self, mock_supabase_client, sample_grant):
        client, mock_sb = mock_supabase_client
        mock_response = MagicMock()
        mock_response.data = [{"dedup_hash": "abc123hash", "id": 1}]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = mock_response

        result = client.upsert_grant(sample_grant)

        assert result["dedup_hash"] == "abc123hash"
        mock_sb.table.assert_called_with("grant_opportunities")
        call_args = mock_sb.table.return_value.upsert.call_args
        assert call_args[1]["on_conflict"] == "dedup_hash"


class TestSavePipelineRun:
    def test_persists_run_metadata(self, mock_supabase_client):
        client, mock_sb = mock_supabase_client
        mock_response = MagicMock()
        mock_response.data = [{"id": 42, "status": "completed"}]
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_response

        now = datetime.now(timezone.utc)
        result = client.save_pipeline_run(
            started_at=now,
            completed_at=now,
            grants_processed=10,
            grants_new=5,
            grants_updated=3,
            errors=["some error"],
            status="completed",
        )

        assert result["status"] == "completed"
        mock_sb.table.assert_called_with("pipeline_runs")
        insert_data = mock_sb.table.return_value.insert.call_args[0][0]
        assert insert_data["grants_processed"] == 10
        assert insert_data["grants_new"] == 5
        assert insert_data["grants_updated"] == 3
        assert insert_data["errors"] == ["some error"]

    def test_defaults_errors_to_empty_list(self, mock_supabase_client):
        client, mock_sb = mock_supabase_client
        mock_response = MagicMock()
        mock_response.data = [{"id": 43}]
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_response

        now = datetime.now(timezone.utc)
        client.save_pipeline_run(
            started_at=now,
            completed_at=now,
            grants_processed=0,
            grants_new=0,
            grants_updated=0,
        )

        insert_data = mock_sb.table.return_value.insert.call_args[0][0]
        assert insert_data["errors"] == []
        assert insert_data["status"] == "completed"
