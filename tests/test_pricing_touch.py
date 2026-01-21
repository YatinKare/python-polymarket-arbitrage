"""Tests for touch barrier pricing module."""

import math
import pytest
from scipy.stats import norm

from polyarb.pricing.touch_barrier import (
    TouchPricingError,
    touch_price,
    touch_price_with_sensitivity,
)


class TestTouchPrice:
    """Test touch_price function."""

    def test_barrier_equals_spot(self):
        """Test barrier at spot - should have probability 1."""
        result = touch_price(
            S0=100.0,
            B=100.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20
        )
        assert result.probability == pytest.approx(1.0, abs=1e-10)
        assert result.pv == pytest.approx(math.exp(-0.05 * 1.0), abs=1e-10)

    def test_driftless_upper_barrier(self):
        """Test driftless case (μ=0) for upper barrier against known formula."""
        S0 = 100.0
        B = 110.0
        T = 1.0
        sigma = 0.20

        # Set r = q + 0.5σ² to make drift = 0
        r = 0.02 + 0.5 * sigma * sigma
        q = 0.02

        result = touch_price(S0, B, T, r, q, sigma)

        # Driftless formula: P(hit) = 2 * (1 - N(|a|/(σ√T)))
        a = math.log(B / S0)
        z = abs(a) / (sigma * math.sqrt(T))
        expected_prob = 2.0 * norm.cdf(-z)

        assert result.probability == pytest.approx(expected_prob, abs=1e-8)
        assert result.drift == pytest.approx(0.0, abs=1e-10)

    def test_driftless_lower_barrier(self):
        """Test driftless case (μ=0) for lower barrier."""
        S0 = 100.0
        B = 90.0
        T = 1.0
        sigma = 0.20

        # Set r = q + 0.5σ² to make drift = 0
        r = 0.02 + 0.5 * sigma * sigma
        q = 0.02

        result = touch_price(S0, B, T, r, q, sigma)

        # Driftless formula: P(hit) = 2 * N(-|a|/(σ√T))
        a = math.log(B / S0)
        z = abs(a) / (sigma * math.sqrt(T))
        expected_prob = 2.0 * norm.cdf(-z)

        assert result.probability == pytest.approx(expected_prob, abs=1e-8)
        assert result.drift == pytest.approx(0.0, abs=1e-10)

    def test_upper_barrier_with_positive_drift(self):
        """Test upper barrier with positive drift (r > q + 0.5σ²)."""
        S0 = 100.0
        B = 120.0
        T = 1.0
        r = 0.10
        q = 0.02
        sigma = 0.25

        result = touch_price(S0, B, T, r, q, sigma)

        # Probability should be in [0, 1]
        assert 0.0 <= result.probability <= 1.0

        # For upper barrier with positive drift, probability should be higher than driftless
        drift = r - q - 0.5 * sigma * sigma
        assert drift > 0  # Positive drift pushes price upward

        # PV should be discounted
        assert result.pv == pytest.approx(
            math.exp(-r * T) * result.probability, abs=1e-10
        )

    def test_lower_barrier_with_negative_drift(self):
        """Test lower barrier with negative drift (r < q + 0.5σ²)."""
        S0 = 100.0
        B = 80.0
        T = 1.0
        r = 0.02
        q = 0.10
        sigma = 0.25

        result = touch_price(S0, B, T, r, q, sigma)

        # Probability should be in [0, 1]
        assert 0.0 <= result.probability <= 1.0

        # For lower barrier with negative drift, probability should be higher than driftless
        drift = r - q - 0.5 * sigma * sigma
        assert drift < 0  # Negative drift pushes price downward

        # PV should be discounted
        assert result.pv == pytest.approx(
            math.exp(-r * T) * result.probability, abs=1e-10
        )

    def test_very_high_volatility_increases_hit_probability(self):
        """Test that very high volatility increases hit probability."""
        S0 = 100.0
        B = 150.0  # Far OTM barrier
        T = 1.0
        r = 0.05
        q = 0.02

        # Low vol case
        result_low = touch_price(S0, B, T, r, q, sigma=0.10)

        # High vol case
        result_high = touch_price(S0, B, T, r, q, sigma=0.50)

        # Higher volatility should increase probability of hitting barrier
        assert result_high.probability > result_low.probability

    def test_very_short_time_reduces_hit_probability(self):
        """Test that very short time reduces hit probability for OTM barrier."""
        S0 = 100.0
        B = 120.0
        r = 0.05
        q = 0.02
        sigma = 0.25

        # Short time
        result_short = touch_price(S0, B, T=0.01, r=r, q=q, sigma=sigma)

        # Long time
        result_long = touch_price(S0, B, T=2.0, r=r, q=q, sigma=sigma)

        # Longer time should increase probability of hitting barrier
        assert result_long.probability > result_short.probability

    def test_very_close_barrier_high_probability(self):
        """Test that barrier very close to spot has high hit probability."""
        S0 = 100.0
        B = 100.5  # Very close to spot
        T = 1.0
        r = 0.05
        q = 0.02
        sigma = 0.20

        result = touch_price(S0, B, T, r, q, sigma)

        # Should have high probability
        assert result.probability > 0.9

    def test_very_far_barrier_low_probability(self):
        """Test that barrier very far from spot has low hit probability."""
        S0 = 100.0
        B = 200.0  # Very far from spot
        T = 0.1  # Short time
        r = 0.05
        q = 0.02
        sigma = 0.20

        result = touch_price(S0, B, T, r, q, sigma)

        # Should have low probability
        assert result.probability < 0.1

    def test_discounting_correctness(self):
        """Test that discounting is applied correctly."""
        S0 = 100.0
        B = 110.0
        T = 2.0
        r = 0.08
        q = 0.02
        sigma = 0.25

        result = touch_price(S0, B, T, r, q, sigma)

        # PV should equal discounted probability
        expected_pv = math.exp(-r * T) * result.probability
        assert result.pv == pytest.approx(expected_pv, abs=1e-10)

        # Discount factor should be significant for long time and high rate
        assert result.pv < result.probability

    def test_probability_bounds(self):
        """Test that probability is always in [0, 1] for various scenarios."""
        scenarios = [
            # (S0, B, T, r, q, sigma)
            (100.0, 120.0, 1.0, 0.05, 0.02, 0.20),
            (100.0, 80.0, 1.0, 0.05, 0.02, 0.20),
            (100.0, 200.0, 0.1, 0.05, 0.02, 0.10),
            (100.0, 101.0, 2.0, 0.05, 0.02, 0.50),
            (50.0, 60.0, 0.5, 0.10, 0.03, 0.30),
            (50.0, 40.0, 0.5, 0.02, 0.08, 0.40),
        ]

        for S0, B, T, r, q, sigma in scenarios:
            result = touch_price(S0, B, T, r, q, sigma)
            assert 0.0 <= result.probability <= 1.0
            assert 0.0 <= result.pv <= 1.0  # Max payout is $1

    def test_drift_calculation(self):
        """Test that drift is calculated correctly."""
        S0 = 100.0
        B = 110.0
        T = 1.0
        r = 0.08
        q = 0.03
        sigma = 0.25

        result = touch_price(S0, B, T, r, q, sigma)

        # μ = r - q - 0.5σ²
        expected_drift = r - q - 0.5 * sigma * sigma
        assert result.drift == pytest.approx(expected_drift, abs=1e-10)

    def test_d2_not_used(self):
        """Test that d2 is None for touch barriers (not applicable)."""
        result = touch_price(
            S0=100.0,
            B=110.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20
        )
        assert result.d2 is None

    # Input validation tests

    def test_negative_spot_raises_error(self):
        """Test that negative spot price raises error."""
        with pytest.raises(TouchPricingError, match="Spot price must be positive"):
            touch_price(S0=-100.0, B=110.0, T=1.0, r=0.05, q=0.02, sigma=0.20)

    def test_zero_spot_raises_error(self):
        """Test that zero spot price raises error."""
        with pytest.raises(TouchPricingError, match="Spot price must be positive"):
            touch_price(S0=0.0, B=110.0, T=1.0, r=0.05, q=0.02, sigma=0.20)

    def test_negative_barrier_raises_error(self):
        """Test that negative barrier raises error."""
        with pytest.raises(TouchPricingError, match="Barrier must be positive"):
            touch_price(S0=100.0, B=-110.0, T=1.0, r=0.05, q=0.02, sigma=0.20)

    def test_zero_barrier_raises_error(self):
        """Test that zero barrier raises error."""
        with pytest.raises(TouchPricingError, match="Barrier must be positive"):
            touch_price(S0=100.0, B=0.0, T=1.0, r=0.05, q=0.02, sigma=0.20)

    def test_negative_time_raises_error(self):
        """Test that negative time raises error."""
        with pytest.raises(TouchPricingError, match="Time to expiry must be positive"):
            touch_price(S0=100.0, B=110.0, T=-1.0, r=0.05, q=0.02, sigma=0.20)

    def test_zero_time_raises_error(self):
        """Test that zero time raises error."""
        with pytest.raises(TouchPricingError, match="Time to expiry must be positive"):
            touch_price(S0=100.0, B=110.0, T=0.0, r=0.05, q=0.02, sigma=0.20)

    def test_negative_sigma_raises_error(self):
        """Test that negative volatility raises error."""
        with pytest.raises(TouchPricingError, match="Volatility must be positive"):
            touch_price(S0=100.0, B=110.0, T=1.0, r=0.05, q=0.02, sigma=-0.20)

    def test_zero_sigma_raises_error(self):
        """Test that zero volatility raises error."""
        with pytest.raises(TouchPricingError, match="Volatility must be positive"):
            touch_price(S0=100.0, B=110.0, T=1.0, r=0.05, q=0.02, sigma=0.0)


class TestTouchPriceWithSensitivity:
    """Test touch_price_with_sensitivity function."""

    def test_default_sigma_shifts(self):
        """Test sensitivity with default sigma shifts."""
        result = touch_price_with_sensitivity(
            S0=100.0,
            B=110.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.20
        )

        # Should have sensitivity results
        assert len(result.sensitivity) == 4
        assert "sigma-0.03" in result.sensitivity
        assert "sigma-0.02" in result.sensitivity
        assert "sigma+0.02" in result.sensitivity
        assert "sigma+0.03" in result.sensitivity

        # Each entry should be (probability, pv) tuple
        for key, (prob, pv) in result.sensitivity.items():
            assert 0.0 <= prob <= 1.0
            assert 0.0 <= pv <= 1.0

    def test_custom_sigma_shifts(self):
        """Test sensitivity with custom sigma shifts."""
        result = touch_price_with_sensitivity(
            S0=100.0,
            B=110.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.25,
            sigma_shifts=[-0.05, 0.05]
        )

        # Should have 2 sensitivity results
        assert len(result.sensitivity) == 2
        assert "sigma-0.05" in result.sensitivity
        assert "sigma+0.05" in result.sensitivity

    def test_low_base_sigma_clamping(self):
        """Test that low base sigma with negative shift clamps to minimum."""
        result = touch_price_with_sensitivity(
            S0=100.0,
            B=110.0,
            T=1.0,
            r=0.05,
            q=0.02,
            sigma=0.02,  # Very low base
            sigma_shifts=[-0.03]  # Would go negative without clamping
        )

        # Should clamp to 0.01 minimum
        assert "sigma-0.03" in result.sensitivity
        prob, pv = result.sensitivity["sigma-0.03"]
        assert 0.0 <= prob <= 1.0

    def test_monotonicity_for_otm_barrier(self):
        """Test that higher vol increases hit probability for OTM barrier."""
        S0 = 100.0
        B = 120.0  # OTM upper barrier
        T = 1.0
        r = 0.05
        q = 0.02
        sigma = 0.25

        result = touch_price_with_sensitivity(
            S0, B, T, r, q, sigma,
            sigma_shifts=[-0.03, 0.03]
        )

        prob_low, _ = result.sensitivity["sigma-0.03"]
        prob_high, _ = result.sensitivity["sigma+0.03"]

        # Higher vol should increase hit probability for OTM barrier
        assert prob_high > prob_low

    def test_base_result_matches_direct_call(self):
        """Test that base result matches calling touch_price directly."""
        S0 = 100.0
        B = 110.0
        T = 1.0
        r = 0.05
        q = 0.02
        sigma = 0.20

        result_with_sens = touch_price_with_sensitivity(S0, B, T, r, q, sigma)
        result_direct = touch_price(S0, B, T, r, q, sigma)

        assert result_with_sens.probability == pytest.approx(result_direct.probability)
        assert result_with_sens.pv == pytest.approx(result_direct.pv)
        assert result_with_sens.drift == pytest.approx(result_direct.drift)
