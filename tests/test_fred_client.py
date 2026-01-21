"""Tests for FRED API client."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from polyarb.clients.fred import FredClient, FredClientError


@pytest.fixture
def fred_client():
    """Create FRED client with test API key."""
    return FredClient(api_key="test_api_key")


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.Client for isolated testing."""
    with patch("httpx.Client") as mock:
        yield mock


def test_fred_client_init_with_api_key():
    """Test FredClient initialization with explicit API key."""
    client = FredClient(api_key="my_key")
    assert client.api_key == "my_key"
    assert client.timeout == FredClient.DEFAULT_TIMEOUT


def test_fred_client_init_from_env():
    """Test FredClient initialization from environment variable."""
    with patch.dict(os.environ, {"FRED_API_KEY": "env_key"}):
        client = FredClient()
        assert client.api_key == "env_key"


def test_fred_client_init_no_api_key():
    """Test FredClient raises error when no API key provided."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(FredClientError, match="FRED API key not provided"):
            FredClient()


def test_get_latest_observation_success(fred_client, mock_httpx_client):
    """Test successful retrieval of latest observation."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {
                "value": "4.25",
                "date": "2026-01-15",
            }
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    value, obs_date = fred_client.get_latest_observation("DGS10")

    assert value == 4.25
    assert obs_date == datetime(2026, 1, 15)
    assert mock_httpx_client.return_value.__enter__.return_value.get.call_count == 1


def test_get_latest_observation_missing_value(fred_client, mock_httpx_client):
    """Test handling of missing observation value (FRED uses '.')."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {
                "value": ".",
                "date": "2026-01-15",
            }
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    with pytest.raises(FredClientError, match="Latest observation.*is missing"):
        fred_client.get_latest_observation("DGS10")


def test_get_latest_observation_no_observations(fred_client, mock_httpx_client):
    """Test handling of empty observations list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"observations": []}
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    with pytest.raises(FredClientError, match="No observations found"):
        fred_client.get_latest_observation("INVALID")


def test_get_latest_observation_invalid_value(fred_client, mock_httpx_client):
    """Test handling of non-numeric value."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {
                "value": "not_a_number",
                "date": "2026-01-15",
            }
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    with pytest.raises(FredClientError, match="Invalid value"):
        fred_client.get_latest_observation("DGS10")


def test_get_latest_observation_invalid_date(fred_client, mock_httpx_client):
    """Test handling of invalid date format."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "observations": [
            {
                "value": "4.25",
                "date": "invalid-date",
            }
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    with pytest.raises(FredClientError, match="Invalid date"):
        fred_client.get_latest_observation("DGS10")


def test_get_latest_observation_http_404(fred_client, mock_httpx_client):
    """Test handling of 404 HTTP error."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Series not found"
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=mock_response,
    )

    with pytest.raises(FredClientError, match="HTTP error"):
        fred_client.get_latest_observation("INVALID")


def test_get_latest_observation_http_400_bad_series(fred_client, mock_httpx_client):
    """Test handling of 400 error for invalid series ID."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request: series does not exist"
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.HTTPStatusError(
        "Bad Request",
        request=MagicMock(),
        response=mock_response,
    )

    with pytest.raises(FredClientError, match="Invalid series ID"):
        fred_client.get_latest_observation("BAD_SERIES")


def test_get_latest_observation_request_error(fred_client, mock_httpx_client):
    """Test handling of network request error."""
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.RequestError("Connection failed")

    with pytest.raises(FredClientError, match="Request error"):
        fred_client.get_latest_observation("DGS10")


def test_get_series_info_success(fred_client, mock_httpx_client):
    """Test successful retrieval of series metadata."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "seriess": [
            {
                "id": "DGS10",
                "title": "10-Year Treasury Constant Maturity Rate",
                "units": "Percent",
                "frequency": "Daily",
                "seasonal_adjustment": "Not Seasonally Adjusted",
            }
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    info = fred_client.get_series_info("DGS10")

    assert info["id"] == "DGS10"
    assert info["title"] == "10-Year Treasury Constant Maturity Rate"
    assert info["units"] == "Percent"


def test_get_series_info_not_found(fred_client, mock_httpx_client):
    """Test handling of series not found."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"seriess": []}
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    with pytest.raises(FredClientError, match="Series.*not found"):
        fred_client.get_series_info("INVALID")


def test_get_series_info_http_400(fred_client, mock_httpx_client):
    """Test handling of 400 error for get_series_info."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.HTTPStatusError(
        "Bad Request",
        request=MagicMock(),
        response=mock_response,
    )

    with pytest.raises(FredClientError, match="Invalid series ID"):
        fred_client.get_series_info("BAD")


def test_search_series_success(fred_client, mock_httpx_client):
    """Test successful search for series."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "seriess": [
            {
                "id": "DGS10",
                "title": "10-Year Treasury Constant Maturity Rate",
            },
            {
                "id": "DGS5",
                "title": "5-Year Treasury Constant Maturity Rate",
            },
        ]
    }
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    results = fred_client.search_series("treasury rate")

    assert len(results) == 2
    assert results[0]["id"] == "DGS10"
    assert results[1]["id"] == "DGS5"


def test_search_series_no_results(fred_client, mock_httpx_client):
    """Test search with no results."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"seriess": []}
    mock_httpx_client.return_value.__enter__.return_value.get.return_value = mock_response

    results = fred_client.search_series("nonexistent query xyz")

    assert results == []


def test_search_series_http_error(fred_client, mock_httpx_client):
    """Test handling of HTTP error during search."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.HTTPStatusError(
        "Internal Server Error",
        request=MagicMock(),
        response=mock_response,
    )

    with pytest.raises(FredClientError, match="HTTP error searching"):
        fred_client.search_series("test")


def test_search_series_request_error(fred_client, mock_httpx_client):
    """Test handling of request error during search."""
    mock_get = mock_httpx_client.return_value.__enter__.return_value.get
    mock_get.side_effect = httpx.RequestError("Network timeout")

    with pytest.raises(FredClientError, match="Request error searching"):
        fred_client.search_series("test")


def test_custom_timeout(mock_httpx_client):
    """Test that custom timeout is used."""
    client = FredClient(api_key="test_key", timeout=60.0)
    assert client.timeout == 60.0
