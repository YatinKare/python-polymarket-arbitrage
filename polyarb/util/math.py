"""Mathematical helper functions for log, exp, and clamping operations."""

import math
from typing import Union


def safe_log(x: float, min_value: float = 1e-10) -> float:
    """
    Compute natural logarithm with protection against invalid inputs.

    Args:
        x: Value to take log of
        min_value: Minimum value to clamp x to (prevents log(0) or log(negative))

    Returns:
        Natural logarithm of max(x, min_value)
    """
    return math.log(max(x, min_value))


def safe_exp(x: float, max_input: float = 700.0) -> float:
    """
    Compute exponential with protection against overflow.

    Args:
        x: Exponent value
        max_input: Maximum input to prevent overflow (exp(710) ≈ 1.7e308, near float max)

    Returns:
        Exponential of clipped input
    """
    # Clip to prevent overflow (exp(710) is close to max float)
    x_clipped = min(x, max_input)
    return math.exp(x_clipped)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to be within [min_val, max_val].

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value

    Raises:
        ValueError: If min_val > max_val
    """
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) must be <= max_val ({max_val})")
    return max(min_val, min(value, max_val))


def is_close(a: float, b: float, rel_tol: float = 1e-9, abs_tol: float = 1e-9) -> bool:
    """
    Check if two floating-point numbers are close to each other.

    Args:
        a: First value
        b: Second value
        rel_tol: Relative tolerance
        abs_tol: Absolute tolerance

    Returns:
        True if values are close within tolerance
    """
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def sqrt(x: float) -> float:
    """
    Compute square root with validation.

    Args:
        x: Value to take square root of

    Returns:
        Square root of x

    Raises:
        ValueError: If x is negative
    """
    if x < 0:
        raise ValueError(f"Cannot take square root of negative number: {x}")
    return math.sqrt(x)
