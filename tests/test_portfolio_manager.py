"""ポートフォリオマネージャーのユニットテスト."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.portfolio_manager import PortfolioManager


class DummyAgent(BaseAgent):
    """テスト用のダミーエージェント."""

    def __init__(self, name: str, action: str, confidence: float):
        super().__init__(name)
        self._action = action
        self._confidence = confidence

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        return AgentOpinion(
            agent_name=self.name,
            symbol=symbol,
            action=self._action,
            confidence=self._confidence,
            reasoning=f"dummy {self._action}",
        )


class ErrorAgent(BaseAgent):
    """エラーを発生させるダミーエージェント."""

    def __init__(self, name: str):
        super().__init__(name)

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        raise RuntimeError("agent error")


class TestPortfolioManager:
    def test_all_buy(self):
        agents = [
            DummyAgent("technical", "BUY", 0.8),
            DummyAgent("fundamental", "BUY", 0.7),
            DummyAgent("sentiment", "BUY", 0.6),
            DummyAgent("volume", "BUY", 0.8),
            DummyAgent("theme", "BUY", 0.7),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert result["final_action"] == "BUY"
        assert result["final_score"] > 0.3
        assert len(result["opinions"]) == 5

    def test_all_sell(self):
        agents = [
            DummyAgent("technical", "SELL", 0.8),
            DummyAgent("fundamental", "SELL", 0.7),
            DummyAgent("sentiment", "SELL", 0.6),
            DummyAgent("volume", "SELL", 0.8),
            DummyAgent("theme", "SELL", 0.7),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert result["final_action"] == "SELL"
        assert result["final_score"] < -0.3

    def test_mixed_opinions_hold(self):
        agents = [
            DummyAgent("technical", "BUY", 0.5),
            DummyAgent("fundamental", "SELL", 0.5),
            DummyAgent("sentiment", "HOLD", 0.5),
            DummyAgent("volume", "BUY", 0.3),
            DummyAgent("theme", "SELL", 0.3),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert result["final_action"] == "HOLD"

    def test_confidence_weighting(self):
        # 高confidence BUY vs 低confidence SELL → BUY が勝つ
        agents = [
            DummyAgent("technical", "BUY", 1.0),
            DummyAgent("fundamental", "BUY", 0.9),
            DummyAgent("sentiment", "SELL", 0.1),
            DummyAgent("volume", "SELL", 0.1),
            DummyAgent("theme", "HOLD", 0.5),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert result["final_action"] == "BUY"

    def test_custom_weights(self):
        agents = [
            DummyAgent("technical", "BUY", 0.8),
            DummyAgent("fundamental", "SELL", 0.8),
        ]
        # technical に重み100%
        weights = {"technical": 1.0, "fundamental": 0.0}
        pm = PortfolioManager(agents=agents, weights=weights)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert result["final_action"] == "BUY"

    def test_custom_thresholds(self):
        agents = [
            DummyAgent("technical", "BUY", 0.5),
            DummyAgent("fundamental", "HOLD", 0.5),
            DummyAgent("sentiment", "HOLD", 0.5),
            DummyAgent("volume", "HOLD", 0.5),
            DummyAgent("theme", "HOLD", 0.5),
        ]
        # 低い閾値 → BUY になりやすい
        pm = PortfolioManager(agents=agents, buy_threshold=0.05)
        result = pm.evaluate("9432.T", pd.DataFrame())
        assert result["final_action"] == "BUY"

    def test_agent_error_handled(self):
        agents = [
            DummyAgent("technical", "BUY", 0.8),
            ErrorAgent("fundamental"),
            DummyAgent("sentiment", "BUY", 0.6),
            DummyAgent("volume", "BUY", 0.7),
            DummyAgent("theme", "BUY", 0.7),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        # エラーエージェントはHOLD(conf=0)扱い、他のBUYが勝つ
        assert result["final_action"] == "BUY"
        assert len(result["opinions"]) == 5
        error_opinion = [o for o in result["opinions"] if o.agent_name == "fundamental"][0]
        assert error_opinion.action == "HOLD"
        assert error_opinion.confidence == 0.0

    def test_reasoning_contains_all_agents(self):
        agents = [
            DummyAgent("technical", "BUY", 0.8),
            DummyAgent("fundamental", "SELL", 0.5),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())

        assert "technical" in result["reasoning"]
        assert "fundamental" in result["reasoning"]

    def test_score_range(self):
        agents = [
            DummyAgent("technical", "BUY", 1.0),
            DummyAgent("fundamental", "BUY", 1.0),
            DummyAgent("sentiment", "BUY", 1.0),
            DummyAgent("volume", "BUY", 1.0),
            DummyAgent("theme", "BUY", 1.0),
        ]
        pm = PortfolioManager(agents=agents)
        result = pm.evaluate("9432.T", pd.DataFrame())
        assert -1.0 <= result["final_score"] <= 1.0

    def test_empty_agents(self):
        pm = PortfolioManager(agents=[])
        result = pm.evaluate("9432.T", pd.DataFrame())
        assert result["final_action"] == "HOLD"
        assert result["final_score"] == 0.0
