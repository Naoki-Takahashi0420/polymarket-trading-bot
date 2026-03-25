"""notifier のユニットテスト（モック使用）."""

from unittest.mock import MagicMock, patch

import pytest

from src.notifier import DailyReport, Notifier
from src.position_manager import Order, Position
from src.signal_generator import Signal, TradeSignal


@pytest.fixture
def notifier():
    return Notifier(webhook_url="https://discord.com/api/webhooks/test/test")


class TestNotifySignal:
    @patch("src.notifier.requests.post")
    def test_buy_signal_notification(self, mock_post, notifier):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        result = notifier.notify_signal(signal)
        assert result is True
        mock_post.assert_called_once()

        payload = mock_post.call_args[1]["json"]
        assert "BUY" in payload["embeds"][0]["title"]

    @patch("src.notifier.requests.post")
    def test_sell_signal_notification(self, mock_post, notifier):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        signal = TradeSignal(
            symbol="9432.T", signal=Signal.SELL,
            current_price=160.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        result = notifier.notify_signal(signal)
        assert result is True


class TestNotifyFill:
    @patch("src.notifier.requests.post")
    def test_fill_notification(self, mock_post, notifier):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100, order_id="ORD001",
            filled_price=149.5,
        )
        result = notifier.notify_fill(order)
        assert result is True

        payload = mock_post.call_args[1]["json"]
        assert "約定" in payload["embeds"][0]["title"]


class TestNotifyError:
    @patch("src.notifier.requests.post")
    def test_error_notification(self, mock_post, notifier):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        result = notifier.notify_error("API connection failed")
        assert result is True

        payload = mock_post.call_args[1]["json"]
        assert "エラー" in payload["embeds"][0]["title"]


class TestDailyReport:
    @patch("src.notifier.requests.post")
    def test_daily_report(self, mock_post, notifier):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        report = DailyReport(
            date="2026-03-21",
            total_pnl=5000.0,
            realized_pnl=3000.0,
            unrealized_pnl=2000.0,
            positions=[
                Position(symbol="9432.T", side="long", quantity=100, entry_price=150.0),
            ],
            trades_today=2,
            balance=1_005_000,
        )
        result = notifier.send_daily_report(report)
        assert result is True

        payload = mock_post.call_args[1]["json"]
        assert "日次レポート" in payload["embeds"][0]["title"]


class TestNoWebhook:
    def test_no_url_returns_false(self):
        n = Notifier(webhook_url="")
        result = n.notify_error("test")
        assert result is False
