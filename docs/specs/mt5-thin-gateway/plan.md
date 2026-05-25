# Implementation plan: MT5 Thin Gateway

| Spec | [spec.md](./spec.md) |
|------|----------------------|
| **Status** | Draft |

---

## 1. Architecture

`PendingOrderWorker` and `mt5.py` both call `create_mt5_client()`. If `MT5_GATEWAY_URL` is **unset**, the factory returns in-process `MT5Client` (existing behavior; MT5 Terminal must be reachable from the API host). If the URL is **set**, the factory returns `MT5GatewayClient`, which calls `mt5_gateway` on Windows over HTTP (`/v1/*`, shared API key); only the gateway process loads `MetaTrader5`.

### 1.1 Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **mt5_gateway** | `mt5_gateway/` (new) | Standalone Flask app; API key auth; wraps `MT5Client` |
| **MT5GatewayClient** | `backend_api_python/app/services/mt5_trading/gateway_client.py` | HTTP adapter; same public methods as `MT5Client` |
| **Protocol marker** | `backend_api_python/app/services/mt5_trading/base.py` | `MT5ClientProtocol` or `BaseMT5BrokerClient` for `isinstance` / routing |
| **Factory switch** | `live_trading/factory.py` | `MT5_GATEWAY_URL` → gateway client |
| **Type checks** | `pending_order_worker.py`, `execution.py` | Use protocol/base instead of `MT5Client` only |
| **UI routes (Q3)** | `app/routes/mt5.py` | Shared `get_mt5_broker_client()` helper: local `MT5Client` or `MT5GatewayClient` when URL set |

### 1.2 Transport transparency

The gateway does **not** implement account policy. Flow:

1. Core backend resolves credentials (`resolve_exchange_config`, UI connect body) → `MT5Config` / connect JSON.
2. `MT5GatewayClient.connect(config)` → `POST /v1/connect` with the same `login`, `password`, `server`, `terminal_path`.
3. Orders and queries → `/v1/order`, `/v1/positions`, etc., on the session established by that connect.

Strategy `credential_id` and per-strategy `exchange_config` are unchanged. HTTP is a drop-in transport for `MT5Client` method calls.

### 1.3 Process singleton and lock (G-09, G-10)

`mt5_gateway` keeps **one** `MT5Client` for the process lifetime and a **process-wide** `threading.Lock` (e.g. `mt5_gateway/session.py`: `get_gateway_client()`, `gateway_lock()`).

| Handler group | Under lock |
|---------------|------------|
| `POST /v1/connect`, `POST /v1/disconnect` | Yes — connect path disconnects first if already connected (mirror `mt5.py`) |
| `POST /v1/order`, `POST /v1/close`, `DELETE /v1/order/<ticket>` | Yes |
| `GET /v1/status`, `/v1/account`, `/v1/positions`, … | Yes — reads use the same Terminal session |
| `GET /health` | No — no MT5 touch |

Flask may serve requests on multiple threads; the lock serializes all MT5 side effects. Do **not** construct a new `MT5Client` per HTTP request.

### 1.4 API contract (gateway ↔ Linux client)

Base URL: `{MT5_GATEWAY_URL}` (no trailing slash). All `/v1/*` require header:

```http
X-MT5-Gateway-Key: <MT5_GATEWAY_API_KEY>
```

| Method | Path | Maps to |
|--------|------|---------|
| GET | `/health` | Liveness (no auth) |
| GET | `/v1/status` | `get_connection_status()` |
| POST | `/v1/connect` | `connect()` body: login, password, server, terminal_path |
| POST | `/v1/disconnect` | `disconnect()` |
| GET | `/v1/account` | `get_account_info()` |
| GET | `/v1/positions?symbol=` | `get_positions(symbol)` |
| GET | `/v1/orders?symbol=` | `get_orders(symbol)` |
| GET | `/v1/symbols?group=` | `get_symbols(group)` |
| GET | `/v1/quote?symbol=` | `get_quote(symbol)` |
| POST | `/v1/order` | `place_market_order` / `place_limit_order` |
| POST | `/v1/close` | `close_position` |
| DELETE | `/v1/order/<ticket>` | `cancel_order` |

JSON shapes mirror `backend_api_python/app/routes/mt5.py` responses.

---

## 2. Environment variables

**Terminology:** *Core backend* = the `backend_api_python` Flask API (Compose `backend` service, workers, `/api/mt5/*`). Distinct from `mt5_gateway` on Windows.

### 2.1 Gateway (Windows)

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_GATEWAY_HOST` | `127.0.0.1` | Bind address |
| `MT5_GATEWAY_PORT` | `5100` | Listen port |
| `MT5_GATEWAY_API_KEY` | *(required)* | Shared secret |
| `MT5_GATEWAY_LOG_LEVEL` | `INFO` | Logging |

### 2.2 Core backend

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_GATEWAY_URL` | *(empty)* | e.g. `http://192.168.1.50:5100` |
| `MT5_GATEWAY_API_KEY` | *(empty)* | Must match gateway |
| `MT5_GATEWAY_TIMEOUT_SEC` | `30` | HTTP timeout for orders |

Existing: `ALLOW_LOCAL_DESKTOP_BROKERS`, strategy `mt5_login` / `mt5_password` / `mt5_server` unchanged.

---

## 3. File map

| Action | Path |
|--------|------|
| **Add** | `mt5_gateway/__init__.py` |
| **Add** | `mt5_gateway/app.py` — Flask routes |
| **Add** | `mt5_gateway/run.py` — entrypoint |
| **Add** | `mt5_gateway/README.md` — Windows runbook |
| **Add** | `backend_api_python/app/services/mt5_trading/gateway_client.py` |
| **Add** | `backend_api_python/app/services/mt5_trading/protocol.py` (or `base_client.py`) |
| **Modify** | `backend_api_python/app/services/mt5_trading/client.py` — implement protocol |
| **Modify** | `backend_api_python/app/services/live_trading/factory.py` |
| **Modify** | `backend_api_python/app/services/live_trading/execution.py` |
| **Modify** | `backend_api_python/app/services/pending_order_worker.py` |
| **Modify** | `backend_api_python/app/routes/mt5.py` — Q3: shared client helper when `MT5_GATEWAY_URL` set |
| **Add** | `backend_api_python/app/services/mt5_trading/broker_client.py` (optional name) — `get_mt5_broker_client()` used by factory + `mt5.py` |
| **Modify** | `backend_api_python/env.example` |
| **Add** | `backend_api_python/tests/test_mt5_gateway_client.py` |
| **Modify** | `docs/MT5_TRADING_GUIDE_EN.md`, `docs/MT5_TRADING_GUIDE_CN.md` |
| **Modify** | `docs/specs/README.md` (status when done) |

**Q3 (required):** When `MT5_GATEWAY_URL` is set, `mt5.py` must not use in-process `MT5Client` on hosts without local MT5. Refactor `_get_client()` / `connect` to use the same helper as `create_mt5_client()` (see spec §7).

---

## 4. Security (minimal)

- Default bind `127.0.0.1`; document when to set `0.0.0.0` for LAN (trusted network only).
- API key on all `/v1/*` routes; do not log passwords or API keys.
- No TLS/reverse-proxy implementation or runbook in this feature.

---

## 5. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Gateway down during live trade | Fail pending order with explicit error; retry policy unchanged |
| Stale singleton on gateway | One process per machine; document restart after MT5 reconnect; document same-account practice for UI + strategies |
| Concurrent connect/order from UI + worker | Process-wide lock on all `/v1/*` MT5 handlers (G-09); connect disconnects-then-connects under lock (G-10) |
| UI vs strategy different accounts | Not a gateway feature; last `connect` wins on Terminal — document in MT5 guide |
| `isinstance` misses gateway client | Protocol base class + register both implementations |
| CI imports MetaTrader5 | Gateway tests use `responses` / `unittest.mock` only |

---

## 6. Out of scope reminders

See [spec.md §3](./spec.md#3-out-of-scope-this-feature).
