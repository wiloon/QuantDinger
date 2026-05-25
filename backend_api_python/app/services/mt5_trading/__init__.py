"""
MetaTrader 5 Trading Module

Provides forex trading capabilities via MT5 terminal.
Requires Windows platform and MetaTrader5 Python library.
"""

from app.services.mt5_trading.client import MT5Client, MT5Config, OrderResult
from app.services.mt5_trading.symbols import normalize_symbol, parse_symbol
from app.services.mt5_trading.protocol import MT5BrokerClient, is_mt5_broker_client
from app.services.mt5_trading.broker_client import (
    create_mt5_broker_client,
    get_mt5_gateway_url,
    use_mt5_gateway,
)

__all__ = [
    "MT5Client",
    "MT5Config",
    "OrderResult",
    "MT5BrokerClient",
    "is_mt5_broker_client",
    "create_mt5_broker_client",
    "get_mt5_gateway_url",
    "use_mt5_gateway",
    "normalize_symbol",
    "parse_symbol",
]
