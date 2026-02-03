"""Tests for Polymarket Gamma API client."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from polyarb.clients.polymarket_gamma import GammaClient, GammaClientError
from polyarb.models import Market


@pytest.fixture
def sample_market_response():
    """Sample market response from Gamma API."""
    return {
        "id": "0x123abc",
        "condition_id": "0x123abc",
        "title": "Will BTC reach $100k by end of 2024?",
        "description": "This market resolves to Yes if Bitcoin...",
        "endDate": "2024-12-31T23:59:59Z",
        "outcomes": ["Yes", "No"],
        "clobTokenIds": ["0xtoken1", "0xtoken2"],
        "active": True,
        "closed": False,
        "archived": False,
    }


@pytest.fixture
def sample_markets_list_response():
    """Sample markets list response from Gamma API."""
    return [
        {
            "id": "0x111",
            "title": "Market 1",
            "description": "Description 1",
            "endDate": "2024-12-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
            "clobTokenIds": ["0xa", "0xb"],
        },
        {
            "id": "0x222",
            "title": "Market 2",
            "description": "Description 2",
            "endDate": "2025-01-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
            "clobTokenIds": ["0xc", "0xd"],
        },
    ]


class TestGammaClient:
    """Test cases for GammaClient."""

    def test_init(self):
        """Test client initialization."""
        client = GammaClient()
        assert client.timeout == GammaClient.DEFAULT_TIMEOUT

        client_custom = GammaClient(timeout=60.0)
        assert client_custom.timeout == 60.0

    @patch("httpx.Client")
    def test_get_market_success(self, mock_client_class, sample_market_response):
        """Test successful market fetch."""
        # Setup mock
        mock_response = Mock()
        mock_response.json.return_value = sample_market_response
        mock_response.raise_for_status = Mock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False

        mock_client_class.return_value = mock_client

        # Test
        client = GammaClient()
        market = client.get_market("0x123abc")

        # Verify
        assert isinstance(market, Market)
        assert market.id == "0x123abc"
        assert market.title == "Will BTC reach $100k by end of 2024?"
        assert market.description == "This market resolves to Yes if Bitcoin..."
        assert len(market.outcomes) == 2
        assert market.outcomes == ["Yes", "No"]
        assert market.clob_token_ids == {"Yes": "0xtoken1", "No": "0xtoken2"}
        assert market.active is True
        assert market.closed is False
        assert market.has_binary_outcomes is True

        # Verify API call
        mock_client.get.assert_called_once_with(
            "https://gamma-api.polymarket.com/markets/0x123abc"
        )

    @patch("httpx.Client")
    def test_get_market_not_found(self, mock_client_class):
        """Test market not found error."""
        # Setup mock for 404
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404")

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False

        # Need to make raise_for_status raise HTTPStatusError
        import httpx
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=Mock(), response=mock_response
        )

        mock_client_class.return_value = mock_client

        # Test
        client = GammaClient()
        with pytest.raises(GammaClientError, match="not found"):
            client.get_market("0xnonexistent")

    @patch("httpx.Client")
    def test_search_markets_success(self, mock_client_class, sample_markets_list_response):
        """Test successful market search routes through /public-search."""
        # Setup mock — /public-search returns {events: [{markets: [...]}]}
        mock_response = Mock()
        mock_response.json.return_value = {"events": [{"markets": sample_markets_list_response}]}
        mock_response.raise_for_status = Mock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False

        mock_client_class.return_value = mock_client

        # Test
        client = GammaClient()
        markets = client.search_markets(query="BTC", limit=10)

        # Verify
        assert len(markets) == 2
        assert all(isinstance(m, Market) for m in markets)
        assert markets[0].id == "0x111"
        assert markets[1].id == "0x222"

        # Verify API call went to /public-search with correct params
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://gamma-api.polymarket.com/public-search"
        assert call_args[1]["params"]["q"] == "BTC"
        assert call_args[1]["params"]["limit"] == 10

    @patch("httpx.Client")
    def test_search_markets_with_data_wrapper(self, mock_client_class, sample_markets_list_response):
        """Test market search when response has data wrapper."""
        # Setup mock with data wrapper
        mock_response = Mock()
        mock_response.json.return_value = {"data": sample_markets_list_response}
        mock_response.raise_for_status = Mock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False

        mock_client_class.return_value = mock_client

        # Test
        client = GammaClient()
        markets = client.search_markets()

        # Verify
        assert len(markets) == 2

    def test_parse_market_missing_id(self):
        """Test parsing market with missing ID."""
        client = GammaClient()
        data = {
            "title": "Test Market",
            "endDate": "2024-12-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
        }

        with pytest.raises(GammaClientError, match="Missing market ID"):
            client._parse_market(data)

    def test_parse_market_missing_end_date(self):
        """Test parsing market with missing end date."""
        client = GammaClient()
        data = {
            "id": "0x123",
            "title": "Test Market",
            "outcomes": ["Yes", "No"],
        }

        with pytest.raises(GammaClientError, match="Missing end date"):
            client._parse_market(data)

    def test_parse_market_missing_outcomes(self):
        """Test parsing market with missing outcomes."""
        client = GammaClient()
        data = {
            "id": "0x123",
            "title": "Test Market",
            "endDate": "2024-12-31T23:59:59Z",
        }

        with pytest.raises(GammaClientError, match="Missing outcomes"):
            client._parse_market(data)

    def test_parse_market_dict_token_ids(self):
        """Test parsing market with dict-format token IDs."""
        client = GammaClient()
        data = {
            "id": "0x123",
            "title": "Test Market",
            "endDate": "2024-12-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
            "clobTokenIds": {"Yes": "0xa", "No": "0xb"},
        }

        market = client._parse_market(data)
        assert market.clob_token_ids == {"Yes": "0xa", "No": "0xb"}

    def test_parse_market_alternate_field_names(self):
        """Test parsing market with alternate API field names."""
        client = GammaClient()
        data = {
            "conditionId": "0x456",  # alternate for id
            "question": "Will it rain?",  # alternate for title
            "expirationDate": "2024-12-31T23:59:59Z",  # alternate for endDate
            "outcomes": ["Yes", "No"],
            "tokens": ["0xa", "0xb"],  # alternate for clobTokenIds
        }

        market = client._parse_market(data)
        assert market.id == "0x456"
        assert market.title == "Will it rain?"
        assert market.end_date.year == 2024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
