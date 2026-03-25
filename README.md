# 日本株レンジ取引ボット

東証大型株のレンジ相場を自動検出し、下限で買い→上限で売りを繰り返すトレーディングボット。

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

### 1. レンジ銘柄の検出

```python
from src.data_fetcher import fetch_multiple
from src.range_detector import detect_range_stocks, print_ranking

import yaml

with open("config/settings.yaml") as f:
    config = yaml.safe_load(f)

data = fetch_multiple(config["symbols"])
rankings = detect_range_stocks(
    data,
    lookback_days=config["range_detection"]["lookback_days"],
    bb_width_threshold=config["range_detection"]["bb_width_threshold"],
    atr_ratio_threshold=config["range_detection"]["atr_ratio_threshold"],
    range_containment_threshold=config["range_detection"]["range_containment_threshold"],
)
print_ranking(rankings)
```

### 2. バックテスト

```python
from src.backtester import run_backtest, save_results

symbol = "9432.T"
df = data[symbol]
info = next(r for r in rankings if r.symbol == symbol)

result, stats, bt = run_backtest(
    df,
    range_upper=info.range_upper,
    range_lower=info.range_lower,
    initial_cash=config["backtest"]["initial_cash"],
    commission=config["backtest"]["commission"],
)
print(result)
save_results(result, stats, bt, symbol)
```

### 3. シグナル生成

```python
from src.signal_generator import generate_signals_for_rankings

signals = generate_signals_for_rankings(
    rankings,
    total_capital=config["backtest"]["initial_cash"],
    position_size_pct=config["trading"]["position_size_pct"],
    stop_loss_pct=config["trading"]["stop_loss_pct"],
    max_positions=config["trading"]["max_positions"],
)
for s in signals:
    print(f"{s.symbol}: {s.signal.value} @ {s.current_price}")
```

### 4. テスト実行

```bash
pytest tests/ -v
```

## 設定

`config/settings.yaml` で以下を設定可能:

- **symbols**: 監視対象の銘柄リスト
- **range_detection**: レンジ検出パラメータ（BB幅閾値、ATR比率閾値、滞在率閾値）
- **backtest**: バックテスト設定（初期資金、手数料、期間）
- **trading**: 取引設定（ポジションサイズ、損切り率、最大ポジション数）

## プロジェクト構造

```
src/
  data_fetcher.py      # Yahoo Finance データ取得
  range_detector.py    # レンジ銘柄検出・スコアリング
  backtester.py        # バックテストエンジン
  signal_generator.py  # 売買シグナル生成
tests/
  test_range_detector.py
  test_backtester.py
config/
  settings.yaml        # 設定ファイル
data/                  # キャッシュ・出力ディレクトリ
```
