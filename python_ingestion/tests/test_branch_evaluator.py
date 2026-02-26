"""Tests for VTK-102 branch evaluator."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from branch_evaluator.evaluator import (
    BranchInfo,
    EvaluationReport,
    evaluate_branches,
    list_remote_branches,
)


class TestBranchInfo:
    def test_active_branch(self):
        b = BranchInfo(name="feature/x", days_inactive=10, is_merged=False)
        assert not b.is_stale
        assert not b.is_dead
        assert b.reason == "active"

    def test_stale_branch(self):
        b = BranchInfo(name="old/thing", days_inactive=91, is_merged=False)
        assert b.is_stale
        assert b.is_dead
        assert "inactive 91 days" in b.reason

    def test_merged_branch(self):
        b = BranchInfo(name="done/pr", days_inactive=5, is_merged=True)
        assert b.is_dead
        assert "merged into main" in b.reason

    def test_merged_and_stale(self):
        b = BranchInfo(name="ancient", days_inactive=200, is_merged=True)
        assert "merged" in b.reason
        assert "inactive" in b.reason

    def test_exactly_90_days_is_stale(self):
        b = BranchInfo(name="edge", days_inactive=90, is_merged=False)
        assert b.is_stale

    def test_89_days_is_not_stale(self):
        b = BranchInfo(name="edge", days_inactive=89, is_merged=False)
        assert not b.is_stale

    def test_custom_threshold(self):
        b = BranchInfo(name="x", days_inactive=30, stale_threshold_days=25)
        assert b.is_stale
        b2 = BranchInfo(name="x", days_inactive=30, stale_threshold_days=60)
        assert not b2.is_stale


class TestEvaluationReport:
    def _make_report(self):
        now = datetime(2026, 2, 26, tzinfo=timezone.utc)
        return EvaluationReport(
            evaluated_at=now,
            stale_threshold_days=90,
            branches=[
                BranchInfo("active/a", datetime(2026, 2, 1, tzinfo=timezone.utc), False, 25),
                BranchInfo("merged/b", datetime(2025, 12, 1, tzinfo=timezone.utc), True, 87),
                BranchInfo("stale/c", datetime(2025, 6, 1, tzinfo=timezone.utc), False, 270),
            ],
        )

    def test_dead_branches_count(self):
        r = self._make_report()
        assert len(r.dead_branches) == 2

    def test_active_branches_count(self):
        r = self._make_report()
        assert len(r.active_branches) == 1

    def test_report_contains_deletion_commands(self):
        r = self._make_report()
        text = r.format_report()
        assert "git push origin --delete merged/b" in text
        assert "git push origin --delete stale/c" in text
        assert "git push origin --delete active/a" not in text

    def test_report_header(self):
        r = self._make_report()
        text = r.format_report()
        assert "BRANCH EVALUATION REPORT" in text

    def test_empty_report(self):
        r = EvaluationReport()
        text = r.format_report()
        assert "Dead/stale branches: 0" in text


class TestEvaluateBranches:
    @patch("branch_evaluator.evaluator._run_git")
    def test_identifies_stale_and_merged(self, mock_git):
        now = datetime(2026, 2, 26, 12, 0, 0, tzinfo=timezone.utc)

        def side_effect(args, repo_path="."):
            cmd = " ".join(args)
            if "fetch" in cmd:
                return ""
            if "branch -r --merged" in cmd:
                return "  origin/fc/alpha/merged-one\n  origin/main"
            if "branch -r" in cmd:
                return (
                    "  origin/HEAD -> origin/main\n"
                    "  origin/main\n"
                    "  origin/fc/alpha/merged-one\n"
                    "  origin/fc/beta/active\n"
                    "  origin/fc/gamma/ancient"
                )
            if "log" in cmd:
                if "merged-one" in cmd:
                    return "2026-02-20T10:00:00+00:00"
                if "active" in cmd:
                    return "2026-02-25T10:00:00+00:00"
                if "ancient" in cmd:
                    return "2025-06-01T10:00:00+00:00"
            return ""

        mock_git.side_effect = side_effect
        report = evaluate_branches("/fake", stale_threshold_days=90, now=now)

        assert len(report.branches) == 3
        dead_names = {b.name for b in report.dead_branches}
        assert "fc/alpha/merged-one" in dead_names
        assert "fc/gamma/ancient" in dead_names
        assert "fc/beta/active" not in dead_names

    @patch("branch_evaluator.evaluator._run_git")
    def test_no_branches(self, mock_git):
        def side_effect(args, repo_path="."):
            cmd = " ".join(args)
            if "fetch" in cmd:
                return ""
            if "branch -r --merged" in cmd:
                return "  origin/main"
            if "branch -r" in cmd:
                return "  origin/HEAD -> origin/main\n  origin/main"
            return ""

        mock_git.side_effect = side_effect
        report = evaluate_branches("/fake", now=datetime.now(timezone.utc))
        assert len(report.branches) == 0

    @patch("branch_evaluator.evaluator._run_git")
    def test_custom_threshold(self, mock_git):
        now = datetime(2026, 2, 26, tzinfo=timezone.utc)

        def side_effect(args, repo_path="."):
            cmd = " ".join(args)
            if "fetch" in cmd:
                return ""
            if "branch -r --merged" in cmd:
                return "  origin/main"
            if "branch -r" in cmd:
                return "  origin/HEAD -> origin/main\n  origin/main\n  origin/fc/x"
            if "log" in cmd:
                return "2026-02-01T00:00:00+00:00"
            return ""

        mock_git.side_effect = side_effect

        report90 = evaluate_branches("/fake", stale_threshold_days=90, now=now)
        assert len(report90.dead_branches) == 0

        report20 = evaluate_branches("/fake", stale_threshold_days=20, now=now)
        assert len(report20.dead_branches) == 1
        assert report20.dead_branches[0].name == "fc/x"


class TestListRemoteBranches:
    @patch("branch_evaluator.evaluator._run_git")
    def test_filters_head_and_main(self, mock_git):
        mock_git.return_value = (
            "  origin/HEAD -> origin/main\n"
            "  origin/main\n"
            "  origin/feature/x"
        )
        result = list_remote_branches("/fake")
        assert result == ["feature/x"]
