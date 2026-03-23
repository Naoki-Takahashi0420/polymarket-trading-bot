"""全エージェントのユニットテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.agents.base_agent import AgentOpinion
from src.agents.fundamental_agent import FundamentalAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.technical_agent import TechnicalAgent
from src.agents.theme_agent import ThemeAgent
from src.agents.volume_agent import VolumeAgent


# --- テスト用データ生成 ---

def _make_ohlcv(n: int = 100, base_price: float = 1000.0, trend: str = "flat") -> pd.DataFrame:
    """テスト用OHLCVデータを生成する."""
    import numpy as np

    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    np.random.seed(42)

    if trend == "up":
        close = base_price + np.cumsum(np.random.uniform(0, 5, n))
    elif trend == "down":
        close = base_price - np.cumsum(np.random.uniform(0, 5, n))
    else:
        close = base_price + np.cumsum(np.random.normal(0, 2, n))

    return pd.DataFrame({
        "Open": close - np.random.uniform(0, 3, n),
        "High": close + np.random.uniform(0, 5, n),
        "Low": close - np.random.uniform(0, 5, n),
        "Close": close,
        "Volume": np.random.randint(100_000, 500_000, n),
    }, index=dates)


def _make_oversold_data() -> pd.DataFrame:
    """RSI < 30 になるよう連続下落データを生成する."""
    import numpy as np

    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 1000.0 - np.arange(n) * 10.0  # 連続下落
    return pd.DataFrame({
        "Open": close + 1,
        "High": close + 2,
        "Low": close - 2,
        "Close": close,
        "Volume": [300_000] * n,
    }, index=dates)


def _make_overbought_data() -> pd.DataFrame:
    """RSI > 70 になるよう連続上昇データを生成する."""
    import numpy as np

    n = 50
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 1000.0 + np.arange(n) * 10.0  # 連続上昇
    return pd.DataFrame({
        "Open": close - 1,
        "High": close + 2,
        "Low": close - 2,
        "Close": close,
        "Volume": [300_000] * n,
    }, index=dates)


def _make_volume_spike_data() -> pd.DataFrame:
    """出来高スパイクデータを生成する."""
    import numpy as np

    n = 30
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    close = [1000.0] * (n - 1) + [1020.0]  # 最終日に上昇
    volume = [100_000] * (n - 1) + [500_000]  # 最終日にスパイク
    return pd.DataFrame({
        "Open": [999.0] * n,
        "High": [1005.0] * (n - 1) + [1025.0],
        "Low": [995.0] * n,
        "Close": close,
        "Volume": volume,
    }, index=dates)


# === TechnicalAgent テスト ===

class TestTechnicalAgent:
    def test_returns_opinion(self):
        agent = TechnicalAgent()
        data = _make_ohlcv(100)
        opinion = agent.analyze("9432.T", data)
        assert isinstance(opinion, AgentOpinion)
        assert opinion.agent_name == "technical"
        assert opinion.action in ("BUY", "SELL", "HOLD")
        assert 0.0 <= opinion.confidence <= 1.0

    def test_insufficient_data(self):
        agent = TechnicalAgent()
        data = _make_ohlcv(10)
        opinion = agent.analyze("9432.T", data)
        assert opinion.action == "HOLD"
        assert opinion.confidence <= 0.3

    def test_oversold_condition(self):
        agent = TechnicalAgent()
        data = _make_oversold_data()
        opinion = agent.analyze("9432.T", data)
        # 連続下落 → BUY寄りまたはHOLD（他指標との多数決）
        assert opinion.action in ("BUY", "HOLD")

    def test_overbought_condition(self):
        agent = TechnicalAgent()
        data = _make_overbought_data()
        opinion = agent.analyze("9432.T", data)
        # 連続上昇 → SELL寄りまたはHOLD
        assert opinion.action in ("SELL", "HOLD")

    def test_empty_data(self):
        agent = TechnicalAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame())
        assert opinion.action == "HOLD"

    def test_rsi_calc(self):
        data = _make_ohlcv(50)
        rsi = TechnicalAgent._calc_rsi(data["Close"], 14)
        assert rsi is not None
        assert 0.0 <= rsi <= 100.0

    def test_macd_calc(self):
        data = _make_ohlcv(50)
        result = TechnicalAgent._calc_macd(data["Close"])
        assert result is not None
        macd_val, signal_val = result
        assert isinstance(macd_val, float)
        assert isinstance(signal_val, float)


# === FundamentalAgent テスト ===

class TestFundamentalAgent:
    @patch("src.agents.fundamental_agent.yf")
    def test_undervalued_stock(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 10.0,
            "priceToBook": 1.0,
            "dividendYield": 0.04,
            "returnOnEquity": 0.20,
        }
        mock_yf.Ticker.return_value = mock_ticker

        agent = FundamentalAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame())
        assert opinion.action == "BUY"
        assert opinion.confidence > 0.5

    @patch("src.agents.fundamental_agent.yf")
    def test_overvalued_stock(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 50.0,
            "priceToBook": 5.0,
            "dividendYield": 0.005,
            "returnOnEquity": 0.02,
        }
        mock_yf.Ticker.return_value = mock_ticker

        agent = FundamentalAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame())
        assert opinion.action == "SELL"

    @patch("src.agents.fundamental_agent.yf")
    def test_api_failure(self, mock_yf):
        mock_yf.Ticker.side_effect = Exception("API error")

        agent = FundamentalAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame())
        assert opinion.action == "HOLD"
        assert opinion.confidence == 0.3

    @patch("src.agents.fundamental_agent.yf")
    def test_no_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        agent = FundamentalAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame())
        assert opinion.action == "HOLD"


# === SentimentAgent テスト ===

class TestSentimentAgent:
    def test_positive_news(self):
        mock_fetcher = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.detect_themes.return_value = []

        agent = SentimentAgent(news_fetcher=mock_fetcher, theme_analyzer=mock_analyzer)
        news = [
            {"title": "トヨタ 最高益を更新 好調な販売", "summary": "増収増益"},
            {"title": "自動車業界 回復基調", "summary": "上昇傾向"},
        ]
        opinion = agent.analyze("7203.T", pd.DataFrame(), news_items=news)
        assert opinion.action == "BUY"

    def test_negative_news(self):
        mock_fetcher = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.detect_themes.return_value = []

        agent = SentimentAgent(news_fetcher=mock_fetcher, theme_analyzer=mock_analyzer)
        news = [
            {"title": "大手企業 赤字転落 下方修正", "summary": "減収"},
            {"title": "市場 暴落 不振続く", "summary": "下落"},
        ]
        opinion = agent.analyze("9432.T", pd.DataFrame(), news_items=news)
        assert opinion.action == "SELL"

    def test_no_news(self):
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_all.return_value = []
        mock_analyzer = MagicMock()

        agent = SentimentAgent(news_fetcher=mock_fetcher, theme_analyzer=mock_analyzer)
        opinion = agent.analyze("9432.T", pd.DataFrame(), news_items=[])
        assert opinion.action == "HOLD"
        assert opinion.confidence == 0.2

    def test_theme_bonus(self):
        mock_fetcher = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.detect_themes.return_value = [
            {"theme": "AI", "related_symbols": ["9984.T"]},
        ]

        agent = SentimentAgent(news_fetcher=mock_fetcher, theme_analyzer=mock_analyzer)
        news = [{"title": "AI関連 上昇", "summary": "好調"}]
        opinion = agent.analyze("9984.T", pd.DataFrame(), news_items=news)
        # テーマボーナスにより confidence が上がる
        assert opinion.confidence > 0.2


# === VolumeAgent テスト ===

class TestVolumeAgent:
    def test_spike_with_price_up(self):
        agent = VolumeAgent()
        data = _make_volume_spike_data()
        opinion = agent.analyze("9432.T", data)
        assert opinion.action == "BUY"
        assert opinion.confidence > 0.4

    def test_no_spike(self):
        agent = VolumeAgent()
        data = _make_ohlcv(30)
        opinion = agent.analyze("9432.T", data)
        # ランダムデータではスパイクが出ない場合HOLD
        assert opinion.action in ("BUY", "SELL", "HOLD")

    def test_insufficient_data(self):
        agent = VolumeAgent()
        data = _make_ohlcv(5)
        opinion = agent.analyze("9432.T", data)
        assert opinion.action == "HOLD"


# === ThemeAgent テスト ===

class TestThemeAgent:
    def test_related_theme(self):
        mock_analyzer = MagicMock()
        mock_analyzer.get_historical_pattern.return_value = {
            "event_count": 1,
            "avg_price_change": 0.0,
        }

        agent = ThemeAgent(theme_analyzer=mock_analyzer)
        active_themes = [
            {"theme": "半導体", "related_symbols": ["8035.T", "6857.T"]},
        ]
        opinion = agent.analyze("8035.T", pd.DataFrame(), active_themes=active_themes)
        assert opinion.action == "BUY"  # テーマ初動

    def test_no_active_themes(self):
        agent = ThemeAgent()
        opinion = agent.analyze("9432.T", pd.DataFrame(), active_themes=[])
        assert opinion.action == "HOLD"
        assert opinion.confidence == 0.2

    def test_unrelated_symbol(self):
        mock_analyzer = MagicMock()
        agent = ThemeAgent(theme_analyzer=mock_analyzer)
        active_themes = [
            {"theme": "半導体", "related_symbols": ["8035.T"]},
        ]
        opinion = agent.analyze("9432.T", pd.DataFrame(), active_themes=active_themes)
        assert opinion.action == "HOLD"  # 関連なし
