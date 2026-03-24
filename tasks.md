# Tasks — Phase 1: レンジ取引ボット MVP

## Phase 1-A: データ取得 + レンジ検出 + バックテスト基盤

- [x] プロジェクト構造セットアップ（src/, tests/, config/, data/）
- [x] requirements.txt 作成（yfinance, backtesting, pandas, numpy, pyyaml, requests）
- [x] config/settings.yaml 作成（銘柄リスト、パラメータ、APIエンドポイント）
- [x] src/data_fetcher.py — Yahoo Finance から日本株データ取得（日足・5分足）
- [x] src/range_detector.py — レンジ銘柄の自動検出・スコアリング
  - ボリンジャーバンド幅
  - ATR（平均真の値幅）
  - レンジ内滞在率
  - 流動性フィルター（出来高）
- [x] src/backtester.py — backtesting.py ベースのバックテストエンジン
  - レンジ取引戦略クラス（RangeStrategy）
  - レンジ下限で買い、上限で売り
  - 損切りロジック
  - 結果レポート（勝率、PnL、最大DD、シャープレシオ）
- [x] src/signal_generator.py — 売買シグナル生成
  - リアルタイム価格監視
  - エントリー/エグジット条件判定
  - ポジションサイジング
- [x] tests/test_range_detector.py — レンジ検出のユニットテスト
- [x] tests/test_backtester.py — バックテストのユニットテスト
- [x] README.md 作成

## Phase 1-B: kabu Station API 接続 + 売買執行

- [x] src/kabu_api.py — kabu Station API クライアント
  - トークン取得・更新
  - 銘柄情報取得
  - 注文発注（指値）
  - 注文取消
  - ポジション照会
  - 残高照会
- [x] src/executor.py — 売買執行エンジン
  - ペーパートレードモード
  - 本番モード（kabu API経由）
  - リスク管理（最大ポジション数、1銘柄最大金額）
- [x] src/notifier.py — Discord Webhook 通知
  - 売買シグナル通知
  - 約定通知
  - 日次レポート
  - エラー通知
- [x] src/main.py — メインループ
  - スケジューラー（東証取引時間のみ）
  - データ取得 → シグナル判定 → 注文執行 → 通知
- [x] config/settings.yaml に API 設定追加
- [x] tests/test_kabu_api.py — API接続テスト（モック）
- [x] git commit + push
- [x] gh pr create
