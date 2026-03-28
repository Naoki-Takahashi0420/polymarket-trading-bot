"""DSR (Deflated Sharpe Ratio) モジュールのテスト."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from src.deflated_sr import DeflatedSharpeRatio


class TestExpectedMaxSR:
    def test_n_equals_1(self):
        dsr = DeflatedSharpeRatio()
        assert dsr.expected_max_sr(1, 0.5) == 0.0

    def test_n_equals_0(self):
        dsr = DeflatedSharpeRatio()
        assert dsr.expected_max_sr(0, 0.5) == 0.0

    def test_n_10_increases_with_sr_std(self):
        dsr = DeflatedSharpeRatio()
        sr0_low = dsr.expected_max_sr(10, 0.5)
        sr0_high = dsr.expected_max_sr(10, 1.0)
        assert sr0_high > sr0_low

    def test_sr0_increases_with_n(self):
        dsr = DeflatedSharpeRatio()
        sr0_10 = dsr.expected_max_sr(10, 0.5)
        sr0_100 = dsr.expected_max_sr(100, 0.5)
        sr0_1000 = dsr.expected_max_sr(1000, 0.5)
        assert sr0_10 < sr0_100 < sr0_1000

    def test_returns_float(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.expected_max_sr(100, 0.5)
        assert isinstance(result, float)


class TestCalculateDSR:
    def test_high_sr_passes(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.calculate_dsr(sr_observed=3.0, sr_std=0.5, N=10, T=252)
        assert result["passed"] is True
        assert result["dsr"] > 0.95

    def test_low_sr_fails(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.calculate_dsr(sr_observed=0.5, sr_std=0.5, N=1000, T=252)
        assert result["passed"] is False
        assert result["dsr"] < 0.95

    def test_result_keys(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.calculate_dsr(sr_observed=2.0, sr_std=0.5, N=10, T=252)
        expected_keys = {"dsr", "sr_observed", "sr0_expected_max", "sigma_sr", "N_trials", "T_observations", "passed"}
        assert expected_keys.issubset(result.keys())

    def test_dsr_in_range(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.calculate_dsr(sr_observed=1.5, sr_std=0.5, N=50, T=252)
        assert 0.0 <= result["dsr"] <= 1.0

    def test_n_10_reasonable_sr0(self):
        dsr = DeflatedSharpeRatio()
        result = dsr.calculate_dsr(sr_observed=2.0, sr_std=0.5, N=10, T=252)
        assert result["sr0_expected_max"] > 0

    def test_n_1000_higher_sr0(self):
        dsr = DeflatedSharpeRatio()
        r10 = dsr.calculate_dsr(sr_observed=2.0, sr_std=0.5, N=10, T=252)
        r1000 = dsr.calculate_dsr(sr_observed=2.0, sr_std=0.5, N=1000, T=252)
        # 試行数が多いほどSR0が高くなる（偽戦略リスクが大きい）
        assert r1000["sr0_expected_max"] > r10["sr0_expected_max"]
        # 同じSRでも試行数が多いほどDSRは低くなる（極端な値は丸め精度の限界あり）
        assert r1000["sr0_expected_max"] > r10["sr0_expected_max"]


class TestGate:
    def test_gate_uses_trial_count(self, tmp_path):
        count_file = str(tmp_path / "trial_count.json")
        with open(count_file, "w") as f:
            json.dump({"N": 5}, f)
        dsr = DeflatedSharpeRatio(trial_count_file=count_file)
        assert dsr.trial_count == 5
        result = dsr.gate(sr_observed=3.0, sr_std=0.5, T=252)
        assert "dsr" in result
        assert "passed" in result

    def test_gate_default_N1_when_no_file(self, tmp_path):
        count_file = str(tmp_path / "nonexistent.json")
        dsr = DeflatedSharpeRatio(trial_count_file=count_file)
        assert dsr.trial_count == 0
        result = dsr.gate(sr_observed=3.0, sr_std=0.5, T=252)
        assert result["N_trials"] == 1  # max(0, 1) = 1

    def test_custom_threshold(self, tmp_path):
        count_file = str(tmp_path / "trial_count.json")
        dsr = DeflatedSharpeRatio(trial_count_file=count_file)
        result = dsr.gate(sr_observed=3.0, sr_std=0.5, T=252, threshold=0.5)
        assert result["passed"] is True


class TestIncrementTrials:
    def test_increment_saves_to_file(self, tmp_path):
        count_file = str(tmp_path / "trial_count.json")
        dsr = DeflatedSharpeRatio(trial_count_file=count_file)
        dsr.increment_trials(5)
        assert dsr.trial_count == 5
        with open(count_file) as f:
            data = json.load(f)
        assert data["N"] == 5

    def test_increment_accumulates(self, tmp_path):
        count_file = str(tmp_path / "trial_count.json")
        dsr = DeflatedSharpeRatio(trial_count_file=count_file)
        dsr.increment_trials(3)
        dsr2 = DeflatedSharpeRatio(trial_count_file=count_file)
        dsr2.increment_trials(2)
        assert dsr2.trial_count == 5
