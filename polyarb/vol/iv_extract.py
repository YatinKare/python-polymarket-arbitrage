"""
IV extraction from option chains.

This module extracts implied volatility from option chain data, focusing on
the strike region around a target level (barrier or strike).
"""

import warnings
from typing import Optional

import numpy as np
import pandas as pd


class IVExtractionError(Exception):
    """Raised when IV extraction fails."""
    pass


def extract_strike_region_iv(
    chain_df: pd.DataFrame,
    strike_level: float,
    window_pct: float = 0.05,
    min_strikes: int = 2
) -> float:
    """
    Extract implied volatility from the strike region around a target level.

    This function finds strikes near the target level and interpolates the IV
    at the exact strike using log-moneyness interpolation.

    Parameters
    ----------
    chain_df : pd.DataFrame
        Option chain DataFrame with columns: 'strike', 'impliedVolatility'
        IV should be in decimal form (0.25 for 25%)
    strike_level : float
        Target strike/barrier level to extract IV at
    window_pct : float, default=0.05
        Moneyness window as a percentage (0.05 = ±5%)
    min_strikes : int, default=2
        Minimum number of strikes required in the region

    Returns
    -------
    float
        Interpolated implied volatility in decimal form

    Raises
    ------
    IVExtractionError
        If insufficient data is available or IV extraction fails

    Notes
    -----
    The function:
    1. Filters strikes within the moneyness window: [K * (1-w), K * (1+w)]
    2. Drops strikes with missing IV
    3. Interpolates IV at exact strike using log-moneyness
    4. Falls back to nearest strike if only one strike available
    """
    if chain_df.empty:
        raise IVExtractionError("Option chain is empty")

    if 'strike' not in chain_df.columns or 'impliedVolatility' not in chain_df.columns:
        raise IVExtractionError(
            "Chain must have 'strike' and 'impliedVolatility' columns"
        )

    if strike_level <= 0:
        raise IVExtractionError(f"Strike level must be positive, got {strike_level}")

    if window_pct <= 0 or window_pct >= 1:
        raise IVExtractionError(f"Window percentage must be in (0, 1), got {window_pct}")

    # Filter to strike region
    lower_bound = strike_level * (1 - window_pct)
    upper_bound = strike_level * (1 + window_pct)

    region_df = chain_df[
        (chain_df['strike'] >= lower_bound) &
        (chain_df['strike'] <= upper_bound)
    ].copy()

    # Drop missing IVs
    region_df = region_df.dropna(subset=['impliedVolatility'])

    if len(region_df) == 0:
        # Try expanding the window
        warnings.warn(
            f"No strikes with valid IV in ±{window_pct*100:.1f}% window around {strike_level}. "
            f"Trying wider window (±20%)."
        )
        window_pct = 0.20
        lower_bound = strike_level * (1 - window_pct)
        upper_bound = strike_level * (1 + window_pct)

        region_df = chain_df[
            (chain_df['strike'] >= lower_bound) &
            (chain_df['strike'] <= upper_bound)
        ].copy()
        region_df = region_df.dropna(subset=['impliedVolatility'])

        if len(region_df) == 0:
            raise IVExtractionError(
                f"No strikes with valid IV found near {strike_level} "
                f"(tried ±{window_pct*100:.0f}% window)"
            )

    if len(region_df) < min_strikes:
        warnings.warn(
            f"Only {len(region_df)} strike(s) available in region (min {min_strikes} preferred). "
            f"Using available data."
        )

    # Sort by strike
    region_df = region_df.sort_values('strike')

    # If only one strike, use it directly
    if len(region_df) == 1:
        iv = float(region_df.iloc[0]['impliedVolatility'])
        strike = float(region_df.iloc[0]['strike'])
        warnings.warn(
            f"Only one strike ({strike:.2f}) available. Using IV={iv:.4f} directly."
        )
        return iv

    # Interpolate using log-moneyness
    # Log-moneyness: m = ln(K / K_target)
    strikes = region_df['strike'].values
    ivs = region_df['impliedVolatility'].values

    log_moneyness = np.log(strikes / strike_level)
    target_log_moneyness = 0.0  # ln(K_target / K_target) = 0

    # Linear interpolation in log-moneyness space
    # If target is outside the range, use nearest neighbor (no extrapolation)
    if target_log_moneyness < log_moneyness[0]:
        # Below all strikes, use lowest
        iv = float(ivs[0])
        warnings.warn(
            f"Target strike {strike_level} below available range. "
            f"Using IV from nearest strike {strikes[0]:.2f}"
        )
    elif target_log_moneyness > log_moneyness[-1]:
        # Above all strikes, use highest
        iv = float(ivs[-1])
        warnings.warn(
            f"Target strike {strike_level} above available range. "
            f"Using IV from nearest strike {strikes[-1]:.2f}"
        )
    else:
        # Interpolate
        iv = float(np.interp(target_log_moneyness, log_moneyness, ivs))

    # Validate result
    if iv <= 0:
        raise IVExtractionError(f"Extracted IV is non-positive: {iv}")

    if iv > 5.0:  # 500% vol is unreasonable
        warnings.warn(f"Extracted IV is very high: {iv:.4f} ({iv*100:.1f}%)")

    return iv


def compute_sensitivity_ivs(base_iv: float) -> dict[str, float]:
    """
    Compute a set of IVs for sensitivity analysis.

    Parameters
    ----------
    base_iv : float
        Base implied volatility in decimal form

    Returns
    -------
    dict[str, float]
        Dictionary with keys: 'base', 'minus_3', 'minus_2', 'plus_2', 'plus_3'
        Values are clipped to be positive (minimum 0.01)

    Examples
    --------
    >>> compute_sensitivity_ivs(0.25)
    {'base': 0.25, 'minus_3': 0.22, 'minus_2': 0.23, 'plus_2': 0.27, 'plus_3': 0.28}
    """
    if base_iv <= 0:
        raise ValueError(f"Base IV must be positive, got {base_iv}")

    return {
        'base': base_iv,
        'minus_3': max(base_iv - 0.03, 0.01),
        'minus_2': max(base_iv - 0.02, 0.01),
        'plus_2': base_iv + 0.02,
        'plus_3': base_iv + 0.03,
    }


def get_average_iv_from_region(
    chain_df: pd.DataFrame,
    strike_level: float,
    window_pct: float = 0.05
) -> Optional[float]:
    """
    Get simple average IV from strikes in the region (fallback method).

    This is a simpler alternative to interpolation when data is sparse.

    Parameters
    ----------
    chain_df : pd.DataFrame
        Option chain DataFrame with 'strike' and 'impliedVolatility'
    strike_level : float
        Target strike level
    window_pct : float, default=0.05
        Moneyness window percentage

    Returns
    -------
    float or None
        Average IV if available, None otherwise
    """
    if chain_df.empty:
        return None

    lower_bound = strike_level * (1 - window_pct)
    upper_bound = strike_level * (1 + window_pct)

    region_df = chain_df[
        (chain_df['strike'] >= lower_bound) &
        (chain_df['strike'] <= upper_bound)
    ].copy()

    region_df = region_df.dropna(subset=['impliedVolatility'])

    if len(region_df) == 0:
        return None

    avg_iv = float(region_df['impliedVolatility'].mean())

    if avg_iv <= 0:
        return None

    return avg_iv
