"""Tests for CLI input validation logic."""

from datetime import date, timedelta
from unittest.mock import Mock, patch
from contextlib import contextmanager

import pytest
from click.testing import CliRunner
import pandas as pd

from polyarb.cli import main
from polyarb.models import Market, PricingResult


@pytest.fixture
def mock_market():
    """Create a mock market for testing."""
    future_date = date.today() + timedelta(days=30)
    return Market(
        id="test-market-id",
        title="Test Market: Will BTC reach $100k?",
        description="This is a test market to validate BTC price predictions.",
        end_date=future_date,
        clob_token_ids={"Yes": "token-yes", "No": "token-no"},
        outcomes=["Yes", "No"],
    )


@contextmanager
def mock_orchestration_dependencies():
    """Context manager to mock all orchestration dependencies for tests."""
    # Create mock pricing result
    mock_pricing_result = PricingResult(
        probability=0.65,
        pv=0.63,
        d2=None,
        drift=-0.02,
        sensitivity={
            'sigma-0.03': (0.60, 0.58),
            'sigma-0.02': (0.62, 0.60),
            'sigma+0.02': (0.68, 0.66),
            'sigma+0.03': (0.70, 0.68),
        }
    )

    # Create mock option chain data
    calls_df = pd.DataFrame({
        'strike': [90000, 95000, 100000, 105000, 110000],
        'impliedVolatility': [0.55, 0.50, 0.45, 0.42, 0.40]
    })
    puts_df = pd.DataFrame({
        'strike': [90000, 95000, 100000, 105000, 110000],
        'impliedVolatility': [0.40, 0.42, 0.45, 0.50, 0.55]
    })

    with patch('polyarb.clients.polymarket_clob.ClobClient') as mock_clob, \
         patch('polyarb.clients.yfinance_md.YFMarketData') as mock_yf, \
         patch('polyarb.pricing.touch_barrier.touch_price_with_sensitivity') as mock_touch_pricing, \
         patch('polyarb.pricing.digital_bs.digital_price_with_sensitivity') as mock_digital_pricing, \
         patch('polyarb.vol.iv_extract.extract_strike_region_iv') as mock_iv_extract, \
         patch('polyarb.vol.term_structure.interpolate_iv_term_structure') as mock_iv_interp, \
         patch('polyarb.clients.fred.FredClient') as mock_fred:

        # Setup mocks
        mock_clob.return_value.get_yes_price.return_value = 0.65
        mock_yf.return_value.get_spot.return_value = 95000.0
        mock_yf.return_value.get_option_expiries.return_value = [
            date.today() + timedelta(days=7),
            date.today() + timedelta(days=30),
            date.today() + timedelta(days=60),
        ]
        mock_yf.return_value.get_chain.return_value = (calls_df, puts_df)
        mock_iv_extract.return_value = 0.45
        mock_iv_interp.return_value = 0.45
        mock_touch_pricing.return_value = mock_pricing_result
        mock_digital_pricing.return_value = mock_pricing_result
        mock_fred.return_value.get_latest_observation.return_value = (4.0, date.today())

        yield {
            'clob': mock_clob,
            'yf': mock_yf,
            'touch_pricing': mock_touch_pricing,
            'digital_pricing': mock_digital_pricing,
            'iv_extract': mock_iv_extract,
            'iv_interp': mock_iv_interp,
            'fred': mock_fred,
        }


def test_analyze_validation_negative_level(mock_market):
    """Test that negative level fails validation."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "-100",  # Negative level (invalid)
                "--rate", "0.04",
            ],
        )

        assert result.exit_code == 1
        assert "Level/strike must be positive" in result.output


def test_analyze_validation_expiry_in_past(mock_market):
    """Test that expiry in the past fails validation."""
    runner = CliRunner()
    past_date = date.today() - timedelta(days=1)

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        # Override end_date to be in the past
        past_market = Market(
            id=mock_market.id,
            title=mock_market.title,
            description=mock_market.description,
            end_date=past_date,
            clob_token_ids=mock_market.clob_token_ids,
            outcomes=mock_market.outcomes,
        )
        mock_client.return_value.get_market.return_value = past_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
            ],
        )

        assert result.exit_code == 1
        assert "must be in the future" in result.output


def test_analyze_validation_yes_price_out_of_range(mock_market):
    """Test that yes price outside [0,1] fails validation."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
                "--yes-price", "1.5",  # Out of range
            ],
        )

        assert result.exit_code == 1
        assert "Yes price must be in [0, 1]" in result.output


def test_analyze_validation_manual_iv_mode_missing_iv(mock_market):
    """Test that manual IV mode without --iv fails validation."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
                "--iv-mode", "manual",
                # Missing --iv
            ],
        )

        assert result.exit_code == 1
        assert "Manual IV mode requires --iv parameter" in result.output


def test_analyze_validation_missing_rate(mock_market):
    """Test that missing both --rate and --fred-series-id fails validation."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                # Missing --rate and --fred-series-id
            ],
        )

        assert result.exit_code == 1
        assert "Must provide either --rate or --fred-series-id" in result.output


def test_analyze_validation_negative_iv(mock_market):
    """Test that negative IV fails validation."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client:
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
                "--iv-mode", "manual",
                "--iv", "-0.25",  # Negative IV
            ],
        )

        assert result.exit_code == 1
        assert "Implied volatility must be positive" in result.output


def test_analyze_validation_valid_inputs(mock_market):
    """Test that valid inputs pass validation and run analysis."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client, \
         mock_orchestration_dependencies():
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
            ],
        )

        # Should pass validation and complete analysis
        assert result.exit_code == 0
        # Check that analysis completed (should have report sections)
        assert "# Polymarket Analysis Report" in result.output or "Analysis complete" in result.stderr


def test_analyze_warns_both_rate_and_fred(mock_market):
    """Test that providing both --rate and --fred-series-id issues a warning."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client, \
         mock_orchestration_dependencies():
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
                "--fred-series-id", "DGS3MO",
            ],
        )

        # Should warn but not fail
        assert result.exit_code == 0
        combined_output = result.output + result.stderr
        assert "Both --rate and --fred-series-id provided" in combined_output


def test_analyze_warns_unusual_rate(mock_market):
    """Test that unusual rate values trigger a warning."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client, \
         mock_orchestration_dependencies():
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.5",  # 50% rate is unusual
            ],
        )

        # Should warn but not fail
        assert result.exit_code == 0
        combined_output = result.output + result.stderr
        assert "seems unusual" in combined_output


def test_analyze_uses_market_end_date(mock_market):
    """Test that market end date is used when expiry not provided."""
    runner = CliRunner()

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client, \
         mock_orchestration_dependencies():
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
            ],
        )

        assert result.exit_code == 0
        # Check that market end date is referenced in the output
        combined_output = result.output + result.stderr
        assert mock_market.end_date.strftime('%Y-%m-%d') in combined_output


def test_analyze_warns_expiry_override(mock_market):
    """Test that overriding market end date triggers a warning."""
    runner = CliRunner()
    different_date = date.today() + timedelta(days=60)

    with patch("polyarb.clients.polymarket_gamma.GammaClient") as mock_client, \
         mock_orchestration_dependencies():
        mock_client.return_value.get_market.return_value = mock_market

        result = runner.invoke(
            main,
            [
                "analyze",
                "test-market-id",
                "--ticker", "BTC-USD",
                "--event-type", "touch",
                "--level", "100000",
                "--rate", "0.04",
                "--expiry", different_date.strftime("%Y-%m-%d"),
            ],
        )

        assert result.exit_code == 0
        combined_output = result.output + result.stderr
        assert "differs from market end date" in combined_output
