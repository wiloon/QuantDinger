# Feature specification: MT5 Thin Gateway

| Field | Value |
|-------|--------|
| **ID** | `mt5-thin-gateway` |
| **Status** | Draft |
| **Branch** | `feat/mt5-thin-gateway` |
| **Owner** | QuantDinger maintainers |
| **Related docs** | [MT5_TRADING_GUIDE_EN.md](../../MT5_TRADING_GUIDE_EN.md), [MT5_TRADING_GUIDE_CN.md](../../MT5_TRADING_GUIDE_CN.md) |

---

## 1. Problem statement

QuantDinger’s default deployment runs the Flask backend in a **Linux Docker** container. The official `MetaTrader5` Python library requires a **Windows MT5 Terminal** on the same machine as the process that calls `mt5.initialize()`.

Operators run the QuantDinger core on Linux (including Docker or WSL2) while MT5 must stay on Windows. This feature adds a thin HTTP gateway so **non–MT5 services stay on the Linux side** and **MT5 Terminal + `MetaTrader5` stay on Windows**, typically on the same LAN or the same physical PC (`host.docker.internal` / `127.0.0.1`).

As of **`main` @ `91dd4e2`** (baseline before this feature), the repo documents a future “Windows MT5 gateway/bridge” but ships **no** remote client or standalone gateway service.

---

## 2. Goals

1. **Decouple Linux core from Windows MT5**: Run `docker compose` backend, Postgres, Redis, frontend, and non-MT5 trading on Linux; run a minimal Windows gateway for MT5. Connect with `MT5_GATEWAY_URL` (LAN IP or loopback on one PC).
2. **Thin gateway**: Reuse existing `MT5Client` logic on Windows; expose a small HTTP API aligned with current `/api/mt5/*` shapes.
3. **Remote integration (transport adapter)**: When `MT5_GATEWAY_URL` is set, both **strategy live execution** (factory / worker) and **broker UI** (`/api/mt5/*`) use an **`MT5GatewayClient`** that speaks HTTP to the Windows gateway. Credential resolution (`credential_id`, `resolve_exchange_config`, strategy `exchange_config`) stays in the core backend unchanged.
4. **UI path parity (Q3, required)**: `app/routes/mt5.py` must use the same client factory as `create_mt5_client()` when the gateway URL is set, so Broker page connect / query / manual order work via the gateway—not only the pending-order worker.
5. **Single gateway per deployment (this feature)**: One `MT5_GATEWAY_URL` ↔ one Windows gateway process ↔ one MT5 Terminal session—the same single-session limit as the current setup. Broader multi-user or multi-account orchestration is **not** part of this spec.

---

## 3. Out of scope (this feature)

| Item | Rationale |
|------|-----------|
| Multi-account / multi-user gateway session orchestration | One Terminal login per gateway; not needed for initial decouple |
| TLS/mTLS, reverse proxies, public-internet deployment guides | Trusted LAN / loopback + API key only; operators handle hardening outside this feature if ever needed |
| Rewriting order logic | Gateway wraps `MT5Client`; no duplicate trading rules |
| MQL5 EA / ZeroMQ bridge | Official Python API path only |
| Changing crypto / Alpaca / IBKR paths | Unaffected |
| UI redesign | Existing broker pages; only backend transport changes |
| Shipping Windows installer | PowerShell + `requirements-windows.txt` documented |

---

## 4. Personas and scenarios

### 4.1 Operator (split stack — LAN, WSL, or Docker Desktop)

- **Given** the “rest” of QuantDinger runs on a non–MT5-capable runtime (Linux host, WSL2, or Linux containers under Docker Desktop).
- **Given** a **Windows** process (thin gateway) can reach MT5 Terminal on that Windows environment (logged in).
- **When** the operator sets `MT5_GATEWAY_URL` to the gateway’s reachable URL (LAN IP, `host.docker.internal`, or `127.0.0.1` on the same PC) and binds a forex strategy to MT5 credentials.
- **Then** pending orders for that strategy execute via the gateway on Windows, and positions sync back to Postgres on the core side.
- **And** Broker UI (`POST /api/mt5/connect`, positions, manual order) reaches the same gateway with the credentials the user enters in the UI.

### 4.2 Developer (local test)

- **Given** gateway on `http://127.0.0.1:5100` with `MT5_GATEWAY_API_KEY` set.
- **When** `curl` hits `/health` and `/v1/status` with the API key header.
- **Then** responses match the JSON contract in `plan.md` without importing `MetaTrader5` on the client machine.

---

## 5. Functional requirements (EARS)

### Gateway (Windows service)

| ID | Requirement |
|----|-------------|
| **G-01** | WHEN the gateway process starts THEN the system SHALL expose `GET /health` returning `{"ok": true}` without requiring MT5 connection. |
| **G-02** | WHEN a request includes a valid `X-MT5-Gateway-Key` matching `MT5_GATEWAY_API_KEY` THEN the system SHALL process the request; ELSE it SHALL return HTTP 401. |
| **G-03** | WHEN `POST /v1/connect` receives `login`, `password`, `server`, and optional `terminal_path` THEN the system SHALL call `MT5Client.connect()` and return success/failure JSON consistent with existing `/api/mt5/connect`. |
| **G-04** | WHEN `GET /v1/status` is called THEN the system SHALL return `MT5Client.get_connection_status()` payload. |
| **G-05** | WHEN `POST /v1/order` receives market/limit order fields THEN the system SHALL delegate to `place_market_order` / `place_limit_order` and return the same success/error JSON shape as `/api/mt5/order`. |
| **G-06** | WHEN `GET /v1/positions` or `GET /v1/account` is called while connected THEN the system SHALL return data from `MT5Client` query methods. |
| **G-07** | WHEN the gateway receives SIGTERM THEN the system SHALL call `MT5Client.disconnect()` best-effort before exit. |
| **G-08** | WHEN `MT5_GATEWAY_BIND` is set THEN the system SHALL bind only to that host (default `127.0.0.1` for safety). |
| **G-09** | The gateway process SHALL hold **one** process-wide `MT5Client` singleton and **one** process-wide lock. All `/v1/*` handlers that touch MT5 (`connect`, `disconnect`, `order`, queries) SHALL acquire that lock for the full handler body so concurrent HTTP requests cannot interleave `initialize` / `shutdown` / order calls. |
| **G-10** | WHEN `POST /v1/connect` runs while another request holds the lock THEN the caller SHALL block until the prior handler completes; WHEN connect runs inside the lock THEN it SHALL follow the same semantics as `mt5.py` (disconnect existing session if connected, then connect with the new credentials). |

### Core backend (`backend_api_python`)

Requirements for the Flask API and background workers in `backend_api_python`. When `MT5_GATEWAY_URL` is set, MT5 calls use the HTTP client; when unset, the current in-process `MT5Client` path is unchanged.

| ID | Requirement |
|----|-------------|
| **L-01** | WHEN `MT5_GATEWAY_URL` is unset THEN the system SHALL use in-process `MT5Client` (existing Windows-native integration). |
| **L-02** | WHEN `MT5_GATEWAY_URL` is set THEN `create_mt5_client()` SHALL return an HTTP-backed client implementing the same methods used by `pending_order_worker` and `live_trading.execution`. |
| **L-03** | WHEN `MT5_GATEWAY_URL` is set on a host where `MetaTrader5` is not installed THEN MT5 code paths SHALL work without importing `MetaTrader5` locally. |
| **L-04** | WHEN the remote gateway returns connection errors THEN live order execution SHALL mark pending orders failed with a clear `mt5_gateway_*` error (no silent fallback to local MT5). |
| **L-05** | WHEN `ALLOW_LOCAL_DESKTOP_BROKERS=false` THEN MT5 routes SHALL continue to respect the existing cloud rejection (gateway does not bypass this flag). |
| **L-06** | WHEN `MT5_GATEWAY_URL` is set THEN `mt5.py` route handlers SHALL obtain an `MT5GatewayClient` (or shared helper) instead of in-process `MT5Client`, forwarding the same JSON bodies to gateway `/v1/*` that current routes use locally. |

---

## 6. Acceptance criteria (traceable)

| AC | Criterion | Verifies |
|----|-----------|----------|
| **AC-1** | Gateway `/health` returns 200 without MT5 installed connection | G-01 |
| **AC-2** | Missing/wrong API key → 401 on all `/v1/*` routes | G-02 |
| **AC-3** | With MT5 Terminal running on Windows, `POST /v1/connect` succeeds and `GET /v1/status` shows `connected: true` | G-03, G-04 |
| **AC-4** | `POST /v1/order` demo market order on demo account returns `success: true` or broker rejection with `success: false` and message | G-05 |
| **AC-5** | Backend with `MT5_GATEWAY_URL` on a host without `MetaTrader5` creates client without `ImportError` | L-02, L-03 |
| **AC-6** | Forex strategy live signal executes via gateway when URL is set (pending order → filled or explicit failure) | L-02, scenario 4.1 |
| **AC-7** | `isinstance` / type checks route MT5 orders through `_execute_mt5_order` for both local and gateway clients | L-02 |
| **AC-8** | Unit tests mock HTTP gateway; no Windows required in CI | harness H-02 |
| **AC-9** | `env.example` documents `MT5_GATEWAY_URL`, `MT5_GATEWAY_API_KEY`, gateway bind/port | plan §4 |
| **AC-10** | MT5 guides + `mt5_gateway/README.md` add a **short** “split stack” setup (env vars, URL examples)—no TLS/public-network runbooks | docs |
| **AC-11** | With `MT5_GATEWAY_URL` set, `POST /api/mt5/connect` and `GET /api/mt5/positions` succeed against gateway (demo account) | L-06 |
| **AC-12** | Gateway route tests (or unit test of session module) show two concurrent `/v1/connect` or connect+order requests are serialized by the process lock (no overlapping handler execution) | G-09, G-10 |

---

## 7. Transport transparency and credentials (no account-model change)

The thin gateway is a **transport adapter only**. It does not choose which MT5 account to use; the core backend does, with the same rules as the current codebase.

### 7.1 Where accounts are configured (unchanged)

| Path | Config source | Used by |
|------|---------------|---------|
| **Strategy live orders** | Strategy `exchange_config` and/or `credential_id` → `qd_exchange_credentials` (`mt5_login`, `mt5_password`, `mt5_server`, …) resolved by `resolve_exchange_config()` | `create_mt5_client()` → worker / `place_order_from_signal` |
| **Broker UI** | User input on connect → `POST /api/mt5/connect` body (same field names) | `mt5.py` routes (status, account, positions, manual order) |

The HTTP layer does **not** introduce a third account store. Upstream passes the same `MT5Config` / connect JSON it would pass to local `MT5Client`; the gateway forwards those fields to `POST /v1/connect` and subsequent `/v1/*` calls use the resulting terminal session.

### 7.2 Transparency contract

| Layer | Behavior |
|-------|----------|
| **Upstream (core backend)** | Still resolves `credential_id`, merges strategy overrides, builds connect/order payloads. Swaps `MT5Client` for `MT5GatewayClient` when `MT5_GATEWAY_URL` is set — same method signatures. |
| **HTTP** | Serializes existing `/api/mt5/*` request/response shapes to gateway `/v1/*` (see [plan.md](./plan.md)). |
| **Downstream (gateway)** | Instantiates `MT5Client` on Windows; `connect(login, password, server)` then `place_market_order` / `get_positions` using the same client methods as now. |

**Not in scope for “transparency”:** network failures, gateway downtime, and extra latency — callers see errors, not silent fallback to local MT5 (see **L-04**).

### 7.3 Two MT5 entry points (why Q3 is required)

| Entry | Module | With gateway enabled |
|-------|--------|-----------------|
| Automated trading | `live_trading/factory.py` | `MT5GatewayClient` via **L-02** |
| Broker desk UI | `app/routes/mt5.py` | `MT5GatewayClient` via **L-06** (Q3) |

Both must use the gateway when configured, or split deployments would only automate strategies while the Broker page still tried to use in-process `MetaTrader5` where it is unavailable.

### 7.4 Account and session assumptions (this delivery)

- **Per-strategy credentials** remain supported: each strategy may reference a different `credential_id`; factory passes that strategy’s resolved config into `connect()` (local or HTTP).
- **UI connect** uses whatever account the user submits; it is stored in the route-layer client/session, not in the gateway’s own DB.
- **MT5 Terminal** still allows typically **one active login per gateway process**. If UI connect uses account A and a strategy immediately `connect`s account B, behavior is the same as in the current codebase (later connect may replace the terminal session)—this is **not introduced by HTTP** and is **not** a product goal of “query on A, trade on B.”
- **Recommended operator practice:** use the **same** MT5 account for Broker UI connect and for strategies (or the same `credential_id` values), especially with a single gateway instance.

Per-user MT5 UI sessions (like IBKR/Alpaca `BrokerSessionRegistry`) are outside this feature; `mt5.py` may still use a module-level client until changed separately.

### 7.5 Gateway concurrency (singleton + lock)

The core backend may issue overlapping MT5 traffic: Broker UI `connect` while `PendingOrderWorker` calls `connect()` on a new `MT5GatewayClient`, or two worker threads processing different strategies. On Windows, `MetaTrader5` is **process-global**; multiple in-flight `mt5.initialize()` / `order_send()` calls are unsafe.

| Concern | Gateway behavior (G-09, G-10) |
|---------|-------------------------------|
| Multiple HTTP clients | One `MT5Client` per gateway **process**, not per request |
| Concurrent `/v1/connect` | Serialized; last connect wins on the Terminal session (same as today) |
| `connect` vs `order` | Same lock — order waits until connect/disconnect finishes |
| `disconnect` vs `order` | Same lock — no shutdown mid-order handler |
| Per-request `MT5Client` | **Forbidden** on the gateway |

The gateway lock is **in addition to** `MT5Client`’s per-instance `_lock` (which only protects one object). Implementation may reuse the pattern in `mt5_trading/client.py` (`_global_client` / `_global_lock`) inside `mt5_gateway/session.py` or equivalent.

---

## 8. Constraints and assumptions

- **Network**: **Trusted LAN or same host only** (loopback, `host.docker.internal`, private RFC1918 address). QuantDinger does not target MT5 gateway access over the public internet. Auth is a shared API key on HTTP.
- **Latency**: One extra LAN HTTP hop is acceptable for forex strategies (not HFT).
- **Credentials**: Unchanged—login/password in connect JSON over HTTP on the trusted link; gateway must not log secrets.
- **Worker**: A single backend instance should run `ENABLE_PENDING_ORDER_WORKER=true`; no dual-backend race (see MT5 guide).
- **Python**: Gateway uses a thin `mt5_gateway/` package importing `MT5Client` from `backend_api_python`.

---

## 9. Resolved decisions (plan review)

| # | Decision | Choice |
|---|----------|--------|
| Q1 | Gateway package location | `mt5_gateway/` at repo root |
| Q2 | Gateway port default | `5100` |
| Q3 | UI `/api/mt5/*` when gateway enabled | **Required:** `mt5.py` uses shared gateway client helper (same as factory), not optional |

---

## 10. Success metrics

- Operator can run **full Compose on Linux** + **gateway on Windows** and complete one demo forex round-trip (strategy **and** Broker UI connect/positions).
- CI stays green on Linux (gateway client tested with mocks).
