"""
VTK-102 — Evaluate and Clean Dead Branches

Scans remote branches and identifies stale/dead ones based on:
  1. Already merged into main
  2. No commits in 90+ days (configurable)

Outputs a cleanup report with safe deletion commands.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class BranchInfo:
    name: str
    last_commit_date: Optional[datetime] = None
    is_merged: bool = False
    days_inactive: Optional[int] = None
    stale_threshold_days: int = 90

    @property
    def is_stale(self) -> bool:
        return self.days_inactive is not None and self.days_inactive >= self.stale_threshold_days

    @property
    def is_dead(self) -> bool:
        return self.is_merged or self.is_stale

    @property
    def reason(self) -> str:
        reasons = []
        if self.is_merged:
            reasons.append("merged into main")
        if self.is_stale:
            reasons.append(f"inactive {self.days_inactive} days")
        return "; ".join(reasons) if reasons else "active"


@dataclass
class EvaluationReport:
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    branches: List[BranchInfo] = field(default_factory=list)
    stale_threshold_days: int = 90

    @property
    def dead_branches(self) -> List[BranchInfo]:
        return [b for b in self.branches if b.is_dead]

    @property
    def active_branches(self) -> List[BranchInfo]:
        return [b for b in self.branches if not b.is_dead]

    def format_report(self) -> str:
        lines = [
            "=" * 60,
            "BRANCH EVALUATION REPORT",
            f"Generated: {self.evaluated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Stale threshold: {self.stale_threshold_days} days",
            "=" * 60,
            "",
            f"Total remote branches evaluated: {len(self.branches)}",
            f"Dead/stale branches: {len(self.dead_branches)}",
            f"Active branches: {len(self.active_branches)}",
            "",
        ]

        if self.dead_branches:
            lines.append("--- DEAD / STALE BRANCHES ---")
            for b in sorted(self.dead_branches, key=lambda x: x.name):
                date_str = b.last_commit_date.strftime("%Y-%m-%d") if b.last_commit_date else "unknown"
                lines.append(f"  {b.name}")
                lines.append(f"    Last commit: {date_str}  |  Reason: {b.reason}")
            lines.append("")

        if self.active_branches:
            lines.append("--- ACTIVE BRANCHES ---")
            for b in sorted(self.active_branches, key=lambda x: x.name):
                date_str = b.last_commit_date.strftime("%Y-%m-%d") if b.last_commit_date else "unknown"
                lines.append(f"  {b.name}  (last commit: {date_str})")
            lines.append("")

        if self.dead_branches:
            lines.append("--- SAFE DELETION COMMANDS ---")
            lines.append("# Review carefully before running!")
            for b in sorted(self.dead_branches, key=lambda x: x.name):
                lines.append(f"git push origin --delete {b.name}")
            lines.append("")

        return "\n".join(lines)


def _run_git(args: list[str], repo_path: str = ".") -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def list_remote_branches(repo_path: str = ".") -> list[str]:
    output = _run_git(["branch", "-r", "--no-color"], repo_path)
    branches = []
    for line in output.splitlines():
        line = line.strip()
        if "->" in line:
            continue
        name = re.sub(r"^origin/", "", line)
        if name == "main":
            continue
        branches.append(name)
    return branches


def get_merged_branches(repo_path: str = ".", target: str = "origin/main") -> set[str]:
    output = _run_git(["branch", "-r", "--merged", target, "--no-color"], repo_path)
    merged = set()
    for line in output.splitlines():
        line = line.strip()
        if "->" in line:
            continue
        name = re.sub(r"^origin/", "", line)
        if name == "main":
            continue
        merged.add(name)
    return merged


def get_last_commit_date(branch: str, repo_path: str = ".") -> Optional[datetime]:
    try:
        output = _run_git(["log", "-1", "--format=%aI", f"origin/{branch}"], repo_path)
        if output:
            return datetime.fromisoformat(output)
    except (RuntimeError, ValueError):
        pass
    return None


def evaluate_branches(
    repo_path: str = ".",
    stale_threshold_days: int = 90,
    now: Optional[datetime] = None,
) -> EvaluationReport:
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        _run_git(["fetch", "--prune"], repo_path)
    except RuntimeError:
        pass

    branches = list_remote_branches(repo_path)
    merged = get_merged_branches(repo_path)

    report = EvaluationReport(evaluated_at=now, stale_threshold_days=stale_threshold_days)

    for name in branches:
        last_date = get_last_commit_date(name, repo_path)
        days_inactive = None
        if last_date:
            days_inactive = (now - last_date).days

        report.branches.append(BranchInfo(
            name=name,
            last_commit_date=last_date,
            is_merged=name in merged,
            days_inactive=days_inactive,
            stale_threshold_days=stale_threshold_days,
        ))

    return report


def main(repo_path: str = ".", stale_threshold_days: int = 90) -> None:
    report = evaluate_branches(repo_path, stale_threshold_days)
    print(report.format_report())


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    main(path, days)
