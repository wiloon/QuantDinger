"""
Sanitized HTTP access logging for mt5_gateway.

Logs method, path, status, client IP, and a small allowlist of query/body fields.
Never logs headers, API keys, or credentials (password, etc.).
"""

import logging
import os

from flask import Flask, Response, request

_ACCESS_LOGGER = "mt5_gateway.access"

_SENSITIVE_BODY_KEYS = frozenset({
    "password",
    "mt5_password",
    "api_key",
    "secret",
    "token",
})
_SAFE_QUERY_KEYS = ("symbol", "group", "ticket")
_SAFE_BODY_KEYS = (
    "symbol",
    "side",
    "volume",
    "quantity",
    "orderType",
    "order_type",
    "price",
    "ticket",
    "login",
    "mt5_login",
    "server",
    "mt5_server",
)


def access_logger() -> logging.Logger:
    return logging.getLogger(_ACCESS_LOGGER)


def _log_health_at_info() -> bool:
    raw = os.environ.get("MT5_GATEWAY_LOG_HEALTH", "").strip().lower()
    return raw in ("1", "true", "yes")


def _safe_extra() -> str:
    parts: list[str] = []
    for key in _SAFE_QUERY_KEYS:
        val = request.args.get(key)
        if val is not None and str(val).strip():
            parts.append(f"{key}={val}")

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            for key in _SAFE_BODY_KEYS:
                if key in _SENSITIVE_BODY_KEYS:
                    continue
                val = data.get(key)
                if val is not None and str(val).strip() != "":
                    parts.append(f"{key}={val}")

    return (" " + " ".join(parts)) if parts else ""


def _level_for_response(status: int, path: str) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    if path == "/health" and not _log_health_at_info():
        return logging.DEBUG
    return logging.INFO


def log_request(response: Response) -> Response:
    path = request.path or "/"
    status = response.status_code
    level = _level_for_response(status, path)
    access_logger().log(
        level,
        "%s %s%s -> %s from %s",
        request.method,
        path,
        _safe_extra(),
        status,
        request.remote_addr or "-",
    )
    return response


def register_access_logging(app: Flask) -> None:
    @app.after_request
    def _log_access(response: Response):
        return log_request(response)
