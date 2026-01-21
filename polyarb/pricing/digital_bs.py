"""Digital option pricing using Black-Scholes framework.

Implements risk-neutral pricing for terminal (settle-at-expiry) events where a payout
occurs if the underlying settles above or below a strike at expiration.
"""

import math
from typing import Literal

from scipy.stats import norm

from polyarb.models import PricingResult
from polyarb.util.math import safe_exp, safe_log


class DigitalPricingError(Exception):
    """Exception raised for digital pricing errors."""
    pass


def digital_price(
    S0: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    direction: Literal["above", "below"]
) -> PricingResult:
    """
    Price a digital option that pays $1 if underlying settles above/below strike at expiry.

    Uses Black-Scholes framework with risk-neutral drift μ = r - q - 0.5σ²

    Args:
        S0: Current spot price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annual, decimal)
        q: Dividend yield (annual, decimal)
        sigma: Implied volatility (annual, decimal)
        direction: "above" or "below" - direction of the terminal condition

    Returns:
        PricingResult with probability and present value

    Raises:
        DigitalPricingError: If inputs are invalid

    Formula:
        d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
        P(above) = N(d2)
        P(below) = N(-d2) = 1 - N(d2)
        PV = exp(-rT) * P(event)

    where N(x) is the standard normal cumulative distribution function.
    """
    # Validate inputs
    if S0 <= 0:
        raise DigitalPricingError(f"Spot price must be positive, got {S0}")
    if K <= 0:
        raise DigitalPricingError(f"Strike must be positive, got {K}")
    if T <= 0:
        raise DigitalPricingError(f"Time to expiry must be positive, got {T}")
    if sigma <= 0:
        raise DigitalPricingError(f"Volatility must be positive, got {sigma}")
    if direction not in ("above", "below"):
        raise DigitalPricingError(f"Direction must be 'above' or 'below', got {direction}")

    # Compute risk-neutral drift
    drift = r - q - 0.5 * sigma * sigma

    # Compute d2 parameter
    # d2 = (ln(S0/K) + (r - q - 0.5σ²)T) / (σ√T)
    log_moneyness = safe_log(S0 / K)
    variance_term = sigma * math.sqrt(T)

    d2 = (log_moneyness + drift * T) / variance_term

    # Compute probability using standard normal CDF
    if direction == "above":
        probability = norm.cdf(d2)
    else:  # direction == "below"
        probability = norm.cdf(-d2)

    # Clamp probability to [0, 1] to handle numerical edge cases
    probability = max(0.0, min(1.0, probability))

    # Compute present value: PV = exp(-rT) * P(event)
    discount_factor = safe_exp(-r * T)
    pv = discount_factor * probability

    return PricingResult(
        probability=probability,
        pv=pv,
        d2=d2,
        drift=drift,
        sensitivity={}
    )


def digital_price_with_sensitivity(
    S0: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    direction: Literal["above", "below"],
    sigma_shifts: list[float] | None = None
) -> PricingResult:
    """
    Price a digital option with sensitivity analysis for volatility.

    Computes the base price and then re-prices at shifted volatility levels
    to show sensitivity to sigma.

    Args:
        S0: Current spot price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annual, decimal)
        q: Dividend yield (annual, decimal)
        sigma: Base implied volatility (annual, decimal)
        direction: "above" or "below"
        sigma_shifts: List of sigma shifts (e.g., [-0.03, -0.02, 0.02, 0.03])
                     Defaults to [-0.03, -0.02, 0.02, 0.03] if not provided

    Returns:
        PricingResult with base pricing and sensitivity dict populated

    Sensitivity dict format:
        {"sigma-0.02": (prob, pv), "sigma+0.02": (prob, pv), ...}
    """
    if sigma_shifts is None:
        sigma_shifts = [-0.03, -0.02, 0.02, 0.03]

    # Compute base price
    base_result = digital_price(S0, K, T, r, q, sigma, direction)

    # Compute sensitivity for each sigma shift
    sensitivity = {}
    for shift in sigma_shifts:
        shifted_sigma = sigma + shift
        # Ensure shifted sigma is positive (minimum 1%)
        if shifted_sigma <= 0.01:
            shifted_sigma = 0.01

        # Format key
        if shift >= 0:
            key = f"sigma+{shift:.2f}"
        else:
            key = f"sigma{shift:.2f}"  # negative sign already in shift

        # Compute shifted price
        shifted_result = digital_price(S0, K, T, r, q, shifted_sigma, direction)
        sensitivity[key] = (shifted_result.probability, shifted_result.pv)

    # Update base result with sensitivity
    base_result.sensitivity = sensitivity
    return base_result


def compute_verdict(
    poly_price: float,
    fair_pv: float,
    abs_tol: float = 0.01,
    pct_tol: float = 0.05
) -> str:
    """
    Determine verdict on Polymarket price vs fair value.

    Args:
        poly_price: Polymarket tradable price
        fair_pv: Model fair present value
        abs_tol: Absolute price difference tolerance (default 0.01 = 1 cent)
        pct_tol: Percentage difference tolerance (default 0.05 = 5%)

    Returns:
        "Fair" if within tolerance, "Cheap" if poly < fair, "Expensive" if poly > fair

    Logic:
        If |poly_price - fair_pv| <= abs_tol OR |poly_price - fair_pv| / fair_pv <= pct_tol:
            return "Fair"
        Else if poly_price < fair_pv:
            return "Cheap"
        Else:
            return "Expensive"
    """
    abs_diff = abs(poly_price - fair_pv)

    # Avoid division by zero in percentage calculation
    if fair_pv > 0:
        pct_diff = abs_diff / fair_pv
    else:
        # If fair value is zero, use absolute tolerance only
        pct_diff = float('inf')

    # Check if within tolerance
    if abs_diff <= abs_tol or pct_diff <= pct_tol:
        return "Fair"

    # Outside tolerance - determine direction
    if poly_price < fair_pv:
        return "Cheap"
    else:
        return "Expensive"
