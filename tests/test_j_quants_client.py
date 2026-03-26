"""J-Quants API クライアントのモックテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.j_quants_client import JQuantsClient


@pytest.fixture
def client():
    return JQuantsClient(refresh_token="test_refresh_token")


class TestEnsureToken:
    def test_fetches_token_on_first_call(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"idToken": "test_id_token"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            client._ensure_token()

        mock_post.assert_called_once()
        assert client.id_token == "test_id_token"
        assert client.token_expires_at > 0

    def test_skips_fetch_when_token_valid(self, client):
        import time
        client.id_token = "existing_token"
        client.token_expires_at = time.time() + 3600  # 1時間後まで有効

        with patch("requests.post") as mock_post:
            client._ensure_token()

        mock_post.assert_not_called()
        assert client.id_token == "existing_token"


class TestGetPricesDaily:
    def test_returns_daily_quotes(self, client):
        mock_quotes = [
            {"Code": "7203", "Date": "20260101", "Open": 3000, "Close": 3100},
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"daily_quotes": mock_quotes}

        with patch.object(client, "_get", return_value={"daily_quotes": mock_quotes}):
            result = client.get_prices_daily("7203")

        assert result == mock_quotes

    def test_returns_empty_list_when_no_data(self, client):
        with patch.object(client, "_get", return_value={}):
            result = client.get_prices_daily("9999")

        assert result == []

    def test_passes_date_params(self, client):
        with patch.object(client, "_get", return_value={"daily_quotes": []}) as mock_get:
            client.get_prices_daily("7203", date_from="20260101", date_to="20260131")

        mock_get.assert_called_once_with(
            "/prices/daily_quotes",
            {"code": "7203", "from": "20260101", "to": "20260131"},
        )


class TestGetFinancialStatements:
    def test_returns_statements(self, client):
        mock_statements = [{"PriceEarningsRatio": "15.5", "ROE": "12.3"}]
        with patch.object(client, "_get", return_value={"statements": mock_statements}):
            result = client.get_financial_statements("7203")

        assert result == mock_statements

    def test_returns_empty_list_when_no_data(self, client):
        with patch.object(client, "_get", return_value={}):
            result = client.get_financial_statements("9999")

        assert result == []


class TestGetMarginTrading:
    def test_returns_margin_data(self, client):
        mock_data = [{"ShortMarginTradeVolume": "1000", "LongMarginTradeVolume": "3000"}]
        with patch.object(client, "_get", return_value={"weekly_margin_interest": mock_data}):
            result = client.get_margin_trading("7203")

        assert result == mock_data

    def test_returns_empty_list_when_no_data(self, client):
        with patch.object(client, "_get", return_value={}):
            result = client.get_margin_trading("9999")

        assert result == []


class TestGetStockInfo:
    def test_returns_first_info(self, client):
        mock_info = [{"Code": "7203", "CompanyName": "トヨタ自動車", "Sector33Code": "3700"}]
        with patch.object(client, "_get", return_value={"info": mock_info}):
            result = client.get_stock_info("7203")

        assert result == mock_info[0]

    def test_returns_empty_dict_when_no_data(self, client):
        with patch.object(client, "_get", return_value={"info": []}):
            result = client.get_stock_info("9999")

        assert result == {}
