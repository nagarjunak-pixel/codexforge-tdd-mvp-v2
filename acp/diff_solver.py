"""
CodexForge Diff3 Three-Way Merge Solver — v2

Performs line-level three-way merge between:
  - base: original source code
  - mine: developer's current local version
  - other: agent's proposed version

Produces a merged result with git-style conflict markers when
non-overlapping changes cannot be auto-resolved.
"""

import difflib
from typing import List, Tuple


def three_way_merge(base: str, mine: str, other: str) -> str:
    """
    Performs a line-level three-way merge.

    Args:
        base: Original source code (common ancestor).
        mine: Developer's current local version.
        other: Agent's proposed version.

    Returns:
        Merged text. Contains git-style conflict markers if conflicts exist.
    """
    # Trivial cases
    if mine == other:
        return mine
    if base == other:
        return mine  # Only developer changed
    if base == mine:
        return other  # Only agent changed

    base_lines = base.splitlines()
    mine_lines = mine.splitlines()
    other_lines = other.splitlines()

    # Compute opcodes for base→mine and base→other
    sm_mine = difflib.SequenceMatcher(None, base_lines, mine_lines)
    sm_other = difflib.SequenceMatcher(None, base_lines, other_lines)

    mine_ops = sm_mine.get_opcodes()
    other_ops = sm_other.get_opcodes()

    # Build change maps: for each base line index, track what mine and other did
    mine_changes = _build_change_map(base_lines, mine_lines, mine_ops)
    other_changes = _build_change_map(base_lines, other_lines, other_ops)

    merged = []
    has_conflicts = False

    for i in range(len(base_lines)):
        m_action, m_lines = mine_changes.get(i, ("keep", [base_lines[i]]))
        o_action, o_lines = other_changes.get(i, ("keep", [base_lines[i]]))

        if m_action == "keep" and o_action == "keep":
            merged.append(base_lines[i])
        elif m_action == "keep" and o_action != "keep":
            # Only other changed this line
            merged.extend(o_lines)
        elif m_action != "keep" and o_action == "keep":
            # Only mine changed this line
            merged.extend(m_lines)
        elif m_lines == o_lines:
            # Both changed to the same thing
            merged.extend(m_lines)
        else:
            # Conflict: both changed differently
            has_conflicts = True
            merged.append("<<<<<<< DEVELOPER_EDIT")
            merged.extend(m_lines)
            merged.append("=======")
            merged.extend(o_lines)
            merged.append(">>>>>>> AGENT_EDIT")

    # Handle trailing lines added beyond base length
    mine_trailing = mine_lines[len(base_lines):]
    other_trailing = other_lines[len(base_lines):]

    if mine_trailing and other_trailing:
        if mine_trailing == other_trailing:
            merged.extend(mine_trailing)
        else:
            has_conflicts = True
            merged.append("<<<<<<< DEVELOPER_EDIT")
            merged.extend(mine_trailing)
            merged.append("=======")
            merged.extend(other_trailing)
            merged.append(">>>>>>> AGENT_EDIT")
    elif mine_trailing:
        merged.extend(mine_trailing)
    elif other_trailing:
        merged.extend(other_trailing)

    return "\n".join(merged)


def has_conflict_markers(text: str) -> bool:
    """Check if merged text contains unresolved conflict markers."""
    return "<<<<<<< DEVELOPER_EDIT" in text


def _build_change_map(
    base_lines: List[str],
    changed_lines: List[str],
    opcodes: List[Tuple]
) -> dict:
    """
    Build a map from base line index to (action, replacement_lines).

    Actions: "keep", "replace", "delete"
    """
    change_map = {}

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for idx in range(i1, i2):
                change_map[idx] = ("keep", [base_lines[idx]])
        elif tag == "replace":
            # Map replaced lines
            replacement = changed_lines[j1:j2]
            for k, idx in enumerate(range(i1, i2)):
                if k == 0:
                    # First replaced line gets all new lines
                    change_map[idx] = ("replace", replacement)
                else:
                    # Subsequent replaced lines are consumed
                    change_map[idx] = ("delete", [])
        elif tag == "delete":
            for idx in range(i1, i2):
                change_map[idx] = ("delete", [])
        elif tag == "insert":
            # Inserts happen before a base line; attach to preceding line
            if i1 > 0 and (i1 - 1) in change_map:
                action, lines = change_map[i1 - 1]
                change_map[i1 - 1] = (action, lines + changed_lines[j1:j2])

    return change_map


# CLI test
if __name__ == "__main__":
    # Test 1: Non-overlapping changes
    base = "line1\nline2\nline3\nline4"
    mine = "line1\nmine_changed\nline3\nline4"
    other = "line1\nline2\nline3\nother_changed"

    result = three_way_merge(base, mine, other)
    print("Test 1 (non-overlapping):")
    print(result)
    assert "mine_changed" in result
    assert "other_changed" in result
    assert not has_conflict_markers(result)
    print("PASSED\n")

    # Test 2: Conflicting changes
    base2 = "line1\nline2\nline3"
    mine2 = "line1\nmine_version\nline3"
    other2 = "line1\nother_version\nline3"

    result2 = three_way_merge(base2, mine2, other2)
    print("Test 2 (conflict):")
    print(result2)
    assert has_conflict_markers(result2)
    print("PASSED\n")

    # Test 3: Only one side changed
    result3 = three_way_merge(base, mine, base)
    print("Test 3 (only mine changed):")
    print(result3)
    assert result3 == mine
    print("PASSED\n")

    print("All diff solver tests passed!")
