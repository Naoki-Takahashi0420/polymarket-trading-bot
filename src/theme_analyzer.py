"""テーマ分析エンジン: ニュースからテーマを検出し銘柄との関連を分析する."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "trading.db"

THEME_KEYWORDS: dict[str, list[str]] = {
    "戦争・地政学": ["戦争", "紛争", "制裁", "ミサイル", "軍事", "防衛"],
    "半導体": ["半導体", "TSMC", "エヌビディア", "GPU", "チップ"],
    "AI": ["AI", "人工知能", "LLM", "ChatGPT", "生成AI"],
    "脱炭素": ["脱炭素", "EV", "再エネ", "太陽光", "水素"],
    "金融政策": ["利上げ", "利下げ", "日銀", "FRB", "金融緩和", "インフレ"],
    "決算": ["決算", "増収", "減収", "上方修正", "下方修正"],
    "インバウンド": ["インバウンド", "訪日", "観光", "免税"],
    "不動産": ["不動産", "REIT", "地価", "マンション"],
}

THEME_SECTORS: dict[str, list[str]] = {
    "戦争・地政学": ["7011.T", "7012.T", "6208.T"],  # 三菱重工, 川崎重工, 石川製作所
    "半導体": ["8035.T", "6723.T", "6857.T"],  # 東京エレクトロン, ルネサス, アドバンテスト
    "AI": ["9984.T", "4849.T", "3993.T"],  # ソフトバンクG, エンジャパン, PKSHA
    "脱炭素": ["7203.T", "6752.T", "9519.T"],  # トヨタ, パナソニック, レノバ
    "金融政策": ["8306.T", "8316.T", "8411.T"],  # 三菱UFJ, 三井住友FG, みずほFG
    "決算": [],  # 決算は個別銘柄に依存
    "インバウンド": ["9603.T", "2801.T", "7832.T"],  # エイチ・アイ・エス, キッコーマン, バンナムHD
    "不動産": ["8802.T", "3462.T", "8830.T"],  # 三菱地所, 野村不動産マスターF, 住友不動産
}


class ThemeAnalyzer:
    """ニュースからテーマを検出し、銘柄インパクトを分析・記録する."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        theme_keywords: Optional[dict[str, list[str]]] = None,
        theme_sectors: Optional[dict[str, list[str]]] = None,
    ):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.theme_keywords = theme_keywords or THEME_KEYWORDS
        self.theme_sectors = theme_sectors or THEME_SECTORS

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def detect_themes(self, news_items: list[dict]) -> list[dict]:
        """ニュースからテーマを検出する.

        Args:
            news_items: [{"title": str, "summary": str, "link": str, ...}]

        Returns:
            [{"theme": str, "keywords_matched": list, "news_title": str, "news_url": str}]
        """
        results = []
        for item in news_items:
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            for theme, keywords in self.theme_keywords.items():
                matched = [kw for kw in keywords if kw in text]
                if matched:
                    results.append({
                        "theme": theme,
                        "keywords_matched": matched,
                        "news_title": item.get("title", ""),
                        "news_url": item.get("link", ""),
                        "related_symbols": self.theme_sectors.get(theme, []),
                    })
        return results

    def record_theme_event(self, theme: str, news_title: str, news_url: str = "") -> int:
        """テーマイベントをDBに記録する."""
        conn = self._connect()
        cursor = conn.cursor()

        # テーマが未登録なら登録
        cursor.execute("SELECT id FROM themes WHERE theme_name = ?", (theme,))
        row = cursor.fetchone()
        if row:
            theme_id = row[0]
        else:
            keywords = ",".join(self.theme_keywords.get(theme, []))
            cursor.execute(
                "INSERT INTO themes (theme_name, keywords) VALUES (?, ?)",
                (theme, keywords),
            )
            theme_id = cursor.lastrowid

        # イベント記録
        cursor.execute(
            "INSERT INTO theme_events (theme_id, news_title, news_url) VALUES (?, ?, ?)",
            (theme_id, news_title, news_url),
        )
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def record_theme_impact(
        self, theme: str, symbol: str, price_change_pct: float, period_days: int = 5,
    ) -> None:
        """テーマ発生→銘柄値動きをDBに記録する."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM themes WHERE theme_name = ?", (theme,))
        row = cursor.fetchone()
        if not row:
            logger.warning("Theme '%s' not found in DB, skipping impact record", theme)
            conn.close()
            return

        theme_id = row[0]
        cursor.execute(
            "INSERT INTO theme_impacts (theme_id, symbol, price_change_pct, period_days) VALUES (?, ?, ?, ?)",
            (theme_id, symbol, price_change_pct, period_days),
        )
        conn.commit()
        conn.close()

    def get_historical_pattern(self, theme: str) -> dict:
        """過去の同テーマ発生時のパターンを返す.

        Returns:
            {"theme": str, "event_count": int, "avg_price_change": float,
             "symbols": [{"symbol": str, "avg_change": float, "count": int}]}
        """
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM themes WHERE theme_name = ?", (theme,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"theme": theme, "event_count": 0, "avg_price_change": 0.0, "symbols": []}

        theme_id = row[0]

        # イベント数
        cursor.execute("SELECT COUNT(*) FROM theme_events WHERE theme_id = ?", (theme_id,))
        event_count = cursor.fetchone()[0]

        # 銘柄別平均変動
        cursor.execute(
            """SELECT symbol, AVG(price_change_pct), COUNT(*)
               FROM theme_impacts WHERE theme_id = ?
               GROUP BY symbol""",
            (theme_id,),
        )
        symbols = []
        total_change = 0.0
        total_count = 0
        for sym, avg_change, count in cursor.fetchall():
            symbols.append({"symbol": sym, "avg_change": round(avg_change, 4), "count": count})
            total_change += avg_change * count
            total_count += count

        avg_price_change = round(total_change / total_count, 4) if total_count > 0 else 0.0

        conn.close()
        return {
            "theme": theme,
            "event_count": event_count,
            "avg_price_change": avg_price_change,
            "symbols": symbols,
        }
