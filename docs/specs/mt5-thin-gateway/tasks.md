# Task breakdown: MT5 Thin Gateway

| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Harness | [harness.md](./harness.md) |

Tasks are ordered by dependency. Mark `[x]` when done. Each task lists **acceptance criteria (AC)** IDs from the spec.

---

## Phase 0 — SDD setup (this branch)

| ID | Task | AC | Deps | Status |
|----|------|-----|------|--------|
| T-0.1 | Create branch `feat/mt5-thin-gateway` | — | — | [x] |
| T-0.2 | Add `docs/specs/mt5-thin-gateway/{spec,plan,tasks,harness}.md` | — | T-0.1 | [x] |

---

## Phase 1 — Protocol and gateway service (Windows)

| ID | Task | AC | Deps | Status |
|----|------|-----|------|--------|
| T-1.1 | Add `MT5BrokerClient` protocol (`connect`, `disconnect`, `connected`, `place_market_order`, `place_limit_order`, `close_position`, `get_positions`, `get_account_info`, `get_connection_status`, `get_quote`, `cancel_order`) | L-02, AC-7 | T-0.2 | [x] |
| T-1.2 | Make `MT5Client` implement protocol (no behavior change) | AC-7 | T-1.1 | [x] |
| T-1.3 | Scaffold `mt5_gateway/` package with `run.py`, `app.py`, `GET /health` | G-01, AC-1 | T-0.2 | [x] |
| T-1.4 | Implement API-key middleware for `/v1/*` | G-02, AC-2 | T-1.3 | [x] |
| T-1.5 | Add `mt5_gateway/session.py`: process-singleton `MT5Client` + process-wide `threading.Lock`; wire `/v1/connect` (disconnect-if-connected then connect), `/v1/disconnect`, `/v1/status` — all MT5 handlers acquire lock for full handler | G-03, G-04, G-09, G-10, AC-3 | T-1.4, T-1.2 | [x] |
| T-1.6 | Wire `/v1/order`, `/v1/close`, `/v1/order/<ticket>` DELETE (same session lock as T-1.5) | G-05, G-09, AC-4 | T-1.5 | [x] |
| T-1.7 | Wire `/v1/account`, `/v1/positions`, `/v1/orders`, `/v1/symbols`, `/v1/quote` (same lock) | G-06, G-09 | T-1.5 | [x] |
| T-1.8 | Add `mt5_gateway/README.md` (PowerShell start, `MT5_GATEWAY_*`, trusted LAN URL examples only) | AC-9, AC-10 | T-1.3 | [x] |
| T-1.9 | Graceful shutdown: disconnect MT5 on exit | G-07 | T-1.5 | [x] |

---

## Phase 2 — Core backend remote client (`MT5GatewayClient`)

| ID | Task | AC | Deps | Status |
|----|------|-----|------|--------|
| T-2.1 | Implement `MT5GatewayClient` (HTTP, `requests`, maps errors to `ConnectionError` / `OrderResult`) | L-02, L-04 | T-1.1, plan §1.2 | [x] |
| T-2.2 | `create_mt5_client()`: if `MT5_GATEWAY_URL` set → `MT5GatewayClient(MT5Config)` else existing local path | L-01, L-02 | T-2.1 | [x] |
| T-2.3 | Replace `isinstance(client, MT5Client)` with protocol check in `execution.py` | AC-7 | T-1.1, T-2.1 | [x] |
| T-2.4 | Same protocol check in `pending_order_worker.py` (execute + position sync) | AC-6, AC-7 | T-2.3 | [x] |
| T-2.5 | Document `MT5_GATEWAY_*` in `env.example` | AC-9 | T-2.2 | [x] |
| T-2.6 | **Q3:** Refactor `mt5.py` to use shared `create_mt5_broker_client()` (gateway or local); connect/status/positions/order/close/quote | L-06, AC-11 | T-2.1, T-2.2 | [x] |

---

## Phase 3 — Harness (tests and docs)

| ID | Task | AC | Deps | Status |
|----|------|-----|------|--------|
| T-3.1 | `test_mt5_gateway_client.py`: mock HTTP, connect/order/status paths | AC-5, AC-8 | T-2.1 | [x] |
| T-3.2 | `test_mt5_factory_gateway.py`: factory returns gateway client when env set | AC-5 | T-2.2 | [x] |
| T-3.2b | `test_mt5_routes_gateway.py`: `mt5.py` connect/positions use mocked gateway when env set | AC-11, L-06 | T-2.6 | [x] |
| T-3.3 | Gateway route tests with Flask test client (no MT5): auth + concurrent `/v1/connect` or connect+status serialized (mock slow handler or lock probe) | AC-1, AC-2, AC-12 | T-1.5 | [x] |
| T-3.4 | Update MT5 guides (EN/CN): short split-stack section + env table (no TLS/public-network docs) | AC-10 | T-1.8, T-2.5 | [x] |
| T-3.5 | Run `python -m pytest tests/ -q` in `backend_api_python` | harness H-01 | T-3.1–T-3.3 | [x] |

---

## Phase 4 — Manual validation (operator)

| ID | Task | AC | Deps | Status |
|----|------|-----|------|--------|
| T-4.1 | Windows: start MT5 Terminal (demo), run gateway, verify AC-3/AC-4 via curl | AC-3, AC-4 | Phase 1 | [ ] |
| T-4.2 | Linux: Compose up, set `MT5_GATEWAY_URL`, run one forex strategy signal to fill or fail clearly | AC-6 | Phase 2 | [ ] |
| T-4.2b | Linux: Broker UI — `POST /api/mt5/connect` + `GET /api/mt5/positions` via gateway | AC-11 | T-2.6 | [ ] |
| T-4.3 | Regression: Windows all-in-one with `MT5_GATEWAY_URL` unset still works | spec §9 | T-2.2 | [ ] |

---

## Dependency graph (summary)

```text
T-0.* → T-1.1 → T-1.2 → T-1.3 → T-1.4 → T-1.5 → T-1.6/T-1.7
                    ↘ T-2.1 → T-2.2 → T-2.3 → T-2.4 → T-3.* → T-4.*
```

---

## Suggested commit slices

1. `docs: add MT5 thin gateway SDD spec` (Phase 0)
2. `feat(mt5): add gateway service and protocol` (Phase 1)
3. `feat(mt5): add MT5GatewayClient, factory switch, and mt5.py Q3` (Phase 2)
4. `test(mt5): gateway client mocks` (Phase 3)
5. `docs(mt5): thin gateway deployment guide` (Phase 3–4)
