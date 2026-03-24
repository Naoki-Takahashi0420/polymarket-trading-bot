# Implementation Plan — Phase 3: マルチエージェント投資システム + 統合強化

## Phase 3-A: マルチエージェント分析基盤

- [ ] 1. src/agents/base_agent.py — エージェント基底クラス
  - BaseAgent ABC: analyze(symbol, data) -> AgentOpinion
  - AgentOpinion dataclass: agent_name, symbol, action(BUY/SELL/HOLD), confidence(0-1), reasoning
  - 全エージェントが統一インターフェースで分析結果を返す

- [ ] 2. src/agents/technical_agent.py — テクニカル分析エージェント
  - RSI, MACD, ボリンジャーバンド, 移動平均線を計算
  - 複数指標の総合判断でBUY/SELL/HOLD + confidence算出
  - 既存のsignal_generatorのロジックを拡張

- [ ] 3. src/agents/fundamental_agent.py — ファンダメンタル分析エージェント
  - PER, PBR, 配当利回り, ROEをyfinanceから取得
  - 業種平均との比較で割安/割高判定
  - 決算サプライズ（実績 vs 予想）の評価

- [ ] 4. src/agents/sentiment_agent.py — ニュースセンチメントエージェント
  - news_fetcher.pyからニュース取得
  - キーワードベースのポジティブ/ネガティブ判定
  - テーマ分析結果（theme_analyzer.py）も統合

- [ ] 5. src/agents/volume_agent.py — 需給分析エージェント
  - volume_spike_detector.pyのスパイク検知結果を活用
  - 出来高トレンド（増加/減少）分析
  - 信用残（貸借倍率）の評価（J-Quants API対応時に拡張）

- [ ] 6. src/agents/theme_agent.py — テーマ分析エージェント
  - theme_analyzer.pyの結果を活用
  - 現在のホットテーマと銘柄の関連度評価
  - 過去テーマパターンとの照合で方向性判断

## Phase 3-B: ポートフォリオマネージャー（統合判断）

- [ ] 7. src/portfolio_manager.py — ポートフォリオマネージャー
  - 全エージェントのAgentOpinionを収集
  - 加重投票: 各エージェントのconfidence × weight で最終判断
  - デフォルトweight: technical=0.3, fundamental=0.2, sentiment=0.15, volume=0.2, theme=0.15
  - 最終判断: 加重スコア > 0.6 → BUY, < -0.6 → SELL, else HOLD
  - 判断根拠のログ出力（どのエージェントがどう判断したか）
  - Discord通知に全エージェントの判断内訳を含める

- [ ] 8. src/main.py 更新 — マルチエージェント統合
  - 既存のsignal_generator単独判断 → portfolio_manager経由に切替
  - 設定でシングルモード/マルチエージェントモードを切替可能
  - マルチエージェントモード時の処理フロー:
    data取得 → 各エージェント分析(並列) → PM統合判断 → executor実行

## Phase 3-C: テスト + 統合

- [ ] 9. tests/test_agents.py — 全エージェントのユニットテスト
- [ ] 10. tests/test_portfolio_manager.py — PMのユニットテスト
  - 全BUY → BUY判定
  - 意見分裂 → HOLD判定
  - confidence加重の正確性
- [ ] 11. 結合テスト — マルチエージェントモードで1サイクル実行（ペーパー）

- [ ] 12. git commit + push + PR
  - コミット: "feat: Phase 3 マルチエージェント投資システム"
