"""テーマ分析エージェント."""

from __future__ import annotations

import logging
import os

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.theme_analyzer import THEME_SECTORS, ThemeAnalyzer
from src.x_sentiment import XSentimentAnalyzer

logger = logging.getLogger(__name__)

# X上でのテーマバズ検知に使うキーワードマッピング
THEME_X_KEYWORDS: dict[str, list[str]] = {
    "防衛": ["防衛株", "防衛費", "軍事費", "防衛産業"],
    "半導体": ["半導体", "AI半導体", "NVIDIA", "tsmc"],
    "AI": ["生成AI", "ChatGPT", "AI投資", "人工知能"],
    "再生可能エネルギー": ["再エネ", "太陽光", "風力発電", "グリーン"],
    "EV": ["EV", "電気自動車", "テスラ", "バッテリー"],
    "インバウンド": ["インバウンド", "観光需要", "訪日客", "円安恩恵"],
}


class ThemeAgent(BaseAgent):
    """アクティブテーマと銘柄の関連度で方向性を判断する.

    X上のテーマ言及頻度をテーマ活性度に加算する。
    """

    def __init__(
        self,
        theme_analyzer: ThemeAnalyzer | None = None,
        x_analyzer: XSentimentAnalyzer | None = None,
    ):
        super().__init__("theme")
        self.theme_analyzer = theme_analyzer or ThemeAnalyzer()
        self.x_analyzer = x_analyzer or XSentimentAnalyzer(
            api_key=os.environ.get("GROK_API_KEY"),
            fallback_to_web=True,
        )

    def _get_x_theme_boost(self, theme_name: str) -> float:
        """X上のテーマ言及頻度に基づくブーストスコアを取得する.

        buzz_detected=True の場合 0.2 を返す、それ以外は 0.0。
        """
        keywords = THEME_X_KEYWORDS.get(theme_name)
        if not keywords:
            return 0.0
        try:
            query = " ".join(keywords[:2])  # 最初の2キーワードで検索
            result = self.x_analyzer.analyze_sentiment(query)
            if result.get("buzz_detected"):
                return 0.2
            x_score = result.get("sentiment_score", 0.0)
            return max(0.0, x_score * 0.1)
        except Exception as e:
            logger.warning("X theme boost failed for %s: %s", theme_name, e)
            return 0.0

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
                base_score = 0.5
                details.append(f"{theme_name}(初動, events={event_count})")
            elif avg_change > 0:
                base_score = min(0.5, avg_change * 5)
                details.append(f"{theme_name}(過去+{avg_change:.2%})")
            else:
                # テーマ終盤 or ネガティブパターン
                base_score = -0.3
                details.append(f"{theme_name}(終盤, avg={avg_change:.2%})")

            # X上のテーマ言及頻度を加算
            x_boost = self._get_x_theme_boost(theme_name)
            if x_boost > 0:
                details[-1] += f"+X{x_boost:.1f}"

            total_score += base_score + x_boost

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
