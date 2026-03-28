# Implementation Plan

## Phase 1-A: データ取得・レンジ検出・バックテスト（✅️ 完了）
- [x] 1. プロジェクト構造セットアップ
- [x] 2. data_fetcher.py — Yahoo Finance データ取得
- [x] 3. range_detector.py — レンジ銘柄自動検出
- [x] 4. backtester.py — バックテスト基盤
- [x] 5. signal_generator.py — 売買シグナル生成
- [x] 6. テスト（test_range_detector, test_backtester）
- [x] 7. config/settings.yaml + README.md

## Phase 1-B: kabu Station API接続・売買執行・通知

### インフラ・データ層
- [ ] 8. position_manager.py — SQLiteベースのポジション・注文管理
  - SQLiteデータベース初期化（positions, orders, daily_reports テーブル）
  - Position/Order dataclass定義（design.mdのインターフェースに従う）
  - add_position, close_position, get_open_positions 実装
  - can_open_new_position（最大ポジション数・最大金額チェック）
  - save_order, get_pending_orders 実装
  - get_daily_pnl 実装
  - _Requirements: 5, 9_

- [ ] 9. test_position_manager.py — ポジション管理のユニットテスト
  - ポジション追加・クローズ・PnL計算のテスト
  - リスクチェック（最大ポジション数超過）のテスト
  - _Requirements: 5_

### API接続層
- [ ] 10. kabu_api.py — kabu Station APIクライアント
  - KabuApiClient クラス作成
  - authenticate(password) — POST /token でトークン取得
  - get_board(symbol, exchange) — 時価情報取得
  - place_order(order) — 注文発注（POST /sendorder）
  - cancel_order(order_id) — 注文取消（PUT /cancelorder）
  - get_orders() — 注文一覧取得（GET /orders）
  - get_positions() — ポジション一覧取得（GET /positions）
  - レート制限（1秒10リクエスト以下）
  - リトライロジック（3回、指数バックオフ）
  - 本番URL(localhost:18080) / デモURL(localhost:18081) 切替
  - _Requirements: 1, 2, 3, 4, 10_

- [ ] 11. test_kabu_api.py — APIクライアントのユニットテスト（モック）
  - 認証成功/失敗のテスト
  - 注文発注のテスト
  - リトライロジックのテスト
  - _Requirements: 1, 3, 10_

### シミュレーション層
- [ ] 12. paper_trader.py — ペーパートレードシミュレーター
  - 仮想残高管理（初期値: settings.yamlのinitial_cash）
  - place_order — 仮想注文受付、仮想注文ID発行
  - check_fills(current_prices) — 指値到達で仮想約定
  - get_positions, get_balance
  - export_history(filepath) — CSV出力
  - _Requirements: 6_

- [ ] 13. test_paper_trader.py — ペーパートレーダーのユニットテスト
  - 仮想注文→仮想約定のフローテスト
  - 残高計算の正確性テスト
  - _Requirements: 6_

### 執行層
- [ ] 14. executor.py — 売買執行エンジン
  - mode設定（paper/live）でペーパー/本番切替
  - execute_signal(signal) — TradingSignalを受けて注文発行
  - 重複注文防止（同一銘柄・同方向の未約定注文チェック）
  - check_and_cancel_stale_orders(max_age_minutes) — 古い注文キャンセル
  - sync_positions() — API/シミュレーターからポジション同期
  - リスクチェック（position_manager.can_open_new_position）
  - _Requirements: 3, 4, 5, 6, 10_

- [ ] 15. test_executor.py — 執行エンジンのユニットテスト
  - ペーパーモードでのシグナル→注文フローテスト
  - 重複注文防止のテスト
  - リスクチェック超過時のテスト
  - _Requirements: 3, 4, 5_

### 通知層
- [ ] 16. notifier.py — Discord Webhook通知
  - notify_signal(signal) — シグナル通知（Embed形式）
  - notify_fill(order) — 約定通知
  - notify_error(error) — エラー通知
  - send_daily_report(report) — 日次レポート送信
  - Webhook URL は環境変数から取得
  - _Requirements: 7_

- [ ] 17. test_notifier.py — 通知のユニットテスト（モック）
  - 各種通知のフォーマット検証
  - _Requirements: 7_

### 統合・メインループ
- [ ] 18. main.py — メインスケジューラー
  - run() — メインエントリーポイント
  - is_trading_hours() — 取引時間判定（前場/後場/昼休み）
  - trading_loop() — 1サイクル: データ取得→レンジ検出→シグナル→執行→通知
  - pre_market_check() — 8:55 ヘルスチェック（API認証、DB接続）
  - post_market_report() — 15:35 日次レポート生成・送信
  - グレースフルシャットダウン（SIGINT/SIGTERM対応）
  - ログ設定（日付ローテーション、レベル設定可能）
  - _Requirements: 8, 9, 10_

- [ ] 19. config/settings.yaml 更新
  - kabu API設定（ホスト、ポート、デモ/本番）
  - 取引モード（paper/live）
  - 通知設定
  - ログ設定
  - _Requirements: 1, 6, 7, 8, 9_

- [ ] 20. 結合テスト — ペーパーモードで1サイクル実行
  - メインループの1サイクルがエラーなく完了することを確認
  - _Requirements: 6, 8_

- [ ] 21. git commit + push + PR作成
  - コミット: "feat: Phase 1-B kabu Station API接続 + 売買執行エンジン"
  - push to origin (Naoki-AI0420)
  - PR to upstream (Naoki-Takahashi0420)
  - _Requirements: all_
