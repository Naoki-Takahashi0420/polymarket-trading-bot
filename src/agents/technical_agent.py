"""テクニカル分析エージェント."""

from __future__ import annotations

import logging

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    """RSI, MACD, ボリンジャーバンド, 移動平均線で総合判断する."""

    def __init__(self):
        super().__init__("technical")

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        if data.empty or len(data) < 26:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="データ不足",
            )

        close = data["Close"]

        votes = []  # (action, confidence)

        # 1. RSI(14)
        rsi = self._calc_rsi(close, 14)
        if rsi is not None:
            if rsi < 30:
                votes.append(("BUY", min(1.0, (30 - rsi) / 30)))
            elif rsi > 70:
                votes.append(("SELL", min(1.0, (rsi - 70) / 30)))
            else:
                votes.append(("HOLD", 0.3))

        # 2. MACD
        macd_signal = self._calc_macd(close)
        if macd_signal is not None:
            macd_val, signal_val = macd_signal
            if macd_val > signal_val:
                votes.append(("BUY", min(1.0, abs(macd_val - signal_val) / abs(signal_val) if signal_val != 0 else 0.5)))
            elif macd_val < signal_val:
                votes.append(("SELL", min(1.0, abs(macd_val - signal_val) / abs(signal_val) if signal_val != 0 else 0.5)))
            else:
                votes.append(("HOLD", 0.3))

        # 3. ボリンジャーバンド(20, 2)
        bb = self._calc_bollinger(close, 20, 2)
        if bb is not None:
            price = float(close.iloc[-1])
            lower, upper = bb
            if price <= lower:
                votes.append(("BUY", 0.7))
            elif price >= upper:
                votes.append(("SELL", 0.7))
            else:
                votes.append(("HOLD", 0.3))

        # 4. 移動平均クロス(5, 25)
        ma_signal = self._calc_ma_cross(close, 5, 25)
        if ma_signal is not None:
            votes.append(ma_signal)

        if not votes:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.2,
                reasoning="指標計算不可",
            )

        # 多数決 + 平均confidence
        buy_votes = [(a, c) for a, c in votes if a == "BUY"]
        sell_votes = [(a, c) for a, c in votes if a == "SELL"]
        hold_votes = [(a, c) for a, c in votes if a == "HOLD"]

        if len(buy_votes) > len(sell_votes) and len(buy_votes) > len(hold_votes):
            action = "BUY"
            conf = sum(c for _, c in buy_votes) / len(buy_votes)
        elif len(sell_votes) > len(buy_votes) and len(sell_votes) > len(hold_votes):
            action = "SELL"
            conf = sum(c for _, c in sell_votes) / len(sell_votes)
        else:
            action = "HOLD"
            conf = sum(c for _, c in hold_votes) / len(hold_votes) if hold_votes else 0.3

        details = []
        if rsi is not None:
            details.append(f"RSI={rsi:.1f}")
        details.append(f"votes: BUY={len(buy_votes)} SELL={len(sell_votes)} HOLD={len(hold_votes)}")

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(min(conf, 1.0), 2),
            reasoning=", ".join(details),
        )

    @staticmethod
    def _calc_rsi(close: pd.Series, period: int = 14) -> float | None:
        if len(close) < period + 1:
            return None
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
        last_gain = float(gain.iloc[-1])
        last_loss = float(loss.iloc[-1])
        if last_loss == 0:
            return 100.0
        rs = last_gain / last_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_macd(close: pd.Series) -> tuple[float, float] | None:
        if len(close) < 26:
            return None
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return float(macd.iloc[-1]), float(signal.iloc[-1])

    @staticmethod
    def _calc_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[float, float] | None:
        if len(close) < period:
            return None
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        lower = float(sma.iloc[-1] - num_std * std.iloc[-1])
        upper = float(sma.iloc[-1] + num_std * std.iloc[-1])
        return lower, upper

    @staticmethod
    def _calc_ma_cross(close: pd.Series, short: int = 5, long: int = 25) -> tuple[str, float] | None:
        if len(close) < long + 1:
            return None
        ma_short = close.rolling(window=short).mean()
        ma_long = close.rolling(window=long).mean()
        # 直近2本でクロス判定
        prev_diff = float(ma_short.iloc[-2] - ma_long.iloc[-2])
        curr_diff = float(ma_short.iloc[-1] - ma_long.iloc[-1])
        if prev_diff <= 0 < curr_diff:
            return ("BUY", 0.6)  # ゴールデンクロス
        elif prev_diff >= 0 > curr_diff:
            return ("SELL", 0.6)  # デッドクロス
        return ("HOLD", 0.3)
