"""売買シグナル生成モジュール."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    symbol: str
    signal: Signal
    current_price: float
    range_upper: float
    range_lower: float
    stop_loss: float
    position_size: int  # 株数


def generate_signal(
    symbol: str,
    current_price: float,
    range_upper: float,
    range_lower: float,
    stop_loss_pct: float = 0.03,
    total_capital: float = 1_000_000,
    position_size_pct: float = 0.10,
) -> TradeSignal:
    """現在価格とレンジ上限/下限を比較してシグナルを生成する.

    Args:
        symbol: 銘柄コード
        current_price: 現在価格
        range_upper: レンジ上限
        range_lower: レンジ下限
        stop_loss_pct: 損切り率
        total_capital: 総資金
        position_size_pct: 1銘柄あたりの資金割合

    Returns:
        TradeSignal
    """
    stop_loss = range_lower * (1 - stop_loss_pct)

    # ポジションサイジング: 全資金の position_size_pct を1銘柄に
    alloc = total_capital * position_size_pct
    position_size = int(alloc // current_price) if current_price > 0 else 0

    # 100株単位に切り捨て（日本株の売買単位）
    position_size = (position_size // 100) * 100

    if current_price <= range_lower:
        signal = Signal.BUY
    elif current_price >= range_upper:
        signal = Signal.SELL
    else:
        signal = Signal.HOLD

    return TradeSignal(
        symbol=symbol,
        signal=signal,
        current_price=current_price,
        range_upper=range_upper,
        range_lower=range_lower,
        stop_loss=round(stop_loss, 1),
        position_size=position_size,
    )


def generate_signals_for_rankings(
    rankings: list,
    total_capital: float = 1_000_000,
    position_size_pct: float = 0.10,
    stop_loss_pct: float = 0.03,
    max_positions: int = 3,
) -> list[TradeSignal]:
    """ランキング上位銘柄のシグナルを一括生成する."""
    signals = []
    for info in rankings[:max_positions]:
        sig = generate_signal(
            symbol=info.symbol,
            current_price=info.current_price,
            range_upper=info.range_upper,
            range_lower=info.range_lower,
            stop_loss_pct=stop_loss_pct,
            total_capital=total_capital,
            position_size_pct=position_size_pct,
        )
        signals.append(sig)
    return signals
