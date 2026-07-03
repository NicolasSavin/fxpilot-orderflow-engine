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

```bash
cp .env.example .env
docker compose up --build
```

The service listens on port `8010`.

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
- `POST /api/orderflow/ingest`
- `GET /api/orderflow/debug`
- `GET /api/orderflow/provider/status`
