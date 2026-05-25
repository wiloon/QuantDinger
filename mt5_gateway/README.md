# MT5 Thin Gateway

Windows-side HTTP service that wraps `MT5Client` from `backend_api_python`. The core backend (Linux Docker / WSL) sets `MT5_GATEWAY_URL` and talks to this process over a trusted LAN.

## Prerequisites

- Windows with MT5 Terminal installed and logged in
- Python 3.10+
- `pip install -r backend_api_python/requirements.txt`
- `pip install -r backend_api_python/requirements-windows.txt` (includes `MetaTrader5`)

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `MT5_GATEWAY_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for LAN) |
| `MT5_GATEWAY_PORT` | `5100` | Listen port |
| `MT5_GATEWAY_API_KEY` | *(required)* | Shared secret; header `X-MT5-Gateway-Key` |
| `MT5_GATEWAY_LOG_HEALTH` | *(off)* | Set `1` / `true` to log `/health` at INFO (default: DEBUG) |
| `LOG_LEVEL` | `INFO` | Root log level (same as core backend) |

## Logging

Each request writes one sanitized line to logger `mt5_gateway.access`:

- Included: method, path, HTTP status, client IP, allowlisted query/body fields (`symbol`, `login`, `server`, `ticket`, etc.)
- Never logged: headers, `X-MT5-Gateway-Key`, passwords, or other secrets

`/health` is logged at DEBUG unless `MT5_GATEWAY_LOG_HEALTH=true` (reduces probe noise). Werkzeug access logs are suppressed; use the lines above instead.

Connect/disconnect outcomes are logged on logger `mt5_gateway.app` (`login` + `server` only, no password).

## Start (PowerShell)

```powershell
cd C:\path\to\QuantDinger
$env:MT5_GATEWAY_API_KEY = "your-shared-secret"
py -m pip install -r backend_api_python\requirements.txt -r backend_api_python\requirements-windows.txt
py -m mt5_gateway.run
```

## Core backend `.env`

```env
MT5_GATEWAY_URL=http://192.168.1.50:5100
MT5_GATEWAY_API_KEY=your-shared-secret
ALLOW_LOCAL_DESKTOP_BROKERS=true
```

URL examples:

- Same PC, Docker Desktop: `http://host.docker.internal:5100`
- LAN Windows host: `http://192.168.x.x:5100`
- Loopback test: `http://127.0.0.1:5100`

## Health check

```powershell
curl http://127.0.0.1:5100/health
curl -H "X-MT5-Gateway-Key: your-shared-secret" http://127.0.0.1:5100/v1/status
```

Use the same MT5 account for Broker UI connect and live strategies when running a single gateway instance.
