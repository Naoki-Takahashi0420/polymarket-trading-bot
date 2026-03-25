"""ポートフォリオマネージャー: 全エージェントの意見を統合して最終判断を行う."""

from __future__ import annotations

import logging

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "technical": 0.30,
    "fundamental": 0.20,
    "sentiment": 0.15,
    "volume": 0.20,
    "theme": 0.15,
}


class PortfolioManager:
    """全エージェントから意見を収集し、加重投票で最終判断を行う."""

    def __init__(
        self,
        agents: list[BaseAgent],
        weights: dict[str, float] | None = None,
        buy_threshold: float = 0.3,
        sell_threshold: float = -0.3,
    ):
        self.agents = agents
        self.weights = weights or DEFAULT_WEIGHTS
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def evaluate(self, symbol: str, data: pd.DataFrame, **kwargs) -> dict:
        """全エージェントから意見を収集し、加重投票で最終判断する."""
        opinions: list[AgentOpinion] = []

        for agent in self.agents:
            try:
                opinion = agent.analyze(symbol, data, **kwargs)
                opinions.append(opinion)
            except Exception as e:
                logger.error("Agent %s error for %s: %s", agent.name, symbol, e)
                opinions.append(AgentOpinion(
                    agent_name=agent.name, symbol=symbol,
                    action="HOLD", confidence=0.0, reasoning=f"Error: {e}",
                ))

        # 加重スコア計算
        score = 0.0
        for opinion in opinions:
            weight = self.weights.get(opinion.agent_name, 0.1)
            action_value = {"BUY": 1.0, "SELL": -1.0, "HOLD": 0.0}[opinion.action]
            score += action_value * opinion.confidence * weight

        # 正規化（-1 to 1）
        total_weight = sum(self.weights.get(o.agent_name, 0.1) for o in opinions)
        normalized_score = score / total_weight if total_weight > 0 else 0.0

        if normalized_score > self.buy_threshold:
            final_action = "BUY"
        elif normalized_score < self.sell_threshold:
            final_action = "SELL"
        else:
            final_action = "HOLD"

        return {
            "symbol": symbol,
            "final_action": final_action,
            "final_score": round(normalized_score, 4),
            "opinions": opinions,
            "reasoning": self._build_reasoning(opinions, final_action, normalized_score),
        }

    def _build_reasoning(
        self,
        opinions: list[AgentOpinion],
        final_action: str,
        score: float,
    ) -> str:
        lines = [f"最終判断: {final_action} (score={score:.4f})"]
        for o in opinions:
            w = self.weights.get(o.agent_name, 0.1)
            lines.append(f"  [{o.agent_name}] {o.action}(conf={o.confidence:.2f}, w={w:.2f}) - {o.reasoning}")
        return "\n".join(lines)
