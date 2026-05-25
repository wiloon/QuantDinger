"""
MetaTrader 5 Trading API Routes

Provides REST API for MT5 trading operations.
Uses in-process MT5Client or MT5GatewayClient when MT5_GATEWAY_URL is set.
"""

from flask import jsonify, request
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.utils.auth import login_required

from app.utils.logger import get_logger
from app.utils.local_brokers import (
    local_desktop_brokers_allowed,
    desktop_broker_cloud_reject_message,
)
from app.services.mt5_trading.client import MT5Config
from app.services.mt5_trading.broker_client import (
    create_mt5_broker_client,
    use_mt5_gateway,
)

logger = get_logger(__name__)

mt5_blp = Blueprint("mt5", __name__)

_ui_client = None


def _get_client():
    """Module-level broker client for UI session (local or gateway)."""
    global _ui_client
    if _ui_client is None:
        _ui_client = create_mt5_broker_client()
    return _ui_client


def _mt5_import_hint() -> str:
    if use_mt5_gateway():
        return "Set MT5_GATEWAY_URL to reach the Windows MT5 gateway"
    return "MetaTrader5 library is not installed or not on Windows"


# ==================== Connection Management ====================

@mt5_blp.route("/status", methods=["GET"])
@login_required
def get_status():
    """Get MT5 connection status."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({
                "connected": False,
                "error": desktop_broker_cloud_reject_message(),
            }), 403

        client = _get_client()
        status = client.get_connection_status()
        return jsonify(status)
    except ImportError as e:
        return jsonify({
            "connected": False,
            "error": str(e),
            "hint": _mt5_import_hint(),
        })
    except Exception as e:
        logger.error(f"Get MT5 status failed: {e}")
        return jsonify({"connected": False, "error": str(e)})


@mt5_blp.route("/connect", methods=["POST"])
@login_required
def connect():
    """
    Connect to MT5 terminal (local or via gateway).

    Request body:
    {
        "login": 12345678,
        "password": "xxx",
        "server": "ICMarkets-Demo",
        "terminal_path": ""
    }
    """
    global _ui_client

    try:
        if not local_desktop_brokers_allowed():
            return jsonify({
                "success": False,
                "error": desktop_broker_cloud_reject_message(),
            }), 403

        data = request.get_json() or {}

        login = data.get("login") or data.get("mt5_login")
        password = data.get("password") or data.get("mt5_password")
        server = data.get("server") or data.get("mt5_server")
        terminal_path = data.get("terminal_path") or data.get("mt5_terminal_path") or ""

        if not login or not password or not server:
            return jsonify({
                "success": False,
                "error": "Missing required fields: login, password, server",
            }), 400

        config = MT5Config(
            login=int(login),
            password=str(password),
            server=str(server),
            terminal_path=str(terminal_path),
        )

        if _ui_client is not None:
            try:
                _ui_client.disconnect()
            except Exception:
                pass

        _ui_client = create_mt5_broker_client(config)

        if _ui_client.connect():
            account_info = _ui_client.get_account_info()
            return jsonify({
                "success": True,
                "message": "Connected to MT5",
                "account": account_info,
            })
        return jsonify({
            "success": False,
            "error": "Failed to connect to MT5. Check credentials and gateway/terminal.",
        }), 400

    except ImportError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        logger.error(f"MT5 connect failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/disconnect", methods=["POST"])
@login_required
def disconnect():
    """Disconnect from MT5 terminal."""
    global _ui_client

    try:
        if not local_desktop_brokers_allowed():
            return jsonify({
                "success": False,
                "error": desktop_broker_cloud_reject_message(),
            }), 403

        if _ui_client is not None:
            _ui_client.disconnect()
            _ui_client = None
        return jsonify({"success": True, "message": "Disconnected"})
    except Exception as e:
        logger.error(f"MT5 disconnect failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Account Queries ====================

@mt5_blp.route("/account", methods=["GET"])
@login_required
def get_account():
    """Get account information."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        info = client.get_account_info()
        return jsonify(info)
    except Exception as e:
        logger.error(f"Get MT5 account failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/positions", methods=["GET"])
@login_required
def get_positions():
    """Get open positions."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        symbol = request.args.get("symbol")
        positions = client.get_positions(symbol=symbol)
        return jsonify({"success": True, "positions": positions})
    except Exception as e:
        logger.error(f"Get MT5 positions failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/orders", methods=["GET"])
@login_required
def get_orders():
    """Get pending orders."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        symbol = request.args.get("symbol")
        orders = client.get_orders(symbol=symbol)
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        logger.error(f"Get MT5 orders failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/symbols", methods=["GET"])
@login_required
def get_symbols():
    """Get available symbols."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        group = request.args.get("group", "*")
        symbols = client.get_symbols(group=group)
        return jsonify({"success": True, "symbols": symbols})
    except Exception as e:
        logger.error(f"Get MT5 symbols failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Trading ====================

@mt5_blp.route("/order", methods=["POST"])
@login_required
def place_order():
    """Place an order."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        data = request.get_json() or {}

        symbol = data.get("symbol")
        side = data.get("side")
        volume = data.get("volume") or data.get("quantity")
        order_type = data.get("orderType", "market").lower()
        price = data.get("price")
        comment = data.get("comment", "QuantDinger")

        if not symbol or not side or not volume:
            return jsonify({
                "success": False,
                "error": "Missing required fields: symbol, side, volume",
            }), 400

        if order_type == "limit":
            if not price:
                return jsonify({
                    "success": False,
                    "error": "Limit order requires price",
                }), 400
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

    except Exception as e:
        logger.error(f"MT5 place order failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/close", methods=["POST"])
@login_required
def close_position():
    """Close a position."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        data = request.get_json() or {}

        ticket = data.get("ticket")
        volume = data.get("volume")

        if not ticket:
            return jsonify({
                "success": False,
                "error": "Missing required field: ticket",
            }), 400

        result = client.close_position(
            ticket=int(ticket),
            volume=float(volume) if volume else None,
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

    except Exception as e:
        logger.error(f"MT5 close position failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@mt5_blp.route("/order/<int:ticket>", methods=["DELETE"])
@login_required
def cancel_order(ticket: int):
    """Cancel a pending order."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        if client.cancel_order(ticket):
            return jsonify({"success": True, "message": f"Order {ticket} cancelled"})
        return jsonify({"success": False, "error": "Failed to cancel order"}), 400

    except Exception as e:
        logger.error(f"MT5 cancel order failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Market Data ====================

@mt5_blp.route("/quote", methods=["GET"])
@login_required
def get_quote():
    """Get real-time quote."""
    try:
        if not local_desktop_brokers_allowed():
            return jsonify({"success": False, "error": desktop_broker_cloud_reject_message()}), 403

        client = _get_client()
        if not client.connected:
            return jsonify({"success": False, "error": "Not connected to MT5"}), 400

        symbol = request.args.get("symbol")
        if not symbol:
            return jsonify({"success": False, "error": "Missing symbol parameter"}), 400

        quote = client.get_quote(symbol)
        return jsonify(quote)

    except Exception as e:
        logger.error(f"MT5 get quote failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# openapi-compat: legacy import name
mt5_bp = mt5_blp
