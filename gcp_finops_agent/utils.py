"""Utility functions for formatting and conversions."""


def format_bytes(bytes_value: float, precision: int = 2) -> str:
    """Convert bytes to human-readable format.

    Args:
        bytes_value: Number of bytes
        precision: Decimal places to show

    Returns:
        Formatted string like "1.23 GB"
    """
    if bytes_value < 0:
        return f"{bytes_value} bytes"

    units = ["bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    unit_index = 0
    value = float(bytes_value)

    while value >= 1024.0 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1

    if unit_index == 0:
        # Don't show decimals for bytes
        return f"{int(value)} {units[unit_index]}"

    return f"{value:.{precision}f} {units[unit_index]}"


def format_usage_amount(amount: float, unit: str) -> str:
    """Format usage amount based on unit type.

    Args:
        amount: Usage amount
        unit: Usage unit (e.g., "byte-seconds", "bytes", "requests")

    Returns:
        Formatted string
    """
    if not unit or not amount:
        return f"{amount:,.0f}"

    unit_lower = unit.lower()

    # Handle byte-based units
    if "byte" in unit_lower:
        if "second" in unit_lower:
            # byte-seconds: show as "X GB-seconds"
            return f"{format_bytes(amount)}-seconds"
        else:
            return format_bytes(amount)

    # Handle other units
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M {unit}"
    elif amount >= 1_000:
        return f"{amount / 1_000:.2f}K {unit}"
    else:
        return f"{amount:,.2f} {unit}"
