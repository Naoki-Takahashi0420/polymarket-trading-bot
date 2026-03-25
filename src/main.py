"""メインスケジューラーモジュール."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import yaml

from src.data_fetcher import fetch_multiple, fetch_ohlcv
from src.executor import Executor
from src.kabu_api import KabuApiClient, KabuApiConfig
from src.notifier import DailyReport, Notifier
from src.paper_trader import PaperTrader
from src.position_manager import PositionManager
from src.range_detector import detect_range_stocks
from src.signal_generator import Signal, generate_signal

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """設定ファイルを読み込む."""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 環境変数の展開
    _expand_env_vars(config)
    return config


def _expand_env_vars(obj):
    """設定値内の ${VAR} を環境変数で置換する."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                obj[key] = os.environ.get(env_var, "")
            elif isinstance(value, (dict, list)):
                _expand_env_vars(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item.startswith("${") and item.endswith("}"):
                env_var = item[2:-1]
                obj[i] = os.environ.get(env_var, "")
            elif isinstance(item, (dict, list)):
                _expand_env_vars(item)


def setup_logging(config: dict) -> None:
    """ログ設定を行う."""
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)
    log_dir = Path(log_config.get("log_dir", "data/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ファイルハンドラ（日付ローテーション）
    file_handler = TimedRotatingFileHandler(
        str(log_file), when="midnight", backupCount=30, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def is_trading_hours(now: datetime = None) -> str:
    """取引時間を判定する.

    Returns:
        "pre_market" (8:55前), "morning" (9:00-11:30), "lunch" (11:30-12:30),
        "afternoon" (12:30-15:30), "post_market" (15:30以降), "closed" (上記以外)
    """
    if now is None:
        now = datetime.now()

    hour, minute = now.hour, now.minute
    t = hour * 60 + minute  # 分に変換

    if t < 8 * 60 + 55:
        return "closed"
    elif t < 9 * 60:
        return "pre_market"
    elif t < 11 * 60 + 30:
        return "morning"
    elif t < 12 * 60 + 30:
        return "lunch"
    elif t < 15 * 60 + 30:
        return "afternoon"
    elif t < 15 * 60 + 40:
        return "post_market"
    else:
        return "closed"


class TradingBot:
    """メインの取引ボット."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False

        # コンポーネント初期化
        trading_config = config.get("trading", {})
        self.mode = trading_config.get("mode", "paper")
        self.interval = trading_config.get("interval_seconds", 300)
        self.max_positions = trading_config.get("max_positions", 3)
        self.stale_order_minutes = trading_config.get("stale_order_minutes", 30)

        # Position Manager
        db_path = DATA_DIR / "trading.db"
        self.position_manager = PositionManager(
            db_path=db_path,
            max_positions=self.max_positions,
            max_per_stock=trading_config.get("max_per_stock", 500_000),
        )

        # Paper Trader / kabu API
        self.paper_trader = None
        self.kabu_client = None

        if self.mode == "paper":
            initial_cash = config.get("backtest", {}).get("initial_cash", 1_000_000)
            self.paper_trader = PaperTrader(initial_cash=initial_cash)
        else:
            kabu_config = config.get("kabu_api", {})
            self.kabu_client = KabuApiClient(KabuApiConfig(
                host=kabu_config.get("host", "localhost"),
                port=kabu_config.get("port", 18080),
                password=kabu_config.get("password", ""),
            ))

        # Executor
        self.executor = Executor(
            mode=self.mode,
            kabu_client=self.kabu_client,
            paper_trader=self.paper_trader,
            position_manager=self.position_manager,
        )

        # Notifier
        notif_config = config.get("notification", {})
        self.notifier = Notifier(webhook_url=notif_config.get("discord_webhook_url", ""))
        self.daily_report_time = notif_config.get("daily_report_time", "15:35")

        # Symbols
        self.symbols = config.get("symbols", [])

    def run(self) -> None:
        """メインエントリーポイント."""
        self.running = True
        logger.info("Trading bot started (mode=%s, interval=%ds)", self.mode, self.interval)
        logger.info("Monitoring %d symbols", len(self.symbols))

        # シグナルハンドラ設定
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        pre_market_done = False
        post_market_done = False
        last_date = datetime.now().strftime("%Y-%m-%d")

        while self.running:
            try:
                now = datetime.now()
                current_date = now.strftime("%Y-%m-%d")

                # 日付が変わったらフラグリセット
                if current_date != last_date:
                    pre_market_done = False
                    post_market_done = False
                    last_date = current_date

                status = is_trading_hours(now)

                if status == "pre_market" and not pre_market_done:
                    self.pre_market_check()
                    pre_market_done = True

                elif status in ("morning", "afternoon"):
                    self.trading_loop()

                elif status == "post_market" and not post_market_done:
                    self.post_market_report()
                    post_market_done = True

                elif status in ("lunch", "closed"):
                    logger.debug("Market %s, waiting...", status)

                time.sleep(self.interval)

            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                self.notifier.notify_error(f"メインループエラー: {e}")
                time.sleep(self.interval)

        logger.info("Trading bot stopped")

    def _handle_shutdown(self, signum, frame) -> None:
        """グレースフルシャットダウン."""
        logger.info("Shutdown signal received (signal=%d)", signum)
        self.running = False

    def pre_market_check(self) -> bool:
        """取引前ヘルスチェック."""
        logger.info("=== Pre-market health check ===")
        ok = True

        # DB接続チェック
        try:
            self.position_manager.get_open_positions()
            logger.info("DB connection: OK")
        except Exception as e:
            logger.error("DB connection failed: %s", e)
            self.notifier.notify_error(f"DB接続エラー: {e}")
            ok = False

        # API認証チェック（本番モードのみ）
        if self.mode == "live" and self.kabu_client:
            try:
                self.kabu_client.authenticate()
                logger.info("API authentication: OK")
            except Exception as e:
                logger.error("API authentication failed: %s", e)
                self.notifier.notify_error(f"API認証エラー: {e}")
                ok = False

        if ok:
            logger.info("Pre-market check: ALL OK")
        return ok

    def trading_loop(self) -> None:
        """1サイクルの処理: データ取得→レンジ検出→シグナル→執行→通知."""
        logger.info("--- Trading cycle start ---")

        # 古い注文のキャンセル
        self.executor.check_and_cancel_stale_orders(self.stale_order_minutes)

        # ペーパーモード: 約定チェック
        if self.mode == "paper" and self.paper_trader:
            current_prices = {}
            for sym in self.symbols:
                try:
                    df = fetch_ohlcv(sym, period="5d", interval="1d", use_cache=False)
                    if not df.empty:
                        current_prices[sym] = float(df["Close"].iloc[-1])
                except Exception as e:
                    logger.warning("Failed to fetch price for %s: %s", sym, e)

            filled = self.paper_trader.check_fills(current_prices)
            for order in filled:
                self.notifier.notify_fill(order)
                if self.position_manager:
                    self.position_manager.update_order_status(
                        order.order_id, "filled", order.filled_price
                    )

        # データ取得
        data = fetch_multiple(self.symbols, period="6mo", interval="1d")

        if not data:
            logger.warning("No data fetched, skipping cycle")
            return

        # レンジ検出
        rd_config = self.config.get("range_detection", {})
        rankings = detect_range_stocks(
            data,
            lookback_days=rd_config.get("lookback_days", 60),
            bb_width_threshold=rd_config.get("bb_width_threshold", 0.08),
            atr_ratio_threshold=rd_config.get("atr_ratio_threshold", 0.02),
            range_containment_threshold=rd_config.get("range_containment_threshold", 0.70),
        )

        if not rankings:
            logger.info("No range stocks detected")
            return

        # シグナル生成 & 執行
        trading_config = self.config.get("trading", {})
        for info in rankings[:self.max_positions]:
            try:
                sig = generate_signal(
                    symbol=info.symbol,
                    current_price=info.current_price,
                    range_upper=info.range_upper,
                    range_lower=info.range_lower,
                    stop_loss_pct=trading_config.get("stop_loss_pct", 0.03),
                    total_capital=self.config.get("backtest", {}).get("initial_cash", 1_000_000),
                    position_size_pct=trading_config.get("position_size_pct", 0.10),
                )

                if sig.signal != Signal.HOLD:
                    self.notifier.notify_signal(sig)
                    order = self.executor.execute_signal(sig)
                    if order:
                        logger.info("Order placed for %s: %s", info.symbol, order.order_id)

            except Exception as e:
                logger.error("Error processing %s: %s", info.symbol, e, exc_info=True)

        logger.info("--- Trading cycle end ---")

    def post_market_report(self) -> None:
        """取引後の日次レポート生成・送信."""
        logger.info("=== Post-market report ===")
        today = datetime.now().strftime("%Y-%m-%d")

        positions = self.position_manager.get_open_positions()
        realized_pnl = self.position_manager.get_daily_pnl(today)
        unrealized_pnl = 0.0  # ペーパーモードでは簡易計算

        if self.mode == "paper" and self.paper_trader:
            balance = self.paper_trader.get_balance()
            # ペーパートレード履歴をCSV出力
            csv_path = DATA_DIR / "paper_trades.csv"
            self.paper_trader.export_history(str(csv_path))
        else:
            balance = 0.0  # 本番ではAPI経由で取得

        pending = self.position_manager.get_pending_orders()
        total_pnl = realized_pnl + unrealized_pnl

        report = DailyReport(
            date=today,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            positions=positions,
            trades_today=len(pending),
            balance=balance,
        )

        self.notifier.send_daily_report(report)
        self.position_manager.save_daily_report(
            today, total_pnl, realized_pnl, unrealized_pnl, balance, len(pending),
        )
        logger.info("Daily report sent for %s", today)


def main():
    """エントリーポイント."""
    config = load_config()
    setup_logging(config)
    bot = TradingBot(config)
    bot.run()


if __name__ == "__main__":
    main()
