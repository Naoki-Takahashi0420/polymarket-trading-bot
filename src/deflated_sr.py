"""偽戦略定理ベースの Deflated Sharpe Ratio (DSR) 計算モジュール."""

from __future__ import annotations

import json
import os

import numpy as np
from scipy.stats import norm


class DeflatedSharpeRatio:
    """Bailey and López de Prado (2014) に基づく DSR 計算."""

    EULER_MASCHERONI = 0.5772156649

    def __init__(self, trial_count_file: str = "data/trial_count.json"):
        self.trial_count_file = trial_count_file
        self._load_trial_count()

    def _load_trial_count(self) -> None:
        if os.path.exists(self.trial_count_file):
            with open(self.trial_count_file) as f:
                data = json.load(f)
                self.trial_count = data.get("N", 0)
        else:
            self.trial_count = 0

    def _save_trial_count(self) -> None:
        os.makedirs(os.path.dirname(self.trial_count_file), exist_ok=True)
        with open(self.trial_count_file, "w") as f:
            json.dump({"N": self.trial_count}, f)

    def increment_trials(self, n: int = 1) -> None:
        """バックテスト試行回数をインクリメントして永続化する."""
        self.trial_count += n
        self._save_trial_count()

    def expected_max_sr(self, N: int, sr_std: float) -> float:
        """偽戦略定理に基づく E[max SR] を計算する.

        Args:
            N: 試行（戦略）の数
            sr_std: 全試行の SR の標準偏差

        Returns:
            期待最大シャープレシオ SR0
        """
        if N <= 1:
            return 0.0
        gamma = self.EULER_MASCHERONI
        e = np.e
        sr0 = sr_std * (
            (1 - gamma) * norm.ppf(1 - 1 / N)
            + gamma * norm.ppf(1 - 1 / (N * e))
        )
        return float(sr0)

    def calculate_dsr(
        self,
        sr_observed: float,
        sr_std: float,
        N: int,
        T: int,
    ) -> dict:
        """Deflated Sharpe Ratio を計算する.

        Args:
            sr_observed: 観測された最良 SR（年率）
            sr_std: 全試行の SR の標準偏差
            N: 試行（戦略）の数
            T: 観測数（日次なら日数）

        Returns:
            dsr, sr_observed, sr0_expected_max, sigma_sr, N_trials, T_observations, passed を含む dict
        """
        sigma_sr = 1 / np.sqrt(T - 1) if T > 1 else 1.0
        sr0 = self.expected_max_sr(N, sr_std)

        if sigma_sr > 0:
            dsr = float(norm.cdf((sr_observed - sr0) * np.sqrt(T - 1)))
        else:
            dsr = 1.0 if sr_observed > sr0 else 0.0

        return {
            "dsr": round(dsr, 6),
            "sr_observed": sr_observed,
            "sr0_expected_max": round(sr0, 6),
            "sigma_sr": round(sigma_sr, 6),
            "N_trials": N,
            "T_observations": T,
            "passed": dsr > 0.95,
        }

    def gate(
        self,
        sr_observed: float,
        sr_std: float,
        T: int,
        threshold: float = 0.95,
    ) -> dict:
        """現在の試行回数で DSR ゲート判定する.

        Args:
            sr_observed: 観測された最良 SR
            sr_std: 全試行の SR の標準偏差
            T: 観測数
            threshold: 合格閾値（デフォルト 0.95）

        Returns:
            calculate_dsr の結果（passed が threshold で上書き）
        """
        N = max(self.trial_count, 1)
        result = self.calculate_dsr(sr_observed, sr_std, N, T)
        result["passed"] = result["dsr"] > threshold
        return result
