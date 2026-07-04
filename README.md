# FXPilot OrderFlow Engine v1

Standalone Python/FastAPI service for calculating an FXPilot-owned Order Flow layer from professional market data. Version 1 runs fully on mock/historical-style data and is architected so Databento can be added later without rewriting the service.

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

## Databento later

Set:

```env
DATABENTO_API_KEY=your_key
ORDERFLOW_PROVIDER=databento
```

The current Databento provider is a safe scaffold. Without a key it returns `provider_not_configured` status instead of crashing. Live Databento is intentionally not required in v1.

## Useful endpoints

- `GET /health`
- `GET /api/orderflow/latest?symbol=EURUSD`
- `GET /api/orderflow/provider/status`
- `GET /api/orderflow/symbols`
- `POST /api/orderflow/ingest`
- `GET /api/orderflow/debug`

## curl examples

```bash
curl http://localhost:8010/health
curl 'http://localhost:8010/api/orderflow/latest?symbol=EURUSD'
curl http://localhost:8010/api/orderflow/provider/status
curl http://localhost:8010/api/orderflow/symbols
curl -X POST http://localhost:8010/api/orderflow/ingest \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"EURUSD","trades":[{"symbol":"6E","price":1.145,"size":10,"side":"buy"}],"book":[{"price":1.145,"bid_size":100,"ask_size":80}],"candles":[{"symbol":"6E","open":1.144,"high":1.146,"low":1.143,"close":1.145,"volume":1000}]}'
```
