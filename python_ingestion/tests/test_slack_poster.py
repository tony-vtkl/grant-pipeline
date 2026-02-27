"""Tests for slack_poster module (VTK-107).

Covers:
  1. GO Block Kit shape — includes emoji, score, title, deadline, summary, risk, CTA
  2. NO-GO abbreviated — only emoji, score, title, risk (no summary, no deadline, no CTA)
  3. Retry on 429 — SlackPoster retries and eventually fails to dead_letter
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

# Adjust path so imports work when running from python_ingestion/
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slack_poster.formatters import format_verdict_blocks
from slack_poster.poster import SlackPoster, SlackRetryableError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _go_report() -> dict:
    return {
        "opportunity_id": "TEST-GO-001",
        "verdict": "GO",
        "composite_score": 85.5,
        "title": "AI Healthcare Grant",
        "response_deadline": "2026-06-15T00:00:00",
        "executive_summary": "Strong fit for VTKL capabilities.",
        "risk_assessment": "Timeline is tight but manageable.",
    }


def _nogo_report() -> dict:
    return {
        "opportunity_id": "TEST-NOGO-001",
        "verdict": "NO-GO",
        "composite_score": 22.0,
        "title": "Restricted Program",
        "risk_assessment": "Missing 8(a) certification.",
    }


# ---------------------------------------------------------------------------
# Test 1: GO Block Kit shape
# ---------------------------------------------------------------------------

class TestGoBlockKitShape:
    def test_go_has_required_elements(self):
        blocks = format_verdict_blocks(_go_report())

        # Flatten all text content for easy assertion
        all_text = json.dumps(blocks, ensure_ascii=False)

        # Must include emoji, score, title, deadline, summary, risk, CTA
        assert "🟢" in all_text, "GO must include 🟢 emoji"
        assert "85.5" in all_text, "GO must include composite score"
        assert "AI Healthcare Grant" in all_text, "GO must include title"
        assert "Jun 15, 2026" in all_text, "GO must include formatted deadline"
        assert "Strong fit" in all_text, "GO must include executive summary"
        assert "Timeline is tight" in all_text, "GO must include risk assessment"

        # CTA button
        actions_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions_blocks) >= 1, "GO must include Human Decision Required CTA"
        button_text = json.dumps(actions_blocks)
        assert "Human Decision Required" in button_text

    def test_go_has_header(self):
        blocks = format_verdict_blocks(_go_report())
        headers = [b for b in blocks if b.get("type") == "header"]
        assert len(headers) >= 1
        assert "GO" in headers[0]["text"]["text"]


# ---------------------------------------------------------------------------
# Test 2: NO-GO abbreviated
# ---------------------------------------------------------------------------

class TestNoGoAbbreviated:
    def test_nogo_has_only_required_fields(self):
        blocks = format_verdict_blocks(_nogo_report())
        all_text = json.dumps(blocks, ensure_ascii=False)

        # Must include emoji, score, title, risk
        assert "🔴" in all_text, "NO-GO must include 🔴 emoji"
        assert "22.0" in all_text or "22" in all_text, "NO-GO must include score"
        assert "Restricted Program" in all_text, "NO-GO must include title"
        assert "Missing 8(a)" in all_text, "NO-GO must include risk"

        # Must NOT include executive summary or CTA
        actions_blocks = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions_blocks) == 0, "NO-GO must NOT include CTA button"

        # No executive_summary field text (wasn't provided, shouldn't appear)
        assert "Executive Summary" not in all_text, "NO-GO must NOT include executive summary section"


# ---------------------------------------------------------------------------
# Test 3: Retry on 429
# ---------------------------------------------------------------------------

class TestRetryOn429:
    @respx.mock
    def test_429_triggers_retry_and_dead_letter(self):
        """SlackPoster retries 3x on 429, then writes to dead_letter_posts."""
        # Mock Slack API returning 429 every time
        route = respx.post("https://slack.com/api/chat.postMessage").mock(
            return_value=httpx.Response(429, text="rate_limited")
        )

        # Mock DB client
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        poster = SlackPoster(
            bot_token="xoxb-test-token",
            channel="C0TEST",
            supabase_client=mock_db,
        )

        report = _go_report()
        result = poster.post_verdict(report)

        # Should fail after retries
        assert result is False, "Should return False after exhausting retries"

        # Should have retried 3 times
        assert route.call_count == 3, f"Expected 3 attempts, got {route.call_count}"

        # Should have written to dead_letter_posts
        mock_db.table.assert_any_call("dead_letter_posts")
