"""J-Quants API クライアント（東証公式データ）."""

from __future__ import annotations

import time

import requests


class JQuantsClient:
    """J-Quants API v1 クライアント.

    無料プラン制約:
        - 過去2年分データ
        - 1日あたり約12回の APIコール制限
    """

    BASE_URL = "https://api.jquants.com/v1"

    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self.id_token: str | None = None
        self.token_expires_at: float = 0

    def _ensure_token(self) -> None:
        """IDトークンを取得/更新する."""
        if time.time() < self.token_expires_at - 60:
            return
        resp = requests.post(
            f"{self.BASE_URL}/token/auth_refresh",
            params={"refreshtoken": self.refresh_token},
            timeout=30,
        )
        resp.raise_for_status()
        self.id_token = resp.json()["idToken"]
        self.token_expires_at = time.time() + 3600  # 1時間有効

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self.id_token}"}
        resp = requests.get(
            f"{self.BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_prices_daily(
        self,
        code: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list:
        """日足株価（四本値・出来高）を取得する.

        Args:
            code: 銘柄コード（例: "7203"）
            date_from: 開始日 "YYYYMMDD"
            date_to: 終了日 "YYYYMMDD"

        Returns:
            daily_quotes のリスト
        """
        params: dict = {"code": code}
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        return self._get("/prices/daily_quotes", params).get("daily_quotes", [])

    def get_financial_statements(self, code: str) -> list:
        """財務情報（PER, PBR, ROE 等）を取得する.

        Args:
            code: 銘柄コード

        Returns:
            statements のリスト
        """
        return self._get("/fins/statements", {"code": code}).get("statements", [])

    def get_margin_trading(self, code: str) -> list:
        """信用残（貸借倍率）を取得する.

        Args:
            code: 銘柄コード

        Returns:
            weekly_margin_interest のリスト
        """
        return self._get(
            "/markets/weekly_margin_interest", {"code": code}
        ).get("weekly_margin_interest", [])

    def get_stock_info(self, code: str) -> dict:
        """銘柄情報（業種等）を取得する.

        Args:
            code: 銘柄コード

        Returns:
            info の最初の要素（なければ空 dict）
        """
        result = self._get("/listed/info", {"code": code})
        info_list = result.get("info", [])
        return info_list[0] if info_list else {}
