"""yfinance wrapper for market data (spot, options, implied volatility)."""

import warnings
from datetime import date, datetime
from typing import Optional

import pandas as pd
import yfinance as yf


class YFinanceClientError(Exception):
    """Error raised by yfinance market data client."""
    pass


class YFMarketData:
    """Client for fetching market data using yfinance.

    Provides spot prices, option chains, and implied volatility data
    for pricing Polymarket events using options-implied fair values.
    """

    def __init__(self):
        """Initialize yfinance market data client."""
        pass  # yfinance is stateless, no initialization needed

    def get_spot(self, ticker: str) -> float:
        """Fetch current spot price for a ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")

        Returns:
            Current spot price (most recent close or current price)

        Raises:
            YFinanceClientError: If ticker is invalid or data unavailable
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Try different price fields in order of preference
            # 1. Current price (live or close to live)
            # 2. Regular market previous close
            # 3. Previous close
            # Use 'is not None' to handle zero values correctly
            price = None
            for field in ['currentPrice', 'regularMarketPrice', 'previousClose']:
                if field in info and info[field] is not None:
                    price = info[field]
                    break

            if price is None:
                # Try getting from history as fallback
                hist = ticker_obj.history(period="1d")
                if hist.empty:
                    raise YFinanceClientError(
                        f"No price data available for ticker {ticker}. "
                        "Check that the ticker symbol is valid."
                    )
                price = hist['Close'].iloc[-1]

            if price <= 0:
                raise YFinanceClientError(
                    f"Invalid spot price {price} for ticker {ticker}"
                )

            return float(price)

        except Exception as e:
            if isinstance(e, YFinanceClientError):
                raise
            raise YFinanceClientError(f"Error fetching spot price for {ticker}: {e}") from e

    def get_option_expiries(self, ticker: str) -> list[date]:
        """Fetch available option expiration dates for a ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")

        Returns:
            List of expiration dates, sorted chronologically

        Raises:
            YFinanceClientError: If ticker has no options or data unavailable
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            expiries = ticker_obj.options

            if not expiries:
                raise YFinanceClientError(
                    f"No option expiries available for ticker {ticker}. "
                    "This ticker may not have listed options."
                )

            # Convert string dates to date objects
            # yfinance returns dates in "YYYY-MM-DD" format
            expiry_dates = []
            for expiry_str in expiries:
                try:
                    expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                    expiry_dates.append(expiry_date)
                except ValueError:
                    warnings.warn(f"Skipping invalid expiry date format: {expiry_str}")
                    continue

            if not expiry_dates:
                raise YFinanceClientError(
                    f"No valid option expiries found for ticker {ticker}"
                )

            return sorted(expiry_dates)

        except Exception as e:
            if isinstance(e, YFinanceClientError):
                raise
            raise YFinanceClientError(f"Error fetching option expiries for {ticker}: {e}") from e

    def get_chain(
        self,
        ticker: str,
        expiry: date
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch option chain (calls and puts) for a specific expiry.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            expiry: Option expiration date

        Returns:
            Tuple of (calls_df, puts_df) with normalized columns:
            - strike: Strike price
            - lastPrice: Last traded price
            - bid: Bid price
            - ask: Ask price
            - volume: Trading volume
            - impliedVolatility: IV in decimal form (e.g., 0.25 for 25%)

            Rows with missing IV are dropped with a warning.

        Raises:
            YFinanceClientError: If expiry not available or data fetch fails
        """
        try:
            ticker_obj = yf.Ticker(ticker)

            # Convert date to string format expected by yfinance
            expiry_str = expiry.strftime("%Y-%m-%d")

            # Check if expiry is available
            if expiry_str not in ticker_obj.options:
                available = ', '.join(ticker_obj.options[:5])  # Show first 5
                raise YFinanceClientError(
                    f"Expiry {expiry_str} not available for {ticker}. "
                    f"Available expiries: {available}..."
                )

            # Fetch option chain
            chain = ticker_obj.option_chain(expiry_str)
            calls = chain.calls.copy()
            puts = chain.puts.copy()

            # Normalize IV field
            # yfinance should provide impliedVolatility in decimal form
            # but we'll handle both percentage (>1) and decimal forms
            for df in [calls, puts]:
                if 'impliedVolatility' not in df.columns:
                    warnings.warn(
                        f"No impliedVolatility field for {ticker} expiry {expiry_str}. "
                        "IV data is required for pricing."
                    )
                    df['impliedVolatility'] = None
                else:
                    # Convert percentage form to decimal if needed
                    # Assume if IV > 1, it's in percentage form
                    mask = df['impliedVolatility'] > 1.0
                    if mask.any():
                        df.loc[mask, 'impliedVolatility'] = df.loc[mask, 'impliedVolatility'] / 100.0

            # Drop rows with missing IV (NaN or None)
            calls_before = len(calls)
            puts_before = len(puts)

            calls = calls.dropna(subset=['impliedVolatility'])
            puts = puts.dropna(subset=['impliedVolatility'])

            calls_dropped = calls_before - len(calls)
            puts_dropped = puts_before - len(puts)

            if calls_dropped > 0 or puts_dropped > 0:
                warnings.warn(
                    f"Dropped {calls_dropped} calls and {puts_dropped} puts with missing IV "
                    f"for {ticker} expiry {expiry_str}"
                )

            # Ensure we have some data left
            if calls.empty and puts.empty:
                raise YFinanceClientError(
                    f"No valid option data (all IV missing) for {ticker} expiry {expiry_str}"
                )

            return calls, puts

        except Exception as e:
            if isinstance(e, YFinanceClientError):
                raise
            raise YFinanceClientError(
                f"Error fetching option chain for {ticker} expiry {expiry}: {e}"
            ) from e

    def get_dividend_yield(self, ticker: str) -> Optional[float]:
        """Fetch annual dividend yield for a ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "AAPL")

        Returns:
            Annual dividend yield in decimal form (e.g., 0.02 for 2%)
            Returns None if dividend data is not available

        Note:
            This is a best-effort method. For many tickers (especially crypto),
            dividend yield will be unavailable. Caller should default to 0 with warning.
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Try dividend yield field (already in decimal form)
            div_yield = info.get('dividendYield')

            if div_yield is not None:
                return float(div_yield)

            # Try computing from dividendRate and price
            div_rate = info.get('dividendRate')
            price = info.get('currentPrice') or info.get('regularMarketPrice')

            if div_rate is not None and price is not None and price > 0:
                return float(div_rate) / float(price)

            # No dividend data available
            return None

        except Exception:
            # Don't raise - dividend yield is optional
            return None
