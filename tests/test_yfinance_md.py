"""Tests for yfinance market data client."""

import warnings
from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from polyarb.clients.yfinance_md import YFMarketData, YFinanceClientError


@pytest.fixture
def client():
    """Create YFMarketData client."""
    return YFMarketData()


class TestGetSpot:
    """Tests for get_spot method."""

    def test_get_spot_current_price(self, client):
        """Test getting spot price from currentPrice field."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'currentPrice': 450.25}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            spot = client.get_spot('SPY')
            assert spot == 450.25

    def test_get_spot_regular_market_price(self, client):
        """Test getting spot price from regularMarketPrice field."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'regularMarketPrice': 450.25}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            spot = client.get_spot('SPY')
            assert spot == 450.25

    def test_get_spot_previous_close(self, client):
        """Test getting spot price from previousClose field."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'previousClose': 450.25}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            spot = client.get_spot('SPY')
            assert spot == 450.25

    def test_get_spot_from_history_fallback(self, client):
        """Test fallback to history when info fields unavailable."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        # Create mock history DataFrame
        hist_data = pd.DataFrame({
            'Close': [450.25, 451.00, 452.50]
        })
        mock_ticker.history.return_value = hist_data

        with patch('yfinance.Ticker', return_value=mock_ticker):
            spot = client.get_spot('SPY')
            assert spot == 452.50  # Last close from history

    def test_get_spot_invalid_ticker(self, client):
        """Test error when ticker has no data."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_ticker.history.return_value = pd.DataFrame()  # Empty DataFrame

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="No price data available"):
                client.get_spot('INVALID')

    def test_get_spot_zero_price(self, client):
        """Test error when price is zero or negative."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'currentPrice': 0}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="Invalid spot price"):
                client.get_spot('SPY')

    def test_get_spot_negative_price(self, client):
        """Test error when price is negative."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'currentPrice': -100}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="Invalid spot price"):
                client.get_spot('SPY')

    def test_get_spot_exception_handling(self, client):
        """Test generic exception handling."""
        with patch('yfinance.Ticker', side_effect=Exception("Network error")):
            with pytest.raises(YFinanceClientError, match="Error fetching spot price"):
                client.get_spot('SPY')


class TestGetOptionExpiries:
    """Tests for get_option_expiries method."""

    def test_get_option_expiries_success(self, client):
        """Test getting option expiries."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19', '2024-02-16', '2024-03-15')

        with patch('yfinance.Ticker', return_value=mock_ticker):
            expiries = client.get_option_expiries('SPY')
            assert len(expiries) == 3
            assert expiries[0] == date(2024, 1, 19)
            assert expiries[1] == date(2024, 2, 16)
            assert expiries[2] == date(2024, 3, 15)

    def test_get_option_expiries_sorted(self, client):
        """Test that expiries are returned sorted."""
        mock_ticker = MagicMock()
        # Provide unsorted dates
        mock_ticker.options = ('2024-03-15', '2024-01-19', '2024-02-16')

        with patch('yfinance.Ticker', return_value=mock_ticker):
            expiries = client.get_option_expiries('SPY')
            assert expiries[0] == date(2024, 1, 19)
            assert expiries[1] == date(2024, 2, 16)
            assert expiries[2] == date(2024, 3, 15)

    def test_get_option_expiries_no_options(self, client):
        """Test error when ticker has no options."""
        mock_ticker = MagicMock()
        mock_ticker.options = ()  # Empty tuple

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="No option expiries available"):
                client.get_option_expiries('BTC-USD')

    def test_get_option_expiries_invalid_format(self, client):
        """Test handling of invalid date formats."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19', 'invalid-date', '2024-02-16')

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                expiries = client.get_option_expiries('SPY')

                # Should skip invalid date and warn
                assert len(expiries) == 2
                assert len(w) == 1
                assert "invalid expiry date" in str(w[0].message).lower()

    def test_get_option_expiries_all_invalid(self, client):
        """Test error when all expiries have invalid format."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('invalid1', 'invalid2')

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                with pytest.raises(YFinanceClientError, match="No valid option expiries"):
                    client.get_option_expiries('SPY')

    def test_get_option_expiries_exception_handling(self, client):
        """Test generic exception handling."""
        with patch('yfinance.Ticker', side_effect=Exception("Network error")):
            with pytest.raises(YFinanceClientError, match="Error fetching option expiries"):
                client.get_option_expiries('SPY')


class TestGetChain:
    """Tests for get_chain method."""

    def test_get_chain_success(self, client):
        """Test getting option chain with valid IV data."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)

        # Create mock option chain data
        calls_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'lastPrice': [10.5, 7.2, 4.1],
            'bid': [10.4, 7.1, 4.0],
            'ask': [10.6, 7.3, 4.2],
            'volume': [100, 200, 150],
            'impliedVolatility': [0.20, 0.21, 0.22]
        })
        puts_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'lastPrice': [2.1, 4.5, 7.8],
            'bid': [2.0, 4.4, 7.7],
            'ask': [2.2, 4.6, 7.9],
            'volume': [80, 120, 90],
            'impliedVolatility': [0.19, 0.20, 0.21]
        })

        mock_chain = Mock()
        mock_chain.calls = calls_data
        mock_chain.puts = puts_data
        mock_ticker.option_chain.return_value = mock_chain

        with patch('yfinance.Ticker', return_value=mock_ticker):
            calls, puts = client.get_chain('SPY', date(2024, 1, 19))

            assert len(calls) == 3
            assert len(puts) == 3
            assert 'impliedVolatility' in calls.columns
            assert 'impliedVolatility' in puts.columns

    def test_get_chain_expiry_not_available(self, client):
        """Test error when expiry is not available."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19', '2024-02-16')

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="Expiry .* not available"):
                client.get_chain('SPY', date(2024, 3, 15))

    def test_get_chain_missing_iv_field(self, client):
        """Test handling when IV field is missing."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)

        # Create chain data without IV field
        calls_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'lastPrice': [10.5, 7.2, 4.1],
        })
        puts_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'lastPrice': [2.1, 4.5, 7.8],
        })

        mock_chain = Mock()
        mock_chain.calls = calls_data
        mock_chain.puts = puts_data
        mock_ticker.option_chain.return_value = mock_chain

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                with pytest.raises(YFinanceClientError, match="No valid option data"):
                    client.get_chain('SPY', date(2024, 1, 19))

                # Should warn about missing IV
                assert any("No impliedVolatility field" in str(warning.message) for warning in w)

    def test_get_chain_some_missing_iv(self, client):
        """Test dropping rows with missing IV values."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)

        # Create chain with some NaN IV values
        calls_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [0.20, None, 0.22]  # Missing middle value
        })
        puts_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [0.19, 0.20, None]  # Missing last value
        })

        mock_chain = Mock()
        mock_chain.calls = calls_data
        mock_chain.puts = puts_data
        mock_ticker.option_chain.return_value = mock_chain

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                calls, puts = client.get_chain('SPY', date(2024, 1, 19))

                # Should drop rows with missing IV
                assert len(calls) == 2
                assert len(puts) == 2

                # Should warn about dropped rows
                assert any("Dropped" in str(warning.message) for warning in w)

    def test_get_chain_percentage_iv_conversion(self, client):
        """Test conversion of percentage-form IV to decimal."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)

        # Create chain with IV in percentage form (>1.0)
        calls_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [20.0, 21.0, 22.0]  # Percentage form
        })
        puts_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [19.0, 20.0, 21.0]  # Percentage form
        })

        mock_chain = Mock()
        mock_chain.calls = calls_data
        mock_chain.puts = puts_data
        mock_ticker.option_chain.return_value = mock_chain

        with patch('yfinance.Ticker', return_value=mock_ticker):
            calls, puts = client.get_chain('SPY', date(2024, 1, 19))

            # Should convert to decimal form
            assert calls['impliedVolatility'].iloc[0] == pytest.approx(0.20)
            assert calls['impliedVolatility'].iloc[1] == pytest.approx(0.21)
            assert puts['impliedVolatility'].iloc[0] == pytest.approx(0.19)

    def test_get_chain_all_missing_iv(self, client):
        """Test error when all IV values are missing."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)

        # Create chain with all NaN IV values
        calls_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [None, None, None]
        })
        puts_data = pd.DataFrame({
            'strike': [440, 445, 450],
            'impliedVolatility': [None, None, None]
        })

        mock_chain = Mock()
        mock_chain.calls = calls_data
        mock_chain.puts = puts_data
        mock_ticker.option_chain.return_value = mock_chain

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                with pytest.raises(YFinanceClientError, match="No valid option data"):
                    client.get_chain('SPY', date(2024, 1, 19))

    def test_get_chain_exception_handling(self, client):
        """Test generic exception handling."""
        mock_ticker = MagicMock()
        mock_ticker.options = ('2024-01-19',)
        mock_ticker.option_chain.side_effect = Exception("Network error")

        with patch('yfinance.Ticker', return_value=mock_ticker):
            with pytest.raises(YFinanceClientError, match="Error fetching option chain"):
                client.get_chain('SPY', date(2024, 1, 19))


class TestGetDividendYield:
    """Tests for get_dividend_yield method."""

    def test_get_dividend_yield_from_field(self, client):
        """Test getting dividend yield from dividendYield field."""
        mock_ticker = MagicMock()
        mock_ticker.info = {'dividendYield': 0.0152}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            div_yield = client.get_dividend_yield('AAPL')
            assert div_yield == pytest.approx(0.0152)

    def test_get_dividend_yield_computed(self, client):
        """Test computing dividend yield from rate and price."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'dividendRate': 1.00,
            'currentPrice': 180.00
        }

        with patch('yfinance.Ticker', return_value=mock_ticker):
            div_yield = client.get_dividend_yield('AAPL')
            assert div_yield == pytest.approx(1.00 / 180.00)

    def test_get_dividend_yield_not_available(self, client):
        """Test returning None when dividend data unavailable."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with patch('yfinance.Ticker', return_value=mock_ticker):
            div_yield = client.get_dividend_yield('BTC-USD')
            assert div_yield is None

    def test_get_dividend_yield_zero_price(self, client):
        """Test returning None when price is zero (avoid division)."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'dividendRate': 1.00,
            'currentPrice': 0
        }

        with patch('yfinance.Ticker', return_value=mock_ticker):
            div_yield = client.get_dividend_yield('SPY')
            assert div_yield is None

    def test_get_dividend_yield_exception_handling(self, client):
        """Test that exceptions return None (non-critical)."""
        with patch('yfinance.Ticker', side_effect=Exception("Network error")):
            div_yield = client.get_dividend_yield('SPY')
            assert div_yield is None
