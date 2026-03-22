"""volume_spike_detector のユニットテスト."""

import numpy as np
import pandas as pd
import pytest

from src.volume_spike_detector import VolumeSpikeDetector


def _make_volume_df(
    days: int = 30,
    base_volume: int = 100_000,
    last_day_volume: int = 100_000,
) -> pd.DataFrame:
    """出来高テスト用のモックデータを生成する."""
    dates = pd.date_range("2025-01-01", periods=days, freq="B")
    close = [1000.0] * days
    volumes = [base_volume] * (days - 1) + [last_day_volume]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c + 5 for c in close],
            "Low": [c - 5 for c in close],
            "Close": close,
            "Volume": volumes,
        },
        index=dates,
    )


class TestCheckSpike:
    def test_no_spike(self):
        df = _make_volume_df(days=30, base_volume=100_000, last_day_volume=100_000)
        detector = VolumeSpikeDetector(threshold_multiplier=2.0, lookback_days=20)
        result = detector.check_spike(df)
        assert result is None

    def test_spike_detected(self):
        df = _make_volume_df(days=30, base_volume=100_000, last_day_volume=300_000)
        detector = VolumeSpikeDetector(threshold_multiplier=2.0, lookback_days=20)
        result = detector.check_spike(df)
        assert result is not None
        assert result["ratio"] >= 2.0
        assert result["current_volume"] == 300_000

    def test_insufficient_data(self):
        df = _make_volume_df(days=5, base_volume=100_000, last_day_volume=300_000)
        detector = VolumeSpikeDetector(threshold_multiplier=2.0, lookback_days=20)
        result = detector.check_spike(df)
        assert result is None

    def test_custom_threshold(self):
        df = _make_volume_df(days=30, base_volume=100_000, last_day_volume=160_000)
        detector = VolumeSpikeDetector(threshold_multiplier=1.5, lookback_days=20)
        result = detector.check_spike(df)
        assert result is not None
        assert result["ratio"] >= 1.5


class TestDetectSpikes:
    def test_detect_spikes_with_provided_data(self):
        data = {
            "9432.T": _make_volume_df(days=30, base_volume=100_000, last_day_volume=300_000),
            "7203.T": _make_volume_df(days=30, base_volume=100_000, last_day_volume=100_000),
        }
        detector = VolumeSpikeDetector(threshold_multiplier=2.0, lookback_days=20)
        spikes = detector.detect_spikes(["9432.T", "7203.T"], data=data)
        assert len(spikes) == 1
        assert spikes[0]["symbol"] == "9432.T"

    def test_no_spikes(self):
        data = {
            "9432.T": _make_volume_df(days=30, base_volume=100_000, last_day_volume=100_000),
        }
        detector = VolumeSpikeDetector(threshold_multiplier=2.0, lookback_days=20)
        spikes = detector.detect_spikes(["9432.T"], data=data)
        assert len(spikes) == 0
