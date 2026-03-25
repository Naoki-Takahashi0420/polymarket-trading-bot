"""テーマ分析エージェント."""

from __future__ import annotations

import logging

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.theme_analyzer import THEME_SECTORS, ThemeAnalyzer

logger = logging.getLogger(__name__)


class ThemeAgent(BaseAgent):
    """アクティブテーマと銘柄の関連度で方向性を判断する."""

    def __init__(self, theme_analyzer: ThemeAnalyzer | None = None):
        super().__init__("theme")
        self.theme_analyzer = theme_analyzer or ThemeAnalyzer()

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        active_themes = kwargs.get("active_themes", [])

        if not active_themes:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="アクティブテーマなし",
            )

        # 銘柄が関連するテーマを抽出
        related = []
        for theme_info in active_themes:
            theme_name = theme_info.get("theme", "")
            related_symbols = theme_info.get("related_symbols", [])
            if not related_symbols:
                related_symbols = THEME_SECTORS.get(theme_name, [])
            if symbol in related_symbols:
                related.append(theme_info)

        if not related:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="銘柄に関連するテーマなし",
            )

        # 過去パターンと照合
        total_score = 0.0
        details = []
        for theme_info in related:
            theme_name = theme_info.get("theme", "")
            try:
                pattern = self.theme_analyzer.get_historical_pattern(theme_name)
            except Exception:
                pattern = {"event_count": 0, "avg_price_change": 0.0}

            event_count = pattern.get("event_count", 0)
            avg_change = pattern.get("avg_price_change", 0.0)

            if event_count <= 2:
                # テーマ初動
                total_score += 0.5
                details.append(f"{theme_name}(初動, events={event_count})")
            elif avg_change > 0:
                total_score += min(0.5, avg_change * 5)
                details.append(f"{theme_name}(過去+{avg_change:.2%})")
            else:
                # テーマ終盤 or ネガティブパターン
                total_score -= 0.3
                details.append(f"{theme_name}(終盤, avg={avg_change:.2%})")

        avg_score = total_score / len(related)

        if avg_score > 0.2:
            action = "BUY"
            confidence = min(1.0, 0.4 + abs(avg_score))
        elif avg_score < -0.2:
            action = "SELL"
            confidence = min(1.0, 0.3 + abs(avg_score))
        else:
            action = "HOLD"
            confidence = 0.3

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=", ".join(details),
        )
