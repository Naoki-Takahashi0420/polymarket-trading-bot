"""range_detector のユニットテスト."""

import numpy as np
import pandas as pd
import pytest

from src.range_detector import (
    RangeInfo,
    calc_atr_ratio,
    calc_bb_width,
    calc_containment_ratio,
    calc_range_bounds,
    detect_range_stocks,
)


def _make_flat_df(price: float = 1000.0, days: int = 60, noise: float = 5.0) -> pd.DataFrame:
    """ほぼ横ばいのモックデータを生成する."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    close = price + np.random.normal(0, noise, days)
    high = close + abs(np.random.normal(0, noise * 0.5, days))
    low = close - abs(np.random.normal(0, noise * 0.5, days))
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": [1_000_000] * days},
        index=dates,
    )


def _make_trending_df(start: float = 1000.0, days: int = 60) -> pd.DataFrame:
    """上昇トレンドのモックデータを生成する."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    close = start + np.arange(days) * 20.0 + np.random.normal(0, 5, days)
    high = close + 10
    low = close - 10
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": [1_000_000] * days},
        index=dates,
    )


class TestCalcBBWidth:
    def test_flat_price_has_small_bb_width(self):
        df = _make_flat_df(noise=3.0)
        width = calc_bb_width(df["Close"])
        assert width < 0.05

    def test_trending_price_has_larger_bb_width(self):
        df = _make_trending_df()
        width = calc_bb_width(df["Close"])
        assert width > 0.05


class TestCalcATRRatio:
    def test_flat_price_has_small_atr_ratio(self):
        df = _make_flat_df(noise=3.0)
        ratio = calc_atr_ratio(df)
        assert ratio < 0.02

    def test_trending_price_has_larger_atr_ratio(self):
        df = _make_trending_df()
        ratio = calc_atr_ratio(df)
        assert ratio > 0.005


class TestCalcContainmentRatio:
    def test_flat_price_has_high_containment(self):
        df = _make_flat_df(noise=3.0)
        ratio = calc_containment_ratio(df["Close"])
        assert ratio >= 0.60

    def test_trending_price_has_lower_containment(self):
        df = _make_trending_df()
        ratio = calc_containment_ratio(df["Close"])
        assert ratio < 0.80


class TestCalcRangeBounds:
    def test_bounds_contain_mean(self):
        df = _make_flat_df()
        upper, lower = calc_range_bounds(df["Close"])
        mean = df["Close"].mean()
        assert lower < mean < upper


class TestDetectRangeStocks:
    def test_flat_stock_ranks_higher(self):
        data = {
            "FLAT.T": _make_flat_df(noise=3.0),
            "TREND.T": _make_trending_df(),
        }
        results = detect_range_stocks(data)
        assert len(results) == 2
        assert results[0].symbol == "FLAT.T"
        assert results[0].score > results[1].score

    def test_empty_data_returns_empty(self):
        results = detect_range_stocks({})
        assert results == []

    def test_short_data_skipped(self):
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        df = pd.DataFrame(
            {"Open": [100]*5, "High": [101]*5, "Low": [99]*5, "Close": [100]*5, "Volume": [1000]*5},
            index=dates,
        )
        results = detect_range_stocks({"SHORT.T": df})
        assert results == []
