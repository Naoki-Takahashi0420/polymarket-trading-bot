"""Discord Webhook 通知モジュール."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
    date: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    positions: list
    trades_today: int
    balance: float


class Notifier:
    """Discord Webhook でリアルタイム通知を送信する."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")

    def _send(self, payload: dict) -> bool:
        """Webhookにペイロードを送信する."""
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return False

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error("Failed to send Discord notification: %s", e)
            return False

    def _build_embed(self, title: str, description: str, color: int, fields: list[dict] = None) -> dict:
        """Embed形式のペイロードを構築する."""
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now().isoformat(),
        }
        if fields:
            embed["fields"] = fields
        return {"embeds": [embed]}

    def notify_signal(self, signal) -> bool:
        """シグナル通知を送信する."""
        color = 0x00FF00 if signal.signal.value == "BUY" else 0xFF0000 if signal.signal.value == "SELL" else 0x808080
        action = signal.signal.value

        fields = [
            {"name": "銘柄", "value": signal.symbol, "inline": True},
            {"name": "アクション", "value": action, "inline": True},
            {"name": "現在価格", "value": f"¥{signal.current_price:,.1f}", "inline": True},
            {"name": "レンジ上限", "value": f"¥{signal.range_upper:,.1f}", "inline": True},
            {"name": "レンジ下限", "value": f"¥{signal.range_lower:,.1f}", "inline": True},
            {"name": "株数", "value": str(signal.position_size), "inline": True},
        ]

        payload = self._build_embed(
            title=f"📊 シグナル: {action} {signal.symbol}",
            description=f"{signal.symbol} の{action}シグナルを検出",
            color=color,
            fields=fields,
        )
        return self._send(payload)

    def notify_fill(self, order) -> bool:
        """約定通知を送信する."""
        fields = [
            {"name": "銘柄", "value": order.symbol, "inline": True},
            {"name": "売買", "value": order.side.upper(), "inline": True},
            {"name": "約定価格", "value": f"¥{order.filled_price:,.1f}", "inline": True},
            {"name": "数量", "value": str(order.quantity), "inline": True},
            {"name": "注文ID", "value": order.order_id, "inline": True},
        ]

        payload = self._build_embed(
            title=f"✅ 約定: {order.side.upper()} {order.symbol}",
            description=f"{order.symbol} {order.side.upper()} x{order.quantity} @ ¥{order.filled_price:,.1f}",
            color=0x00BFFF,
            fields=fields,
        )
        return self._send(payload)

    def notify_error(self, error: str) -> bool:
        """エラー通知を送信する."""
        payload = self._build_embed(
            title="🚨 エラー発生",
            description=error,
            color=0xFF0000,
        )
        return self._send(payload)

    def send_daily_report(self, report: DailyReport) -> bool:
        """日次レポートを送信する."""
        pnl_color = 0x00FF00 if report.total_pnl >= 0 else 0xFF0000
        pnl_sign = "+" if report.total_pnl >= 0 else ""

        positions_text = "なし"
        if report.positions:
            lines = []
            for p in report.positions:
                lines.append(f"• {p.symbol} {p.side} x{p.quantity} @ ¥{p.entry_price:,.1f}")
            positions_text = "\n".join(lines)

        fields = [
            {"name": "合計損益", "value": f"{pnl_sign}¥{report.total_pnl:,.0f}", "inline": True},
            {"name": "実現損益", "value": f"¥{report.realized_pnl:,.0f}", "inline": True},
            {"name": "含み損益", "value": f"¥{report.unrealized_pnl:,.0f}", "inline": True},
            {"name": "本日取引数", "value": str(report.trades_today), "inline": True},
            {"name": "残高", "value": f"¥{report.balance:,.0f}", "inline": True},
            {"name": "保有ポジション", "value": positions_text, "inline": False},
        ]

        payload = self._build_embed(
            title=f"📈 日次レポート ({report.date})",
            description=f"本日の損益: {pnl_sign}¥{report.total_pnl:,.0f}",
            color=pnl_color,
            fields=fields,
        )
        return self._send(payload)
