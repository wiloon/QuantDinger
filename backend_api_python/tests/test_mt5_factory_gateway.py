"""Factory returns MT5GatewayClient when MT5_GATEWAY_URL is set."""

from unittest.mock import patch

import pytest

from app.services.mt5_trading.client import MT5Config


@pytest.fixture(autouse=True)
def gateway_env(monkeypatch):
    monkeypatch.setenv("MT5_GATEWAY_URL", "http://127.0.0.1:5100")
    monkeypatch.setenv("MT5_GATEWAY_API_KEY", "test-key")


def test_create_mt5_broker_client_returns_gateway():
    from app.services.mt5_trading.broker_client import create_mt5_broker_client
    from app.services.mt5_trading.gateway_client import MT5GatewayClient

    client = create_mt5_broker_client(MT5Config(login=1, password="p", server="S"))
    assert isinstance(client, MT5GatewayClient)


@patch("app.services.mt5_trading.gateway_client.requests.request")
def test_create_mt5_client_connects_via_gateway(mock_request, monkeypatch):
    from app.services.live_trading.factory import create_mt5_client

    mock_resp = type("R", (), {})()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"success": True}
    mock_resp.text = ""
    mock_request.return_value = mock_resp

    cfg = {
        "market_category": "Forex",
        "mt5_login": 123,
        "mt5_password": "secret",
        "mt5_server": "Demo",
    }
    client = create_mt5_client(cfg)
    from app.services.mt5_trading.gateway_client import MT5GatewayClient

    assert isinstance(client, MT5GatewayClient)
    assert client.connected is True


def test_use_mt5_gateway_false_when_unset(monkeypatch):
    monkeypatch.delenv("MT5_GATEWAY_URL", raising=False)
    from app.services.mt5_trading.broker_client import use_mt5_gateway

    assert use_mt5_gateway() is False
