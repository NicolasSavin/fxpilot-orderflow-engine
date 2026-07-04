# Databento Historical Smoke Test

This diagnostic script verifies that the Databento **Historical** provider can fetch trades and pass them through the OrderFlow Engine calculators. It does not change the FastAPI API, does not use live Databento streaming, and does not require a live subscription.

## Prerequisites

1. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

2. Add a historical Databento API key to `.env` in the repository root:

   ```powershell
   "DATABENTO_API_KEY=your_key_here" | Out-File -FilePath .env -Encoding utf8
   ```

## Run on Windows PowerShell

From the repository root:

```powershell
python scripts/databento_smoke_test.py --symbol EURUSD --start 2026-07-01T00:00:00 --end 2026-07-01T01:00:00
```

The script treats timestamps without an offset as UTC. You can also pass `Z` or an explicit offset, for example `2026-07-01T00:00:00Z`.

## Choosing `symbol`

Pass the same FXPilot symbols used by the engine. The Databento provider maps them to futures symbols internally:

| FXPilot symbol | Databento raw futures symbol |
| --- | --- |
| `EURUSD` | `6E` |
| `GBPUSD` | `6B` |
| `USDJPY` | `6J` |
| `XAUUSD` | `GC` |

Start with a short liquid window and a known mapped symbol such as `EURUSD`.

## Choosing `start` and `end`

Use a small historical range first, such as 15 minutes to 1 hour. Historical availability depends on the Databento dataset, symbol, date, and your Databento account permissions. If you receive zero trades, try a different active trading hour or a different symbol.

Example:

```powershell
python scripts/databento_smoke_test.py --symbol GBPUSD --start 2026-07-01T13:00:00 --end 2026-07-01T14:00:00
```

## Possible errors

- `DATABENTO_API_KEY is not configured` — `.env` does not contain `DATABENTO_API_KEY`, or the variable is empty.
- `databento package is not installed. Run pip install databento` — the Databento Python SDK is missing from the active Python environment.
- Empty `trades` / `trade_count: 0` — the request succeeded but no trades were returned for that symbol and time window, or the account does not have access to that historical range.
- Provider status `unavailable` — Databento rejected the request, the SDK call failed, network access failed, or the selected range/dataset/symbol is not available.

## Example result

The command prints a JSON snapshot containing the fetched trade count and the calculators requested for this smoke test:

```json
{
  "symbol": "EURUSD",
  "futures_symbol": "6E",
  "trade_count": 42,
  "volume_profile": {
    "total_volume": 103.0,
    "poc": 1.145,
    "vah": 1.1452,
    "val": 1.1448
  },
  "cumdelta": {
    "current_cumdelta": 17.0,
    "bias": "bullish"
  },
  "vwap": {
    "current_vwap": 1.1451,
    "price_position": "above_vwap"
  },
  "market_state": {
    "market_state": "trend",
    "trend_direction": "bullish"
  }
}
```

This is a manual smoke test, not production integration or an automated live-data workflow.
