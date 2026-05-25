"""
MT5 broker client protocol for local MT5Client and remote MT5GatewayClient.
"""

from typing import Any, Optional, Protocol, runtime_checkable, List, Dict

from app.services.mt5_trading.client import MT5Config, OrderResult


@runtime_checkable
class MT5BrokerClient(Protocol):
    """Shared interface for in-process and HTTP-backed MT5 trading."""

    config: MT5Config

    @property
    def connected(self) -> bool: ...

    def connect(self) -> bool: ...

    def disconnect(self) -> None: ...

    def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        deviation: int = 20,
        comment: str = "QuantDinger",
    ) -> OrderResult: ...

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        comment: str = "QuantDinger",
    ) -> OrderResult: ...

    def close_position(
        self,
        ticket: int,
        volume: Optional[float] = None,
        deviation: int = 20,
        comment: str = "QuantDinger close",
    ) -> OrderResult: ...

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]: ...

    def get_account_info(self) -> Dict[str, Any]: ...

    def get_connection_status(self) -> Dict[str, Any]: ...

    def get_quote(self, symbol: str) -> Dict[str, Any]: ...

    def cancel_order(self, ticket: int) -> bool: ...


def is_mt5_broker_client(client: Any) -> bool:
    """True if client is a local MT5Client or MT5GatewayClient."""
    if client is None:
        return False
    try:
        from app.services.mt5_trading.gateway_client import MT5GatewayClient

        if isinstance(client, MT5GatewayClient):
            return True
    except ImportError:
        pass
    try:
        from app.services.mt5_trading.client import MT5Client

        if isinstance(client, MT5Client):
            return True
    except ImportError:
        pass
    return isinstance(client, MT5BrokerClient)
