"""Polymarket CLOB API client for price and order book data."""

import httpx
from datetime import datetime, timezone
from typing import Optional

from polyarb.models import TokenPrice, OrderBook, OrderBookLevel, Side


class ClobClientError(Exception):
    """Error raised by CLOB API client."""
    pass


class ClobClient:
    """Client for Polymarket CLOB (Central Limit Order Book) API.

    CLOB API provides real-time pricing and order book data for Polymarket tokens.
    Base URL: https://clob.polymarket.com
    """

    BASE_URL = "https://clob.polymarket.com"
    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize CLOB client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def get_price(self, token_id: str, side: Side = Side.BUY) -> TokenPrice:
        """Fetch best price for a token.

        Args:
            token_id: CLOB token ID
            side: Order side (BUY or SELL)
                  BUY = price to buy Yes token (sell No token)
                  SELL = price to sell Yes token (buy No token)

        Returns:
            TokenPrice object with best available price

        Raises:
            ClobClientError: If API request fails or data is invalid
        """
        url = f"{self.BASE_URL}/price"
        params = {
            "token_id": token_id,
            "side": side.value,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ClobClientError(f"Token {token_id} not found") from e
            raise ClobClientError(f"HTTP error fetching price for {token_id}: {e}") from e
        except httpx.RequestError as e:
            raise ClobClientError(f"Request error fetching price for {token_id}: {e}") from e
        except Exception as e:
            raise ClobClientError(f"Unexpected error fetching price for {token_id}: {e}") from e

        return self._parse_price(data, token_id, side)

    def get_book(self, token_id: str) -> OrderBook:
        """Fetch full order book for a token.

        Args:
            token_id: CLOB token ID

        Returns:
            OrderBook object with bids and asks

        Raises:
            ClobClientError: If API request fails or data is invalid
        """
        url = f"{self.BASE_URL}/book"
        params = {"token_id": token_id}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ClobClientError(f"Token {token_id} not found") from e
            raise ClobClientError(f"HTTP error fetching book for {token_id}: {e}") from e
        except httpx.RequestError as e:
            raise ClobClientError(f"Request error fetching book for {token_id}: {e}") from e
        except Exception as e:
            raise ClobClientError(f"Unexpected error fetching book for {token_id}: {e}") from e

        return self._parse_book(data, token_id)

    def get_yes_price(self, token_id: str) -> float:
        """Convenience method to get effective price for buying Yes tokens.

        This is the price you would pay to enter a Yes position.
        Uses best ask (lowest sell price) from order book if available,
        otherwise uses BUY side from /price endpoint.

        Args:
            token_id: CLOB token ID for Yes outcome

        Returns:
            Effective entry price for Yes position (in [0, 1] range)

        Raises:
            ClobClientError: If API request fails or data is invalid
        """
        try:
            # Try to get order book first (more accurate)
            book = self.get_book(token_id)
            if book.best_ask is not None:
                return book.best_ask
        except ClobClientError:
            # Fall back to /price endpoint if book fails
            pass

        # Use /price endpoint as fallback
        token_price = self.get_price(token_id, Side.BUY)
        return token_price.price

    def _parse_price(self, data: dict, token_id: str, side: Side) -> TokenPrice:
        """Parse price data from API response.

        Args:
            data: Raw price data from API
            token_id: Token ID for context
            side: Side for context

        Returns:
            Parsed TokenPrice object

        Raises:
            ClobClientError: If required fields are missing or invalid
        """
        try:
            # Extract price (may be in different fields)
            price_raw = data.get("price") or data.get("mid") or data.get("best_price")

            if price_raw is None:
                raise ClobClientError("Missing price in response")

            price = float(price_raw)

            # Validate price range
            if not 0 <= price <= 1:
                raise ClobClientError(f"Price {price} out of valid range [0, 1]")

            return TokenPrice(
                token_id=token_id,
                side=side,
                price=price,
            )

        except ClobClientError:
            raise
        except Exception as e:
            raise ClobClientError(f"Failed to parse price data: {e}") from e

    def _parse_book(self, data: dict, token_id: str) -> OrderBook:
        """Parse order book data from API response.

        Args:
            data: Raw order book data from API
            token_id: Token ID for context

        Returns:
            Parsed OrderBook object

        Raises:
            ClobClientError: If required fields are missing or invalid
        """
        try:
            # Extract bids and asks
            bids_raw = data.get("bids") or []
            asks_raw = data.get("asks") or []

            # Parse bids (buy orders)
            bids = []
            for bid in bids_raw:
                try:
                    # Bids may be [price, size] or {"price": x, "size": y}
                    if isinstance(bid, list):
                        price, size = float(bid[0]), float(bid[1])
                    else:
                        price = float(bid.get("price", 0))
                        size = float(bid.get("size", 0))

                    bids.append(OrderBookLevel(price=price, size=size))
                except (ValueError, IndexError, KeyError) as e:
                    # Skip invalid entries
                    continue

            # Parse asks (sell orders)
            asks = []
            for ask in asks_raw:
                try:
                    # Asks may be [price, size] or {"price": x, "size": y}
                    if isinstance(ask, list):
                        price, size = float(ask[0]), float(ask[1])
                    else:
                        price = float(ask.get("price", 0))
                        size = float(ask.get("size", 0))

                    asks.append(OrderBookLevel(price=price, size=size))
                except (ValueError, IndexError, KeyError) as e:
                    # Skip invalid entries
                    continue

            # Sort bids descending by price (highest first)
            bids.sort(key=lambda x: x.price, reverse=True)

            # Sort asks ascending by price (lowest first)
            asks.sort(key=lambda x: x.price)

            # Extract timestamp if available
            timestamp_raw = data.get("timestamp") or data.get("time")
            if timestamp_raw:
                try:
                    # Try parsing as ISO format or Unix timestamp
                    if isinstance(timestamp_raw, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_raw)
                    else:
                        timestamp = datetime.fromisoformat(str(timestamp_raw).replace('Z', '+00:00'))
                except Exception:
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            return OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                timestamp=timestamp,
            )

        except ClobClientError:
            raise
        except Exception as e:
            raise ClobClientError(f"Failed to parse order book data: {e}") from e
