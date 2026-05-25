"""mt5.py routes use gateway client when MT5_GATEWAY_URL is set."""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.auth import generate_token


@pytest.fixture(autouse=True)
def gateway_env(monkeypatch):
    monkeypatch.setenv("MT5_GATEWAY_URL", "http://127.0.0.1:5100")
    monkeypatch.setenv("MT5_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("ALLOW_LOCAL_DESKTOP_BROKERS", "true")


@pytest.fixture(autouse=True)
def bypass_token_version_db():
    with patch("app.utils.auth._verify_token_version", return_value=True):
        yield


@pytest.fixture
def auth_headers():
    token = generate_token(user_id=1, username="testuser", role="admin")
    return {"Authorization": f"Bearer {token}"}


@patch("app.routes.mt5.create_mt5_broker_client")
def test_connect_uses_broker_factory(mock_create, client, auth_headers):
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    mock_client.get_account_info.return_value = {"success": True, "balance": 1000}
    mock_create.return_value = mock_client

    resp = client.post(
        "/api/mt5/connect",
        json={"login": 1, "password": "p", "server": "Demo"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    mock_create.assert_called_once()


@patch("app.routes.mt5._get_client")
def test_positions_via_client(mock_get_client, client, auth_headers):
    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.get_positions.return_value = [{"symbol": "EURUSD", "volume": 0.1}]
    mock_get_client.return_value = mock_client

    resp = client.get("/api/mt5/positions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["positions"]) == 1
