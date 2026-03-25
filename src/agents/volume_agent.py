"""需給分析エージェント."""

from __future__ import annotations

import logging

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.volume_spike_detector import VolumeSpikeDetector

logger = logging.getLogger(__name__)


class VolumeAgent(BaseAgent):
    """出来高スパイクと価格変動で需給を判定する."""

    def __init__(self, detector: VolumeSpikeDetector | None = None):
        super().__init__("volume")
        self.detector = detector or VolumeSpikeDetector()

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        if data.empty or "Volume" not in data.columns or len(data) < self.detector.lookback_days + 1:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning="データ不足",
            )

        spike = self.detector.check_spike(data)

        if spike is None:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning="出来高スパイクなし",
            )

        # スパイク検出 → 価格方向で判断
        close = data["Close"]
        if len(close) < 2:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning="価格データ不足",
            )

        price_change = float(close.iloc[-1] - close.iloc[-2])
        ratio = spike["ratio"]
        confidence = min(1.0, 0.5 + (ratio - self.detector.threshold_multiplier) * 0.1)

        if price_change > 0:
            action = "BUY"
            reasoning = f"出来高スパイク(x{ratio:.1f}) + 価格上昇({price_change:+.1f})"
        elif price_change < 0:
            action = "SELL"
            reasoning = f"出来高スパイク(x{ratio:.1f}) + 価格下落({price_change:+.1f})"
        else:
            action = "HOLD"
            confidence = 0.4
            reasoning = f"出来高スパイク(x{ratio:.1f}) + 価格横ばい"

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=reasoning,
        )
