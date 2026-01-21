"""FRED (Federal Reserve Economic Data) API client for risk-free rates."""

import os
from typing import Optional
from datetime import datetime

import httpx


class FredClientError(Exception):
    """Error raised by FRED API client."""
    pass


class FredClient:
    """Client for FRED (Federal Reserve Economic Data) API.

    FRED API provides economic data series including risk-free rates.
    Base URL: https://api.stlouisfed.org/fred
    Requires API key from environment variable FRED_API_KEY.
    """

    BASE_URL = "https://api.stlouisfed.org/fred"
    DEFAULT_TIMEOUT = 30.0  # seconds

    def __init__(self, api_key: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        """Initialize FRED client.

        Args:
            api_key: FRED API key. If not provided, reads from FRED_API_KEY env var.
            timeout: Request timeout in seconds

        Raises:
            FredClientError: If API key is not provided and not in environment
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise FredClientError(
                "FRED API key not provided. Set FRED_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self.timeout = timeout

    def get_latest_observation(self, series_id: str) -> tuple[float, datetime]:
        """Fetch the latest observation for a FRED series.

        Args:
            series_id: FRED series ID (e.g., "DGS10" for 10-Year Treasury)

        Returns:
            Tuple of (value, observation_date) where value is the latest rate
            and observation_date is when it was observed.

        Raises:
            FredClientError: If API request fails or data is invalid
        """
        url = f"{self.BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",  # Most recent first
            "limit": 1,  # Only need the latest
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Check if it's an invalid series ID
                error_msg = e.response.text
                if "Bad Request" in error_msg or "series does not exist" in error_msg.lower():
                    raise FredClientError(f"Invalid series ID: {series_id}") from e
            raise FredClientError(f"HTTP error fetching series {series_id}: {e}") from e
        except httpx.RequestError as e:
            raise FredClientError(f"Request error fetching series {series_id}: {e}") from e
        except Exception as e:
            raise FredClientError(f"Unexpected error fetching series {series_id}: {e}") from e

        # Parse response
        observations = data.get("observations", [])
        if not observations:
            raise FredClientError(f"No observations found for series {series_id}")

        latest = observations[0]
        value_str = latest.get("value")
        date_str = latest.get("date")

        if not value_str or not date_str:
            raise FredClientError(f"Invalid observation data for series {series_id}")

        # Handle missing values (FRED uses "." for missing data)
        if value_str == ".":
            raise FredClientError(f"Latest observation for series {series_id} is missing")

        try:
            value = float(value_str)
        except ValueError as e:
            raise FredClientError(f"Invalid value '{value_str}' for series {series_id}") from e

        try:
            # FRED uses YYYY-MM-DD format
            obs_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as e:
            raise FredClientError(f"Invalid date '{date_str}' for series {series_id}") from e

        return value, obs_date

    def get_series_info(self, series_id: str) -> dict:
        """Fetch metadata for a FRED series.

        Args:
            series_id: FRED series ID

        Returns:
            Dictionary with series metadata (title, units, frequency, etc.)

        Raises:
            FredClientError: If API request fails or series not found
        """
        url = f"{self.BASE_URL}/series"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise FredClientError(f"Invalid series ID: {series_id}") from e
            raise FredClientError(f"HTTP error fetching series info {series_id}: {e}") from e
        except httpx.RequestError as e:
            raise FredClientError(f"Request error fetching series info {series_id}: {e}") from e
        except Exception as e:
            raise FredClientError(f"Unexpected error fetching series info {series_id}: {e}") from e

        series_list = data.get("seriess", [])
        if not series_list:
            raise FredClientError(f"Series {series_id} not found")

        return series_list[0]

    def search_series(self, query: str, limit: int = 10) -> list[dict]:
        """Search for FRED series by keyword.

        Args:
            query: Search query text
            limit: Maximum number of results to return

        Returns:
            List of series metadata dictionaries

        Raises:
            FredClientError: If API request fails
        """
        url = f"{self.BASE_URL}/series/search"
        params = {
            "search_text": query,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": limit,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise FredClientError(f"HTTP error searching series with query '{query}': {e}") from e
        except httpx.RequestError as e:
            raise FredClientError(f"Request error searching series with query '{query}': {e}") from e
        except Exception as e:
            raise FredClientError(f"Unexpected error searching series with query '{query}': {e}") from e

        return data.get("seriess", [])
