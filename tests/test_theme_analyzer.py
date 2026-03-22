"""theme_analyzer のユニットテスト."""

import sqlite3
from pathlib import Path

import pytest

from src.theme_analyzer import ThemeAnalyzer, THEME_KEYWORDS, THEME_SECTORS


@pytest.fixture
def tmp_db(tmp_path):
    """テスト用の一時DBを作成する."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_name TEXT UNIQUE NOT NULL,
            keywords TEXT,
            first_detected_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS theme_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER REFERENCES themes(id),
            news_title TEXT,
            news_url TEXT,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS theme_impacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER REFERENCES themes(id),
            symbol TEXT NOT NULL,
            price_change_pct REAL,
            period_days INTEGER,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def analyzer(tmp_db):
    return ThemeAnalyzer(db_path=tmp_db)


class TestDetectThemes:
    def test_detect_semiconductor_theme(self, analyzer):
        news = [{"title": "半導体需要が急増、TSMCが増産計画", "summary": "", "link": "https://example.com"}]
        results = analyzer.detect_themes(news)
        assert len(results) >= 1
        themes = [r["theme"] for r in results]
        assert "半導体" in themes

    def test_detect_multiple_themes(self, analyzer):
        news = [{"title": "AI半導体の需要拡大でGPU不足深刻化", "summary": "", "link": ""}]
        results = analyzer.detect_themes(news)
        themes = [r["theme"] for r in results]
        assert "半導体" in themes
        assert "AI" in themes

    def test_no_theme_detected(self, analyzer):
        news = [{"title": "天気予報: 明日は晴れ", "summary": "", "link": ""}]
        results = analyzer.detect_themes(news)
        assert len(results) == 0

    def test_related_symbols_included(self, analyzer):
        news = [{"title": "日銀が利上げを決定", "summary": "", "link": ""}]
        results = analyzer.detect_themes(news)
        assert len(results) >= 1
        fin_results = [r for r in results if r["theme"] == "金融政策"]
        assert len(fin_results) == 1
        assert "8306.T" in fin_results[0]["related_symbols"]


class TestRecordAndRetrieve:
    def test_record_theme_event(self, analyzer):
        event_id = analyzer.record_theme_event("半導体", "TSMC増産ニュース", "https://example.com")
        assert event_id > 0

    def test_record_theme_impact(self, analyzer):
        analyzer.record_theme_event("半導体", "テストニュース")
        analyzer.record_theme_impact("半導体", "8035.T", 3.5, period_days=5)

        pattern = analyzer.get_historical_pattern("半導体")
        assert pattern["event_count"] == 1
        assert len(pattern["symbols"]) == 1
        assert pattern["symbols"][0]["symbol"] == "8035.T"
        assert pattern["symbols"][0]["avg_change"] == 3.5

    def test_get_pattern_nonexistent_theme(self, analyzer):
        pattern = analyzer.get_historical_pattern("存在しないテーマ")
        assert pattern["event_count"] == 0
        assert pattern["symbols"] == []
