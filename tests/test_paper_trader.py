"""paper_trader のユニットテスト."""

import tempfile
from pathlib import Path

import pytest

from src.paper_trader import PaperTrader
from src.position_manager import Order


@pytest.fixture
def trader():
    return PaperTrader(initial_cash=1_000_000)


class TestPlaceOrder:
    def test_place_order_returns_id(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        order_id = trader.place_order(order)
        assert order_id.startswith("PAPER-")
        assert len(trader.pending_orders) == 1

    def test_place_order_sets_status(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(order)
        assert trader.pending_orders[0].status == "pending"


class TestCheckFills:
    def test_buy_fill_when_price_drops(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(order)

        filled = trader.check_fills({"9432.T": 149.0})
        assert len(filled) == 1
        assert filled[0].status == "filled"
        assert len(trader.pending_orders) == 0

    def test_buy_no_fill_when_price_above(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(order)

        filled = trader.check_fills({"9432.T": 155.0})
        assert len(filled) == 0
        assert len(trader.pending_orders) == 1

    def test_sell_fill_when_price_rises(self, trader):
        # First buy
        buy_order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(buy_order)
        trader.check_fills({"9432.T": 149.0})

        # Then sell
        sell_order = Order(symbol="9432.T", side="sell", order_type="limit", price=160.0, quantity=100)
        trader.place_order(sell_order)
        filled = trader.check_fills({"9432.T": 161.0})
        assert len(filled) == 1
        assert "9432.T" not in trader.positions


class TestBalance:
    def test_balance_after_buy(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(order)
        trader.check_fills({"9432.T": 150.0})

        assert trader.get_balance() == 1_000_000 - 150.0 * 100

    def test_balance_after_buy_and_sell(self, trader):
        # Buy
        buy = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(buy)
        trader.check_fills({"9432.T": 150.0})

        # Sell at profit
        sell = Order(symbol="9432.T", side="sell", order_type="limit", price=160.0, quantity=100)
        trader.place_order(sell)
        trader.check_fills({"9432.T": 160.0})

        expected = 1_000_000 - 150.0 * 100 + 160.0 * 100
        assert trader.get_balance() == expected


class TestCancelOrder:
    def test_cancel_existing_order(self, trader):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        order_id = trader.place_order(order)
        result = trader.cancel_order(order_id)
        assert result is True
        assert len(trader.pending_orders) == 0

    def test_cancel_nonexistent_order(self, trader):
        result = trader.cancel_order("PAPER-NONEXIST")
        assert result is False


class TestExportHistory:
    def test_export_csv(self, trader, tmp_path):
        order = Order(symbol="9432.T", side="buy", order_type="limit", price=150.0, quantity=100)
        trader.place_order(order)
        trader.check_fills({"9432.T": 150.0})

        filepath = tmp_path / "history.csv"
        trader.export_history(str(filepath))
        assert filepath.exists()

        content = filepath.read_text()
        assert "9432.T" in content
        assert "buy" in content
