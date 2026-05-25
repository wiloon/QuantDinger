"""
HTTP client for the Windows MT5 thin gateway (no MetaTrader5 import).
"""

import os
from typing import Any, Dict, List, Optional

import requests

from app.services.mt5_trading.broker_client import get_mt5_gateway_url
from app.services.mt5_trading.client import MT5Config, OrderResult
from app.utils.logger import get_logger

logger = get_logger(__name__)

GATEWAY_KEY_HEADER = "X-MT5-Gateway-Key"


class MT5GatewayError(Exception):
    """Base error for gateway HTTP failures."""


class MT5GatewayConnectionError(MT5GatewayError, ConnectionError):
    """Gateway unreachable or connect failed."""


def _gateway_timeout() -> float:
    try:
        return float(os.environ.get("MT5_GATEWAY_TIMEOUT_SEC") or "30")
    except (TypeError, ValueError):
        return 30.0


class MT5GatewayClient:
    """MT5BrokerClient implementation that proxies to mt5_gateway over HTTP."""

    def __init__(self, config: Optional[MT5Config] = None):
        self.config = config or MT5Config()
        self._connected = False
        self._base_url = get_mt5_gateway_url()
        if not self._base_url:
            raise MT5GatewayConnectionError(
                "MT5_GATEWAY_URL is not set but MT5GatewayClient was constructed"
            )

    @property
    def connected(self) -> bool:
        return self._connected

    def _api_key(self) -> str:
        return (os.environ.get("MT5_GATEWAY_API_KEY") or "").strip()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self._api_key()
        if key:
            headers[GATEWAY_KEY_HEADER] = key
        return headers

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        try:
            resp = requests.request(
                method,
                self._url(path),
                headers=self._headers(),
                json=json,
                params=params,
                timeout=_gateway_timeout(),
            )
        except requests.RequestException as e:
            raise MT5GatewayConnectionError(f"mt5_gateway_unreachable: {e}") from e
        return resp

    def _check_v1_response(self, resp: requests.Response) -> Dict[str, Any]:
        if resp.status_code == 401:
            raise MT5GatewayConnectionError("mt5_gateway_unauthorized: invalid or missing API key")
        try:
            data = resp.json()
        except ValueError as e:
            raise MT5GatewayError(f"mt5_gateway_invalid_json: {resp.text[:200]}") from e
        if resp.status_code >= 400:
            err = data.get("error") or data.get("message") or resp.text
            raise MT5GatewayError(f"mt5_gateway_http_{resp.status_code}: {err}")
        return data

    def connect(self) -> bool:
        body = {
            "login": self.config.login,
            "password": self.config.password,
            "server": self.config.server,
            "terminal_path": self.config.terminal_path or "",
        }
        try:
            resp = self._request("POST", "/v1/connect", json=body)
            data = self._check_v1_response(resp)
            self._connected = bool(data.get("success"))
            if not self._connected:
                logger.error("MT5 gateway connect failed: %s", data.get("error"))
            return self._connected
        except MT5GatewayConnectionError:
            self._connected = False
            raise
        except MT5GatewayError as e:
            logger.error("MT5 gateway connect error: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        try:
            self._request("POST", "/v1/disconnect")
        except Exception as e:
            logger.warning("MT5 gateway disconnect: %s", e)
        finally:
            self._connected = False

    def get_connection_status(self) -> Dict[str, Any]:
        try:
            resp = self._request("GET", "/v1/status")
            return self._check_v1_response(resp)
        except MT5GatewayError as e:
            return {"connected": False, "error": str(e)}

    def get_account_info(self) -> Dict[str, Any]:
        resp = self._request("GET", "/v1/account")
        return self._check_v1_response(resp)

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"symbol": symbol} if symbol else None
        resp = self._request("GET", "/v1/positions", params=params)
        data = self._check_v1_response(resp)
        return data.get("positions") or []

    def get_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"symbol": symbol} if symbol else None
        resp = self._request("GET", "/v1/orders", params=params)
        data = self._check_v1_response(resp)
        return data.get("orders") or []

    def get_symbols(self, group: str = "*") -> List[Dict[str, Any]]:
        resp = self._request("GET", "/v1/symbols", params={"group": group})
        data = self._check_v1_response(resp)
        return data.get("symbols") or []

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        resp = self._request("GET", "/v1/quote", params={"symbol": symbol})
        return self._check_v1_response(resp)

    def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        deviation: int = 20,
        comment: str = "QuantDinger",
    ) -> OrderResult:
        return self._place_order(
            symbol=symbol,
            side=side,
            volume=volume,
            order_type="market",
            comment=comment,
            deviation=deviation,
        )

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        comment: str = "QuantDinger",
    ) -> OrderResult:
        return self._place_order(
            symbol=symbol,
            side=side,
            volume=volume,
            order_type="limit",
            price=price,
            comment=comment,
        )

    def _place_order(
        self,
        *,
        symbol: str,
        side: str,
        volume: float,
        order_type: str,
        comment: str,
        price: Optional[float] = None,
        deviation: int = 20,
    ) -> OrderResult:
        body: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "orderType": order_type,
            "comment": comment,
            "deviation": deviation,
        }
        if price is not None:
            body["price"] = price
        try:
            resp = self._request("POST", "/v1/order", json=body)
            data = self._check_v1_response(resp)
            if data.get("success"):
                return OrderResult(
                    success=True,
                    order_id=int(data.get("order_id") or 0),
                    deal_id=int(data.get("deal_id") or 0),
                    filled=float(data.get("filled") or 0.0),
                    price=float(data.get("price") or 0.0),
                    status=str(data.get("status") or ""),
                    message=str(data.get("message") or ""),
                    raw=data,
                )
            return OrderResult(
                success=False,
                message=str(data.get("error") or data.get("message") or "mt5_gateway_order_failed"),
                raw=data,
            )
        except MT5GatewayConnectionError as e:
            return OrderResult(success=False, message=str(e))
        except MT5GatewayError as e:
            return OrderResult(success=False, message=str(e))

    def close_position(
        self,
        ticket: int,
        volume: Optional[float] = None,
        deviation: int = 20,
        comment: str = "QuantDinger close",
    ) -> OrderResult:
        body: Dict[str, Any] = {"ticket": ticket, "comment": comment, "deviation": deviation}
        if volume is not None:
            body["volume"] = volume
        try:
            resp = self._request("POST", "/v1/close", json=body)
            data = self._check_v1_response(resp)
            if data.get("success"):
                return OrderResult(
                    success=True,
                    order_id=int(data.get("order_id") or 0),
                    deal_id=int(data.get("deal_id") or 0),
                    filled=float(data.get("filled") or 0.0),
                    price=float(data.get("price") or 0.0),
                    message=str(data.get("message") or ""),
                    raw=data,
                )
            return OrderResult(
                success=False,
                message=str(data.get("error") or "mt5_gateway_close_failed"),
                raw=data,
            )
        except (MT5GatewayConnectionError, MT5GatewayError) as e:
            return OrderResult(success=False, message=str(e))

    def cancel_order(self, ticket: int) -> bool:
        try:
            resp = self._request("DELETE", f"/v1/order/{ticket}")
            data = self._check_v1_response(resp)
            return bool(data.get("success"))
        except MT5GatewayError:
            return False
