"""Tests for Polymarket CLOB API client."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import httpx

from polyarb.clients.polymarket_clob import ClobClient, ClobClientError
from polyarb.models import TokenPrice, OrderBook, OrderBookLevel, Side


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.Client."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        yield mock_client


def test_get_price_success(mock_httpx_client):
    """Test successful price fetch."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"price": "0.55"}
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    # Create client and fetch price
    client = ClobClient()
    result = client.get_price("token123", Side.BUY)

    # Verify
    assert isinstance(result, TokenPrice)
    assert result.token_id == "token123"
    assert result.side == Side.BUY
    assert result.price == 0.55

    # Verify API call
    mock_httpx_client.get.assert_called_once()
    call_args = mock_httpx_client.get.call_args
    assert "/price" in call_args[0][0]
    assert call_args[1]["params"]["token_id"] == "token123"
    assert call_args[1]["params"]["side"] == "BUY"


def test_get_price_alternate_field_names(mock_httpx_client):
    """Test price parsing with alternate field names."""
    # Test with "mid" field
    mock_response = Mock()
    mock_response.json.return_value = {"mid": "0.45"}
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    result = client.get_price("token456", Side.SELL)

    assert result.price == 0.45
    assert result.side == Side.SELL


def test_get_price_best_price_field(mock_httpx_client):
    """Test price parsing with best_price field."""
    mock_response = Mock()
    mock_response.json.return_value = {"best_price": "0.67"}
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    result = client.get_price("token789", Side.BUY)

    assert result.price == 0.67


def test_get_price_invalid_range(mock_httpx_client):
    """Test price validation for out-of-range values."""
    mock_response = Mock()
    mock_response.json.return_value = {"price": "1.5"}  # Invalid: > 1
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    with pytest.raises(ClobClientError, match="out of valid range"):
        client.get_price("token_bad", Side.BUY)


def test_get_price_missing_price(mock_httpx_client):
    """Test error when price field is missing."""
    mock_response = Mock()
    mock_response.json.return_value = {}  # No price field
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    with pytest.raises(ClobClientError, match="Missing price"):
        client.get_price("token_missing", Side.BUY)


def test_get_price_404_error(mock_httpx_client):
    """Test handling of 404 error (token not found)."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_httpx_client.get.side_effect = httpx.HTTPStatusError(
        "Not Found", request=Mock(), response=mock_response
    )

    client = ClobClient()
    with pytest.raises(ClobClientError, match="not found"):
        client.get_price("nonexistent", Side.BUY)


def test_get_book_success_list_format(mock_httpx_client):
    """Test successful order book fetch with list format."""
    # Mock response with [price, size] format
    mock_response = Mock()
    mock_response.json.return_value = {
        "bids": [
            ["0.60", "100"],
            ["0.59", "200"],
            ["0.58", "150"],
        ],
        "asks": [
            ["0.61", "120"],
            ["0.62", "180"],
            ["0.63", "90"],
        ],
        "timestamp": 1234567890,
    }
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    # Create client and fetch book
    client = ClobClient()
    result = client.get_book("token_book")

    # Verify
    assert isinstance(result, OrderBook)
    assert result.token_id == "token_book"
    assert len(result.bids) == 3
    assert len(result.asks) == 3

    # Verify bids sorted descending
    assert result.bids[0].price == 0.60
    assert result.bids[1].price == 0.59
    assert result.bids[2].price == 0.58

    # Verify asks sorted ascending
    assert result.asks[0].price == 0.61
    assert result.asks[1].price == 0.62
    assert result.asks[2].price == 0.63

    # Verify best prices
    assert result.best_bid == 0.60
    assert result.best_ask == 0.61
    assert result.mid_price == 0.605

    # Verify timestamp
    assert isinstance(result.timestamp, datetime)


def test_get_book_dict_format(mock_httpx_client):
    """Test order book parsing with dict format."""
    # Mock response with {"price": x, "size": y} format
    mock_response = Mock()
    mock_response.json.return_value = {
        "bids": [
            {"price": "0.55", "size": "300"},
            {"price": "0.54", "size": "250"},
        ],
        "asks": [
            {"price": "0.56", "size": "200"},
            {"price": "0.57", "size": "400"},
        ],
    }
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    result = client.get_book("token_dict")

    # Verify parsing
    assert len(result.bids) == 2
    assert len(result.asks) == 2
    assert result.bids[0].price == 0.55
    assert result.bids[0].size == 300
    assert result.asks[0].price == 0.56
    assert result.asks[0].size == 200


def test_get_book_empty(mock_httpx_client):
    """Test order book with no orders."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "bids": [],
        "asks": [],
    }
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    result = client.get_book("token_empty")

    assert len(result.bids) == 0
    assert len(result.asks) == 0
    assert result.best_bid is None
    assert result.best_ask is None
    assert result.mid_price is None


def test_get_book_unsorted_input(mock_httpx_client):
    """Test that order book is sorted even if API returns unsorted data."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "bids": [
            ["0.50", "100"],
            ["0.60", "200"],  # Higher price, should be first after sorting
            ["0.55", "150"],
        ],
        "asks": [
            ["0.70", "100"],
            ["0.62", "200"],  # Lower price, should be first after sorting
            ["0.65", "150"],
        ],
    }
    mock_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_response

    client = ClobClient()
    result = client.get_book("token_unsorted")

    # Verify bids sorted descending
    assert result.bids[0].price == 0.60  # Highest
    assert result.bids[1].price == 0.55
    assert result.bids[2].price == 0.50  # Lowest

    # Verify asks sorted ascending
    assert result.asks[0].price == 0.62  # Lowest
    assert result.asks[1].price == 0.65
    assert result.asks[2].price == 0.70  # Highest


def test_get_yes_price_from_book(mock_httpx_client):
    """Test get_yes_price using order book best ask."""
    # Mock book response
    mock_book_response = Mock()
    mock_book_response.json.return_value = {
        "bids": [["0.58", "100"]],
        "asks": [["0.62", "150"]],
    }
    mock_book_response.raise_for_status.return_value = None
    mock_httpx_client.get.return_value = mock_book_response

    client = ClobClient()
    price = client.get_yes_price("token_yes")

    # Should return best ask from book
    assert price == 0.62


def test_get_yes_price_fallback_to_price_endpoint(mock_httpx_client):
    """Test get_yes_price fallback when book fails."""
    call_count = [0]

    def mock_get(url, **kwargs):
        call_count[0] += 1
        if "/book" in url:
            # First call to /book fails
            raise httpx.RequestError("Connection failed")
        else:
            # Second call to /price succeeds
            response = Mock()
            response.json.return_value = {"price": "0.65"}
            response.raise_for_status.return_value = None
            return response

    mock_httpx_client.get.side_effect = mock_get

    client = ClobClient()
    price = client.get_yes_price("token_fallback")

    # Should fall back to /price endpoint
    assert price == 0.65
    assert call_count[0] == 2  # Called both /book and /price


def test_get_book_404_error(mock_httpx_client):
    """Test handling of 404 error for order book."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_httpx_client.get.side_effect = httpx.HTTPStatusError(
        "Not Found", request=Mock(), response=mock_response
    )

    client = ClobClient()
    with pytest.raises(ClobClientError, match="not found"):
        client.get_book("nonexistent")


def test_custom_timeout():
    """Test client initialization with custom timeout."""
    client = ClobClient(timeout=60.0)
    assert client.timeout == 60.0


def test_base_url():
    """Test that client uses correct base URL."""
    client = ClobClient()
    assert client.BASE_URL == "https://clob.polymarket.com"
