"""Yahoo Finance から日本株データを取得するモジュール."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _cache_path(symbol: str, interval: str) -> Path:
    safe = symbol.replace(".", "_")
    return DATA_DIR / f"{safe}_{interval}.csv"


def fetch_ohlcv(
    symbol: str,
    period: str = "6mo",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """指定銘柄のOHLCVデータを取得する.

    Args:
        symbol: ティッカー（例: "9432.T"）
        period: 取得期間（例: "6mo", "1y"）
        interval: 足種（"1d" or "5m"）
        use_cache: True ならキャッシュを使う

    Returns:
        OHLCV の DataFrame（columns: Open, High, Low, Close, Volume）
    """
    cache = _cache_path(symbol, interval)

    if use_cache and cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if len(df) > 0:
            return df

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        return df

    # 必要なカラムだけ残す
    cols = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in cols if c in df.columns]]

    if use_cache:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache)

    return df


def fetch_multiple(
    symbols: list[str],
    period: str = "6mo",
    interval: str = "1d",
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    """複数銘柄のデータを一括取得する."""
    result = {}
    for sym in symbols:
        df = fetch_ohlcv(sym, period=period, interval=interval, use_cache=use_cache)
        if not df.empty:
            result[sym] = df
    return result
