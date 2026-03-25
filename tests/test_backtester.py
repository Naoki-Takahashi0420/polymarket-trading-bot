"""backtester のユニットテスト."""

import numpy as np
import pandas as pd
import pytest

from src.backtester import RangeStrategy, run_backtest


def _make_oscillating_df(
    center: float = 1000.0,
    amplitude: float = 50.0,
    days: int = 200,
) -> pd.DataFrame:
    """上下に振動するモックデータを生成する（レンジ取引向き）."""
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    t = np.arange(days)
    close = center + amplitude * np.sin(2 * np.pi * t / 20)
    high = close + 5
    low = close - 5
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": [500_000] * days},
        index=dates,
    )


class TestRunBacktest:
    def test_basic_run(self):
        df = _make_oscillating_df()
        result, stats, bt = run_backtest(
            df,
            range_upper=1040.0,
            range_lower=960.0,
            initial_cash=1_000_000,
        )
        assert "return_pct" in result
        assert "num_trades" in result
        assert "win_rate_pct" in result
        assert "sharpe_ratio" in result
        assert "final_equity" in result
        assert result["num_trades"] >= 0

    def test_profitable_on_oscillating_data(self):
        df = _make_oscillating_df(amplitude=50.0, days=500)
        result, stats, bt = run_backtest(
            df,
            range_upper=1040.0,
            range_lower=960.0,
            initial_cash=1_000_000,
        )
        # 振動データではレンジ戦略が利益を出すはず
        assert result["num_trades"] > 0

    def test_no_trades_when_price_outside_range(self):
        df = _make_oscillating_df(center=2000.0, amplitude=10.0)
        result, stats, bt = run_backtest(
            df,
            range_upper=1100.0,
            range_lower=900.0,
            initial_cash=1_000_000,
        )
        assert result["num_trades"] == 0
