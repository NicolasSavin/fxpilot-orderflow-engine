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

Successful responses include whether `DATABENTO_API_KEY` is configured, whether the SDK is importable, the dataset, supported futures symbols, connection status, and historical trade availability. The default `lookback_hours` remains configurable and, when no explicit end time is supplied internally, the debug check ends at current UTC time minus 30 minutes to avoid requesting a window beyond Databento's latest processed timestamp. Responses include `actual_start`, `actual_end`, and `retry_used` so callers can inspect the exact historical window that was queried. If Databento returns `data_end_after_available_end`, the provider parses `available_end` from the error and retries once with `actual_end` set to `available_end` minus 1 minute; if that retry succeeds, the endpoint returns a normal successful debug response instead of failing. When trades are returned, the response also includes trade count, first/last trade timestamps, price range, and total volume. If the SDK call succeeds but no trades are found in the requested window, the response explains that the connection was established and no trades were returned for that symbol/time window.

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

## Stage 2 — Historical Storage and Data Catalog

FXPilot OrderFlow Engine now includes a historical-data storage subsystem for **historical and mock data only**. It does not implement Databento Live streaming and does not require a Databento Live subscription. Historical downloads are never automatic and may incur Databento costs when explicitly requested through protected OPS endpoints.

### Architecture

The subsystem lives in `app/services/historical_storage/`:

- `models.py` defines `HistoricalDataset`, `HistoricalDownloadRequest`, `DatasetStatus`, local import requests, and the future `NormalizedTrade` contract.
- `paths.py` owns Windows-compatible `pathlib.Path` directory management, safe component naming, path traversal rejection, and atomic text writes.
- `catalog.py` persists `catalogs/historical_catalog.json` with atomic JSON writes and searchable dataset metadata.
- `integrity.py` validates readable files, required trade columns, checksums, ordered timestamps, positive prices, non-negative sizes, symbols, duplicate trade IDs, duplicate sequences, and malformed rows.
- `downloader.py` wraps providers behind an interface. `MockHistoricalProvider` is deterministic and offline. `DatabentoHistoricalProvider` uses historical APIs only and never starts live streaming.
- `storage.py` coordinates idempotency, atomic generation/import, checksum calculation, quarantine, manifests, and catalog updates.

### Storage directories

Set the storage root with:

```powershell
$env:FXPILOT_ORDERFLOW_DATA_DIR = ".\data"
```

If unset, the service uses the Windows-compatible relative default `./data`. The service creates:

```text
data/
  raw/
  normalized/
  catalogs/
  manifests/
  mock/
  quarantine/
```

All paths are handled with `pathlib.Path`. Imports reject path traversal and files outside the configured data root unless an OPS caller explicitly enables `allow_outside_root` for a trusted local import.

### Environment variables

- `FXPILOT_ORDERFLOW_DATA_DIR` — storage root, default `./data`.
- `FXPILOT_ORDERFLOW_OPS_TOKEN` — required for all mutating OPS endpoints. Send it in the `X-OPS-Token` header; never put tokens in URLs.
- `DATABENTO_API_KEY` — required only for explicit Databento historical downloads. It is never returned by diagnostics or manifests.

### Windows setup

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/ready
```

### Mock workflow

Mock data is deterministic, offline, and clearly marked with `metadata.mock=true`. It contains timestamp, symbol, price, size, side, trade_id, and sequence fields and is never presented as real Databento data.

```powershell
$env:FXPILOT_ORDERFLOW_OPS_TOKEN = "change-me"
$body = @{
  provider = "mock"
  dataset = "GLBX.MDP3"
  schema = "trades"
  symbols = @("6E.FUT")
  start_at = "2026-01-01T00:00:00Z"
  end_at = "2026-01-02T00:00:00Z"
  encoding = "utf-8"
  output_format = "parquet"
  force = $false
  metadata = @{ purpose = "local smoke test" }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ops/historical/download -Headers @{"X-OPS-Token"="change-me"} -Body $body -ContentType "application/json"
```

Repeat the same request with `force=false` to receive the existing validated dataset rather than creating a duplicate file. `force=true` is allowed only through the protected OPS download endpoint and performs a controlled replacement using the same stable dataset ID.

### Databento historical workflow

Databento support is historical-only. The adapter uses `databento.Historical`, does not use live clients, and does not make requests on application startup.

Always estimate first:

```powershell
$env:DATABENTO_API_KEY = "your-key"
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ops/historical/estimate -Headers @{"X-OPS-Token"="change-me"} -Body $body -ContentType "application/json"
```

The estimate response reports provider, dataset, schema, symbols, start/end, requested duration, available size/cost information, warnings, and whether confirmation is required. The estimate endpoint never downloads data.

### Local file import

Protected local import accepts `.dbn`, `.dbn.zst`, `.csv`, and `.parquet`. Imports copy into canonical storage, validate integrity, fingerprint by checksum, catalog metadata, and preserve the original filename.

```powershell
$import = @{
  file_path = ".\data\raw\fixture.csv"
  provider = "local_file"
  dataset = "local-fixtures"
  schema = "trades"
  symbol = "6E.FUT"
  start_at = "2026-01-01T00:00:00Z"
  end_at = "2026-01-02T00:00:00Z"
  metadata = @{ source = "developer fixture" }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/ops/historical/import -Headers @{"X-OPS-Token"="change-me"} -Body $import -ContentType "application/json"
```

### Catalog and diagnostics API

Public read-only endpoints:

- `GET /health`
- `GET /ready`
- `GET /api/historical/datasets`
- `GET /api/historical/datasets/{dataset_id}`
- `GET /api/historical/catalog`
- `GET /api/historical/debug`

Protected OPS endpoints:

- `POST /api/ops/historical/estimate`
- `POST /api/ops/historical/download`
- `POST /api/ops/historical/import`
- `POST /api/ops/historical/validate/{dataset_id}`
- `POST /api/ops/historical/rebuild-catalog`
- `DELETE /api/ops/historical/datasets/{dataset_id}`

### Integrity validation and quarantine

Validation checks file presence, non-empty content, readable format, checksum consistency, required columns, timestamp parse/order status, positive prices, non-negative sizes, symbols, duplicate trade IDs, duplicate sequences, and malformed row counts. Invalid files are moved into `data/quarantine/` and are never silently deleted.

Each cataloged dataset has a manifest at `data/manifests/{dataset_id}.json` containing the original request, file metadata, checksum, record count, validation results, warnings, errors, created time, and provider version when available. API keys are excluded.

### Future Tick Parser contract

`NormalizedTrade` documents the target normalized trade schema for later stages:

- `event_time`
- `receive_time`
- `symbol`
- `instrument_id`
- `price`
- `size`
- `side`
- `trade_id`
- `sequence`
- `source`
- `flags`

This PR intentionally does **not** implement Delta, Cumulative Delta, Volume Profile, POC, VAH, VAL, VWAP, Footprint, Imbalance, Absorption, Market State, or a complete Tick Parser.
