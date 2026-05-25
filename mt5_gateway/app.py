"""
Flask app for the MT5 thin gateway.
"""

import os
from functools import wraps

from flask import Flask, jsonify, request

from app.utils.logger import get_logger
from mt5_gateway.access_log import register_access_logging
from mt5_gateway.session import (
    connect_from_body,
    get_session_client,
    session_lock,
    shutdown_session,
)

logger = get_logger(__name__)

GATEWAY_KEY_HEADER = "X-MT5-Gateway-Key"


def create_app() -> Flask:
    app = Flask(__name__)
    register_access_logging(app)

    @app.before_request
    def _auth_v1():
        if not request.path.startswith("/v1/"):
            return None
        expected = (os.environ.get("MT5_GATEWAY_API_KEY") or "").strip()
        if not expected:
            return jsonify({"error": "MT5_GATEWAY_API_KEY not configured"}), 500
        provided = (request.headers.get(GATEWAY_KEY_HEADER) or "").strip()
        if provided != expected:
            return jsonify({"error": "Unauthorized"}), 401
        return None

    def with_mt5_lock(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            with session_lock():
                return fn(*args, **kwargs)

        return wrapper

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/v1/status")
    @with_mt5_lock
    def v1_status():
        client = get_session_client()
        return jsonify(client.get_connection_status())

    @app.post("/v1/connect")
    @with_mt5_lock
    def v1_connect():
        data = request.get_json(silent=True) or {}
        login = data.get("login") or data.get("mt5_login")
        server = data.get("server") or data.get("mt5_server")
        ok, payload = connect_from_body(data)
        if ok:
            logger.info("MT5 session connected login=%s server=%s", login, server)
        else:
            logger.warning(
                "MT5 session connect failed login=%s server=%s: %s",
                login,
                server,
                payload.get("error"),
            )
        status = 200 if ok else 400
        return jsonify(payload), status

    @app.post("/v1/disconnect")
    @with_mt5_lock
    def v1_disconnect():
        client = get_session_client()
        client.disconnect()
        return jsonify({"success": True, "message": "Disconnected"})

    @app.get("/v1/account")
    @with_mt5_lock
    def v1_account():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        return jsonify(client.get_account_info())

    @app.get("/v1/positions")
    @with_mt5_lock
    def v1_positions():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        symbol = request.args.get("symbol")
        positions = client.get_positions(symbol=symbol)
        return jsonify({"success": True, "positions": positions})

    @app.get("/v1/orders")
    @with_mt5_lock
    def v1_orders():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        symbol = request.args.get("symbol")
        orders = client.get_orders(symbol=symbol)
        return jsonify({"success": True, "orders": orders})

    @app.get("/v1/symbols")
    @with_mt5_lock
    def v1_symbols():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        group = request.args.get("group", "*")
        symbols = client.get_symbols(group=group)
        return jsonify({"success": True, "symbols": symbols})

    @app.get("/v1/quote")
    @with_mt5_lock
    def v1_quote():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        symbol = request.args.get("symbol")
        if not symbol:
            return jsonify({"success": False, "error": "Missing symbol parameter"}), 400
        return jsonify(client.get_quote(symbol))

    @app.post("/v1/order")
    @with_mt5_lock
    def v1_order():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        data = request.get_json(silent=True) or {}
        symbol = data.get("symbol")
        side = data.get("side")
        volume = data.get("volume") or data.get("quantity")
        order_type = (data.get("orderType") or "market").lower()
        price = data.get("price")
        comment = data.get("comment", "QuantDinger")

        if not symbol or not side or volume is None:
            return jsonify({
                "success": False,
                "error": "Missing required fields: symbol, side, volume",
            }), 400

        if order_type == "limit":
            if price is None:
                return jsonify({"success": False, "error": "Limit order requires price"}), 400
            result = client.place_limit_order(
                symbol=symbol,
                side=side,
                volume=float(volume),
                price=float(price),
                comment=comment,
            )
        else:
            result = client.place_market_order(
                symbol=symbol,
                side=side,
                volume=float(volume),
                comment=comment,
            )

        if result.success:
            return jsonify({
                "success": True,
                "order_id": result.order_id,
                "deal_id": result.deal_id,
                "filled": result.filled,
                "price": result.price,
                "status": result.status,
                "message": result.message,
            })
        return jsonify({"success": False, "error": result.message}), 400

    @app.post("/v1/close")
    @with_mt5_lock
    def v1_close():
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        data = request.get_json(silent=True) or {}
        ticket = data.get("ticket")
        volume = data.get("volume")
        if not ticket:
            return jsonify({"success": False, "error": "Missing required field: ticket"}), 400

        result = client.close_position(
            ticket=int(ticket),
            volume=float(volume) if volume is not None else None,
        )
        if result.success:
            return jsonify({
                "success": True,
                "order_id": result.order_id,
                "deal_id": result.deal_id,
                "filled": result.filled,
                "price": result.price,
                "message": result.message,
            })
        return jsonify({"success": False, "error": result.message}), 400

    @app.delete("/v1/order/<int:ticket>")
    @with_mt5_lock
    def v1_cancel_order(ticket: int):
        client = get_session_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400
        if client.cancel_order(ticket):
            return jsonify({"success": True, "message": f"Order {ticket} cancelled"})
        return jsonify({"success": False, "error": "Failed to cancel order"}), 400

    return app


def register_shutdown(_app: Flask) -> None:
    import atexit
    import signal
    import sys

    def _cleanup(*_args):
        logger.info("MT5 gateway shutting down, disconnecting MT5...")
        shutdown_session()

    def _handle_signal(signum, frame):
        _cleanup()
        raise SystemExit(0)

    atexit.register(_cleanup)
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is not None:
            try:
                signal.signal(sig, _handle_signal)
            except Exception:
                pass
