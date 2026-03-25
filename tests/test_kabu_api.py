"""kabu_api のユニットテスト（モック使用）."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.kabu_api import KabuApiClient, KabuApiConfig
from src.position_manager import Order


@pytest.fixture
def client():
    config = KabuApiConfig(host="localhost", port=18081, password="testpass")
    c = KabuApiClient(config)
    c._min_interval = 0  # テスト時はレート制限無効
    return c


class TestAuthenticate:
    @patch("src.kabu_api.requests.request")
    def test_authenticate_success(self, mock_req, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"Token": "abc123"}'
        mock_resp.json.return_value = {"Token": "abc123"}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        token = client.authenticate()
        assert token == "abc123"
        assert client.token == "abc123"

    @patch("src.kabu_api.requests.request")
    def test_authenticate_failure_retries(self, mock_req, client):
        mock_req.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(requests.exceptions.ConnectionError):
            client.authenticate()

        assert mock_req.call_count == 3  # 3 retries


class TestPlaceOrder:
    @patch("src.kabu_api.requests.request")
    def test_place_order_success(self, mock_req, client):
        client.token = "abc123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"OrderId": "20230101A01N001"}'
        mock_resp.json.return_value = {"OrderId": "20230101A01N001"}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100,
        )
        order_id = client.place_order(order)
        assert order_id == "20230101A01N001"

        # Verify the request was made to sendorder
        call_args = mock_req.call_args
        assert "/sendorder" in call_args[0][1]


class TestCancelOrder:
    @patch("src.kabu_api.requests.request")
    def test_cancel_order_success(self, mock_req, client):
        client.token = "abc123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        result = client.cancel_order("20230101A01N001")
        assert result is True


class TestGetBoard:
    @patch("src.kabu_api.requests.request")
    def test_get_board(self, mock_req, client):
        client.token = "abc123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"CurrentPrice": 150.5}'
        mock_resp.json.return_value = {"CurrentPrice": 150.5}
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        board = client.get_board("9432")
        assert board["CurrentPrice"] == 150.5


class TestRetryLogic:
    @patch("src.kabu_api.requests.request")
    @patch("src.kabu_api.time.sleep")
    def test_retry_with_backoff(self, mock_sleep, mock_req, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"Token": "ok"}'
        mock_resp.json.return_value = {"Token": "ok"}
        mock_resp.raise_for_status = MagicMock()

        # Fail twice, succeed on third
        mock_req.side_effect = [
            requests.exceptions.ConnectionError("fail1"),
            requests.exceptions.ConnectionError("fail2"),
            mock_resp,
        ]

        token = client.authenticate()
        assert token == "ok"
        assert mock_req.call_count == 3
        # Backoff: 2^0=1s, 2^1=2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
