"""ファンダメンタル分析エージェント."""

from __future__ import annotations

import logging
import os

import pandas as pd
import yfinance as yf

from src.agents.base_agent import AgentOpinion, BaseAgent

logger = logging.getLogger(__name__)


class FundamentalAgent(BaseAgent):
    """PER, PBR, 配当利回り, ROEで割安/割高を判定する.

    J-Quants API が利用可能な場合は優先使用し、フォールバックで yfinance を使用する。
    """

    def __init__(self):
        super().__init__("fundamental")
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

    def _get_fundamentals_jquants(self, symbol: str) -> dict | None:
        """J-Quants から財務情報を取得する.

        Returns:
            per, pbr, div_yield, roe, equity_ratio を含む dict、失敗時は None
        """
        client = self._get_jquants_client()
        if client is None:
            return None
        try:
            # J-Quants の銘柄コードは ".T" サフィックスなし
            code = symbol.replace(".T", "")
            statements = client.get_financial_statements(code)
            if not statements:
                return None
            # 最新の財務情報を使用
            latest = statements[-1]
            result: dict = {}
            # PER (株価収益率)
            per = latest.get("PriceEarningsRatio")
            if per is not None:
                try:
                    result["per"] = float(per)
                except (ValueError, TypeError):
                    pass
            # PBR (株価純資産倍率)
            pbr = latest.get("PriceBookValueRatio")
            if pbr is not None:
                try:
                    result["pbr"] = float(pbr)
                except (ValueError, TypeError):
                    pass
            # 配当利回り
            div = latest.get("DividendYield")
            if div is not None:
                try:
                    result["div_yield"] = float(div) / 100  # % → 比率
                except (ValueError, TypeError):
                    pass
            # ROE
            roe = latest.get("ROE")
            if roe is not None:
                try:
                    result["roe"] = float(roe) / 100
                except (ValueError, TypeError):
                    pass
            # 自己資本比率
            equity_ratio = latest.get("EquityToAssetRatio")
            if equity_ratio is not None:
                try:
                    result["equity_ratio"] = float(equity_ratio) / 100
                except (ValueError, TypeError):
                    pass
            return result if result else None
        except Exception as e:
            logger.warning("J-Quants fundamentals failed for %s: %s", symbol, e)
            return None

    def _get_fundamentals_yfinance(self, symbol: str) -> dict | None:
        """yfinance から財務情報を取得する."""
        try:
            info = yf.Ticker(symbol).info
        except Exception as e:
            logger.warning("Failed to fetch info for %s: %s", symbol, e)
            return None
        result: dict = {}
        per = info.get("trailingPE") or info.get("forwardPE")
        if per is not None:
            result["per"] = per
        pbr = info.get("priceToBook")
        if pbr is not None:
            result["pbr"] = pbr
        div_yield = info.get("dividendYield")
        if div_yield is not None:
            result["div_yield"] = div_yield
        roe = info.get("returnOnEquity")
        if roe is not None:
            result["roe"] = roe
        return result if result else None

    def get_fundamentals(self, symbol: str) -> dict | None:
        """J-Quants → yfinance のフォールバックで財務情報を取得する."""
        result = self._get_fundamentals_jquants(symbol)
        if result:
            logger.debug("Fundamentals for %s from J-Quants", symbol)
            return result
        result = self._get_fundamentals_yfinance(symbol)
        if result:
            logger.debug("Fundamentals for %s from yfinance (fallback)", symbol)
        return result

    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        info = self.get_fundamentals(symbol)

        if info is None:
            return AgentOpinion(
                agent_name=self.name, symbol=symbol,
                action="HOLD", confidence=0.3,
                reasoning="情報取得失敗",
            )

        per = info.get("per")
        pbr = info.get("pbr")
        div_yield = info.get("div_yield")
        roe = info.get("roe")

        scores = []
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
