# Harness: MT5 Thin Gateway

The **harness** is the enforcement layer: specs define intent; these gates prove the implementation matches before merge.

| Spec | [spec.md](./spec.md) |
| Tasks | [tasks.md](./tasks.md) |

---

## 1. Principles (harness engineering)

| Rule | Enforcement |
|------|-------------|
| No secrets in repo | Review + `env.example` placeholders only |
| No `MetaTrader5` import on Linux CI path | CI `grep`/tests; gateway code only in `mt5_gateway/` + Windows docs |
| Tasks trace to AC | PR description lists AC IDs |
| Minimal diff | Gateway reuses `MT5Client`; no duplicate order mapping |
| Transport only | Credential resolution stays in core backend; gateway forwards connect/order JSON unchanged |
| Gateway session safety | One `MT5Client` per gateway process; all `/v1/*` MT5 routes hold one process lock (G-09) |
| Agent red lines | No weakening `ALLOW_LOCAL_DESKTOP_BROKERS` without explicit ask |

---

## 2. Automated gates

### H-01 — Backend unit tests (required)

```bash
cd backend_api_python && python -m pytest tests/test_mt5_gateway_client.py tests/test_mt5_factory_gateway.py -q
```

**Pass when:**

- All tests green on Linux/macOS CI (no Windows, no real MT5).
- HTTP client tested with mocks (`responses` or `unittest.mock`).

### H-02 — CI compatibility (required)

Existing workflow `.github/workflows/basic-ci.yml` must remain green:

```bash
cd backend_api_python && python -m pytest tests/ -q
```

**Pass when:** No new dependency on `MetaTrader5` in default `requirements.txt`.

### H-03 — Lint / import hygiene (recommended)

- `mt5_gateway` must not be imported by default backend startup on Linux (lazy or separate process only).
- Run existing project lint if configured; no new linter violations in touched files.

### H-04 — Gateway smoke (optional, Windows dev machine)

```powershell
$env:MT5_GATEWAY_API_KEY = "test-key-local"
python -m mt5_gateway.run
# Another shell:
curl http://127.0.0.1:5100/health
curl -H "X-MT5-Gateway-Key: test-key-local" http://127.0.0.1:5100/v1/status
```

**Pass when:** AC-1, AC-2 satisfied without MT5; AC-3+ require Terminal.

---

## 3. Manual QA checklist

| Step | Verifies | Pass criterion |
|------|----------|----------------|
| M-1 | G-02 | Wrong API key → 401 |
| M-2 | G-03, AC-3 | Connect with demo credentials → `connected: true` |
| M-3 | G-05, AC-4 | Small market order on demo → structured JSON response |
| M-4 | L-02, AC-5 | Backend starts with `MT5_GATEWAY_URL` set (no local `MetaTrader5`), no ImportError |
| M-5 | AC-6 | Strategy pending order reaches gateway logs and DB trade row updates |
| M-6 | AC-6 neg | Stop gateway → next order fails with `mt5_gateway_*` error, not hang |
| M-7 | T-4.3 | Windows native, no gateway URL, unchanged behavior |
| M-8 | AC-11 | Linux + gateway: UI connect then positions list returns data or clear error |

---

## 4. Spec compliance matrix

| AC | Automated | Manual |
|----|-----------|--------|
| AC-1 | H-04 | — |
| AC-2 | H-04 / test | M-1 |
| AC-3 | — | M-2 |
| AC-4 | — | M-3 |
| AC-5 | H-01 | M-4 |
| AC-6 | partial mock | M-5, M-6 |
| AC-7 | H-01 (routing) | — |
| AC-8 | H-01, H-02 | — |
| AC-9 | review `env.example` | — |
| AC-10 | — | doc review |
| AC-11 | T-3.2b | M-8 |
| AC-12 | T-3.3 (concurrent route / lock probe) | — |

---

## 5. Definition of Done (feature)

- [ ] All Phase 1–3 tasks in [tasks.md](./tasks.md) marked complete
- [ ] H-01 and H-02 pass
- [ ] At least M-1, M-4, M-6 verified by operator (or documented skip for no-Windows CI)
- [ ] `docs/specs/README.md` status updated to **Implemented** or **In progress**
- [ ] No live-trading safety regressions (`ALLOW_LOCAL_DESKTOP_BROKERS`, agent `paper_only` unchanged)

---

## 6. Agent implementation notes

When implementing via coding agent:

1. Read `spec.md` → `plan.md` → `tasks.md` → this file.
2. Complete tasks in dependency order; one commit slice per suggested section in tasks.md.
3. After each phase, run H-01 (and H-02 before PR).
4. Do not mark AC-6 done without M-5 or an explicit operator sign-off in PR.
