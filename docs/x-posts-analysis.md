# X投稿分析：AI × 投資/トレーディング 最新トレンド（2026年3月）

## 全20ポスト要約

### 🔥 カテゴリA: Claude/AI Codeで株取引を自動化（日本株特化・超バズ）

| # | 投稿者 | 内容 | Views | 要点 |
|---|--------|------|-------|------|
| 1 | @_map_universe_ | Claude Codeで東証株取引を半自動化（シリーズ4本） | 641K〜14K | kabu Station API + Claude Code。準備→未来→スクショ→ペーパートレード。プログラミング不要 |
| 3 | @Bakullc2022 | Claudeで3分でアビトラダッシュボード完成 | 88K | 非エンジニアが感動。「核やろ…」 |
| 5 | @blog_uki (UKI) | 億越え手法の論文公開、Claudeで10分実装 | 1.3M | 中川先生のPCA日米業種間時差アービトラージ論文 |
| 6 | @keeeeei0315 (中川先生本人) | 戦略の「再現」はAI可能、「生成」は不可能 | 144K | 大阪公立大教授。AIの限界を明言 |
| 8 | @aiba_algorithm | Claude Codeにpdf+Yahoo Finance→1発実装 | 81K | 専業botter。ドバイ在住 |

### 📊 カテゴリB: AI投資ツール/インフラ

| # | 投稿者 | 内容 | Views | 要点 |
|---|--------|------|-------|------|
| 11 | @heynavtoor | daily_stock_analysis（GitHub Actions無料自動分析） | - | Gemini/DeepSeekでbuy/sell/hold。Telegram/Discord通知 |
| 12 | @entry20210104 | JPXのJ-RENS（AI株検索） | 108K | 無償。曖昧な言葉でAI検索 |
| 13 | @entry20210104 | Geminiで有価証券報告書→不動産含み損益マッピング | 1.8M | Google Map連携 |
| 14 | @suwadeiijyan_ | 日本株半自動化に使えるAPI 4選 | - | J-Quants、Yahoo Finance、JPX公式、Alpha Vantage |
| 15 | @yonkuro_awesome | Perplexityが証券口座と直接連携開始 | - | 24時間AI監視。決算リスク自動算出 |
| 17 | @unusual_whales | Unusual Whales MCP Server | 8.3K likes | Claude/AIにライブ市場データ提供。MCPプロトコル |

### 🤖 カテゴリC: Bot/クオンツ/自動売買

| # | 投稿者 | 内容 | Views | 要点 |
|---|--------|------|-------|------|
| 4 | @takai_toushi | NTT 150-160円レンジ売買、勝率100% | 1.4M | 感情排除の淡々としたレンジ取引 |
| 9 | @aiba_algorithm | AI時代のbotter 5分類 | 35K | ①アビトラ②イベント③ML④ロングショート⑤高頻度 |
| 10 | @k1rallik | Polymarket bot、2週間で$250K | - | Rust、40ms未満、速度アービトラージ |
| 16 | @quantscience_ | TensorTrade（強化学習トレーディング） | 339K | Python OSS。強化学習ベース |
| 19 | @RoundtableSpace | ai-hedge-fund OSS（18エージェント） | - | 各エージェントが異なる投資哲学→議論→PM判断 |

### 💹 カテゴリD: インフラ/市場アクセス

| # | 投稿者 | 内容 | Views | 要点 |
|---|--------|------|-------|------|
| 2 | @rain_vc | USDCレンディング年率10% | 48K | SBI VCトレード。パッシブ運用 |
| 7 | @tradexyz | S&P 500無期限先物、Hyperliquidで24/7取引 | - | オンチェーン。制度的ブレイクスルー |
| 18 | @aiedge_ | How to Invest in AI | 1.9M | AI関連株への投資ガイド |
| 20 | @nrqa__ | AIをトレード/投資に使う方法 | 249K | 包括的ガイド |

---

## 分析：5つの重要な発見

### 1. 「Claude Code × 東証」が日本で爆発的にバズっている
- @_map_universe_ のシリーズが641K views
- @blog_uki の億越え手法+Claude実装が1.3M views
- **共通点：プログラミング不要で株取引をAI自動化**
- 日本語圏で「バイブトレーディング」的な動きが既に始まっている

### 2. 戦略の「再現」はAI可能、「生成」は不可能（中川先生の指摘）
- AIは論文を渡せば実装できるが、新しい戦略を0から生み出すことはまだできない
- **つまり「良い戦略」を知っていること自体が差別化要因**
- 戦略のキュレーション＋AI実装 = 価値の源泉

### 3. MCPサーバー（AIと市場データの接続層）が急成長
- Unusual Whales MCP Server: Claude/AIに直接市場データを渡す
- Perplexityの証券口座連携
- **AIが直接市場にアクセスするインフラが整いつつある**

### 4. 日本株特化のAPIエコシステムが揃っている
- J-Quants API（JPX公式）
- kabu Station API（au カブコム証券）
- J-RENS（JPX AI検索）
- Yahoo Finance Japan
- **インフラは揃っている。使う人がいないだけ**

### 5. マルチエージェント型ヘッジファンドがOSSで出てきた
- ai-hedge-fund: 18エージェントが各自の投資哲学で分析→議論→判断
- **「バイブトレーディング」の究極形 = AI同士が議論して投資判断**
