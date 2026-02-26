#!/usr/bin/env python3
"""Daily digest: post new grants discovered in the last 24h to Slack.

Usage:
    # Via webhook (default, no bot token needed):
    SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
    SUPABASE_URL="https://yccaskvyabzkzkipwodg.supabase.co" \
    SUPABASE_KEY="..." \
    python3 slack_daily_digest.py

    # Via bot token (posts to specific channel):
    SLACK_BOT_TOKEN="xoxb-..." \
    SLACK_CHANNEL="C09P3R0MBAA" \
    SUPABASE_URL="https://yccaskvyabzkzkipwodg.supabase.co" \
    SUPABASE_KEY="..." \
    python3 slack_daily_digest.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from supabase import create_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "C09P3R0MBAA")
TOP_N = 15


def fetch_new_grants() -> tuple[list[dict], int]:
    """Return (recent grants sorted by deadline, total DB count)."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    resp = (
        client.table("grant_opportunities")
        .select("title, agency, response_deadline, source_url, source")
        .gte("first_detected_at", since)
        .order("response_deadline", desc=False)  # nearest deadlines first
        .limit(TOP_N)
        .execute()
    )
    grants = resp.data or []

    # Total count
    count_resp = (
        client.table("grant_opportunities")
        .select("id", count="exact")
        .execute()
    )
    total = count_resp.count if count_resp.count is not None else len(count_resp.data)

    return grants, total


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "TBD"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(iso)[:10]


def build_blocks(grants: list[dict], total: int) -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    n = len(grants)

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔔 {n} novas grants descobertas — {today}",
                "emoji": True,
            },
        },
        {"type": "divider"},
    ]

    for g in grants:
        title = g.get("title", "Untitled")[:120]
        agency = g.get("agency", "Unknown").strip()
        deadline = fmt_date(g.get("response_deadline"))
        url = g.get("source_url", "")
        source = g.get("source", "").replace("_", ".")

        text = f"*<{url}|{title}>*\n🏛️ {agency}  •  📅 Deadline: {deadline}  •  🔗 {source}"
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            }
        )

    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Total no DB: *{total}* | Fontes: Grants.gov, SAM.gov",
                }
            ],
        }
    )

    return blocks


def post_to_slack(blocks: list[dict]) -> None:
    payload: dict = {"blocks": blocks}

    if SLACK_BOT_TOKEN:
        # Bot token approach
        payload["channel"] = SLACK_CHANNEL
        r = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        data = r.json()
        if not data.get("ok"):
            print(f"Slack API error: {data}", file=sys.stderr)
            sys.exit(1)
        print(f"Posted via bot token to #{SLACK_CHANNEL}: ts={data.get('ts')}")

    elif SLACK_WEBHOOK_URL:
        # Webhook approach
        r = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=30)
        if r.status_code != 200 or r.text != "ok":
            print(f"Webhook error ({r.status_code}): {r.text}", file=sys.stderr)
            sys.exit(1)
        print(f"Posted via webhook: {r.status_code}")

    else:
        # Dry run — print blocks as JSON
        print("No SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL set. Dry run:")
        print(json.dumps(blocks, indent=2, ensure_ascii=False))


def main():
    grants, total = fetch_new_grants()
    if not grants:
        print("No new grants in the last 24h. Skipping.")
        return

    blocks = build_blocks(grants, total)
    post_to_slack(blocks)


if __name__ == "__main__":
    main()
