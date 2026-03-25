"""ペーパートレードシミュレーターモジュール."""

from __future__ import annotations

import csv
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.position_manager import Order, Position

logger = logging.getLogger(__name__)


class PaperTrader:
    """仮想残高・仮想ポジションで取引をシミュレートする."""

    def __init__(self, initial_cash: float = 1_000_000):
        self.cash: float = initial_cash
        self.initial_cash: float = initial_cash
        self.positions: dict[str, Position] = {}  # symbol -> Position
        self.pending_orders: list[Order] = []
        self.history: list[dict] = []

    def place_order(self, order: Order) -> str:
        """仮想注文を受け付け、仮想注文IDを返す."""
        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        order.order_id = order_id
        order.status = "pending"
        order.created_at = datetime.now().isoformat()
        self.pending_orders.append(order)
        logger.info("[Paper] Order placed: %s %s %s @ %.1f (ID: %s)",
                     order.side, order.symbol, order.quantity, order.price, order_id)
        return order_id

    def check_fills(self, current_prices: dict[str, float]) -> list[Order]:
        """現在価格を見て、指値到達した注文を約定させる."""
        filled = []
        remaining = []

        for order in self.pending_orders:
            price = current_prices.get(order.symbol)
            if price is None:
                remaining.append(order)
                continue

            should_fill = False
            if order.side == "buy" and price <= order.price:
                should_fill = True
            elif order.side == "sell" and price >= order.price:
                should_fill = True

            if should_fill:
                self._fill_order(order, price)
                filled.append(order)
            else:
                remaining.append(order)

        self.pending_orders = remaining
        return filled

    def _fill_order(self, order: Order, fill_price: float) -> None:
        """注文を約定させる."""
        order.status = "filled"
        order.filled_price = fill_price
        order.filled_at = datetime.now().isoformat()

        if order.side == "buy":
            cost = fill_price * order.quantity
            self.cash -= cost
            self.positions[order.symbol] = Position(
                symbol=order.symbol,
                side="long",
                quantity=order.quantity,
                entry_price=fill_price,
                current_price=fill_price,
                opened_at=order.filled_at,
            )
            logger.info("[Paper] Filled BUY %s x%d @ %.1f", order.symbol, order.quantity, fill_price)
        elif order.side == "sell":
            pos = self.positions.pop(order.symbol, None)
            if pos:
                proceeds = fill_price * order.quantity
                self.cash += proceeds
                pnl = (fill_price - pos.entry_price) * order.quantity
                logger.info("[Paper] Filled SELL %s x%d @ %.1f PnL=%.0f",
                            order.symbol, order.quantity, fill_price, pnl)

        self.history.append({
            "timestamp": order.filled_at,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": fill_price,
            "order_id": order.order_id,
        })

    def cancel_order(self, order_id: str) -> bool:
        """指定の注文をキャンセルする."""
        for i, order in enumerate(self.pending_orders):
            if order.order_id == order_id:
                order.status = "cancelled"
                self.pending_orders.pop(i)
                logger.info("[Paper] Order cancelled: %s", order_id)
                return True
        return False

    def get_positions(self) -> list[Position]:
        """保有ポジション一覧を返す."""
        return list(self.positions.values())

    def get_balance(self) -> float:
        """現金残高を返す."""
        return self.cash

    def get_orders(self) -> list[dict]:
        """未約定注文をdict形式で返す（kabu_apiと同じインターフェース用）."""
        return [
            {
                "OrderId": o.order_id,
                "Symbol": o.symbol,
                "Side": o.side,
                "Price": o.price,
                "Qty": o.quantity,
                "State": 1 if o.status == "pending" else 5,
            }
            for o in self.pending_orders
        ]

    def export_history(self, filepath: str) -> None:
        """取引履歴をCSV出力する."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "side", "quantity", "price", "order_id"])
            writer.writeheader()
            writer.writerows(self.history)
        logger.info("[Paper] History exported to %s", filepath)
