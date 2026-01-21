"""
Term structure interpolation for implied volatility.

This module handles interpolation of implied volatility across different
time horizons using total variance interpolation.
"""

import warnings
from datetime import date
from typing import Optional

import numpy as np


class TermStructureError(Exception):
    """Raised when term structure interpolation fails."""
    pass


def find_bracketing_expiries(
    target_date: date,
    available_expiries: list[date]
) -> tuple[Optional[date], Optional[date]]:
    """
    Find expiries that bracket the target date.

    Parameters
    ----------
    target_date : date
        Target expiration date to interpolate to
    available_expiries : list[date]
        List of available option expiration dates

    Returns
    -------
    tuple[Optional[date], Optional[date]]
        (before_date, after_date) tuple:
        - Exact match: (target_date, None)
        - Normal case: (nearest_before, nearest_after)
        - Only before: (nearest_before, None)
        - Only after: (None, nearest_after)
        - No data: (None, None)

    Examples
    --------
    >>> from datetime import date
    >>> expiries = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]
    >>> find_bracketing_expiries(date(2024, 5, 1), expiries)
    (date(2024, 3, 15), date(2024, 6, 21))
    """
    if not available_expiries:
        return (None, None)

    # Check for exact match
    if target_date in available_expiries:
        return (target_date, None)

    # Separate into before and after
    before = [exp for exp in available_expiries if exp < target_date]
    after = [exp for exp in available_expiries if exp > target_date]

    nearest_before = max(before) if before else None
    nearest_after = min(after) if after else None

    return (nearest_before, nearest_after)


def interpolate_variance(
    iv1: float,
    t1: float,
    iv2: float,
    t2: float,
    target_t: float
) -> float:
    """
    Interpolate implied volatility using total variance interpolation.

    Total variance w(T) = σ²T is interpolated linearly, then converted
    back to volatility: σ_target = sqrt(w_target / T_target)

    Parameters
    ----------
    iv1 : float
        Implied volatility at time t1 (in decimal, e.g., 0.25)
    t1 : float
        Time to first expiry (in years)
    iv2 : float
        Implied volatility at time t2 (in decimal, e.g., 0.30)
    t2 : float
        Time to second expiry (in years)
    target_t : float
        Target time to interpolate to (in years)

    Returns
    -------
    float
        Interpolated implied volatility at target_t

    Raises
    ------
    TermStructureError
        If times are non-positive or if interpolation fails

    Notes
    -----
    The formula for linear variance interpolation:
        w1 = σ1² * t1
        w2 = σ2² * t2
        w_target = w1 + (w2 - w1) * (t_target - t1) / (t2 - t1)
        σ_target = sqrt(w_target / t_target)

    Examples
    --------
    >>> interpolate_variance(0.20, 0.25, 0.30, 0.50, 0.40)
    0.262...
    """
    # Validate inputs
    if t1 <= 0 or t2 <= 0 or target_t <= 0:
        raise TermStructureError(
            f"All times must be positive: t1={t1}, t2={t2}, target_t={target_t}"
        )

    if iv1 <= 0 or iv2 <= 0:
        raise TermStructureError(
            f"All IVs must be positive: iv1={iv1}, iv2={iv2}"
        )

    if t1 >= t2:
        raise TermStructureError(
            f"First expiry must be before second: t1={t1} >= t2={t2}"
        )

    if target_t < t1 or target_t > t2:
        raise TermStructureError(
            f"Target time {target_t} must be between t1={t1} and t2={t2}"
        )

    # Compute total variances
    w1 = iv1 ** 2 * t1
    w2 = iv2 ** 2 * t2

    # Linear interpolation of variance
    w_target = w1 + (w2 - w1) * (target_t - t1) / (t2 - t1)

    # Convert back to volatility
    if w_target <= 0:
        raise TermStructureError(
            f"Interpolated variance is non-positive: {w_target}"
        )

    target_iv = np.sqrt(w_target / target_t)

    return float(target_iv)


def interpolate_iv_term_structure(
    target_date: date,
    expiry_iv_pairs: list[tuple[date, float]],
    reference_date: Optional[date] = None
) -> float:
    """
    Interpolate IV to target date using term structure interpolation.

    This is a high-level function that combines bracketing and variance
    interpolation. It handles edge cases like exact matches and single expiries.

    Parameters
    ----------
    target_date : date
        Target expiration date
    expiry_iv_pairs : list[tuple[date, float]]
        List of (expiry_date, implied_vol) tuples
        IVs must be in decimal form (0.25 for 25%)
    reference_date : date, optional
        Reference date for time calculations (default: today)

    Returns
    -------
    float
        Interpolated implied volatility at target_date

    Raises
    ------
    TermStructureError
        If insufficient data or interpolation fails

    Notes
    -----
    Handling of edge cases:
    - Exact match: returns the IV for that expiry
    - Target before all expiries: uses nearest expiry with warning
    - Target after all expiries: uses farthest expiry with warning
    - Only one expiry available: uses that expiry with warning
    - Between two expiries: performs variance interpolation

    Examples
    --------
    >>> from datetime import date
    >>> pairs = [(date(2024, 3, 15), 0.20), (date(2024, 6, 21), 0.30)]
    >>> interpolate_iv_term_structure(date(2024, 5, 1), pairs, date(2024, 1, 1))
    0.262...
    """
    if not expiry_iv_pairs:
        raise TermStructureError("No expiry-IV pairs provided")

    if reference_date is None:
        from datetime import date as date_class
        reference_date = date_class.today()

    # Validate all IVs are positive
    for exp_date, iv in expiry_iv_pairs:
        if iv <= 0:
            raise TermStructureError(
                f"All IVs must be positive, got {iv} for expiry {exp_date}"
            )

    # Extract expiries
    expiries = [exp_date for exp_date, _ in expiry_iv_pairs]
    iv_map = dict(expiry_iv_pairs)

    # Find bracketing expiries
    before, after = find_bracketing_expiries(target_date, expiries)

    # Case 1: Exact match
    if before == target_date and after is None:
        return iv_map[before]

    # Case 2: Only one expiry or target outside range
    if before is None and after is not None:
        # Target before all expiries
        warnings.warn(
            f"Target date {target_date} is before all available expiries. "
            f"Using IV from nearest expiry {after}."
        )
        return iv_map[after]

    if after is None and before is not None:
        # Target after all expiries or only one expiry exists
        if len(expiries) == 1:
            warnings.warn(
                f"Only one expiry available ({before}). "
                f"Using its IV for target date {target_date}."
            )
        else:
            warnings.warn(
                f"Target date {target_date} is after all available expiries. "
                f"Using IV from farthest expiry {before}."
            )
        return iv_map[before]

    if before is None and after is None:
        raise TermStructureError("No expiries available")

    # Case 3: Normal interpolation between two expiries
    iv1 = iv_map[before]
    iv2 = iv_map[after]

    # Calculate times in years (assuming 365 days per year)
    t1 = (before - reference_date).days / 365.0
    t2 = (after - reference_date).days / 365.0
    target_t = (target_date - reference_date).days / 365.0

    # Validate times are positive
    if target_t <= 0:
        raise TermStructureError(
            f"Target date {target_date} is not after reference date {reference_date}"
        )

    if t1 <= 0:
        # This can happen if 'before' expiry is on or before reference date
        # Use the 'after' expiry instead
        warnings.warn(
            f"Bracketing expiry {before} is not after reference date {reference_date}. "
            f"Using nearest future expiry {after}."
        )
        return iv_map[after]

    # Perform variance interpolation
    target_iv = interpolate_variance(iv1, t1, iv2, t2, target_t)

    return target_iv


def compute_time_to_expiry(
    expiry_date: date,
    reference_date: Optional[date] = None
) -> float:
    """
    Compute time to expiry in years.

    Parameters
    ----------
    expiry_date : date
        Expiration date
    reference_date : date, optional
        Reference date (default: today)

    Returns
    -------
    float
        Time to expiry in years (365 days = 1 year)

    Raises
    ------
    TermStructureError
        If expiry is not after reference date

    Examples
    --------
    >>> from datetime import date
    >>> compute_time_to_expiry(date(2024, 7, 1), date(2024, 1, 1))
    0.5041...
    """
    if reference_date is None:
        from datetime import date as date_class
        reference_date = date_class.today()

    days_to_expiry = (expiry_date - reference_date).days

    if days_to_expiry <= 0:
        raise TermStructureError(
            f"Expiry date {expiry_date} is not after reference date {reference_date}"
        )

    return days_to_expiry / 365.0
