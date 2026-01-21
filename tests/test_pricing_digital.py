"""Tests for digital option pricing module."""

import math
import pytest
from scipy.stats import norm

from polyarb.pricing.digital_bs import (
    DigitalPricingError,
    compute_verdict,
    digital_price,
    digital_price_with_sensitivity,
)


class TestDigitalPrice:
    """Tests for basic digital_price function."""

    def test_digital_above_at_the_money(self):
        """Test digital call (above) when spot equals strike."""
        # ATM, with no drift (r=q), probability should be ~0.5
        result = digital_price(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.05,  # r=q cancels out drift from rates
            sigma=0.20,
            direction="above"
        )

        # d2 = (ln(1) + (0.05 - 0.05 - 0.5*0.04)*1) / (0.20) = -0.02 / 0.20 = -0.1
        # P(above) = N(-0.1) ≈ 0.46
        assert 0.45 <= result.probability <= 0.47
        assert result.d2 == pytest.approx(-0.1, abs=0.01)
        assert result.drift == pytest.approx(-0.02, abs=1e-6)

        # PV should be discounted
        expected_pv = math.exp(-0.05 * 1.0) * result.probability
        assert result.pv == pytest.approx(expected_pv, abs=1e-6)

    def test_digital_below_at_the_money(self):
        """Test digital put (below) when spot equals strike."""
        result = digital_price(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.05,
            sigma=0.20,
            direction="below"
        )

        # P(below) = N(-d2) = 1 - N(d2), should be complement of above case
        assert 0.53 <= result.probability <= 0.55
        assert result.d2 == pytest.approx(-0.1, abs=0.01)

    def test_digital_above_deep_in_the_money(self):
        """Test digital call when spot >> strike."""
        result = digital_price(
            S0=150.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="above"
        )

        # Deep ITM: probability should be close to 1
        assert result.probability >= 0.95
        assert result.pv >= 0.90  # Discounted value

    def test_digital_above_deep_out_of_the_money(self):
        """Test digital call when spot << strike."""
        result = digital_price(
            S0=50.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="above"
        )

        # Deep OTM: probability should be close to 0
        assert result.probability <= 0.05
        assert result.pv <= 0.05

    def test_digital_below_deep_in_the_money(self):
        """Test digital put when spot << strike."""
        result = digital_price(
            S0=50.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="below"
        )

        # Deep ITM: probability should be close to 1
        assert result.probability >= 0.95
        assert result.pv >= 0.90

    def test_digital_below_deep_out_of_the_money(self):
        """Test digital put when spot >> strike."""
        result = digital_price(
            S0=150.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="below"
        )

        # Deep OTM: probability should be close to 0
        assert result.probability <= 0.05
        assert result.pv <= 0.05

    def test_symmetry_above_plus_below(self):
        """Test that P(above) + P(below) ≈ 1 for same parameters."""
        params = dict(S0=100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.25)

        result_above = digital_price(**params, direction="above")
        result_below = digital_price(**params, direction="below")

        # Probabilities should sum to 1
        assert result_above.probability + result_below.probability == pytest.approx(1.0, abs=1e-9)

        # d2 should be the same for both (opposite sides of same distribution)
        assert result_above.d2 == result_below.d2

    def test_zero_volatility_limit(self):
        """Test behavior as volatility approaches zero."""
        # With very low vol, the distribution becomes deterministic
        # If S0 > K, P(above) → 1, P(below) → 0
        result_above = digital_price(
            S0=105.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.001,  # Very low vol
            direction="above"
        )

        # Should be very close to 1 since S0 > K and no volatility
        assert result_above.probability >= 0.999

        result_below = digital_price(
            S0=105.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.001,
            direction="below"
        )

        # Should be very close to 0
        assert result_below.probability <= 0.001

    def test_zero_time_limit(self):
        """Test behavior as time to expiry approaches zero."""
        # With very short time, outcome is almost deterministic based on current spot
        result = digital_price(
            S0=105.0,
            K=100.0,
            T=0.001,  # Very short time (about 9 hours)
            r=0.05,
            q=0.02,
            sigma=0.25,
            direction="above"
        )

        # S0 > K, so probability should be very high even with short time
        assert result.probability >= 0.95

    def test_high_volatility(self):
        """Test that high volatility increases uncertainty."""
        # Compare low vol vs high vol for ATM option
        result_low_vol = digital_price(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.10,  # 10% vol
            direction="above"
        )

        result_high_vol = digital_price(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.50,  # 50% vol
            direction="above"
        )

        # With higher vol, d2 becomes smaller in magnitude (closer to 0.5)
        assert abs(result_high_vol.d2) < abs(result_low_vol.d2)

    def test_discounting(self):
        """Test that PV is properly discounted."""
        result = digital_price(
            S0=100.0,
            K=90.0,
            T=1.0,
            r=0.10,  # 10% rate for visible discounting
            q=0.00,
            sigma=0.20,
            direction="above"
        )

        # Expected discount factor
        discount_factor = math.exp(-0.10 * 1.0)
        assert result.pv == pytest.approx(discount_factor * result.probability, abs=1e-9)

    def test_probability_bounds(self):
        """Test that probability is always in [0, 1]."""
        # Test a range of scenarios
        test_cases = [
            dict(S0=50.0, K=100.0, T=0.1, r=0.05, q=0.0, sigma=0.10),
            dict(S0=150.0, K=100.0, T=2.0, r=0.01, q=0.05, sigma=0.80),
            dict(S0=100.0, K=100.0, T=1.0, r=0.20, q=0.0, sigma=0.05),
        ]

        for params in test_cases:
            result_above = digital_price(**params, direction="above")
            result_below = digital_price(**params, direction="below")

            assert 0.0 <= result_above.probability <= 1.0
            assert 0.0 <= result_below.probability <= 1.0
            assert 0.0 <= result_above.pv <= 1.0
            assert 0.0 <= result_below.pv <= 1.0

    def test_invalid_spot(self):
        """Test error handling for invalid spot price."""
        with pytest.raises(DigitalPricingError, match="Spot price must be positive"):
            digital_price(S0=-100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.20, direction="above")

        with pytest.raises(DigitalPricingError, match="Spot price must be positive"):
            digital_price(S0=0.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.20, direction="above")

    def test_invalid_strike(self):
        """Test error handling for invalid strike."""
        with pytest.raises(DigitalPricingError, match="Strike must be positive"):
            digital_price(S0=100.0, K=-50.0, T=1.0, r=0.05, q=0.02, sigma=0.20, direction="above")

        with pytest.raises(DigitalPricingError, match="Strike must be positive"):
            digital_price(S0=100.0, K=0.0, T=1.0, r=0.05, q=0.02, sigma=0.20, direction="above")

    def test_invalid_time(self):
        """Test error handling for invalid time to expiry."""
        with pytest.raises(DigitalPricingError, match="Time to expiry must be positive"):
            digital_price(S0=100.0, K=100.0, T=-1.0, r=0.05, q=0.02, sigma=0.20, direction="above")

        with pytest.raises(DigitalPricingError, match="Time to expiry must be positive"):
            digital_price(S0=100.0, K=100.0, T=0.0, r=0.05, q=0.02, sigma=0.20, direction="above")

    def test_invalid_volatility(self):
        """Test error handling for invalid volatility."""
        with pytest.raises(DigitalPricingError, match="Volatility must be positive"):
            digital_price(S0=100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=-0.20, direction="above")

        with pytest.raises(DigitalPricingError, match="Volatility must be positive"):
            digital_price(S0=100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.0, direction="above")

    def test_invalid_direction(self):
        """Test error handling for invalid direction."""
        with pytest.raises(DigitalPricingError, match="Direction must be 'above' or 'below'"):
            digital_price(S0=100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.20, direction="invalid")


class TestDigitalPriceWithSensitivity:
    """Tests for digital_price_with_sensitivity function."""

    def test_sensitivity_default_shifts(self):
        """Test sensitivity analysis with default sigma shifts."""
        result = digital_price_with_sensitivity(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="above"
        )

        # Should have 4 sensitivity entries by default
        assert len(result.sensitivity) == 4
        assert "sigma-0.03" in result.sensitivity
        assert "sigma-0.02" in result.sensitivity
        assert "sigma+0.02" in result.sensitivity
        assert "sigma+0.03" in result.sensitivity

        # Each entry should be a tuple (probability, pv)
        for key, (prob, pv) in result.sensitivity.items():
            assert 0.0 <= prob <= 1.0
            assert 0.0 <= pv <= 1.0

    def test_sensitivity_custom_shifts(self):
        """Test sensitivity analysis with custom sigma shifts."""
        custom_shifts = [-0.05, -0.01, 0.01, 0.05]
        result = digital_price_with_sensitivity(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="above",
            sigma_shifts=custom_shifts
        )

        assert len(result.sensitivity) == 4
        assert "sigma-0.05" in result.sensitivity
        assert "sigma-0.01" in result.sensitivity
        assert "sigma+0.01" in result.sensitivity
        assert "sigma+0.05" in result.sensitivity

    def test_sensitivity_low_base_sigma(self):
        """Test that sensitivity clamps shifted sigma to minimum 1%."""
        result = digital_price_with_sensitivity(
            S0=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.02,  # 2% base vol
            direction="above",
            sigma_shifts=[-0.03, -0.01]  # -3% would make it negative
        )

        # Should not error - negative sigma should be clamped to 0.01
        assert len(result.sensitivity) == 2
        assert "sigma-0.03" in result.sensitivity
        assert "sigma-0.01" in result.sensitivity

        # Verify the values are valid
        for key, (prob, pv) in result.sensitivity.items():
            assert 0.0 <= prob <= 1.0
            assert 0.0 <= pv <= 1.0

    def test_sensitivity_monotonicity_for_above(self):
        """Test that for 'above', higher vol generally increases probability (for OTM)."""
        # For an OTM call (S0 < K), higher vol increases probability
        result = digital_price_with_sensitivity(
            S0=95.0,
            K=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20,
            direction="above",
            sigma_shifts=[-0.02, 0.02]
        )

        prob_low = result.sensitivity["sigma-0.02"][0]
        prob_high = result.sensitivity["sigma+0.02"][0]

        # Higher vol should increase probability for OTM call
        assert prob_high > prob_low

    def test_sensitivity_base_matches_direct_call(self):
        """Test that base result matches direct digital_price call."""
        params = dict(S0=100.0, K=100.0, T=1.0, r=0.05, q=0.02, sigma=0.25, direction="above")

        result_with_sens = digital_price_with_sensitivity(**params)
        result_direct = digital_price(**params)

        # Base pricing should match
        assert result_with_sens.probability == pytest.approx(result_direct.probability)
        assert result_with_sens.pv == pytest.approx(result_direct.pv)
        assert result_with_sens.d2 == pytest.approx(result_direct.d2)
        assert result_with_sens.drift == pytest.approx(result_direct.drift)


class TestComputeVerdict:
    """Tests for compute_verdict function."""

    def test_verdict_fair_within_absolute_tolerance(self):
        """Test verdict is 'Fair' when within absolute tolerance."""
        verdict = compute_verdict(poly_price=0.50, fair_pv=0.505, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Fair"

        verdict = compute_verdict(poly_price=0.505, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Fair"

    def test_verdict_fair_within_percentage_tolerance(self):
        """Test verdict is 'Fair' when within percentage tolerance."""
        # 3% difference: within 5% tolerance
        verdict = compute_verdict(poly_price=0.50, fair_pv=0.515, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Fair"

    def test_verdict_cheap(self):
        """Test verdict is 'Cheap' when poly < fair beyond tolerance."""
        verdict = compute_verdict(poly_price=0.40, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Cheap"

    def test_verdict_expensive(self):
        """Test verdict is 'Expensive' when poly > fair beyond tolerance."""
        verdict = compute_verdict(poly_price=0.60, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Expensive"

    def test_verdict_fair_exactly_at_boundary(self):
        """Test verdict is 'Fair' when exactly at tolerance boundary."""
        # Exactly at abs_tol boundary
        verdict = compute_verdict(poly_price=0.51, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Fair"

        # Just within pct_tol boundary (4.9% difference to avoid floating point issues)
        verdict = compute_verdict(poly_price=0.5245, fair_pv=0.50, abs_tol=0.001, pct_tol=0.05)
        assert verdict == "Fair"

    def test_verdict_with_zero_fair_value(self):
        """Test verdict handles zero fair value gracefully."""
        # When fair value is 0, only use absolute tolerance
        verdict = compute_verdict(poly_price=0.005, fair_pv=0.0, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Fair"

        verdict = compute_verdict(poly_price=0.02, fair_pv=0.0, abs_tol=0.01, pct_tol=0.05)
        assert verdict == "Expensive"

    def test_verdict_custom_tolerances(self):
        """Test verdict with custom tolerance settings."""
        # Tight tolerances
        verdict = compute_verdict(poly_price=0.505, fair_pv=0.50, abs_tol=0.001, pct_tol=0.001)
        assert verdict == "Expensive"  # Outside tight tolerance

        # Loose tolerances
        verdict = compute_verdict(poly_price=0.55, fair_pv=0.50, abs_tol=0.10, pct_tol=0.20)
        assert verdict == "Fair"  # Within loose tolerance

    def test_verdict_symmetric(self):
        """Test that verdict is symmetric for same absolute difference."""
        verdict_low = compute_verdict(poly_price=0.45, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)
        verdict_high = compute_verdict(poly_price=0.55, fair_pv=0.50, abs_tol=0.01, pct_tol=0.05)

        # Both should be outside tolerance
        assert verdict_low == "Cheap"
        assert verdict_high == "Expensive"
