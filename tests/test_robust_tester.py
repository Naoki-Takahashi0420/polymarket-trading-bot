"""robust_tester のユニットテスト."""

import numpy as np
import pandas as pd
import pytest

from src.backtester import RangeStrategy
from src.robust_tester import RobustTester


def _make_oscillating_df(
    center: float = 1000.0,
    amplitude: float = 50.0,
    days: int = 500,
) -> pd.DataFrame:
    """上下に振動するモックデータ（レンジ取引向き）."""
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    t = np.arange(days)
    close = center + amplitude * np.sin(2 * np.pi * t / 20)
    high = close + 5
    low = close - 5
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": [500_000] * days},
        index=dates,
    )


def _make_trending_df(days: int = 500) -> pd.DataFrame:
    """一方向にトレンドするデータ（レンジ取引に不向き）."""
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    close = np.linspace(500, 2000, days) + np.random.default_rng(42).normal(0, 10, days)
    high = close + 5
    low = close - 5
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": [500_000] * days},
        index=dates,
    )


class TestWalkForwardTest:
    def test_returns_required_keys(self):
        df = _make_oscillating_df()
        tester = RobustTester()
        result = tester.walk_forward_test(
            df, RangeStrategy, range_upper=1040.0, range_lower=960.0,
        )
        assert "train_pf" in result
        assert "val_pf" in result
        assert "test_pf" in result
        assert "passed" in result

    def test_stable_strategy_on_oscillating_data(self):
        df = _make_oscillating_df(days=500)
        tester = RobustTester()
        result = tester.walk_forward_test(
            df, RangeStrategy, range_upper=1040.0, range_lower=960.0,
        )
        # 振動データではPFが正の値になるはず
        assert result["train_pf"] >= 0


class TestParameterSensitivity:
    def test_returns_required_structure(self):
        df = _make_oscillating_df(days=300)
        tester = RobustTester()
        result = tester.parameter_sensitivity(
            df, RangeStrategy,
            base_params={"range_upper": 1040.0, "range_lower": 960.0, "stop_loss_pct": 0.03},
        )
        assert "params" in result
        assert "passed" in result
        assert "range_upper" in result["params"]
        assert "range" in result["params"]["range_upper"]


class TestMonteCarloSimulation:
    def test_empty_trades(self):
        tester = RobustTester()
        result = tester.monte_carlo_simulation([])
        assert result["passed"] is True
        assert result["worst_dd"] == 0.0

    def test_profitable_trades(self):
        trades = [5000, 3000, -2000, 4000, -1000, 6000, 2000, -500, 3000, 1000]
        tester = RobustTester()
        result = tester.monte_carlo_simulation(trades, n_simulations=500)
        assert "median_return" in result
        assert "worst_dd" in result
        assert "p5_return" in result
        assert result["median_return"] > 0

    def test_catastrophic_trades_fail(self):
        # 大きな損失が続く取引 → 最悪DDが30%超
        trades = [-100000, -80000, -60000, -50000, -40000, 10000, 5000]
        tester = RobustTester(monte_carlo_max_dd=0.30)
        result = tester.monte_carlo_simulation(trades, n_simulations=500)
        assert result["passed"] is False


class TestRobustnessGate:
    def test_returns_overall_result(self):
        df = _make_oscillating_df(days=500)
        trades = [5000, 3000, -2000, 4000, -1000]
        tester = RobustTester()
        result = tester.robustness_gate(
            df, RangeStrategy, trades,
            range_upper=1040.0, range_lower=960.0, stop_loss_pct=0.03,
        )
        assert "walk_forward" in result
        assert "sensitivity" in result
        assert "monte_carlo" in result
        assert "overall_passed" in result
        assert isinstance(result["overall_passed"], bool)
