"""Tests for MT5GatewayClient (mocked HTTP, no MetaTrader5)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.mt5_trading.client import MT5Config, OrderResult
from app.services.mt5_trading.gateway_client import (
    MT5GatewayClient,
    MT5GatewayConnectionError,
)


@pytest.fixture(autouse=True)
def gateway_env(monkeypatch):
    monkeypatch.setenv("MT5_GATEWAY_URL", "http://127.0.0.1:5100")
    monkeypatch.setenv("MT5_GATEWAY_API_KEY", "test-key")


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    return resp


@patch("app.services.mt5_trading.gateway_client.requests.request")
def test_connect_success(mock_request):
    mock_request.return_value = _mock_response(200, {"success": True})

    client = MT5GatewayClient(MT5Config(login=1, password="p", server="Demo"))
    assert client.connect() is True
    assert client.connected is True
    mock_request.assert_called_once()
    call_kwargs = mock_request.call_args.kwargs
    assert call_kwargs["json"]["login"] == 1
    assert call_kwargs["headers"]["X-MT5-Gateway-Key"] == "test-key"


@patch("app.services.mt5_trading.gateway_client.requests.request")
def test_connect_unauthorized(mock_request):
    mock_request.return_value = _mock_response(401, {"error": "Unauthorized"})

    client = MT5GatewayClient(MT5Config(login=1, password="p", server="Demo"))
    with pytest.raises(MT5GatewayConnectionError, match="unauthorized"):
        client.connect()


@patch("app.services.mt5_trading.gateway_client.requests.request")
def test_place_market_order_success(mock_request):
    mock_request.return_value = _mock_response(
        200,
        {
            "success": True,
            "order_id": 99,
            "deal_id": 1,
            "filled": 0.1,
            "price": 1.1,
            "status": "filled",
            "message": "ok",
        },
    )

    client = MT5GatewayClient(MT5Config())
    client._connected = True
    result = client.place_market_order("EURUSD", "buy", 0.1)
    assert isinstance(result, OrderResult)
    assert result.success is True
    assert result.order_id == 99


@patch("app.services.mt5_trading.gateway_client.requests.request")
def test_get_connection_status(mock_request):
    mock_request.return_value = _mock_response(200, {"connected": True, "server": "Demo"})

    client = MT5GatewayClient(MT5Config())
    status = client.get_connection_status()
    assert status["connected"] is True
