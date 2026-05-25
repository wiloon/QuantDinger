"""mt5_gateway Flask routes (no MetaTrader5)."""

import logging
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api_python"))

from mt5_gateway.app import create_app  # noqa: E402


@pytest.fixture
def gateway_app(monkeypatch):
    monkeypatch.setenv("MT5_GATEWAY_API_KEY", "gw-test-key")
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def gw_client(gateway_app):
    return gateway_app.test_client()


def test_health_no_auth(gw_client):
    resp = gw_client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_v1_missing_key_401(gw_client):
    resp = gw_client.get("/v1/status")
    assert resp.status_code == 401


def test_v1_wrong_key_401(gw_client):
    resp = gw_client.get("/v1/status", headers={"X-MT5-Gateway-Key": "wrong"})
    assert resp.status_code == 401


@patch("mt5_gateway.session.get_session_client")
def test_v1_status_with_key(mock_get_client, gw_client):
    mock_client = type("C", (), {})()
    mock_client.get_connection_status = lambda: {"connected": False}
    mock_get_client.return_value = mock_client

    resp = gw_client.get("/v1/status", headers={"X-MT5-Gateway-Key": "gw-test-key"})
    assert resp.status_code == 200
    assert resp.get_json()["connected"] is False


def test_concurrent_connect_serialized(gateway_app, gw_client, monkeypatch):
    """AC-12: overlapping /v1/connect handlers do not run connect body concurrently."""
    monkeypatch.setenv("MT5_GATEWAY_API_KEY", "gw-test-key")
    active = []
    peak = []

    def slow_connect(data):
        active.append(1)
        peak.append(len(active))
        time.sleep(0.15)
        active.pop()
        return False, {"success": False, "error": "mock"}

    headers = {"X-MT5-Gateway-Key": "gw-test-key", "Content-Type": "application/json"}
    body = {"login": 1, "password": "p", "server": "Demo"}

    with patch("mt5_gateway.app.connect_from_body", side_effect=slow_connect):
        t1 = threading.Thread(
            target=lambda: gw_client.post("/v1/connect", json=body, headers=headers)
        )
        t2 = threading.Thread(
            target=lambda: gw_client.post("/v1/connect", json=body, headers=headers)
        )
        t1.start()
        time.sleep(0.02)
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

    assert max(peak) == 1


def test_access_log_omits_secrets(gw_client, caplog):
    caplog.set_level(logging.DEBUG, logger="mt5_gateway.access")
    secret = "super-secret-password"
    gw_client.post(
        "/v1/connect",
        json={"login": 12345, "password": secret, "server": "Demo-Server"},
        headers={"X-MT5-Gateway-Key": "gw-test-key", "Content-Type": "application/json"},
    )
    text = caplog.text
    assert secret not in text
    assert "gw-test-key" not in text
    assert "login=12345" in text
    assert "server=Demo-Server" in text


def test_health_access_log_debug_by_default(gw_client, caplog):
    caplog.set_level(logging.DEBUG, logger="mt5_gateway.access")
    gw_client.get("/health")
    assert "GET /health -> 200" in caplog.text


def test_health_access_log_info_when_enabled(gw_client, monkeypatch, caplog):
    monkeypatch.setenv("MT5_GATEWAY_LOG_HEALTH", "true")
    caplog.set_level(logging.INFO, logger="mt5_gateway.access")
    gw_client.get("/health")
    assert "GET /health -> 200" in caplog.text
