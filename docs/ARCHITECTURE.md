# FXPilot OrderFlow Engine Architecture

FXPilot OrderFlow Engine is a standalone FastAPI service. It is intentionally separated from the FXPilot website backend, MT4 bridge, and trade-advisor code.

## Flow

1. API calls request an order-flow snapshot for an FX symbol such as `EURUSD`.
2. `symbol_mapper` maps the FX symbol to a futures symbol such as `6E`.
3. A provider (`mock` now, `databento` later) returns trades, book levels, and OHLCV rows.
4. Calculators compute delta, cumulative delta, VWAP, volume profile, POC, value area, DOM pressure, absorption, and market state.
5. The API returns an `OrderFlowSnapshot` compatible with future FXPilot backend fields.

## Runtime components

- `providers/`: market-data abstraction and provider implementations.
- `calculators/`: pure calculation modules.
- `storage/`: in-memory cumulative state and test ingest storage.
- `services/`: orchestration, normalization, and symbol mapping.
- `api/`: health, order-flow, and debug routes.
