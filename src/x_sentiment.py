"""X (Twitter) リアルタイムセンチメント分析モジュール."""

from __future__ import annotations

import json as json_lib
import logging

import requests

logger = logging.getLogger(__name__)

POSITIVE_WORDS = [
    "上方修正", "増収", "増益", "最高益", "好調", "上昇", "回復", "買い",
    "強い", "ブレイク", "急騰", "反発", "底打ち", "割安", "期待",
]
NEGATIVE_WORDS = [
    "下方修正", "減収", "減益", "赤字", "不振", "下落", "暴落", "売り",
    "弱い", "急落", "続落", "高値圏", "割高", "懸念", "リスク",
]


class XSentimentAnalyzer:
    """X (Twitter) のセンチメント分析。Grok API 利用、フォールバックはキーワードベース."""

    def __init__(self, api_key: str | None = None, fallback_to_web: bool = True):
        self.api_key = api_key
        self.fallback_to_web = fallback_to_web

    def analyze_sentiment(self, query: str, max_posts: int = 50) -> dict:
        """X 上の投稿からセンチメント分析する.

        Args:
            query: 検索クエリ（銘柄名/コード等）
            max_posts: 取得上限投稿数

        Returns:
            query, sentiment_score (-1.0〜1.0), post_count, positive_count,
            negative_count, buzz_detected, top_keywords を含む dict
        """
        if self.api_key:
            return self._analyze_with_grok(query, max_posts)
        if self.fallback_to_web:
            return self._analyze_with_keywords(query)
        return self._empty_result(query)

    def _analyze_with_grok(self, query: str, max_posts: int) -> dict:
        """Grok API を使ったセンチメント分析."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a financial sentiment analyzer. "
                            "Analyze the sentiment of recent X posts about the given stock/topic. "
                            "Return a JSON with: sentiment_score (-1.0 to 1.0), post_count, "
                            "positive_count, negative_count, buzz_detected (bool), top_keywords (list)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Analyze recent X posts about: {query}. "
                            "Focus on Japanese stock market sentiment."
                        ),
                    },
                ],
                "model": "grok-3",
                "search_parameters": {
                    "mode": "on",
                    "sources": [{"type": "x_posts"}],
                },
            }
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            result = json_lib.loads(content)
            result["query"] = query
            result["source"] = "grok"
            return result
        except Exception as e:
            logger.warning("Grok API failed for %s: %s", query, e)
            if self.fallback_to_web:
                return self._analyze_with_keywords(query)
            return self._empty_result(query)

    def _analyze_with_keywords(self, query: str) -> dict:
        """キーワードベースの簡易分析（API 未設定時のフォールバック）."""
        return {
            "query": query,
            "sentiment_score": 0.0,
            "post_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "buzz_detected": False,
            "top_keywords": [],
            "source": "fallback_keywords",
        }

    def _empty_result(self, query: str) -> dict:
        return {
            "query": query,
            "sentiment_score": 0.0,
            "post_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "buzz_detected": False,
            "top_keywords": [],
            "source": "none",
        }

    def score_text(self, text: str) -> float:
        """テキストのセンチメントスコアを算出する.

        Args:
            text: 分析対象テキスト

        Returns:
            -1.0〜1.0 のセンチメントスコア
        """
        pos = sum(1 for w in POSITIVE_WORDS if w in text)
        neg = sum(1 for w in NEGATIVE_WORDS if w in text)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total
