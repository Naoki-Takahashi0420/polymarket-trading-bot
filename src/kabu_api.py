"""kabu Station API クライアントモジュール."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from src.position_manager import Order

logger = logging.getLogger(__name__)

# kabu Station API の exchange コード
EXCHANGE_TSE = 1  # 東証


@dataclass
class KabuApiConfig:
    host: str = "localhost"
    port: int = 18081  # デモ: 18081, 本番: 18080
    password: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/kabusapi"


class KabuApiClient:
    """kabu Station REST API のラッパー."""

    def __init__(self, config: KabuApiConfig):
        self.config = config
        self.token: Optional[str] = None
        self._last_request_time: float = 0
        self._min_interval: float = 0.1  # 1秒10リクエスト制限

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-API-KEY"] = self.token
        return headers

    def _rate_limit(self) -> None:
        """レート制限を遵守する."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(
        self, method: str, path: str, json_data: Optional[dict] = None,
        max_retries: int = 3,
    ) -> dict:
        """リトライ付きHTTPリクエスト."""
        url = f"{self.config.base_url}{path}"

        for attempt in range(max_retries):
            try:
                self._rate_limit()
                resp = requests.request(
                    method, url, json=json_data, headers=self._headers(), timeout=10,
                )
                resp.raise_for_status()
                if resp.text:
                    return resp.json()
                return {}
            except requests.exceptions.RequestException as e:
                logger.warning("API request failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    backoff = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(backoff)
                else:
                    raise

    def authenticate(self, password: Optional[str] = None) -> str:
        """POST /token でトークンを取得する."""
        pw = password or self.config.password
        data = {"APIPassword": pw}
        result = self._request("POST", "/token", json_data=data)
        self.token = result.get("Token", "")
        logger.info("Authenticated with kabu Station API")
        return self.token

    def get_board(self, symbol: str, exchange: int = EXCHANGE_TSE) -> dict:
        """時価情報を取得する."""
        path = f"/board/{symbol}@{exchange}"
        return self._request("GET", path)

    def place_order(self, order: Order) -> str:
        """注文を発注し、注文IDを返す."""
        # kabu Station API の注文パラメータに変換
        side_map = {"buy": "2", "sell": "1"}
        trade_type_map = {
            "spot": "2" if order.side == "buy" else "1",  # 現物買い=2, 現物売り=1 (CashMargin)
        }

        data = {
            "Password": self.config.password,
            "Symbol": order.symbol.replace(".T", ""),
            "Exchange": EXCHANGE_TSE,
            "SecurityType": 1,  # 株式
            "Side": side_map.get(order.side, "2"),
            "CashMargin": 1,  # 現物
            "DelivType": 2 if order.side == "buy" else 0,  # 買い: お預り金, 売り: 指定なし
            "AccountType": 4,  # 特定
            "Qty": order.quantity,
            "FrontOrderType": 20,  # 指値
            "Price": order.price,
            "ExpireDay": 0,  # 当日
        }
        result = self._request("POST", "/sendorder", json_data=data)
        order_id = result.get("OrderId", "")
        logger.info("Order placed: %s %s %s @ %.1f (ID: %s)",
                     order.side, order.symbol, order.quantity, order.price, order_id)
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        """注文を取り消す."""
        data = {
            "OrderId": order_id,
            "Password": self.config.password,
        }
        try:
            self._request("PUT", "/cancelorder", json_data=data)
            logger.info("Order cancelled: %s", order_id)
            return True
        except requests.exceptions.RequestException:
            logger.error("Failed to cancel order: %s", order_id)
            return False

    def get_orders(self) -> list[dict]:
        """注文一覧を取得する."""
        return self._request("GET", "/orders") or []

    def get_positions(self) -> list[dict]:
        """ポジション一覧を取得する."""
        return self._request("GET", "/positions") or []
