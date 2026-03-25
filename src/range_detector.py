"""レンジ相場の銘柄を自動検出・スコアリングするモジュール."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RangeInfo:
    symbol: str
    name: str
    score: float
    current_price: float
    range_upper: float
    range_lower: float
    bb_width: float
    atr_ratio: float
    containment_ratio: float


# 銘柄コード → 銘柄名のマッピング
SYMBOL_NAMES: dict[str, str] = {
    "9432.T": "NTT",
    "7203.T": "トヨタ",
    "6758.T": "ソニー",
    "8306.T": "三菱UFJ",
    "6861.T": "キーエンス",
    "9984.T": "ソフトバンクG",
    "6501.T": "日立",
    "8035.T": "東京エレクトロン",
    "4063.T": "信越化学",
    "7741.T": "HOYA",
}


def calc_bb_width(close: pd.Series, window: int = 20) -> float:
    """ボリンジャーバンド幅を計算する."""
    sma = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = sma + 2 * std
    lower = sma - 2 * std

    bb_width = ((upper - lower) / sma).dropna()
    if bb_width.empty:
        return float("inf")
    return float(bb_width.iloc[-1])


def calc_atr_ratio(df: pd.DataFrame, window: int = 14) -> float:
    """ATR / 株価 の比率を計算する."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window).mean().dropna()
    if atr.empty:
        return float("inf")
    return float(atr.iloc[-1] / close.iloc[-1])


def calc_containment_ratio(close: pd.Series, lookback: int = 60) -> float:
    """価格が mean ± 1σ 内に収まっている割合を計算する."""
    data = close.iloc[-lookback:] if len(close) >= lookback else close
    mean = data.mean()
    std = data.std()

    if std == 0:
        return 1.0

    within = ((data >= mean - std) & (data <= mean + std)).sum()
    return float(within / len(data))


def calc_range_bounds(close: pd.Series, lookback: int = 60) -> tuple[float, float]:
    """レンジの上限・下限を計算する（mean ± 1σ）."""
    data = close.iloc[-lookback:] if len(close) >= lookback else close
    mean = data.mean()
    std = data.std()
    return float(mean + std), float(mean - std)


def detect_range_stocks(
    data: dict[str, pd.DataFrame],
    lookback_days: int = 60,
    bb_width_threshold: float = 0.08,
    atr_ratio_threshold: float = 0.02,
    range_containment_threshold: float = 0.70,
    weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
) -> list[RangeInfo]:
    """複数銘柄からレンジ相場の銘柄を検出しスコアリングする.

    Args:
        data: {symbol: DataFrame} の辞書
        lookback_days: 分析対象日数
        bb_width_threshold: BB幅の閾値
        atr_ratio_threshold: ATR比率の閾値
        range_containment_threshold: レンジ内滞在率の閾値
        weights: (bb, atr, containment) のスコア重み

    Returns:
        スコア降順でソートされた RangeInfo のリスト
    """
    results: list[RangeInfo] = []
    w_bb, w_atr, w_cont = weights

    for symbol, df in data.items():
        if len(df) < 20:
            continue

        close = df["Close"]
        bb_width = calc_bb_width(close)
        atr_ratio = calc_atr_ratio(df)
        containment = calc_containment_ratio(close, lookback_days)

        # 各指標を 0-1 にスケール（閾値以下なら 1.0、超えるほど 0 に近づく）
        bb_score = max(0.0, 1.0 - bb_width / bb_width_threshold) if bb_width_threshold > 0 else 0.0
        atr_score = max(0.0, 1.0 - atr_ratio / atr_ratio_threshold) if atr_ratio_threshold > 0 else 0.0
        cont_score = containment / range_containment_threshold if range_containment_threshold > 0 else 0.0
        cont_score = min(cont_score, 1.0)

        score = w_bb * bb_score + w_atr * atr_score + w_cont * cont_score

        range_upper, range_lower = calc_range_bounds(close, lookback_days)
        current_price = float(close.iloc[-1])
        name = SYMBOL_NAMES.get(symbol, symbol)

        results.append(
            RangeInfo(
                symbol=symbol,
                name=name,
                score=round(score, 4),
                current_price=round(current_price, 1),
                range_upper=round(range_upper, 1),
                range_lower=round(range_lower, 1),
                bb_width=round(bb_width, 4),
                atr_ratio=round(atr_ratio, 4),
                containment_ratio=round(containment, 4),
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


def print_ranking(results: list[RangeInfo]) -> None:
    """レンジ銘柄ランキングを表示する."""
    print(f"{'順位':>4} {'スコア':>6} {'コード':<8} {'銘柄名':<12} {'現在値':>10} {'上限':>10} {'下限':>10}")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        print(
            f"{i:>4} {r.score:>6.4f} {r.symbol:<8} {r.name:<12} "
            f"{r.current_price:>10.1f} {r.range_upper:>10.1f} {r.range_lower:>10.1f}"
        )
