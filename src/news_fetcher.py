"""RSSフィードからニュースを自動取得するモジュール."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)

DEFAULT_FEEDS = {
    "reuters_jp": "https://assets.wor.jp/rss/rdf/reuters/top.rdf",
    "nikkei": "https://assets.wor.jp/rss/rdf/nikkei/news.rdf",
}


class NewsFetcher:
    """RSSフィードからニュースを取得しキーワードを抽出する."""

    def __init__(self, feeds: Optional[dict[str, str]] = None):
        self.feeds = feeds or DEFAULT_FEEDS

    def fetch_feed(self, url: str) -> list[dict]:
        """単一RSSフィードからエントリを取得する."""
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries:
                published = ""
                if hasattr(entry, "published"):
                    published = entry.published
                elif hasattr(entry, "updated"):
                    published = entry.updated

                items.append({
                    "title": getattr(entry, "title", ""),
                    "link": getattr(entry, "link", ""),
                    "summary": getattr(entry, "summary", ""),
                    "published": published,
                    "fetched_at": datetime.now().isoformat(),
                })
            return items
        except Exception as e:
            logger.error("Failed to fetch feed %s: %s", url, e)
            return []

    def fetch_all(self) -> list[dict]:
        """全RSSフィードからニュースを取得する."""
        all_items = []
        for name, url in self.feeds.items():
            items = self.fetch_feed(url)
            for item in items:
                item["source"] = name
            all_items.extend(items)
            logger.info("Fetched %d items from %s", len(items), name)
        return all_items

    def extract_keywords(self, text: str) -> list[str]:
        """テキストからキーワードを抽出する（正規表現ベース）."""
        keywords = []

        # カタカナ語（3文字以上）
        katakana = re.findall(r"[\u30A0-\u30FF]{3,}", text)
        keywords.extend(katakana)

        # 英字略語（2文字以上の大文字）
        acronyms = re.findall(r"\b[A-Z]{2,}\b", text)
        keywords.extend(acronyms)

        # 漢字の複合語（2〜6文字）
        kanji = re.findall(r"[\u4E00-\u9FFF]{2,6}", text)
        keywords.extend(kanji)

        return list(set(keywords))
