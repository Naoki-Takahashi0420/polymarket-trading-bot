"""過剰最適化対策: ロバスト性検証エンジン."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from backtesting import Backtest

logger = logging.getLogger(__name__)


class RobustTester:
    """ウォークフォワード分析、パラメータ感度テスト、モンテカルロシミュレーションを提供する."""

    def __init__(
        self,
        walk_forward_min_pf: float = 1.0,
        sensitivity_max_range: float = 0.15,
        monte_carlo_max_dd: float = 0.30,
        monte_carlo_simulations: int = 1000,
    ):
        self.walk_forward_min_pf = walk_forward_min_pf
        self.sensitivity_max_range = sensitivity_max_range
        self.monte_carlo_max_dd = monte_carlo_max_dd
        self.monte_carlo_simulations = monte_carlo_simulations

    def walk_forward_test(
        self,
        data: pd.DataFrame,
        strategy_class,
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        cash: int = 1_000_000,
        commission: float = 0.001,
        **strategy_params,
    ) -> dict:
        """データを train/val/test に分割してウォークフォワード分析.

        Returns:
            {"train_pf": float, "val_pf": float, "test_pf": float, "passed": bool}
        """
        n = len(data)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_data = data.iloc[:train_end]
        val_data = data.iloc[train_end:val_end]
        test_data = data.iloc[val_end:]

        results = {}
        for name, subset in [("train", train_data), ("val", val_data), ("test", test_data)]:
            if len(subset) < 10:
                results[f"{name}_pf"] = 0.0
                continue
            bt = Backtest(subset, strategy_class, cash=cash, commission=commission, exclusive_orders=True)
            stats = bt.run(**strategy_params)
            pf = float(stats["Profit Factor"]) if not np.isnan(stats["Profit Factor"]) else 0.0
            results[f"{name}_pf"] = round(pf, 4)

        results["passed"] = (
            results["val_pf"] > self.walk_forward_min_pf
            and results["test_pf"] > self.walk_forward_min_pf
        )
        return results

    def parameter_sensitivity(
        self,
        data: pd.DataFrame,
        strategy_class,
        base_params: dict,
        variation: float = 0.2,
        cash: int = 1_000_000,
        commission: float = 0.001,
    ) -> dict:
        """各パラメータを±variation振って勝率の変動を測定.

        Returns:
            {"param_name": {"base": float, "min": float, "max": float, "range": float}, ...}
            "passed": bool
        """
        # ベースラインの勝率を取得
        bt = Backtest(data, strategy_class, cash=cash, commission=commission, exclusive_orders=True)
        base_stats = bt.run(**base_params)
        base_wr = float(base_stats["Win Rate [%]"]) if base_stats["# Trades"] > 0 else 0.0

        sensitivity = {}
        all_passed = True

        for param_name, param_value in base_params.items():
            if not isinstance(param_value, (int, float)):
                continue

            win_rates = [base_wr]
            for mult in [1 - variation, 1 + variation]:
                varied_params = base_params.copy()
                varied_params[param_name] = type(param_value)(param_value * mult)
                stats = bt.run(**varied_params)
                wr = float(stats["Win Rate [%]"]) if stats["# Trades"] > 0 else 0.0
                win_rates.append(wr)

            wr_min = min(win_rates)
            wr_max = max(win_rates)
            wr_range = (wr_max - wr_min) / 100.0  # パーセントを比率に変換

            sensitivity[param_name] = {
                "base": round(base_wr, 2),
                "min": round(wr_min, 2),
                "max": round(wr_max, 2),
                "range": round(wr_range, 4),
            }

            if wr_range >= self.sensitivity_max_range:
                all_passed = False

        return {"params": sensitivity, "passed": all_passed}

    def monte_carlo_simulation(
        self,
        trades: list[float],
        n_simulations: Optional[int] = None,
        initial_capital: float = 1_000_000,
    ) -> dict:
        """取引をランダムシャッフルして最悪ケースを算出.

        Args:
            trades: 各取引のPnL（金額）のリスト
            n_simulations: シミュレーション回数
            initial_capital: 初期資金

        Returns:
            {"median_return": float, "worst_dd": float, "p5_return": float, "passed": bool}
        """
        n_simulations = n_simulations or self.monte_carlo_simulations

        if not trades:
            return {
                "median_return": 0.0,
                "worst_dd": 0.0,
                "p5_return": 0.0,
                "passed": True,
            }

        trades_arr = np.array(trades)
        rng = np.random.default_rng(42)

        final_returns = []
        max_drawdowns = []

        for _ in range(n_simulations):
            shuffled = rng.permutation(trades_arr)
            equity = initial_capital + np.cumsum(shuffled)
            equity = np.insert(equity, 0, initial_capital)

            # 最大ドローダウン
            peak = np.maximum.accumulate(equity)
            dd = (peak - equity) / peak
            max_dd = float(np.max(dd))

            final_ret = float((equity[-1] - initial_capital) / initial_capital)
            final_returns.append(final_ret)
            max_drawdowns.append(max_dd)

        final_returns = np.array(final_returns)
        max_drawdowns = np.array(max_drawdowns)

        worst_dd = float(np.max(max_drawdowns))
        median_return = float(np.median(final_returns))
        p5_return = float(np.percentile(final_returns, 5))

        return {
            "median_return": round(median_return, 4),
            "worst_dd": round(worst_dd, 4),
            "p5_return": round(p5_return, 4),
            "passed": worst_dd < self.monte_carlo_max_dd,
        }

    def robustness_gate(
        self,
        data: pd.DataFrame,
        strategy_class,
        trades: list[float],
        cash: int = 1_000_000,
        commission: float = 0.001,
        **strategy_params,
    ) -> dict:
        """3つのチェックを全実行し、総合判定.

        Returns:
            {"walk_forward": dict, "sensitivity": dict, "monte_carlo": dict, "overall_passed": bool}
        """
        wf = self.walk_forward_test(
            data, strategy_class, cash=cash, commission=commission, **strategy_params,
        )
        sens = self.parameter_sensitivity(
            data, strategy_class, base_params=strategy_params, cash=cash, commission=commission,
        )
        mc = self.monte_carlo_simulation(trades)

        overall = wf["passed"] and sens["passed"] and mc["passed"]

        result = {
            "walk_forward": wf,
            "sensitivity": sens,
            "monte_carlo": mc,
            "overall_passed": overall,
        }

        if not overall:
            logger.warning("Robustness gate FAILED: wf=%s, sens=%s, mc=%s", wf["passed"], sens["passed"], mc["passed"])
        else:
            logger.info("Robustness gate PASSED")

        return result

    def save_report(self, result: dict, output_dir: str = "data") -> None:
        """ロバスト性検証結果をJSONで保存する."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "robustness_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info("Robustness report saved to %s", path)
