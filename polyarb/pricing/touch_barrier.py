"""Touch barrier option pricing using first-passage probability.

Implements risk-neutral pricing for barrier hit (touch) events where a payout
occurs if the underlying hits a barrier level at any time before expiration.
"""

import math
from typing import Literal

from scipy.stats import norm

from polyarb.models import PricingResult
from polyarb.util.math import safe_exp, safe_log


class TouchPricingError(Exception):
    """Exception raised for touch barrier pricing errors."""
    pass


def touch_price(
    S0: float,
    B: float,
    T: float,
    r: float,
    q: float,
    sigma: float
) -> PricingResult:
    """
    Price a touch barrier option that pays $1 if barrier is hit before expiry.

    Uses geometric Brownian motion with risk-neutral drift and the reflection
    principle to compute first-passage probability.

    Args:
        S0: Current spot price
        B: Barrier level
        T: Time to expiry in years
        r: Risk-free rate (annual, decimal)
        q: Dividend yield (annual, decimal)
        sigma: Implied volatility (annual, decimal)

    Returns:
        PricingResult with probability and present value

    Raises:
        TouchPricingError: If inputs are invalid

    Formula (for upper barrier B > S0):
        a = ln(B/S0)  (distance to barrier in log space)
        μ = r - q - 0.5σ²  (risk-neutral drift)
        λ = μ / σ²

        Using the reflection principle for first-passage:
        P(hit) = N(-(a - μT)/(σ√T)) + exp(2λa) * N(-(a + μT)/(σ√T))

        For lower barrier B < S0:
        a = ln(B/S0)  (negative)
        P(hit) = N((a - μT)/(σ√T)) + exp(2λa) * N((a + μT)/(σ√T))

        Special case (driftless μ=0):
        P(hit) = 2 * (1 - N(|a|/(σ√T)))  for upper barrier
        P(hit) = 2 * N(-|a|/(σ√T))  for lower barrier

        PV = exp(-rT) * P(hit)

    where N(x) is the standard normal cumulative distribution function.
    """
    # Validate inputs
    if S0 <= 0:
        raise TouchPricingError(f"Spot price must be positive, got {S0}")
    if B <= 0:
        raise TouchPricingError(f"Barrier must be positive, got {B}")
    if T <= 0:
        raise TouchPricingError(f"Time to expiry must be positive, got {T}")
    if sigma <= 0:
        raise TouchPricingError(f"Volatility must be positive, got {sigma}")

    # Determine barrier direction
    if abs(B - S0) / S0 < 1e-10:
        # Barrier equals spot - probability is 1 (already touched)
        probability = 1.0
        discount_factor = safe_exp(-r * T)
        pv = discount_factor * probability
        return PricingResult(
            probability=probability,
            pv=pv,
            d2=None,
            drift=r - q - 0.5 * sigma * sigma,
            sensitivity={}
        )

    barrier_direction: Literal["up", "down"] = "up" if B > S0 else "down"

    # Compute log-distance to barrier
    # a = ln(B/S0)
    a = safe_log(B / S0)

    # Compute risk-neutral drift
    # μ = r - q - 0.5σ²
    drift = r - q - 0.5 * sigma * sigma

    # Compute variance term
    # σ√T
    sigma_sqrt_t = sigma * math.sqrt(T)

    # Check for driftless case (μ ≈ 0)
    if abs(drift) < 1e-10:
        # Driftless case: simpler formula
        # P(hit) = 2 * (1 - N(|a|/(σ√T))) for upper barrier
        # P(hit) = 2 * N(-|a|/(σ√T)) for lower barrier (equivalent)
        abs_a = abs(a)
        z = abs_a / sigma_sqrt_t
        probability = 2.0 * norm.cdf(-z)
    else:
        # General case with drift
        # λ = μ / σ²
        lambda_param = drift / (sigma * sigma)

        # Compute the two terms
        # Term 1: N(-(a - μT)/(σ√T))  or  N((a - μT)/(σ√T)) for lower
        # Term 2: exp(2λa) * N(-(a + μT)/(σ√T))  or  exp(2λa) * N((a + μT)/(σ√T)) for lower

        mu_t = drift * T

        if barrier_direction == "up":
            # Upper barrier: B > S0, a > 0
            z1 = -(a - mu_t) / sigma_sqrt_t
            z2 = -(a + mu_t) / sigma_sqrt_t
            term1 = norm.cdf(z1)
            term2 = safe_exp(2 * lambda_param * a) * norm.cdf(z2)
        else:
            # Lower barrier: B < S0, a < 0
            z1 = (a - mu_t) / sigma_sqrt_t
            z2 = (a + mu_t) / sigma_sqrt_t
            term1 = norm.cdf(z1)
            term2 = safe_exp(2 * lambda_param * a) * norm.cdf(z2)

        probability = term1 + term2

    # Clamp probability to [0, 1] to handle numerical edge cases
    probability = max(0.0, min(1.0, probability))

    # Compute present value: PV = exp(-rT) * P(hit)
    discount_factor = safe_exp(-r * T)
    pv = discount_factor * probability

    return PricingResult(
        probability=probability,
        pv=pv,
        d2=None,  # d2 is not used for touch barriers
        drift=drift,
        sensitivity={}
    )


def touch_price_with_sensitivity(
    S0: float,
    B: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
    sigma_shifts: list[float] | None = None
) -> PricingResult:
    """
    Price a touch barrier option with sensitivity analysis for volatility.

    Computes the base price and then re-prices at shifted volatility levels
    to show sensitivity to sigma.

    Args:
        S0: Current spot price
        B: Barrier level
        T: Time to expiry in years
        r: Risk-free rate (annual, decimal)
        q: Dividend yield (annual, decimal)
        sigma: Base implied volatility (annual, decimal)
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
    base_result = touch_price(S0, B, T, r, q, sigma)

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
        shifted_result = touch_price(S0, B, T, r, q, shifted_sigma)
        sensitivity[key] = (shifted_result.probability, shifted_result.pv)

    # Update base result with sensitivity
    base_result.sensitivity = sensitivity
    return base_result
