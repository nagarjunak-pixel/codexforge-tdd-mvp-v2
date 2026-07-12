"""Unit tests for acp/diff_solver.py"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from acp.diff_solver import three_way_merge, has_conflict_markers


class TestThreeWayMerge:
    """Tests for the three-way merge solver."""

    def test_no_conflict(self):
        """Both sides make compatible changes to different lines."""
        base = "line1\nline2\nline3\n"
        mine = "line1\nmodified_mine\nline3\n"
        other = "line1\nline2\nline3_other\n"
        result = three_way_merge(base, mine, other)
        assert "modified_mine" in result
        assert "line3_other" in result
        assert "<<<<<<" not in result

    def test_identical_changes(self):
        """Both sides make the same change — no conflict."""
        base = "line1\nline2\n"
        mine = "line1\nchanged\n"
        other = "line1\nchanged\n"
        result = three_way_merge(base, mine, other)
        assert "changed" in result
        assert "<<<<<<" not in result

    def test_conflict_detected(self):
        """Both sides modify the same line differently — conflict markers."""
        base = "line1\noriginal\nline3\n"
        mine = "line1\nmine_version\nline3\n"
        other = "line1\nother_version\nline3\n"
        result = three_way_merge(base, mine, other)
        assert "<<<<<<< DEVELOPER_EDIT" in result
        assert "=======" in result
        assert ">>>>>>> AGENT_EDIT" in result
        assert "mine_version" in result
        assert "other_version" in result

    def test_one_side_unchanged(self):
        """Only one side modifies — should take the modification."""
        base = "line1\nline2\n"
        mine = "line1\nline2\n"  # unchanged
        other = "line1\nmodified\n"  # modified
        result = three_way_merge(base, mine, other)
        assert "modified" in result
        assert "<<<<<<" not in result

    def test_empty_base(self):
        """Empty base with additions from both sides."""
        base = ""
        mine = "added_mine\n"
        other = "added_other\n"
        result = three_way_merge(base, mine, other)
        # Both additions should appear (possibly with conflict)
        assert len(result) > 0


class TestHasConflictMarkers:
    """Tests for conflict marker detection."""

    def test_detects_conflict(self):
        text = "line1\n<<<<<<< DEVELOPER_EDIT\na\n=======\nb\n>>>>>>> AGENT_EDIT\n"
        assert has_conflict_markers(text) is True

    def test_clean_text(self):
        text = "line1\nline2\n"
        assert has_conflict_markers(text) is False

    def test_empty_text(self):
        assert has_conflict_markers("") is False
