# Databento Integration Plan

The `DatabentoProvider` is a non-live scaffold for future integration.

## Configuration

Set the API key in `.env`:

```env
DATABENTO_API_KEY=your_key
ORDERFLOW_PROVIDER=databento
```

If `DATABENTO_API_KEY` is missing, the provider raises a controlled `provider_not_configured` error and the API responds with `provider_status: not_configured` instead of crashing.

## Future work

- Add Databento historical trade retrieval in `get_recent_trades`.
- Add order-book snapshot retrieval in `get_recent_book`.
- Add OHLCV retrieval in `get_ohlcv`.
- Add live stream support in `stream_trades`.
