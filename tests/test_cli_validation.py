"""Tests for CLI input validation logic."""

from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from polyarb.cli import main
from polyarb.models import Market


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
    """Test that valid inputs pass validation."""
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
            ],
        )

        # Should pass validation and reach the stub output
        assert result.exit_code == 0
        # Check both stdout and stderr (ctx.log goes to stderr)
        combined_output = result.output + result.stderr
        assert "Orchestration logic not yet implemented" in result.output


def test_analyze_warns_both_rate_and_fred(mock_market):
    """Test that providing both --rate and --fred-series-id issues a warning."""
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
                "--fred-series-id", "DGS3MO",
            ],
        )

        # Should warn but not fail
        assert result.exit_code == 0
        assert "Both --rate and --fred-series-id provided" in result.output


def test_analyze_warns_unusual_rate(mock_market):
    """Test that unusual rate values trigger a warning."""
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
                "--rate", "0.5",  # 50% rate is unusual
            ],
        )

        # Should warn but not fail
        assert result.exit_code == 0
        assert "seems unusual" in result.output


def test_analyze_uses_market_end_date(mock_market):
    """Test that market end date is used when expiry not provided."""
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
            ],
        )

        assert result.exit_code == 0
        # Check that market end date is in the output (cli shows it in stub)
        assert str(mock_market.end_date) in result.output


def test_analyze_warns_expiry_override(mock_market):
    """Test that overriding market end date triggers a warning."""
    runner = CliRunner()
    different_date = date.today() + timedelta(days=60)

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
                "--expiry", different_date.strftime("%Y-%m-%d"),
            ],
        )

        assert result.exit_code == 0
        assert "differs from market end date" in result.output
