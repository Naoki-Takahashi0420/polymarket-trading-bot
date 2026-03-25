"""backtesting.py ベースのバックテストエンジン."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


class RangeStrategy(Strategy):
    """レンジ取引戦略: レンジ下限で買い、上限で売り."""

    range_upper = 0.0
    range_lower = 0.0
    stop_loss_pct = 0.03

    def init(self):
        self.upper = self.range_upper
        self.lower = self.range_lower
        self.stop_price = self.lower * (1 - self.stop_loss_pct)

    def next(self):
        price = self.data.Close[-1]

        if not self.position:
            # レンジ下限に到達したら買い
            if price <= self.lower:
                self.buy()
        else:
            # レンジ上限に到達したら利確
            if price >= self.upper:
                self.position.close()
            # 損切り
            elif price <= self.stop_price:
                self.position.close()


def run_backtest(
    df: pd.DataFrame,
    range_upper: float,
    range_lower: float,
    initial_cash: int = 1_000_000,
    commission: float = 0.001,
    stop_loss_pct: float = 0.03,
) -> dict:
    """バックテストを実行する.

    Args:
        df: OHLCVデータ
        range_upper: レンジ上限
        range_lower: レンジ下限
        initial_cash: 初期資金
        commission: 手数料率
        stop_loss_pct: 損切り率

    Returns:
        結果の辞書
    """
    bt = Backtest(
        df,
        RangeStrategy,
        cash=initial_cash,
        commission=commission,
        exclusive_orders=True,
    )

    stats = bt.run(
        range_upper=range_upper,
        range_lower=range_lower,
        stop_loss_pct=stop_loss_pct,
    )

    result = {
        "return_pct": float(stats["Return [%]"]),
        "buy_and_hold_return_pct": float(stats["Buy & Hold Return [%]"]),
        "max_drawdown_pct": float(stats["Max. Drawdown [%]"]),
        "num_trades": int(stats["# Trades"]),
        "win_rate_pct": float(stats["Win Rate [%]"]) if stats["# Trades"] > 0 else 0.0,
        "sharpe_ratio": float(stats["Sharpe Ratio"]) if not np.isnan(stats["Sharpe Ratio"]) else 0.0,
        "profit_factor": float(stats["Profit Factor"]) if not np.isnan(stats["Profit Factor"]) else 0.0,
        "final_equity": float(stats["Equity Final [$]"]),
    }

    return result, stats, bt


def save_results(
    result: dict,
    stats,
    bt,
    symbol: str,
    output_dir: Union[Path, str] = "data",
) -> None:
    """バックテスト結果を JSON と HTML で保存する."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_symbol = symbol.replace(".", "_")

    # JSON
    json_path = output_dir / f"backtest_{safe_symbol}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # HTML
    html_path = output_dir / f"backtest_{safe_symbol}.html"
    bt.plot(filename=str(html_path), open_browser=False)
