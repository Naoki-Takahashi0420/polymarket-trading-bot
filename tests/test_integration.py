"""結合テスト — ペーパーモードで1サイクル実行."""

from unittest.mock import MagicMock, patch
from datetime import datetime

import pandas as pd
import numpy as np
import pytest

from src.main import TradingBot, is_trading_hours, load_config


def _make_test_config(tmp_path):
    """テスト用設定を返す."""
    return {
        "symbols": ["9432.T", "7203.T"],
        "range_detection": {
            "lookback_days": 60,
            "bb_width_threshold": 0.08,
            "atr_ratio_threshold": 0.02,
            "range_containment_threshold": 0.70,
        },
        "backtest": {"initial_cash": 1_000_000},
        "kabu_api": {"host": "localhost", "port": 18081, "password": ""},
        "trading": {
            "mode": "paper",
            "position_size_pct": 0.10,
            "stop_loss_pct": 0.03,
            "max_positions": 3,
            "max_per_stock": 500_000,
            "interval_seconds": 1,
            "stale_order_minutes": 30,
        },
        "notification": {"discord_webhook_url": ""},
        "logging": {"level": "DEBUG", "log_dir": str(tmp_path / "logs")},
    }


def _make_ohlcv_df(base_price=150.0, days=100):
    """テスト用のOHLCVデータを生成する."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    close = base_price + np.cumsum(np.random.randn(days) * 0.5)
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": np.random.randint(100000, 1000000, days),
    }, index=dates)


class TestIsTradingHours:
    def test_morning_session(self):
        t = datetime(2026, 3, 21, 10, 0)
        assert is_trading_hours(t) == "morning"

    def test_lunch_break(self):
        t = datetime(2026, 3, 21, 12, 0)
        assert is_trading_hours(t) == "lunch"

    def test_afternoon_session(self):
        t = datetime(2026, 3, 21, 13, 0)
        assert is_trading_hours(t) == "afternoon"

    def test_pre_market(self):
        t = datetime(2026, 3, 21, 8, 56)
        assert is_trading_hours(t) == "pre_market"

    def test_post_market(self):
        t = datetime(2026, 3, 21, 15, 35)
        assert is_trading_hours(t) == "post_market"

    def test_closed_early(self):
        t = datetime(2026, 3, 21, 7, 0)
        assert is_trading_hours(t) == "closed"

    def test_closed_late(self):
        t = datetime(2026, 3, 21, 16, 0)
        assert is_trading_hours(t) == "closed"


class TestTradingBotCycle:
    @patch("src.main.fetch_ohlcv")
    @patch("src.main.fetch_multiple")
    def test_one_trading_cycle(self, mock_fetch_multiple, mock_fetch_ohlcv, tmp_path):
        """ペーパーモードで1サイクルがエラーなく完了することを確認."""
        config = _make_test_config(tmp_path)
        # Override DB path to tmp
        config["_db_path"] = str(tmp_path / "test.db")

        bot = TradingBot(config)
        bot.position_manager.db_path = tmp_path / "test.db"
        bot.position_manager._init_db()

        # Mock data
        df = _make_ohlcv_df()
        mock_fetch_multiple.return_value = {
            "9432.T": df,
            "7203.T": _make_ohlcv_df(base_price=200.0),
        }
        mock_fetch_ohlcv.return_value = df

        # Run one cycle
        bot.trading_loop()

        # No errors = success. Check that it ran without exceptions.

    def test_pre_market_check_paper(self, tmp_path):
        """ペーパーモードのプリマーケットチェックが成功する."""
        config = _make_test_config(tmp_path)
        bot = TradingBot(config)
        bot.position_manager.db_path = tmp_path / "test.db"
        bot.position_manager._init_db()

        result = bot.pre_market_check()
        assert result is True

    @patch("src.main.fetch_ohlcv")
    @patch("src.main.fetch_multiple")
    def test_post_market_report(self, mock_fetch_multiple, mock_fetch_ohlcv, tmp_path):
        """日次レポート生成がエラーなく完了する."""
        config = _make_test_config(tmp_path)
        bot = TradingBot(config)
        bot.position_manager.db_path = tmp_path / "test.db"
        bot.position_manager._init_db()

        bot.post_market_report()
        # No errors = success


class TestGracefulShutdown:
    def test_shutdown_handler(self, tmp_path):
        config = _make_test_config(tmp_path)
        bot = TradingBot(config)
        bot.running = True

        bot._handle_shutdown(2, None)
        assert bot.running is False
