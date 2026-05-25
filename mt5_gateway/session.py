"""
Process-wide MT5Client singleton and lock for the thin gateway (G-09, G-10).
"""

import threading
from typing import Optional

from app.services.mt5_trading.client import MT5Client, MT5Config

_session_lock = threading.Lock()
_client: Optional[MT5Client] = None


def get_session_client() -> MT5Client:
    """Return the process singleton MT5Client (caller must hold _session_lock for mutations)."""
    global _client
    if _client is None:
        _client = MT5Client()
    return _client


def session_lock() -> threading.Lock:
    return _session_lock


def shutdown_session() -> None:
    """Disconnect and clear singleton (G-07)."""
    global _client
    with _session_lock:
        if _client is not None:
            try:
                _client.disconnect()
            except Exception:
                pass
            _client = None


def connect_from_body(data: dict) -> tuple[bool, dict]:
    """
    Disconnect-if-connected then connect with new credentials (mirrors mt5.py).
    Must be called with session lock held.
    """
    login = data.get("login") or data.get("mt5_login")
    password = data.get("password") or data.get("mt5_password")
    server = data.get("server") or data.get("mt5_server")
    terminal_path = data.get("terminal_path") or data.get("mt5_terminal_path") or ""

    if not login or not password or not server:
        return False, {
            "success": False,
            "error": "Missing required fields: login, password, server",
        }

    config = MT5Config(
        login=int(login),
        password=str(password),
        server=str(server),
        terminal_path=str(terminal_path),
    )

    client = get_session_client()
    if client.connected:
        try:
            client.disconnect()
        except Exception:
            pass

    client.config = config
    if client.connect():
        return True, {
            "success": True,
            "message": "Connected to MT5",
            "account": client.get_account_info(),
        }
    return False, {
        "success": False,
        "error": "Failed to connect to MT5. Check credentials and ensure terminal is running.",
    }
