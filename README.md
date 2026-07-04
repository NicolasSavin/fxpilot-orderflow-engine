# FXPilot OrderFlow Engine v1

Standalone Python/FastAPI service for calculating an FXPilot-owned Order Flow layer from professional market data. Version 1 runs fully on mock/historical-style data and includes a read-only Databento Historical connectivity check without changing the public FXPilot API.

## Features

- Delta and cumulative delta
- Volume, RVOL, VWAP
- Volume profile, POC, VAH/VAL, HVN/LVN
- DOM pressure and imbalance
- Absorption, exhaustion, market state
- Order-flow bias, continuation probability, reversal probability
- FX-to-futures symbol mapping: `EURUSD -> 6E`, `GBPUSD -> 6B`, `USDJPY -> 6J`, `XAUUSD -> GC`

## Run

### Docker

```bash
cp .env.example .env
docker compose up --build
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:ORDERFLOW_PROVIDER = "mock"
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

### Windows Command Prompt

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
set ORDERFLOW_PROVIDER=mock
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

The service listens on port `8010`.

## Tests

```bash
pytest
```

## Health check

```bash
curl http://localhost:8010/health
```

Expected response:

```json
{"status":"ok","service":"fxpilot-orderflow-engine"}
```

## Latest snapshot

```bash
curl 'http://localhost:8010/api/orderflow/latest?symbol=EURUSD'
```

Returns an `OrderFlowSnapshot` with mock data by default.

## Mock provider

Mock mode is enabled by default:

```env
ORDERFLOW_PROVIDER=mock
```

It generates deterministic realistic trades and book levels for `EURUSD/6E`, `GBPUSD/6B`, `USDJPY/6J`, and `XAUUSD/GC`.

## Databento Historical check

Set the official Databento key before starting the service:

```env
DATABENTO_API_KEY=your_key
ORDERFLOW_PROVIDER=databento
```

The Databento provider uses the official `databento` Python SDK and checks CME Globex MDP 3.0 historical trades (`GLBX.MDP3`, `trades`) for the raw futures symbol `6E` by default. Live Databento streaming is intentionally not required in v1. Without a key, the debug check returns a clear `not_configured` response instead of crashing.

Run the check:

```bash
curl 'http://localhost:8010/api/debug/databento'
```

Optional parameters:

```bash
curl 'http://localhost:8010/api/debug/databento?symbol=6E&lookback_hours=24'
```

Successful responses include whether `DATABENTO_API_KEY` is configured, whether the SDK is importable, the dataset, supported futures symbols, connection status, and historical trade availability. When trades are returned, the response also includes trade count, first/last trade timestamps, price range, and total volume. If the SDK call succeeds but no trades are found in the requested window, the response explains that the connection was established and no trades were returned for that symbol/time window.

## Useful endpoints

- `GET /health`
- `GET /api/orderflow/latest?symbol=EURUSD`
- `GET /api/orderflow/provider/status`
- `GET /api/orderflow/symbols`
- `POST /api/orderflow/ingest`
- `GET /api/orderflow/debug`
- `GET /api/debug/databento`

## curl examples

```bash
curl http://localhost:8010/health
curl 'http://localhost:8010/api/orderflow/latest?symbol=EURUSD'
curl http://localhost:8010/api/orderflow/provider/status
curl http://localhost:8010/api/orderflow/symbols
curl 'http://localhost:8010/api/debug/databento'
curl -X POST http://localhost:8010/api/orderflow/ingest \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"EURUSD","trades":[{"symbol":"6E","price":1.145,"size":10,"side":"buy"}],"book":[{"price":1.145,"bid_size":100,"ask_size":80}],"candles":[{"symbol":"6E","open":1.144,"high":1.146,"low":1.143,"close":1.145,"volume":1000}]}'
```
