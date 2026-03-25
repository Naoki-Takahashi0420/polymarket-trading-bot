"""executor のユニットテスト."""

from datetime import datetime, timedelta

import pytest

from src.executor import Executor
from src.paper_trader import PaperTrader
from src.position_manager import Order, Position, PositionManager
from src.signal_generator import Signal, TradeSignal


@pytest.fixture
def pm(tmp_path):
    return PositionManager(db_path=tmp_path / "test.db", max_positions=3, max_per_stock=500_000)


@pytest.fixture
def paper():
    return PaperTrader(initial_cash=1_000_000)


@pytest.fixture
def executor(pm, paper):
    return Executor(mode="paper", paper_trader=paper, position_manager=pm)


class TestExecuteSignal:
    def test_buy_signal_places_order(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        order = executor.execute_signal(signal)
        assert order is not None
        assert order.side == "buy"
        assert order.price == 140.0  # range_lower
        assert order.order_id.startswith("PAPER-")

    def test_sell_signal_places_order(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.SELL,
            current_price=160.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        order = executor.execute_signal(signal)
        assert order is not None
        assert order.side == "sell"
        assert order.price == 160.0  # range_upper

    def test_hold_signal_returns_none(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.HOLD,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        result = executor.execute_signal(signal)
        assert result is None

    def test_zero_position_size_returns_none(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=0,
        )
        result = executor.execute_signal(signal)
        assert result is None


class TestDuplicateOrderPrevention:
    def test_duplicate_order_blocked(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        # First order succeeds
        order1 = executor.execute_signal(signal)
        assert order1 is not None

        # Second identical order blocked
        order2 = executor.execute_signal(signal)
        assert order2 is None


class TestRiskCheck:
    def test_exceeds_max_positions(self, executor, pm):
        # Fill up positions
        for i in range(3):
            pm.add_position(Position(symbol=f"{9430+i}.T", side="long", quantity=100, entry_price=100.0))

        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=150.0, range_upper=160.0, range_lower=140.0,
            stop_loss=135.8, position_size=100,
        )
        result = executor.execute_signal(signal)
        assert result is None

    def test_exceeds_max_per_stock(self, executor):
        signal = TradeSignal(
            symbol="9432.T", signal=Signal.BUY,
            current_price=6000.0, range_upper=6500.0, range_lower=5500.0,
            stop_loss=5335.0, position_size=100,
        )
        # 6000 * 100 = 600,000 > 500,000 max_per_stock
        result = executor.execute_signal(signal)
        assert result is None


class TestStaleOrders:
    def test_cancel_stale_orders(self, executor, pm):
        # Create an old pending order
        old_time = (datetime.now() - timedelta(minutes=60)).isoformat()
        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100, order_id="PAPER-OLD001",
            created_at=old_time,
        )
        pm.save_order(order)
        executor.paper_trader.pending_orders.append(order)

        cancelled = executor.check_and_cancel_stale_orders(max_age_minutes=30)
        assert "PAPER-OLD001" in cancelled

    def test_recent_orders_not_cancelled(self, executor, pm):
        order = Order(
            symbol="9432.T", side="buy", order_type="limit",
            price=150.0, quantity=100, order_id="PAPER-NEW001",
            created_at=datetime.now().isoformat(),
        )
        pm.save_order(order)

        cancelled = executor.check_and_cancel_stale_orders(max_age_minutes=30)
        assert len(cancelled) == 0


class TestSyncPositions:
    def test_paper_mode_sync(self, executor):
        # Add a position to paper trader
        executor.paper_trader.positions["9432.T"] = Position(
            symbol="9432.T", side="long", quantity=100, entry_price=150.0,
        )
        positions = executor.sync_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "9432.T"
