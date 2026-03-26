"""X センチメント分析モジュールのモックテスト."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.x_sentiment import XSentimentAnalyzer


@pytest.fixture
def analyzer_no_key():
    return XSentimentAnalyzer(api_key=None, fallback_to_web=True)


@pytest.fixture
def analyzer_with_key():
    return XSentimentAnalyzer(api_key="test_grok_key", fallback_to_web=True)


class TestAnalyzeSentiment:
    def test_fallback_when_no_api_key(self, analyzer_no_key):
        result = analyzer_no_key.analyze_sentiment("7203.T")
        assert result["source"] == "fallback_keywords"
        assert result["query"] == "7203.T"
        assert -1.0 <= result["sentiment_score"] <= 1.0

    def test_returns_required_keys(self, analyzer_no_key):
        result = analyzer_no_key.analyze_sentiment("トヨタ")
        required = {"query", "sentiment_score", "post_count", "positive_count",
                    "negative_count", "buzz_detected", "top_keywords"}
        assert required.issubset(result.keys())

    def test_empty_result_when_no_fallback(self):
        analyzer = XSentimentAnalyzer(api_key=None, fallback_to_web=False)
        result = analyzer.analyze_sentiment("7203.T")
        assert result["source"] == "none"

    def test_grok_api_called_when_key_provided(self, analyzer_with_key):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "sentiment_score": 0.8,
                        "post_count": 120,
                        "positive_count": 90,
                        "negative_count": 10,
                        "buzz_detected": True,
                        "top_keywords": ["増益", "好調"],
                    })
                }
            }]
        }
        with patch("requests.post", return_value=mock_resp):
            result = analyzer_with_key.analyze_sentiment("7203.T")

        assert result["sentiment_score"] == 0.8
        assert result["buzz_detected"] is True
        assert result["source"] == "grok"

    def test_grok_falls_back_on_error(self, analyzer_with_key):
        with patch("requests.post", side_effect=Exception("network error")):
            result = analyzer_with_key.analyze_sentiment("7203.T")

        assert result["source"] == "fallback_keywords"


class TestScoreText:
    def test_positive_text(self):
        analyzer = XSentimentAnalyzer()
        score = analyzer.score_text("上方修正で最高益を達成、好調な業績")
        assert score > 0

    def test_negative_text(self):
        analyzer = XSentimentAnalyzer()
        score = analyzer.score_text("下方修正で減収減益、暴落が懸念される")
        assert score < 0

    def test_neutral_text(self):
        analyzer = XSentimentAnalyzer()
        score = analyzer.score_text("今日は晴れです")
        assert score == 0.0

    def test_mixed_text_returns_ratio(self):
        analyzer = XSentimentAnalyzer()
        # 2 positive, 1 negative → (2-1)/3 ≈ 0.333
        score = analyzer.score_text("上方修正 増収 赤字")
        assert score > 0
        assert score < 1.0

    def test_score_range(self):
        analyzer = XSentimentAnalyzer()
        texts = [
            "上方修正 増収 増益 最高益 好調 上昇",
            "下方修正 減収 減益 赤字 不振 下落 暴落",
            "",
        ]
        for text in texts:
            score = analyzer.score_text(text)
            assert -1.0 <= score <= 1.0
