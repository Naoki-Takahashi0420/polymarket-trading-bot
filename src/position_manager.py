"""SQLiteベースのポジション・注文管理モジュール."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "trading.db"


@dataclass
class Position:
    symbol: str
    side: str  # "long" or "short"
    quantity: int
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: str = ""
    id: Optional[int] = None
    status: str = "open"


@dataclass
class Order:
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "limit"
    price: float
    quantity: int
    trade_type: str = "spot"  # "spot" or "margin"
    order_id: str = ""
    status: str = "pending"  # pending/filled/cancelled/error
    created_at: str = ""
    filled_at: str = ""
    filled_price: float = 0.0
    id: Optional[int] = None


class PositionManager:
    """SQLiteでポジション・注文履歴を永続化し、リスク管理を行う."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        max_positions: int = 3,
        max_per_stock: float = 500_000,
    ):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.max_positions = max_positions
        self.max_per_stock = max_per_stock
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                close_price REAL,
                pnl REAL,
                status TEXT DEFAULT 'open',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                filled_price REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_pnl REAL,
                realized_pnl REAL,
                unrealized_pnl REAL,
                balance REAL,
                trades_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def add_position(self, position: Position) -> int:
        """ポジションを追加し、IDを返す."""
        now = position.opened_at or datetime.now().isoformat()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO positions (symbol, side, quantity, entry_price, status, opened_at)
               VALUES (?, ?, ?, ?, 'open', ?)""",
            (position.symbol, position.side, position.quantity, position.entry_price, now),
        )
        pos_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return pos_id

    def close_position(self, symbol: str, close_price: float) -> Optional[float]:
        """指定銘柄のオープンポジションをクローズし、PnLを返す."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, side, quantity, entry_price FROM positions WHERE symbol = ? AND status = 'open' LIMIT 1",
            (symbol,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        pos_id, side, quantity, entry_price = row
        if side == "long":
            pnl = (close_price - entry_price) * quantity
        else:
            pnl = (entry_price - close_price) * quantity

        now = datetime.now().isoformat()
        cursor.execute(
            """UPDATE positions SET status = 'closed', close_price = ?, pnl = ?, closed_at = ?
               WHERE id = ?""",
            (close_price, pnl, now, pos_id),
        )
        conn.commit()
        conn.close()
        return pnl

    def get_open_positions(self) -> list[Position]:
        """オープンポジション一覧を取得する."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, symbol, side, quantity, entry_price, opened_at FROM positions WHERE status = 'open'"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Position(
                id=r[0],
                symbol=r[1],
                side=r[2],
                quantity=r[3],
                entry_price=r[4],
                opened_at=r[5],
            )
            for r in rows
        ]

    def can_open_new_position(self, amount: float = 0) -> bool:
        """新規ポジションを開けるかチェックする."""
        positions = self.get_open_positions()
        if len(positions) >= self.max_positions:
            return False
        if amount > self.max_per_stock:
            return False
        return True

    def save_order(self, order: Order) -> int:
        """注文を保存し、IDを返す."""
        now = order.created_at or datetime.now().isoformat()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (order_id, symbol, side, order_type, price, quantity, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (order.order_id, order.symbol, order.side, order.order_type,
             order.price, order.quantity, order.status, now),
        )
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return order_id

    def update_order_status(self, order_id: str, status: str, filled_price: float = 0.0) -> None:
        """注文ステータスを更新する."""
        now = datetime.now().isoformat()
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ?, filled_price = ?, updated_at = ? WHERE order_id = ?",
            (status, filled_price, now, order_id),
        )
        conn.commit()
        conn.close()

    def get_pending_orders(self) -> list[Order]:
        """未約定の注文一覧を取得する."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, order_id, symbol, side, order_type, price, quantity, status, created_at FROM orders WHERE status = 'pending'"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Order(
                id=r[0],
                order_id=r[1],
                symbol=r[2],
                side=r[3],
                order_type=r[4],
                price=r[5],
                quantity=r[6],
                status=r[7],
                created_at=r[8],
            )
            for r in rows
        ]

    def get_daily_pnl(self, date: Optional[str] = None) -> float:
        """指定日（デフォルト今日）のクローズ済みポジションのPnL合計を返す."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(pnl), 0) FROM positions WHERE status = 'closed' AND closed_at LIKE ?",
            (f"{date}%",),
        )
        result = cursor.fetchone()[0]
        conn.close()
        return float(result)

    def save_daily_report(
        self, date: str, total_pnl: float, realized_pnl: float,
        unrealized_pnl: float, balance: float, trades_count: int,
    ) -> None:
        """日次レポートを保存する."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO daily_reports (date, total_pnl, realized_pnl, unrealized_pnl, balance, trades_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date, total_pnl, realized_pnl, unrealized_pnl, balance, trades_count),
        )
        conn.commit()
        conn.close()
