"""
Tests for IV extraction module.
"""

import numpy as np
import pandas as pd
import pytest

from polyarb.vol.iv_extract import (
    IVExtractionError,
    compute_sensitivity_ivs,
    extract_strike_region_iv,
    get_average_iv_from_region,
)


@pytest.fixture
def sample_chain():
    """Create a sample option chain with strikes and IVs."""
    return pd.DataFrame({
        'strike': [90, 95, 100, 105, 110, 115, 120],
        'impliedVolatility': [0.30, 0.28, 0.25, 0.24, 0.26, 0.28, 0.30],
    })


@pytest.fixture
def sparse_chain():
    """Chain with some missing IVs."""
    return pd.DataFrame({
        'strike': [90, 95, 100, 105, 110, 115, 120],
        'impliedVolatility': [0.30, np.nan, 0.25, 0.24, np.nan, 0.28, 0.30],
    })


@pytest.fixture
def single_strike_chain():
    """Chain with only one valid strike."""
    return pd.DataFrame({
        'strike': [100],
        'impliedVolatility': [0.25],
    })


class TestExtractStrikeRegionIV:
    """Tests for extract_strike_region_iv function."""

    def test_exact_match(self, sample_chain):
        """Test when target strike exactly matches a chain strike."""
        iv = extract_strike_region_iv(sample_chain, strike_level=100.0)
        # Should be very close to 0.25 (the IV at strike 100)
        assert 0.24 <= iv <= 0.26

    def test_interpolation_between_strikes(self, sample_chain):
        """Test interpolation when target is between strikes."""
        iv = extract_strike_region_iv(sample_chain, strike_level=102.5)
        # Should be between 0.24 and 0.25
        assert 0.23 <= iv <= 0.26

    def test_default_window(self, sample_chain):
        """Test default 5% window includes appropriate strikes."""
        # For strike 100, 5% window is [95, 105]
        iv = extract_strike_region_iv(sample_chain, strike_level=100.0, window_pct=0.05)
        assert iv > 0
        # Should use strikes 95, 100, 105
        assert 0.23 <= iv <= 0.29

    def test_narrow_window(self, sample_chain):
        """Test narrower window uses fewer strikes."""
        # 2% window around 100 is [98, 102], only includes strike 100
        iv = extract_strike_region_iv(sample_chain, strike_level=100.0, window_pct=0.02)
        assert iv > 0

    def test_wide_window(self, sample_chain):
        """Test wider window includes more strikes."""
        # 20% window around 100 is [80, 120], includes all strikes
        iv = extract_strike_region_iv(sample_chain, strike_level=100.0, window_pct=0.20)
        assert iv > 0
        assert 0.23 <= iv <= 0.31

    def test_missing_ivs_dropped(self, sparse_chain):
        """Test that strikes with missing IVs are dropped."""
        # Window around 100 should still work, just with fewer strikes
        iv = extract_strike_region_iv(sparse_chain, strike_level=100.0, window_pct=0.10)
        assert iv > 0
        assert not np.isnan(iv)

    def test_single_strike_available(self, single_strike_chain):
        """Test with only one strike in region."""
        with pytest.warns(UserWarning, match="Only one strike"):
            iv = extract_strike_region_iv(single_strike_chain, strike_level=100.0)
        assert iv == 0.25

    def test_below_all_strikes(self, sample_chain):
        """Test when target is below all available strikes."""
        with pytest.warns(UserWarning, match="below available range"):
            iv = extract_strike_region_iv(sample_chain, strike_level=85.0, window_pct=0.02)
        # Should use IV from lowest strike (90)
        assert iv == 0.30

    def test_above_all_strikes(self, sample_chain):
        """Test when target is above all available strikes."""
        with pytest.warns(UserWarning, match="above available range"):
            iv = extract_strike_region_iv(sample_chain, strike_level=125.0, window_pct=0.02)
        # Should use IV from highest strike (120)
        assert iv == 0.30

    def test_empty_chain_raises_error(self):
        """Test error when chain is empty."""
        empty_chain = pd.DataFrame({'strike': [], 'impliedVolatility': []})
        with pytest.raises(IVExtractionError, match="empty"):
            extract_strike_region_iv(empty_chain, strike_level=100.0)

    def test_missing_columns_raises_error(self):
        """Test error when required columns are missing."""
        bad_chain = pd.DataFrame({'strike': [100], 'volatility': [0.25]})
        with pytest.raises(IVExtractionError, match="must have"):
            extract_strike_region_iv(bad_chain, strike_level=100.0)

    def test_negative_strike_raises_error(self, sample_chain):
        """Test error when strike level is negative."""
        with pytest.raises(IVExtractionError, match="must be positive"):
            extract_strike_region_iv(sample_chain, strike_level=-100.0)

    def test_zero_strike_raises_error(self, sample_chain):
        """Test error when strike level is zero."""
        with pytest.raises(IVExtractionError, match="must be positive"):
            extract_strike_region_iv(sample_chain, strike_level=0.0)

    def test_invalid_window_raises_error(self, sample_chain):
        """Test error when window is invalid."""
        with pytest.raises(IVExtractionError, match="Window percentage"):
            extract_strike_region_iv(sample_chain, strike_level=100.0, window_pct=0.0)

        with pytest.raises(IVExtractionError, match="Window percentage"):
            extract_strike_region_iv(sample_chain, strike_level=100.0, window_pct=1.5)

    def test_no_valid_ivs_in_window(self):
        """Test when no strikes with valid IV in window."""
        chain = pd.DataFrame({
            'strike': [50, 60, 140, 150],
            'impliedVolatility': [0.30, 0.28, 0.26, 0.24],
        })
        # Looking at 100 with 5% window [95, 105] - no strikes in range
        # Should auto-expand to 20% window [80, 120] and still find nothing
        with pytest.raises(IVExtractionError, match="No strikes with valid IV"):
            extract_strike_region_iv(chain, strike_level=100.0, window_pct=0.05)

    def test_auto_expand_window(self):
        """Test auto-expansion of window when initial window is too narrow."""
        chain = pd.DataFrame({
            'strike': [85, 115],  # Only these two strikes
            'impliedVolatility': [0.30, 0.26],
        })
        # 5% window around 100 is [95, 105] - no strikes
        # Should auto-expand to 20% window [80, 120] - includes both strikes
        with pytest.warns(UserWarning, match="wider window"):
            iv = extract_strike_region_iv(chain, strike_level=100.0, window_pct=0.05)
        assert iv > 0
        assert 0.25 <= iv <= 0.31

    def test_very_high_iv_warning(self, sample_chain):
        """Test warning when extracted IV is unreasonably high."""
        high_iv_chain = pd.DataFrame({
            'strike': [95, 100, 105],
            'impliedVolatility': [6.0, 6.5, 7.0],  # 600-700% volatility
        })
        with pytest.warns(UserWarning, match="very high"):
            iv = extract_strike_region_iv(high_iv_chain, strike_level=100.0)
        assert iv > 5.0

    def test_log_moneyness_interpolation(self):
        """Test that log-moneyness interpolation is working correctly."""
        # Create chain with known IV smile pattern
        chain = pd.DataFrame({
            'strike': [80, 90, 100, 110, 120],
            'impliedVolatility': [0.40, 0.30, 0.25, 0.30, 0.40],  # U-shaped smile
        })

        # At 100 (ATM), should be close to 0.25
        iv_atm = extract_strike_region_iv(chain, strike_level=100.0, window_pct=0.25)
        assert 0.24 <= iv_atm <= 0.26

        # At 95 (between 90 and 100), should be between 0.25 and 0.30
        iv_95 = extract_strike_region_iv(chain, strike_level=95.0, window_pct=0.25)
        assert 0.25 <= iv_95 <= 0.30


class TestComputeSensitivityIVs:
    """Tests for compute_sensitivity_ivs function."""

    def test_basic_sensitivity(self):
        """Test basic sensitivity computation."""
        result = compute_sensitivity_ivs(0.25)

        assert result['base'] == 0.25
        assert result['minus_3'] == 0.22
        assert result['minus_2'] == 0.23
        assert result['plus_2'] == 0.27
        assert result['plus_3'] == 0.28

    def test_low_base_iv_clipping(self):
        """Test that low IVs are clipped at minimum."""
        result = compute_sensitivity_ivs(0.02)

        assert result['base'] == 0.02
        assert result['minus_3'] == 0.01  # max(0.02 - 0.03, 0.01) = 0.01
        assert result['minus_2'] == 0.01  # max(0.02 - 0.02, 0.01) = 0.01
        assert result['plus_2'] == 0.04
        assert result['plus_3'] == 0.05

    def test_zero_iv_raises_error(self):
        """Test error with zero IV."""
        with pytest.raises(ValueError, match="must be positive"):
            compute_sensitivity_ivs(0.0)

    def test_negative_iv_raises_error(self):
        """Test error with negative IV."""
        with pytest.raises(ValueError, match="must be positive"):
            compute_sensitivity_ivs(-0.1)

    def test_high_iv(self):
        """Test with high IV values."""
        result = compute_sensitivity_ivs(1.0)

        assert result['base'] == 1.0
        assert result['minus_3'] == 0.97
        assert result['minus_2'] == 0.98
        assert result['plus_2'] == 1.02
        assert result['plus_3'] == 1.03

    def test_all_keys_present(self):
        """Test that all expected keys are present."""
        result = compute_sensitivity_ivs(0.25)

        expected_keys = {'base', 'minus_3', 'minus_2', 'plus_2', 'plus_3'}
        assert set(result.keys()) == expected_keys


class TestGetAverageIVFromRegion:
    """Tests for get_average_iv_from_region function."""

    def test_average_in_region(self, sample_chain):
        """Test simple average calculation."""
        # Window around 100 with 10% = [90, 110]
        # Strikes: 90 (0.30), 95 (0.28), 100 (0.25), 105 (0.24), 110 (0.26)
        # Average = (0.30 + 0.28 + 0.25 + 0.24 + 0.26) / 5 = 0.266
        avg_iv = get_average_iv_from_region(sample_chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv is not None
        assert 0.26 <= avg_iv <= 0.27

    def test_missing_ivs_excluded(self, sparse_chain):
        """Test that missing IVs are excluded from average."""
        avg_iv = get_average_iv_from_region(sparse_chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv is not None
        assert not np.isnan(avg_iv)

    def test_empty_chain_returns_none(self):
        """Test that empty chain returns None."""
        empty_chain = pd.DataFrame({'strike': [], 'impliedVolatility': []})
        avg_iv = get_average_iv_from_region(empty_chain, strike_level=100.0)
        assert avg_iv is None

    def test_no_strikes_in_window_returns_none(self, sample_chain):
        """Test None returned when no strikes in window."""
        avg_iv = get_average_iv_from_region(sample_chain, strike_level=200.0, window_pct=0.05)
        assert avg_iv is None

    def test_all_missing_ivs_returns_none(self):
        """Test None when all IVs in region are missing."""
        chain = pd.DataFrame({
            'strike': [95, 100, 105],
            'impliedVolatility': [np.nan, np.nan, np.nan],
        })
        avg_iv = get_average_iv_from_region(chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv is None

    def test_single_strike_returns_value(self, single_strike_chain):
        """Test with single strike in region."""
        avg_iv = get_average_iv_from_region(single_strike_chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv == 0.25

    def test_negative_iv_returns_none(self):
        """Test None returned when average IV is negative."""
        chain = pd.DataFrame({
            'strike': [95, 100, 105],
            'impliedVolatility': [-0.1, -0.2, -0.3],
        })
        avg_iv = get_average_iv_from_region(chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv is None

    def test_zero_iv_returns_none(self):
        """Test None returned when average IV is zero."""
        chain = pd.DataFrame({
            'strike': [95, 100, 105],
            'impliedVolatility': [0.0, 0.0, 0.0],
        })
        avg_iv = get_average_iv_from_region(chain, strike_level=100.0, window_pct=0.10)
        assert avg_iv is None
