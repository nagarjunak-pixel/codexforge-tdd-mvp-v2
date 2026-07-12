def parse_csv_line(line):
    """Parse a single CSV line into a list of field values.

    Bug: Splits on ALL commas, including those inside quoted fields.
    Requirement: Commas inside double-quoted fields should not split.
    Example: 'a,"hello, world",c' should produce ["a", "hello, world", "c"]
             but this implementation produces ["a", '"hello', ' world"', "c"]
    """
    return line.split(",")
