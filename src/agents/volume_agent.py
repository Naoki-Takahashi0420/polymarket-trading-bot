"""需給分析エージェント."""

from __future__ import annotations

import logging
import os

import pandas as pd

from src.agents.base_agent import AgentOpinion, BaseAgent
from src.volume_spike_detector import VolumeSpikeDetector

logger = logging.getLogger(__name__)


class VolumeAgent(BaseAgent):
    """出来高スパイクと価格変動で需給を判定する.

    J-Quants の信用残（貸借倍率）データも加味する。
    """

    def __init__(self, detector: VolumeSpikeDetector | None = None):
        super().__init__("volume")
        self.detector = detector or VolumeSpikeDetector()
        self._jquants_client = None

    def _get_jquants_client(self):
        """J-Quants クライアントを遅延初期化する."""
        if self._jquants_client is not None:
            return self._jquants_client
        refresh_token = os.environ.get("JQUANTS_REFRESH_TOKEN")
        if not refresh_token:
            return None
        try:
            from src.j_quants_client import JQuantsClient
            self._jquants_client = JQuantsClient(refresh_token)
            return self._jquants_client
        except Exception as e:
            logger.warning("Failed to initialize JQuantsClient: %s", e)
            return None

    def _get_margin_ratio(self, symbol: str) -> float | None:
        """信用残貸借倍率を取得する.

        Returns:
            貸借倍率（取得失敗時は None）
        """
        client = self._get_jquants_client()
        if client is None:
            return None
        try:
            code = symbol.replace(".T", "")
            records = client.get_margin_trading(code)
            if not records:
                return None
            latest = records[-1]
            ratio = latest.get("ShortMarginTradeVolume")
            long_vol = latest.get("LongMarginTradeVolume")
            # 貸借倍率 = 買い残 / 売り残
            if ratio and long_vol and float(ratio) > 0:
                return float(long_vol) / float(ratio)
            return None
        except Exception as e:
            logger.warning("Margin trading data failed for %s: %s", symbol, e)
            return None

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

        # 信用残貸借倍率を加味
        margin_ratio = self._get_margin_ratio(symbol)
        if margin_ratio is not None:
            if margin_ratio < 1.0:
                # 売り残 > 買い残 → 売り圧力強い
                if action == "BUY":
                    confidence = max(0.3, confidence - 0.1)
                elif action == "HOLD":
                    action = "SELL"
                    confidence = 0.4
                reasoning += f", 貸借倍率={margin_ratio:.2f}(売り圧力)"
            elif margin_ratio > 3.0:
                # 買い残優勢 → 買い圧力強い
                if action == "SELL":
                    confidence = max(0.3, confidence - 0.1)
                elif action == "HOLD":
                    action = "BUY"
                    confidence = 0.4
                reasoning += f", 貸借倍率={margin_ratio:.2f}(買い圧力)"
            else:
                reasoning += f", 貸借倍率={margin_ratio:.2f}"

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=reasoning,
        )
