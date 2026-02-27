"""Post Block Kit messages to Slack with retry logic and dead-letter handling."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .formatters import format_verdict_blocks

logger = logging.getLogger(__name__)


class SlackRetryableError(Exception):
    """Raised on 429 / 5xx so tenacity retries."""
    pass


class SlackPoster:
    """Posts VerdictReport Block Kit messages to Slack with retry + dead-letter."""

    def __init__(
        self,
        bot_token: str | None = None,
        channel: str | None = None,
        supabase_client: Any | None = None,
    ) -> None:
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        self.channel = channel or os.environ.get("SLACK_CHANNEL", "")
        self._db = supabase_client  # supabase Client or None

    # ------------------------------------------------------------------
    # Retry-wrapped HTTP post
    # ------------------------------------------------------------------
    @retry(
        retry=retry_if_exception_type(SlackRetryableError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _post_blocks(self, blocks: list[dict]) -> dict:
        """Post blocks to Slack. Raises SlackRetryableError on 429/5xx."""
        resp = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json",
            },
            json={"channel": self.channel, "blocks": blocks},
            timeout=30,
        )

        if resp.status_code == 429 or resp.status_code >= 500:
            raise SlackRetryableError(
                f"Slack returned {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        if not data.get("ok"):
            # Non-retryable Slack API error (bad token, invalid blocks, etc.)
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")

        return data

    # ------------------------------------------------------------------
    # Public: post a single verdict report
    # ------------------------------------------------------------------
    def post_verdict(self, report: dict) -> bool:
        """Format and post a VerdictReport dict. Returns True on success."""
        blocks = format_verdict_blocks(report)
        opportunity_id = report.get("opportunity_id", "unknown")

        try:
            data = self._post_blocks(blocks)
            logger.info("Posted verdict for %s: ts=%s", opportunity_id, data.get("ts"))
            self._mark_posted(opportunity_id)
            return True
        except (SlackRetryableError, RuntimeError) as exc:
            logger.error("Failed to post verdict for %s: %s", opportunity_id, exc)
            self._write_dead_letter(report, str(exc))
            return False

    # ------------------------------------------------------------------
    # Post a set of blocks directly (used by digest)
    # ------------------------------------------------------------------
    def post_blocks(self, blocks: list[dict]) -> dict:
        """Post arbitrary blocks. Raises on failure."""
        return self._post_blocks(blocks)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _mark_posted(self, opportunity_id: str) -> None:
        if self._db is None:
            return
        try:
            self._db.table("verdict_reports").update(
                {"posted_to_slack_at": datetime.now(timezone.utc).isoformat()}
            ).eq("opportunity_id", opportunity_id).execute()
        except Exception as exc:
            logger.warning("Could not mark posted_to_slack_at for %s: %s", opportunity_id, exc)

    def _write_dead_letter(self, report: dict, error_message: str) -> None:
        if self._db is None:
            return
        try:
            self._db.table("dead_letter_posts").insert({
                "opportunity_id": report.get("opportunity_id", "unknown"),
                "verdict": report.get("verdict", "unknown"),
                "payload": json.dumps(report, default=str),
                "error_message": error_message[:1000],
                "attempts": 3,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_attempted_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as exc:
            logger.error("Could not write dead letter for %s: %s", report.get("opportunity_id"), exc)
