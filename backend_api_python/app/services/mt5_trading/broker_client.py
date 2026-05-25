"""
Shared MT5 broker client factory for core backend and UI routes.
"""

import os
from typing import Optional

from app.services.mt5_trading.client import MT5Config


def get_mt5_gateway_url() -> str:
    return (os.environ.get("MT5_GATEWAY_URL") or "").strip().rstrip("/")


def use_mt5_gateway() -> bool:
    return bool(get_mt5_gateway_url())


def create_mt5_broker_client(config: Optional[MT5Config] = None):
    """
    Return MT5GatewayClient when MT5_GATEWAY_URL is set, else in-process MT5Client.
    Does not call connect().
    """
    cfg = config or MT5Config()
    if use_mt5_gateway():
        from app.services.mt5_trading.gateway_client import MT5GatewayClient

        return MT5GatewayClient(cfg)
    from app.services.mt5_trading.client import MT5Client

    return MT5Client(cfg)
