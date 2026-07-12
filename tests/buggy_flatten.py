"""Buggy flatten function — Example 5: Nested List Flattening

Bug: The flatten function only handles one level of nesting.
     [1, [2, [3, 4]], 5] returns [1, 2, [3, 4], 5] instead of [1, 2, 3, 4, 5].

Requirement: Recursively flatten arbitrarily nested lists while preserving
             element order.
"""


def flatten(lst):
    """Flatten a nested list into a single-level list.

    Bug: Only handles one level of nesting (not recursive).
    Requirement: Must recursively flatten all levels.
    """
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(item)  # Bug: only one level deep
        else:
            result.append(item)
    return result
