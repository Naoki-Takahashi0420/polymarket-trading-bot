"""出来高スパイク検知モジュール."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from src.data_fetcher import fetch_ohlcv

logger = logging.getLogger(__name__)


class VolumeSpikeDetector:
    """全監視銘柄の出来高をチェックし、スパイクを検出する."""

    def __init__(self, threshold_multiplier: float = 2.0, lookback_days: int = 20):
        self.threshold_multiplier = threshold_multiplier
        self.lookback_days = lookback_days

    def check_spike(self, df: pd.DataFrame) -> Optional[dict]:
        """単一銘柄のDataFrameから出来高スパイクを判定する.

        Args:
            df: OHLCVデータ（Volume列必須）

        Returns:
            スパイク検出時: {"current_volume": int, "avg_volume": float, "ratio": float}
            非検出時: None
        """
        if "Volume" not in df.columns or len(df) < self.lookback_days + 1:
            return None

        current_volume = int(df["Volume"].iloc[-1])
        avg_volume = float(df["Volume"].iloc[-(self.lookback_days + 1):-1].mean())

        if avg_volume <= 0:
            return None

        ratio = current_volume / avg_volume

        if ratio >= self.threshold_multiplier:
            return {
                "current_volume": current_volume,
                "avg_volume": round(avg_volume, 0),
                "ratio": round(ratio, 2),
            }
        return None

    def detect_spikes(self, symbols: list[str], data: Optional[dict[str, pd.DataFrame]] = None) -> list[dict]:
        """全銘柄の出来高をチェック、スパイクを検出する.

        Args:
            symbols: 銘柄コードのリスト
            data: 事前取得済みのデータ（なければfetch_ohlcvで取得）

        Returns:
            [{"symbol": str, "current_volume": int, "avg_volume": float, "ratio": float}]
        """
        spikes = []
        for symbol in symbols:
            try:
                if data and symbol in data:
                    df = data[symbol]
                else:
                    df = fetch_ohlcv(symbol, period="3mo", interval="1d")

                if df.empty:
                    continue

                result = self.check_spike(df)
                if result:
                    result["symbol"] = symbol
                    spikes.append(result)
                    logger.info(
                        "Volume spike detected: %s ratio=%.2f",
                        symbol, result["ratio"],
                    )
            except Exception as e:
                logger.error("Error checking volume for %s: %s", symbol, e)

        return spikes
