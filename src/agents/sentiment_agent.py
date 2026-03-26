"""ニュースセンチメントエージェント."""

from __future__ import annotations

import logging
import os

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.news_fetcher import NewsFetcher
from src.theme_analyzer import ThemeAnalyzer
from src.x_sentiment import XSentimentAnalyzer

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = ["上方修正", "増収", "最高益", "好調", "上昇", "回復"]
NEGATIVE_KEYWORDS = ["下方修正", "減収", "赤字", "不振", "下落", "暴落"]


class SentimentAgent(BaseAgent):
    """ニュースキーワードマッチ + Xセンチメントでセンチメントを判定する.

    重み: ニュース 60% + Xセンチメント 40%
    X上でのバズ検知 → confidence を 0.2 上乗せ
    """

    def __init__(
        self,
        news_fetcher: NewsFetcher | None = None,
        theme_analyzer: ThemeAnalyzer | None = None,
        x_analyzer: XSentimentAnalyzer | None = None,
    ):
        super().__init__("sentiment")
        self.news_fetcher = news_fetcher or NewsFetcher()
        self.theme_analyzer = theme_analyzer or ThemeAnalyzer()
        self.x_analyzer = x_analyzer or XSentimentAnalyzer(
            api_key=os.environ.get("GROK_API_KEY"),
            fallback_to_web=True,
        )

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        news_items = kwargs.get("news_items")
        if news_items is None:
            try:
                news_items = self.news_fetcher.fetch_all()
            except Exception as e:
                logger.warning("Failed to fetch news: %s", e)
                news_items = []

        # --- ニュースセンチメント（重み 0.6）---
        news_score = 0.0
        pos_count = 0
        neg_count = 0
        if news_items:
            for item in news_items:
                text = f"{item.get('title', '')} {item.get('summary', '')}"
                for kw in POSITIVE_KEYWORDS:
                    if kw in text:
                        pos_count += 1
                for kw in NEGATIVE_KEYWORDS:
                    if kw in text:
                        neg_count += 1
            total = pos_count + neg_count
            if total > 0:
                news_score = (pos_count - neg_count) / total

        # テーマ情報も加味
        theme_bonus = 0.0
        try:
            themes = self.theme_analyzer.detect_themes(news_items or [])
            for t in themes:
                if symbol in t.get("related_symbols", []):
                    theme_bonus += 0.1
        except Exception as e:
            logger.warning("Theme analysis failed: %s", e)

        news_score = max(-1.0, min(1.0, news_score + theme_bonus))

        # --- Xセンチメント（重み 0.4）---
        x_score = 0.0
        buzz_detected = False
        try:
            x_result = self.x_analyzer.analyze_sentiment(symbol)
            x_score = x_result.get("sentiment_score", 0.0)
            buzz_detected = x_result.get("buzz_detected", False)
        except Exception as e:
            logger.warning("X sentiment analysis failed for %s: %s", symbol, e)

        # 統合スコア
        combined_score = news_score * 0.6 + x_score * 0.4

        if pos_count == 0 and neg_count == 0 and x_score == 0.0:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="センチメント情報なし",
            )

        if combined_score > 0.2:
            action = "BUY"
            confidence = min(1.0, 0.3 + abs(combined_score) * 0.5)
        elif combined_score < -0.2:
            action = "SELL"
            confidence = min(1.0, 0.3 + abs(combined_score) * 0.5)
        else:
            action = "HOLD"
            confidence = 0.3

        # バズ検知 → confidence 上乗せ
        if buzz_detected:
            confidence = min(1.0, confidence + 0.2)

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=(
                f"news_score={news_score:.2f}(pos={pos_count},neg={neg_count}), "
                f"x_score={x_score:.2f}, buzz={buzz_detected}, "
                f"theme_bonus={theme_bonus:.1f}"
            ),
        )
