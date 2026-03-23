"""エージェント基底クラス."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class AgentOpinion:
    agent_name: str
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    reasoning: str


class BaseAgent(ABC):
    """全エージェントの基底クラス."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, symbol: str, data: pd.DataFrame, **kwargs) -> AgentOpinion:
        """銘柄を分析し、意見を返す."""
        pass
