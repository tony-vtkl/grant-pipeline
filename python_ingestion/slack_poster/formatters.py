"""Block Kit formatters for each verdict type."""

from __future__ import annotations

from datetime import datetime
from typing import Any


VERDICT_EMOJI = {
    "GO": "🟢",
    "SHAPE": "🟡",
    "MONITOR": "🟠",
    "NO-GO": "🔴",
}


def _header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}


def _divider() -> dict:
    return {"type": "divider"}


def _section(mrkdwn: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": mrkdwn}}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def _actions_cta(text: str = "Human Decision Required") -> dict:
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": text, "emoji": True},
                "style": "primary",
                "action_id": "human_decision_required",
            }
        ],
    }


def _fmt_date(iso: str | datetime | None) -> str:
    if iso is None:
        return "TBD"
    if isinstance(iso, datetime):
        return iso.strftime("%b %d, %Y")
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y")
    except Exception:
        return str(iso)[:10]


# ---------------------------------------------------------------------------
# Per-verdict formatters
# ---------------------------------------------------------------------------

def _format_go(report: dict) -> list[dict]:
    emoji = VERDICT_EMOJI["GO"]
    score = report.get("composite_score", "?")
    title = report.get("title", report.get("opportunity_id", "Unknown"))
    deadline = _fmt_date(report.get("response_deadline"))
    summary = report.get("executive_summary", "")
    risk = report.get("risk_assessment", "")

    blocks = [
        _header(f"{emoji} GO — {title}"),
        _section(f"*Score:* {score}/100  •  *Deadline:* {deadline}"),
        _section(f"*Executive Summary*\n{summary}"),
        _section(f"*Risk Assessment*\n{risk}"),
        _actions_cta("Human Decision Required"),
        _divider(),
    ]
    return blocks


def _format_shape(report: dict) -> list[dict]:
    emoji = VERDICT_EMOJI["SHAPE"]
    score = report.get("composite_score", "?")
    title = report.get("title", report.get("opportunity_id", "Unknown"))
    deadline = _fmt_date(report.get("response_deadline"))
    summary = report.get("executive_summary", "")
    risk = report.get("risk_assessment", "")

    blocks = [
        _header(f"{emoji} SHAPE — {title}"),
        _section(f"*Score:* {score}/100  •  *Deadline:* {deadline}"),
        _section(f"*Executive Summary*\n{summary}"),
        _section(f"*Risk Assessment*\n{risk}"),
        _divider(),
    ]
    return blocks


def _format_monitor(report: dict) -> list[dict]:
    emoji = VERDICT_EMOJI["MONITOR"]
    score = report.get("composite_score", "?")
    title = report.get("title", report.get("opportunity_id", "Unknown"))
    deadline = _fmt_date(report.get("response_deadline"))
    risk = report.get("risk_assessment", "")

    blocks = [
        _header(f"{emoji} MONITOR — {title}"),
        _section(f"*Score:* {score}/100  •  *Deadline:* {deadline}"),
        _section(f"*Risk Assessment*\n{risk}"),
        _divider(),
    ]
    return blocks


def _format_nogo(report: dict) -> list[dict]:
    emoji = VERDICT_EMOJI["NO-GO"]
    score = report.get("composite_score", "?")
    title = report.get("title", report.get("opportunity_id", "Unknown"))
    risk = report.get("risk_assessment", "")

    blocks = [
        _header(f"{emoji} NO-GO — {title}"),
        _section(f"*Score:* {score}/100  •  *Title:* {title}"),
        _section(f"*Risk Assessment*\n{risk}"),
        _divider(),
    ]
    return blocks


_FORMATTERS = {
    "GO": _format_go,
    "SHAPE": _format_shape,
    "MONITOR": _format_monitor,
    "NO-GO": _format_nogo,
}


def format_verdict_blocks(report: dict) -> list[dict]:
    """Return Slack Block Kit blocks for a single VerdictReport dict."""
    verdict = report.get("verdict", "").upper()
    formatter = _FORMATTERS.get(verdict, _format_nogo)
    return formatter(report)


# ---------------------------------------------------------------------------
# Daily digest
# ---------------------------------------------------------------------------

def format_digest_blocks(reports: list[dict], date_str: str | None = None) -> list[dict]:
    """Build a daily digest summary of verdicts."""
    if date_str is None:
        date_str = datetime.utcnow().strftime("%b %d, %Y")

    counts: dict[str, int] = {"GO": 0, "SHAPE": 0, "MONITOR": 0, "NO-GO": 0}
    top_reports: list[dict] = sorted(reports, key=lambda r: r.get("composite_score", 0), reverse=True)

    for r in reports:
        v = r.get("verdict", "").upper()
        if v in counts:
            counts[v] += 1

    blocks: list[dict] = [
        _header(f"📊 Daily Verdict Digest — {date_str}"),
        _divider(),
        _section(
            f"*{VERDICT_EMOJI['GO']} GO:* {counts['GO']}  |  "
            f"*{VERDICT_EMOJI['SHAPE']} SHAPE:* {counts['SHAPE']}  |  "
            f"*{VERDICT_EMOJI['MONITOR']} MONITOR:* {counts['MONITOR']}  |  "
            f"*{VERDICT_EMOJI['NO-GO']} NO-GO:* {counts['NO-GO']}"
        ),
        _divider(),
    ]

    for r in top_reports[:10]:
        emoji = VERDICT_EMOJI.get(r.get("verdict", "").upper(), "❓")
        title = r.get("title", r.get("opportunity_id", "?"))[:80]
        score = r.get("composite_score", "?")
        blocks.append(_section(f"{emoji} *{title}* — Score: {score}/100"))

    blocks.append(_context(f"Total reports: {len(reports)} | Generated: {date_str}"))
    return blocks
