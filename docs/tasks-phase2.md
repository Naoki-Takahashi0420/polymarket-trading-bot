# Implementation Plan — Phase 2: 過剰最適化対策 + テーマ分析基盤

## Phase 2-A: 過剰最適化対策（バックテスト強化）

- [ ] 1. src/robust_tester.py — ロバスト性検証エンジン
  - walk_forward_test(): データを学習60%/検証20%/最終テスト20%に分割、ウォークフォワード分析
  - parameter_sensitivity(): 全パラメータを±20%振って勝率変動を測定
  - monte_carlo_simulation(): 取引順序をランダム入替で1000回シミュレーション、最悪ケースDD算出
  - robustness_gate(): 3つのチェック全パスで合格判定
    - ウォークフォワード: 検証期間PF > 1.0
    - パラメータ感度: ±20%で勝率変動 < 15%
    - モンテカルロ: 最悪ケースDD < 30%
  - HTML + JSON レポート出力
  - _Requirements: 過剰最適化防止_

- [ ] 2. tests/test_robust_tester.py — ロバスト性検証のユニットテスト
  - 既知の過剰最適化パターンでフェイル判定されることを確認
  - 安定した戦略でパス判定されることを確認

- [ ] 3. src/backtester.py 統合 — 既存バックテストにロバスト性ゲート追加
  - バックテスト実行後に自動でrobustness_gate()を呼び出し
  - 不合格の場合は警告ログ + Discord通知

## Phase 2-B: テーマ分析基盤

- [ ] 4. src/theme_analyzer.py — テーマ分析エンジン
  - ニュースソースからテーマキーワード抽出（RSS: 日経、ロイター、適時開示）
  - テーマ→関連銘柄マッピング（セクター分類 + キーワード辞書）
  - テーマ発生→銘柄群の値動きパターンをSQLiteに記録
  - 過去パターン照合: 「テーマX発生時、銘柄Y群は平均Z%上昇、期間W日」
  - _Requirements: テーマ分析、ナレッジ蓄積_

- [ ] 5. src/news_fetcher.py — ニュース自動取得
  - RSS/Atomフィードからニュース取得（日経、ロイター日本語版、適時開示）
  - キーワード抽出（形態素解析 or 正規表現）
  - テーマ分類（戦争、半導体、AI、脱炭素、金融政策 等）
  - SQLiteにニュース + テーマ + 日時を保存

- [ ] 6. src/volume_spike_detector.py — 出来高スパイク検知
  - 全監視銘柄の出来高を定期取得
  - 過去20日平均出来高の2倍以上 → スパイク判定
  - スパイク検知時にDiscord通知 + シグナル生成への入力
  - _Requirements: 資金流入初動検知_

- [ ] 7. DBスキーマ追加（position_manager.py拡張）
  - themes テーブル: id, theme_name, keywords, first_detected_at
  - theme_events テーブル: id, theme_id, news_title, news_url, detected_at
  - theme_impacts テーブル: id, theme_id, symbol, price_change_pct, period_days, recorded_at

- [ ] 8. tests/test_theme_analyzer.py
- [ ] 9. tests/test_volume_spike_detector.py

- [ ] 10. config/settings.yaml 更新
  - ニュースソースURL
  - テーマキーワード辞書
  - 出来高スパイク閾値

- [ ] 11. git commit + push + PR
  - コミット: "feat: Phase 2 過剰最適化対策 + テーマ分析基盤"
