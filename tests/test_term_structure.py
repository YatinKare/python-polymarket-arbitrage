"""
Tests for term structure interpolation module.
"""

import warnings
from datetime import date

import pytest

from polyarb.vol.term_structure import (
    TermStructureError,
    compute_time_to_expiry,
    find_bracketing_expiries,
    interpolate_iv_term_structure,
    interpolate_variance,
)


class TestFindBracketingExpiries:
    """Tests for find_bracketing_expiries function."""

    def test_exact_match(self):
        """Test when target exactly matches an available expiry."""
        target = date(2024, 6, 21)
        expiries = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 6, 21)
        assert after is None

    def test_between_two_expiries(self):
        """Test when target is between two expiries."""
        target = date(2024, 5, 1)
        expiries = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 3, 15)
        assert after == date(2024, 6, 21)

    def test_before_all_expiries(self):
        """Test when target is before all available expiries."""
        target = date(2024, 1, 1)
        expiries = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before is None
        assert after == date(2024, 3, 15)

    def test_after_all_expiries(self):
        """Test when target is after all available expiries."""
        target = date(2024, 12, 31)
        expiries = [date(2024, 3, 15), date(2024, 6, 21), date(2024, 9, 20)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 9, 20)
        assert after is None

    def test_empty_expiries(self):
        """Test with no available expiries."""
        target = date(2024, 5, 1)
        expiries = []

        before, after = find_bracketing_expiries(target, expiries)

        assert before is None
        assert after is None

    def test_single_expiry_before(self):
        """Test with single expiry that is before target."""
        target = date(2024, 6, 1)
        expiries = [date(2024, 3, 15)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 3, 15)
        assert after is None

    def test_single_expiry_after(self):
        """Test with single expiry that is after target."""
        target = date(2024, 1, 1)
        expiries = [date(2024, 3, 15)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before is None
        assert after == date(2024, 3, 15)

    def test_single_expiry_exact_match(self):
        """Test with single expiry that exactly matches target."""
        target = date(2024, 3, 15)
        expiries = [date(2024, 3, 15)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 3, 15)
        assert after is None

    def test_unsorted_expiries(self):
        """Test that function works with unsorted expiries."""
        target = date(2024, 5, 1)
        expiries = [date(2024, 9, 20), date(2024, 3, 15), date(2024, 6, 21)]

        before, after = find_bracketing_expiries(target, expiries)

        assert before == date(2024, 3, 15)
        assert after == date(2024, 6, 21)


class TestInterpolateVariance:
    """Tests for interpolate_variance function."""

    def test_basic_interpolation(self):
        """Test basic variance interpolation."""
        # IV at 3 months: 20%, IV at 6 months: 30%
        # Target: 4.5 months (midpoint)
        iv1 = 0.20
        t1 = 0.25  # 3 months
        iv2 = 0.30
        t2 = 0.50  # 6 months
        target_t = 0.375  # 4.5 months

        result = interpolate_variance(iv1, t1, iv2, t2, target_t)

        # Manual calculation:
        # w1 = 0.20^2 * 0.25 = 0.01
        # w2 = 0.30^2 * 0.50 = 0.045
        # w_target = 0.01 + (0.045 - 0.01) * (0.375 - 0.25) / (0.50 - 0.25)
        #          = 0.01 + 0.035 * 0.5 = 0.0275
        # iv_target = sqrt(0.0275 / 0.375) = sqrt(0.0733...) = 0.2708...

        assert result == pytest.approx(0.2708, abs=0.001)

    def test_interpolation_at_t1(self):
        """Test interpolation at first time point."""
        iv1 = 0.20
        t1 = 0.25
        iv2 = 0.30
        t2 = 0.50
        target_t = 0.25

        result = interpolate_variance(iv1, t1, iv2, t2, target_t)

        # At t1, should return iv1
        assert result == pytest.approx(iv1, abs=1e-6)

    def test_interpolation_at_t2(self):
        """Test interpolation at second time point."""
        iv1 = 0.20
        t1 = 0.25
        iv2 = 0.30
        t2 = 0.50
        target_t = 0.50

        result = interpolate_variance(iv1, t1, iv2, t2, target_t)

        # At t2, should return iv2
        assert result == pytest.approx(iv2, abs=1e-6)

    def test_increasing_variance_term_structure(self):
        """Test with increasing variance (normal term structure)."""
        # Longer expiries usually have higher IV
        iv1 = 0.15
        t1 = 0.25
        iv2 = 0.25
        t2 = 1.00
        target_t = 0.50

        result = interpolate_variance(iv1, t1, iv2, t2, target_t)

        # Result should be between iv1 and iv2
        assert iv1 < result < iv2

    def test_decreasing_variance_term_structure(self):
        """Test with decreasing variance (inverted term structure)."""
        # Sometimes short-term IV is higher (e.g., before events)
        iv1 = 0.40
        t1 = 0.083  # 1 month
        iv2 = 0.20
        t2 = 0.50  # 6 months
        target_t = 0.25  # 3 months

        result = interpolate_variance(iv1, t1, iv2, t2, target_t)

        # Result should be between iv2 and iv1
        assert iv2 < result < iv1

    def test_error_on_negative_time(self):
        """Test that negative times raise an error."""
        with pytest.raises(TermStructureError, match="All times must be positive"):
            interpolate_variance(0.20, -0.25, 0.30, 0.50, 0.40)

    def test_error_on_zero_time(self):
        """Test that zero time raises an error."""
        with pytest.raises(TermStructureError, match="All times must be positive"):
            interpolate_variance(0.20, 0.25, 0.30, 0.0, 0.40)

    def test_error_on_negative_iv(self):
        """Test that negative IV raises an error."""
        with pytest.raises(TermStructureError, match="All IVs must be positive"):
            interpolate_variance(-0.20, 0.25, 0.30, 0.50, 0.40)

    def test_error_on_zero_iv(self):
        """Test that zero IV raises an error."""
        with pytest.raises(TermStructureError, match="All IVs must be positive"):
            interpolate_variance(0.20, 0.25, 0.0, 0.50, 0.40)

    def test_error_on_reversed_times(self):
        """Test that t1 >= t2 raises an error."""
        with pytest.raises(TermStructureError, match="First expiry must be before second"):
            interpolate_variance(0.20, 0.50, 0.30, 0.25, 0.40)

    def test_error_on_target_outside_range_low(self):
        """Test that target_t < t1 raises an error."""
        with pytest.raises(TermStructureError, match="Target time .* must be between"):
            interpolate_variance(0.20, 0.25, 0.30, 0.50, 0.10)

    def test_error_on_target_outside_range_high(self):
        """Test that target_t > t2 raises an error."""
        with pytest.raises(TermStructureError, match="Target time .* must be between"):
            interpolate_variance(0.20, 0.25, 0.30, 0.50, 0.75)


class TestInterpolateIVTermStructure:
    """Tests for interpolate_iv_term_structure function."""

    def test_exact_match(self):
        """Test when target date exactly matches an expiry."""
        target = date(2024, 6, 21)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), 0.25),
            (date(2024, 9, 20), 0.30),
        ]
        ref_date = date(2024, 1, 1)

        result = interpolate_iv_term_structure(target, pairs, ref_date)

        assert result == 0.25

    def test_interpolation_between_two(self):
        """Test interpolation between two expiries."""
        target = date(2024, 5, 1)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), 0.30),
        ]
        ref_date = date(2024, 1, 1)

        result = interpolate_iv_term_structure(target, pairs, ref_date)

        # Result should be between 0.20 and 0.30
        assert 0.20 < result < 0.30

    def test_before_all_expiries_with_warning(self):
        """Test when target is before all expiries (should warn)."""
        target = date(2024, 1, 15)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), 0.25),
        ]
        ref_date = date(2024, 1, 1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpolate_iv_term_structure(target, pairs, ref_date)

            assert len(w) == 1
            assert "before all available expiries" in str(w[0].message)

        # Should use nearest expiry
        assert result == 0.20

    def test_after_all_expiries_with_warning(self):
        """Test when target is after all expiries (should warn)."""
        target = date(2024, 12, 31)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), 0.25),
        ]
        ref_date = date(2024, 1, 1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpolate_iv_term_structure(target, pairs, ref_date)

            assert len(w) == 1
            assert "after all available expiries" in str(w[0].message)

        # Should use farthest expiry
        assert result == 0.25

    def test_single_expiry_with_warning(self):
        """Test with only one expiry available (should warn)."""
        target = date(2024, 6, 1)
        pairs = [(date(2024, 3, 15), 0.20)]
        ref_date = date(2024, 1, 1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpolate_iv_term_structure(target, pairs, ref_date)

            assert len(w) == 1
            assert "Only one expiry available" in str(w[0].message)

        assert result == 0.20

    def test_no_pairs_raises_error(self):
        """Test that empty pairs list raises an error."""
        target = date(2024, 6, 1)
        pairs = []
        ref_date = date(2024, 1, 1)

        with pytest.raises(TermStructureError, match="No expiry-IV pairs provided"):
            interpolate_iv_term_structure(target, pairs, ref_date)

    def test_negative_iv_raises_error(self):
        """Test that negative IV in pairs raises an error."""
        target = date(2024, 5, 1)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), -0.25),
        ]
        ref_date = date(2024, 1, 1)

        with pytest.raises(TermStructureError, match="All IVs must be positive"):
            interpolate_iv_term_structure(target, pairs, ref_date)

    def test_target_before_reference_with_warning(self):
        """Test that target before reference date but before all expiries gives warning."""
        target = date(2023, 12, 1)
        pairs = [
            (date(2024, 3, 15), 0.20),
            (date(2024, 6, 21), 0.25),
        ]
        ref_date = date(2024, 1, 1)

        # When target is before reference but also before all expiries,
        # it uses the nearest future expiry with a warning (more graceful)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpolate_iv_term_structure(target, pairs, ref_date)

            assert len(w) == 1
            assert "before all available expiries" in str(w[0].message)

        assert result == 0.20

    def test_default_reference_date(self):
        """Test that function works without explicit reference date."""
        from datetime import date as date_class
        today = date_class.today()

        # Create expiries in the future
        from datetime import timedelta
        exp1 = today + timedelta(days=90)
        exp2 = today + timedelta(days=180)
        target = today + timedelta(days=135)

        pairs = [(exp1, 0.20), (exp2, 0.30)]

        result = interpolate_iv_term_structure(target, pairs)

        # Should interpolate without error
        assert 0.20 < result < 0.30

    def test_expiry_at_reference_date_with_warning(self):
        """Test when bracketing expiry is at or before reference date."""
        target = date(2024, 2, 1)
        pairs = [
            (date(2024, 1, 1), 0.20),  # Same as reference date
            (date(2024, 3, 15), 0.25),
        ]
        ref_date = date(2024, 1, 1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = interpolate_iv_term_structure(target, pairs, ref_date)

            assert len(w) == 1
            assert "not after reference date" in str(w[0].message)

        # Should use the future expiry
        assert result == 0.25


class TestComputeTimeToExpiry:
    """Tests for compute_time_to_expiry function."""

    def test_basic_calculation(self):
        """Test basic time to expiry calculation."""
        expiry = date(2024, 7, 1)
        ref_date = date(2024, 1, 1)

        result = compute_time_to_expiry(expiry, ref_date)

        # 182 days (non-leap year from Jan 1 to Jul 1) / 365
        expected = 182 / 365.0
        assert result == pytest.approx(expected, abs=0.001)

    def test_one_year(self):
        """Test exactly one year."""
        expiry = date(2025, 1, 1)
        ref_date = date(2024, 1, 1)

        result = compute_time_to_expiry(expiry, ref_date)

        # 366 days (2024 is a leap year) / 365
        expected = 366 / 365.0
        assert result == pytest.approx(expected, abs=0.001)

    def test_one_month_approx(self):
        """Test approximately one month."""
        expiry = date(2024, 2, 1)
        ref_date = date(2024, 1, 1)

        result = compute_time_to_expiry(expiry, ref_date)

        # 31 days / 365
        expected = 31 / 365.0
        assert result == pytest.approx(expected, abs=0.001)

    def test_default_reference_date(self):
        """Test using default reference date (today)."""
        from datetime import date as date_class, timedelta
        today = date_class.today()
        expiry = today + timedelta(days=90)

        result = compute_time_to_expiry(expiry)

        # Should be approximately 90/365 = 0.2466
        assert result == pytest.approx(0.2466, abs=0.001)

    def test_error_on_expiry_in_past(self):
        """Test that expiry in past raises an error."""
        expiry = date(2023, 1, 1)
        ref_date = date(2024, 1, 1)

        with pytest.raises(TermStructureError, match="not after reference date"):
            compute_time_to_expiry(expiry, ref_date)

    def test_error_on_expiry_same_as_reference(self):
        """Test that expiry same as reference raises an error."""
        expiry = date(2024, 1, 1)
        ref_date = date(2024, 1, 1)

        with pytest.raises(TermStructureError, match="not after reference date"):
            compute_time_to_expiry(expiry, ref_date)

    def test_very_short_expiry(self):
        """Test with very short time to expiry (1 day)."""
        expiry = date(2024, 1, 2)
        ref_date = date(2024, 1, 1)

        result = compute_time_to_expiry(expiry, ref_date)

        # 1 day / 365
        expected = 1 / 365.0
        assert result == pytest.approx(expected, abs=1e-6)

    def test_very_long_expiry(self):
        """Test with very long time to expiry (5 years)."""
        expiry = date(2029, 1, 1)
        ref_date = date(2024, 1, 1)

        result = compute_time_to_expiry(expiry, ref_date)

        # Should be approximately 5 years (accounting for leap years)
        assert 4.9 < result < 5.1
