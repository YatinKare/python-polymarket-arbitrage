"""Polymarket Gamma API client for market data."""

import json

import httpx
from datetime import datetime
from typing import Optional

from polyarb.models import Market
from polyarb.util.dates import parse_datetime


class GammaClientError(Exception):
    """Error raised by Gamma API client."""
    pass


class GammaClient:
    """Client for Polymarket Gamma API.

    Gamma API provides market metadata, outcomes, and token mappings.
    Base URL: https://gamma-api.polymarket.com
    """

    BASE_URL = "https://gamma-api.polymarket.com"
    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        """Initialize Gamma client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def get_market(self, market_id: str) -> Market:
        """Fetch market details by ID.

        Args:
            market_id: Polymarket market ID (condition ID)

        Returns:
            Market object with metadata and token mappings

        Raises:
            GammaClientError: If API request fails or data is invalid
        """
        url = f"{self.BASE_URL}/markets/{market_id}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise GammaClientError(f"Market {market_id} not found") from e
            raise GammaClientError(f"HTTP error fetching market {market_id}: {e}") from e
        except httpx.RequestError as e:
            raise GammaClientError(f"Request error fetching market {market_id}: {e}") from e
        except Exception as e:
            raise GammaClientError(f"Unexpected error fetching market {market_id}: {e}") from e

        return self._parse_market(data)

    def search_markets(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        closed: bool = False,
        archived: bool = False,
    ) -> list[Market]:
        """Search markets by query string.

        Args:
            query: Search text (searches title, description, tags)
            limit: Maximum number of markets to return
            offset: Number of markets to skip (for pagination)
            closed: Include closed markets
            archived: Include archived markets

        Returns:
            List of Market objects matching search criteria

        Raises:
            GammaClientError: If API request fails
        """
        url = f"{self.BASE_URL}/markets"

        # Build query parameters
        params = {
            "limit": limit,
            "offset": offset,
        }
        if query:
            params["query"] = query
        if closed:
            params["closed"] = "true"
        if archived:
            params["archived"] = "true"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise GammaClientError(f"HTTP error searching markets: {e}") from e
        except httpx.RequestError as e:
            raise GammaClientError(f"Request error searching markets: {e}") from e
        except Exception as e:
            raise GammaClientError(f"Unexpected error searching markets: {e}") from e

        # Gamma API may return list directly or nested in a data field
        # Handle both formats
        if isinstance(data, list):
            markets_data = data
        elif isinstance(data, dict) and "data" in data:
            markets_data = data["data"]
        else:
            raise GammaClientError(f"Unexpected API response format: {data}")

        markets = []
        for market_data in markets_data:
            try:
                market = self._parse_market(market_data)
                markets.append(market)
            except Exception as e:
                # Log warning but continue processing other markets
                print(f"Warning: Failed to parse market: {e}")
                continue

        return markets

    def public_search(self, query: str, limit: int = 10) -> list[Market]:
        """Search markets using the /public-search endpoint.

        Args:
            query: Search keyword (e.g. "BTC", "bitcoin")
            limit: Maximum number of markets to return

        Returns:
            Flattened list of Market objects from matching events

        Raises:
            GammaClientError: If API request fails
        """
        url = f"{self.BASE_URL}/public-search"
        params = {"q": query, "limit": limit}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise GammaClientError(f"HTTP error in public search: {e}") from e
        except httpx.RequestError as e:
            raise GammaClientError(f"Request error in public search: {e}") from e
        except Exception as e:
            raise GammaClientError(f"Unexpected error in public search: {e}") from e

        # Response: {"events": [{"markets": [...], ...}, ...]}
        events = data.get("events", [])

        markets = []
        for event in events:
            for market_data in event.get("markets", []):
                try:
                    market = self._parse_market(market_data)
                    markets.append(market)
                except Exception as e:
                    print(f"Warning: Failed to parse market in search result: {e}")
                    continue

        return markets

    def _parse_market(self, data: dict) -> Market:
        """Parse market data from API response.

        Args:
            data: Raw market data from API

        Returns:
            Parsed Market object

        Raises:
            GammaClientError: If required fields are missing or invalid
        """
        try:
            # Extract required fields
            market_id = data.get("id") or data.get("condition_id") or data.get("conditionId")
            if not market_id:
                raise GammaClientError("Missing market ID in response")

            title = data.get("title") or data.get("question", "")
            description = data.get("description", "")

            # Parse end date (may be endDate, end_date, or expirationDate)
            end_date_str = (
                data.get("endDate")
                or data.get("end_date")
                or data.get("expirationDate")
                or data.get("expiration_date")
            )
            if not end_date_str:
                raise GammaClientError("Missing end date in response")

            end_date = parse_datetime(end_date_str)

            # Parse outcomes
            outcomes_data = data.get("outcomes") or []
            if isinstance(outcomes_data, str):
                outcomes_data = json.loads(outcomes_data)
            if not outcomes_data:
                raise GammaClientError("Missing outcomes in response")

            outcomes = [str(outcome) for outcome in outcomes_data]

            # Parse CLOB token IDs mapping
            # Format may vary: clobTokenIds, clob_token_ids, tokens
            clob_token_ids_raw = (
                data.get("clobTokenIds")
                or data.get("clob_token_ids")
                or data.get("tokens")
                or []
            )

            if isinstance(clob_token_ids_raw, str):
                clob_token_ids_raw = json.loads(clob_token_ids_raw)

            # Build outcome -> token_id mapping
            clob_token_ids = {}
            if isinstance(clob_token_ids_raw, list):
                # List format: [token_id1, token_id2, ...]
                # Map by index to outcomes
                for i, token_id in enumerate(clob_token_ids_raw):
                    if i < len(outcomes):
                        clob_token_ids[outcomes[i]] = str(token_id)
            elif isinstance(clob_token_ids_raw, dict):
                # Dict format: {outcome: token_id, ...}
                clob_token_ids = {str(k): str(v) for k, v in clob_token_ids_raw.items()}

            # Note: For search results, CLOB token IDs may not always be present
            # Only the get_market() endpoint is guaranteed to have them

            # Parse optional status fields
            active = data.get("active", True)
            closed = data.get("closed", False)
            archived = data.get("archived", False)

            return Market(
                id=market_id,
                title=title,
                description=description,
                end_date=end_date,
                outcomes=outcomes,
                clob_token_ids=clob_token_ids,
                active=active,
                closed=closed,
                archived=archived,
            )

        except GammaClientError:
            raise
        except Exception as e:
            raise GammaClientError(f"Failed to parse market data: {e}") from e
