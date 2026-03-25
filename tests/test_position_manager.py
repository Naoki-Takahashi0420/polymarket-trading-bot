"""position_manager のユニットテスト."""

import tempfile
from pathlib import Path

import pytest

from src.position_manager import Order, Position, PositionManager


@pytest.fixture
def pm(tmp_path):
    """一時DBを使うPositionManagerを返す."""
    db_path = tmp_path / "test.db"
    return PositionManager(db_path=db_path, max_positions=3, max_per_stock=500_000)


class TestPositionCRUD:
    def test_add_and_get_open_positions(self, pm):
        pos = Position(symbol="9432.T", side="long", quantity=100, entry_price=150.0)
        pos_id = pm.add_position(pos)
        assert pos_id >= 1

        positions = pm.get_open_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "9432.T"
        assert positions[0].quantity == 100

    def test_close_position_pnl(self, pm):
        pos = Position(symbol="9432.T", side="long", quantity=100, entry_price=150.0)
        pm.add_position(pos)

        pnl = pm.close_position("9432.T", close_price=160.0)
        assert pnl == 1000.0  # (160 - 150) * 100

        positions = pm.get_open_positions()
        assert len(positions) == 0

    def test_close_short_position_pnl(self, pm):
        pos = Position(symbol="7203.T", side="short", quantity=100, entry_price=200.0)
        pm.add_position(pos)

        pnl = pm.close_position("7203.T", close_price=190.0)
        assert pnl == 1000.0  # (200 - 190) * 100

    def test_close_nonexistent_returns_none(self, pm):
        result = pm.close_position("9999.T", close_price=100.0)
        assert result is None


class TestRiskCheck:
    def test_can_open_within_limit(self, pm):
        assert pm.can_open_new_position(amount=100_000) is True

    def test_cannot_exceed_max_positions(self, pm):
        for i in range(3):
            pm.add_position(Position(symbol=f"{9430 + i}.T", side="long", quantity=100, entry_price=100.0))

        assert pm.can_open_new_position() is False

    def test_cannot_exceed_max_per_stock(self, pm):
        assert pm.can_open_new_position(amount=600_000) is False


class TestOrderManagement:
    def test_save_and_get_pending_orders(self, pm):
        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100, order_id="ORD001",
        )
        pm.save_order(order)

        pending = pm.get_pending_orders()
        assert len(pending) == 1
        assert pending[0].order_id == "ORD001"

    def test_update_order_status(self, pm):
        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100, order_id="ORD002",
        )
        pm.save_order(order)
        pm.update_order_status("ORD002", "filled", filled_price=150.0)

        pending = pm.get_pending_orders()
        assert len(pending) == 0


class TestDailyPnL:
    def test_daily_pnl_no_trades(self, pm):
        assert pm.get_daily_pnl() == 0.0

    def test_daily_pnl_with_closed_positions(self, pm):
        pos = Position(symbol="9432.T", side="long", quantity=100, entry_price=150.0)
        pm.add_position(pos)
        pm.close_position("9432.T", close_price=160.0)

        # closed_at is today, so daily pnl should reflect it
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        pnl = pm.get_daily_pnl(today)
        assert pnl == 1000.0
