def format_count(value):
    """Keep exact integers in the game; truncate large display values to three digits."""
    if abs(value) < 1_000_000:
        return f"{value:,}"
    digits = str(abs(value))
    fraction = digits[1:3].rstrip("0")
    mantissa = digits[0] + (f".{fraction}" if fraction else "")
    return f"{'-' if value < 0 else ''}{mantissa}E+{len(digits) - 1}"
