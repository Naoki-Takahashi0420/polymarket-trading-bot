# Requirements Document

## Introduction
本プロジェクトは、Growing up社内専用の日本株自動売買システムである。東証上場銘柄のレンジ相場を自動検出し、kabu Station API（三菱UFJ eスマート証券）を通じて自動売買を行う。

Phase 1-A（データ取得・レンジ検出・バックテスト・シグナル生成）は実装済み。本ドキュメントはPhase 1-B（API接続・売買執行・通知・メインループ）の要件を定義する。

### 前提条件
- このドキュメントでは、三菱UFJ eスマート証券（旧auカブコム証券）のkabu Station APIを使用することを想定する
- kabu Station APIはローカルPCで起動したkabuステーションを経由してREST APIでアクセスする
- ペーパートレード（デモ環境）と本番環境の両方に対応する
- 取引対象は東証上場の大型株（TOPIX Core30 + Large70）
- 取引時間は東証前場（9:00-11:30）・後場（12:30-15:30）のみ

## Requirements

### Requirement 1: kabu Station API認証
**User Story:** As a trader, I want the system to automatically authenticate with kabu Station API and maintain a valid session, so that I can execute trades without manual intervention.
#### Acceptance Criteria
1. APIパスワードを使用してトークンを取得できる
2. トークンの有効期限を管理し、期限切れ前に自動更新する
3. 認証失敗時は3回リトライし、それでも失敗したらDiscord通知を送る
4. 認証情報（パスワード）は環境変数から読み取り、コードにハードコードしない

### Requirement 2: 銘柄情報取得
**User Story:** As a trader, I want the system to fetch real-time stock information via API, so that I can make informed trading decisions.
#### Acceptance Criteria
1. 銘柄コード指定で現在値・売買気配値・出来高を取得できる
2. 複数銘柄の一括取得に対応する
3. API呼び出しのレート制限を遵守する（1秒あたり10リクエスト以下）

### Requirement 3: 注文発注
**User Story:** As a trader, I want the system to place limit orders automatically based on trading signals, so that I can execute range trading strategies without emotional bias.
#### Acceptance Criteria
1. 指値注文（買い・売り）を発注できる
2. 注文種別: 現物買い、現物売り、信用新規買い、信用新規売り、信用返済に対応
3. 注文数量とポジションサイジングはsignal_generatorの出力に基づく
4. 重複注文を防止するロジックを実装する
5. 注文発注後、注文IDを記録する

### Requirement 4: 注文管理
**User Story:** As a trader, I want the system to monitor and manage open orders, so that I can track order status and cancel stale orders.
#### Acceptance Criteria
1. 未約定注文の一覧を取得できる
2. 指定した注文をキャンセルできる
3. 一定時間（設定可能）未約定の注文は自動キャンセルする
4. 約定通知をDiscordに送信する

### Requirement 5: ポジション管理
**User Story:** As a trader, I want the system to track all open positions, so that I can enforce risk management rules.
#### Acceptance Criteria
1. 現在の保有ポジション（銘柄・数量・取得価格・評価損益）を取得できる
2. 最大同時ポジション数（デフォルト3）を超えないよう制御する
3. 1銘柄あたりの最大投資金額を制限する
4. ポジション情報をローカルDBに記録する

### Requirement 6: ペーパートレードモード
**User Story:** As a developer, I want a paper trading mode that simulates trades without real money, so that I can test strategies safely before going live.
#### Acceptance Criteria
1. 設定ファイルでペーパートレード/本番モードを切り替えられる
2. ペーパートレードモードでは実際のAPI発注は行わず、シミュレーション結果をログに記録する
3. 仮想残高・仮想ポジションを管理し、損益を計算する
4. ペーパートレードの取引履歴をCSVで出力できる

### Requirement 7: Discord通知
**User Story:** As a team member, I want to receive trading notifications on Discord, so that I can monitor the bot's activity in real-time.
#### Acceptance Criteria
1. 売買シグナル発生時にDiscordに通知する（銘柄名、方向、価格、理由）
2. 注文約定時に通知する（銘柄名、約定価格、数量、損益）
3. 日次レポートを毎日15:35（取引終了後）に送信する（当日損益、保有ポジション、残高）
4. エラー発生時に即座に通知する
5. 通知先はDiscord Webhookで設定可能

### Requirement 8: メインループ（スケジューラー）
**User Story:** As a trader, I want the system to run autonomously during market hours, so that I don't need to manually trigger any actions.
#### Acceptance Criteria
1. 東証取引時間（9:00-11:30、12:30-15:30 JST）のみ稼働する
2. 一定間隔（デフォルト5分）でデータ取得→シグナル判定→注文執行のループを回す
3. 取引開始前（8:55）にシステムヘルスチェックを行う
4. 取引終了後（15:35）に日次レポートを生成・送信する
5. 昼休み（11:30-12:30）は待機状態にする
6. Ctrl+Cでグレースフルシャットダウンする

### Requirement 9: ログ・監査証跡
**User Story:** As a developer, I want comprehensive logging and audit trails, so that I can debug issues and review trading history.
#### Acceptance Criteria
1. 全API呼び出しのリクエスト/レスポンスをログに記録する
2. 全取引判断（シグナル生成→注文→約定）の根拠をログに記録する
3. ログファイルは日付ごとにローテーションする
4. ログレベル（DEBUG/INFO/WARNING/ERROR）を設定ファイルで制御できる

### Requirement 10: エラーハンドリング
**User Story:** As a trader, I want the system to handle errors gracefully, so that a single failure doesn't crash the entire bot.
#### Acceptance Criteria
1. API通信エラー時は3回リトライ（指数バックオフ）する
2. リトライ失敗時はDiscord通知を送り、そのサイクルをスキップする
3. 致命的エラー（認証失敗、残高不足）時はボットを停止しDiscord通知する
4. 個別銘柄のエラーが他の銘柄の処理に影響しない
