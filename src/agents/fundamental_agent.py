"""ファンダメンタル分析エージェント."""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from src.agents.base_agent import AgentOpinion, BaseAgent

logger = logging.getLogger(__name__)


class FundamentalAgent(BaseAgent):
    """PER, PBR, 配当利回り, ROEで割安/割高を判定する."""

    def __init__(self):
        super().__init__("fundamental")

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        try:
            info = yf.Ticker(symbol).info
        except Exception as e:
            logger.warning("Failed to fetch info for %s: %s", symbol, e)
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning=f"情報取得失敗: {e}",
            )

        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        div_yield = info.get("dividendYield")  # 0.03 = 3%
        roe = info.get("returnOnEquity")

        scores = []  # positive = bullish
        details = []

        if per is not None:
            details.append(f"PER={per:.1f}")
            if per < 15:
                scores.append(0.6)
            elif per > 30:
                scores.append(-0.5)
            else:
                scores.append(0.0)

        if pbr is not None:
            details.append(f"PBR={pbr:.2f}")
            if pbr < 1.5:
                scores.append(0.5)
            elif pbr > 3.0:
                scores.append(-0.4)
            else:
                scores.append(0.0)

        if div_yield is not None:
            pct = div_yield * 100
            details.append(f"配当={pct:.1f}%")
            if div_yield > 0.03:
                scores.append(0.5)
            elif div_yield > 0.02:
                scores.append(0.2)
            else:
                scores.append(0.0)

        if roe is not None:
            details.append(f"ROE={roe * 100:.1f}%")
            if roe > 0.15:
                scores.append(0.4)
            elif roe < 0.05:
                scores.append(-0.3)
            else:
                scores.append(0.0)

        if not scores:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning="ファンダメンタル情報なし",
            )

        avg_score = sum(scores) / len(scores)

        if avg_score > 0.2:
            action = "BUY"
            confidence = min(1.0, 0.4 + avg_score)
        elif avg_score < -0.2:
            action = "SELL"
            confidence = min(1.0, 0.4 + abs(avg_score))
        else:
            action = "HOLD"
            confidence = 0.4

        return AgentOpinion(
            agent_name=self.name, symbol=symbol,
            action=action, confidence=round(confidence, 2),
            reasoning=", ".join(details),
        )
