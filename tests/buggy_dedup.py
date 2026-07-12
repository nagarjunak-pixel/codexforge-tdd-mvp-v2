def deduplicate(items):
    """Remove duplicates from a list.

    Bug: Uses set() which does not preserve insertion order in the output.
    Requirement: Must preserve the order of first occurrence.
    Example: [3, 1, 4, 1, 5] should produce [3, 1, 4, 5]
             but this implementation may produce [1, 3, 4, 5] (sorted set).
    """
    return sorted(set(items))
