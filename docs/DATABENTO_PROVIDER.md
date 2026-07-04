# Databento Historical Provider v1

The Databento provider connects the OrderFlow Engine to Databento historical market data through the official Python SDK. This version is historical-only: live streaming is intentionally disabled.

## Configuration

Add the Databento API key to `.env` and select the provider when you want the engine to use Databento instead of the mock provider:

```env
DATABENTO_API_KEY=your_databento_key
ORDERFLOW_PROVIDER=databento
```

The provider reads configuration through `app.config.Settings`, which loads `.env` via `pydantic-settings`.

## Supported symbols

FXPilot symbols are mapped to Databento futures root symbols before requests are sent:

| FXPilot | Databento futures symbol |
| --- | --- |
| `EURUSD` | `6E` |
| `GBPUSD` | `6B` |
| `USDJPY` | `6J` |
| `XAUUSD` | `GC` |

## Historical requests

Implemented methods:

- `get_recent_trades(symbol, start=None, end=None)` uses Databento `timeseries.get_range` with schema `trades`.
- `get_ohlcv(symbol, timeframe, start=None, end=None)` uses Databento `timeseries.get_range` with schema `ohlcv-{timeframe}`; for example `ohlcv-1m`.

Databento rows are normalized into internal models:

- `Trade`
- `Candle`

Order-book live data is not enabled in this phase, so `get_recent_book()` returns an empty list.

## Provider status

Use:

```http
GET /api/orderflow/provider/status
```

Response fields:

```json
{
  "provider": "databento",
  "api_key_present": true,
  "historical_supported": true,
  "live_supported": false,
  "status": "ok"
}
```

Status behavior:

- Missing `DATABENTO_API_KEY`: `status` is `not_configured`; historical methods return empty lists without raising.
- Databento SDK import or request failure: `status` is `unavailable`; historical methods return empty lists without raising.
- Successful historical requests: `status` is `ok`.

## Scope limitations

- Live Databento streaming is not connected.
- Order-flow calculators, models, Docker files, and the main FXPilot application are not changed by this provider integration.
