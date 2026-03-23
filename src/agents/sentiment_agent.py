"""ニュースセンチメントエージェント."""

from __future__ import annotations

import logging

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.news_fetcher import NewsFetcher
from src.theme_analyzer import ThemeAnalyzer

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = ["上方修正", "増収", "最高益", "好調", "上昇", "回復"]
NEGATIVE_KEYWORDS = ["下方修正", "減収", "赤字", "不振", "下落", "暴落"]


class SentimentAgent(BaseAgent):
    """ニュースキーワードマッチでセンチメントを判定する."""

    def __init__(
        self,
        news_fetcher: NewsFetcher | None = None,
        theme_analyzer: ThemeAnalyzer | None = None,
    ):
        super().__init__("sentiment")
        self.news_fetcher = news_fetcher or NewsFetcher()
        self.theme_analyzer = theme_analyzer or ThemeAnalyzer()

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        news_items = kwargs.get("news_items")
        if news_items is None:
            try:
                news_items = self.news_fetcher.fetch_all()
            except Exception as e:
                logger.warning("Failed to fetch news: %s", e)
                news_items = []

        if not news_items:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="ニュースなし",
            )

        # キーワードマッチでスコア算出
        pos_count = 0
        neg_count = 0
        for item in news_items:
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            for kw in POSITIVE_KEYWORDS:
                if kw in text:
                    pos_count += 1
            for kw in NEGATIVE_KEYWORDS:
                if kw in text:
                    neg_count += 1

        # テーマ情報も加味
        theme_bonus = 0.0
        try:
            themes = self.theme_analyzer.detect_themes(news_items)
            for t in themes:
                if symbol in t.get("related_symbols", []):
                    theme_bonus += 0.1
        except Exception as e:
            logger.warning("Theme analysis failed: %s", e)

        total = pos_count + neg_count
        if total == 0:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="関連キーワードなし",
            )

        sentiment_score = (pos_count - neg_count) / total  # -1 to 1
        sentiment_score += theme_bonus
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        if sentiment_score > 0.2:
            action = "BUY"
            confidence = min(1.0, 0.3 + abs(sentiment_score) * 0.5)
        elif sentiment_score < -0.2:
            action = "SELL"
            confidence = min(1.0, 0.3 + abs(sentiment_score) * 0.5)
        else:
            action = "HOLD"
            confidence = 0.3

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=f"positive={pos_count}, negative={neg_count}, theme_bonus={theme_bonus:.1f}",
        )
