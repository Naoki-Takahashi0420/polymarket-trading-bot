"""売買執行エンジンモジュール."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.kabu_api import KabuApiClient
from src.paper_trader import PaperTrader
from src.position_manager import Order, Position, PositionManager
from src.signal_generator import Signal, TradeSignal

logger = logging.getLogger(__name__)


class Executor:
    """TradingSignalを受け取り、適切な注文を発行する."""

    def __init__(
        self,
        mode: str = "paper",
        kabu_client: Optional[KabuApiClient] = None,
        paper_trader: Optional[PaperTrader] = None,
        position_manager: Optional[PositionManager] = None,
    ):
        self.mode = mode
        self.kabu_client = kabu_client
        self.paper_trader = paper_trader or (PaperTrader() if mode == "paper" else None)
        self.position_manager = position_manager

    def execute_signal(self, signal: TradeSignal) -> Optional[Order]:
        """シグナルに基づき注文を執行する."""
        if signal.signal == Signal.HOLD:
            logger.debug("HOLD signal for %s, skipping", signal.symbol)
            return None

        if signal.position_size <= 0:
            logger.warning("Position size is 0 for %s, skipping", signal.symbol)
            return None

        # 重複注文チェック
        if self._has_duplicate_order(signal):
            logger.info("Duplicate order detected for %s %s, skipping",
                        signal.signal.value, signal.symbol)
            return None

        # リスクチェック
        if signal.signal == Signal.BUY and self.position_manager:
            amount = signal.current_price * signal.position_size
            if not self.position_manager.can_open_new_position(amount):
                logger.warning("Risk check failed for %s (amount=%.0f), skipping",
                               signal.symbol, amount)
                return None

        # 注文作成
        side = "buy" if signal.signal == Signal.BUY else "sell"
        price = signal.range_lower if signal.signal == Signal.BUY else signal.range_upper

        order = Order(
            symbol=signal.symbol,
            side=side,
            order_type="limit",
            price=price,
            quantity=signal.position_size,
        )

        # 発注
        order_id = self._place_order(order)
        if order_id:
            order.order_id = order_id
            order.status = "pending"
            order.created_at = datetime.now().isoformat()

            if self.position_manager:
                self.position_manager.save_order(order)

            logger.info("Executed %s %s x%d @ %.1f (ID: %s)",
                        side, signal.symbol, signal.position_size, price, order_id)
        return order

    def _place_order(self, order: Order) -> Optional[str]:
        """モードに応じて注文を発行する."""
        if self.mode == "paper" and self.paper_trader:
            return self.paper_trader.place_order(order)
        elif self.mode == "live" and self.kabu_client:
            return self.kabu_client.place_order(order)
        else:
            logger.error("No trading client available for mode=%s", self.mode)
            return None

    def _has_duplicate_order(self, signal: TradeSignal) -> bool:
        """同一銘柄・同方向の未約定注文があるかチェックする."""
        if self.position_manager:
            pending = self.position_manager.get_pending_orders()
            side = "buy" if signal.signal == Signal.BUY else "sell"
            for order in pending:
                if order.symbol == signal.symbol and order.side == side:
                    return True
        return False

    def check_and_cancel_stale_orders(self, max_age_minutes: int = 30) -> list[str]:
        """古い未約定注文をキャンセルする."""
        if not self.position_manager:
            return []

        cancelled = []
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        pending = self.position_manager.get_pending_orders()

        for order in pending:
            try:
                created = datetime.fromisoformat(order.created_at)
            except (ValueError, TypeError):
                continue

            if created < cutoff:
                success = False
                if self.mode == "paper" and self.paper_trader:
                    success = self.paper_trader.cancel_order(order.order_id)
                elif self.mode == "live" and self.kabu_client:
                    success = self.kabu_client.cancel_order(order.order_id)

                if success:
                    self.position_manager.update_order_status(order.order_id, "cancelled")
                    cancelled.append(order.order_id)
                    logger.info("Cancelled stale order: %s", order.order_id)

        return cancelled

    def sync_positions(self) -> list[Position]:
        """API/シミュレーターからポジションを取得する."""
        if self.mode == "paper" and self.paper_trader:
            return self.paper_trader.get_positions()
        elif self.mode == "live" and self.kabu_client:
            api_positions = self.kabu_client.get_positions()
            return [
                Position(
                    symbol=p.get("Symbol", ""),
                    side="long" if p.get("Side", "") == "2" else "short",
                    quantity=int(p.get("LeavesQty", 0)),
                    entry_price=float(p.get("Price", 0)),
                    current_price=float(p.get("CurrentPrice", 0)),
                )
                for p in api_positions
            ]
        return []
