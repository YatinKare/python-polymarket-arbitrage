"""Number formatting utilities for tables and reports."""

from typing import Optional


def format_percent(value: float, decimals: int = 2, include_sign: bool = False) -> str:
    """
    Format a decimal value as a percentage string.

    Args:
        value: Decimal value (e.g., 0.05 for 5%)
        decimals: Number of decimal places
        include_sign: Whether to include '+' for positive values

    Returns:
        Formatted percentage string (e.g., "5.00%")
    """
    pct = value * 100
    if include_sign and pct > 0:
        return f"+{pct:.{decimals}f}%"
    return f"{pct:.{decimals}f}%"


def format_price(value: float, decimals: int = 4) -> str:
    """
    Format a price value (typically in [0, 1] range for Polymarket).

    Args:
        value: Price value
        decimals: Number of decimal places

    Returns:
        Formatted price string
    """
    return f"{value:.{decimals}f}"


def format_dollar(value: float, decimals: int = 2, include_dollar_sign: bool = True) -> str:
    """
    Format a value as US dollars.

    Args:
        value: Dollar amount
        decimals: Number of decimal places
        include_dollar_sign: Whether to include '$' prefix

    Returns:
        Formatted dollar string
    """
    formatted = f"{value:,.{decimals}f}"
    if include_dollar_sign:
        return f"${formatted}"
    return formatted


def format_number(value: float, decimals: int = 2, scientific: bool = False) -> str:
    """
    Format a general number with specified precision.

    Args:
        value: Numeric value
        decimals: Number of decimal places
        scientific: Whether to use scientific notation for very large/small values

    Returns:
        Formatted number string
    """
    if scientific and (abs(value) >= 1e6 or (abs(value) < 0.001 and value != 0)):
        return f"{value:.{decimals}e}"
    return f"{value:.{decimals}f}"


def format_probability(value: float, decimals: int = 4) -> str:
    """
    Format a probability value (in [0, 1] range).

    Args:
        value: Probability value
        decimals: Number of decimal places

    Returns:
        Formatted probability string
    """
    return f"{value:.{decimals}f}"


def format_bps(value: float, decimals: int = 1) -> str:
    """
    Format a decimal value as basis points.

    Args:
        value: Decimal value (e.g., 0.0005 for 5 bps)
        decimals: Number of decimal places

    Returns:
        Formatted basis points string (e.g., "5.0 bps")
    """
    bps = value * 10000
    return f"{bps:.{decimals}f} bps"


def format_table_row(values: list, widths: list[int], align: Optional[list[str]] = None) -> str:
    """
    Format a row of values for a markdown table.

    Args:
        values: List of values to format
        widths: List of column widths
        align: List of alignment specifiers ('left', 'right', 'center') per column

    Returns:
        Formatted table row string with '|' separators
    """
    if align is None:
        align = ['left'] * len(values)

    if len(values) != len(widths) or len(values) != len(align):
        raise ValueError("values, widths, and align must have the same length")

    formatted_cells = []
    for value, width, alignment in zip(values, widths, align):
        cell_str = str(value)
        if alignment == 'right':
            cell = cell_str.rjust(width)
        elif alignment == 'center':
            cell = cell_str.center(width)
        else:  # left
            cell = cell_str.ljust(width)
        formatted_cells.append(cell)

    return "| " + " | ".join(formatted_cells) + " |"


def format_markdown_table(headers: list[str], rows: list[list], align: Optional[list[str]] = None) -> str:
    """
    Format a complete markdown table.

    Args:
        headers: List of header strings
        rows: List of rows (each row is a list of values)
        align: List of alignment specifiers per column ('left', 'right', 'center')

    Returns:
        Complete markdown table as a string
    """
    if align is None:
        align = ['left'] * len(headers)

    if len(headers) != len(align):
        raise ValueError("headers and align must have the same length")

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Build table
    lines = []

    # Header row
    lines.append(format_table_row(headers, widths, align))

    # Separator row
    separators = []
    for width, alignment in zip(widths, align):
        if alignment == 'right':
            sep = '-' * (width - 1) + ':'
        elif alignment == 'center':
            sep = ':' + '-' * (width - 2) + ':'
        else:  # left
            sep = '-' * width
        separators.append(sep)
    lines.append("| " + " | ".join(separators) + " |")

    # Data rows
    for row in rows:
        lines.append(format_table_row(row, widths, align))

    return "\n".join(lines)
