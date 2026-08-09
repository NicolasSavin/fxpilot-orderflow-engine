# FXPilot MT4 Bridge v2

The advisor `FXPilot_MT4_Bridge.mq4` runs on one MT4 chart and sends data for:

- EURUSD
- GBPUSD
- USDJPY
- XAUUSD

Timeframes: M15, H1, H4, D1, W1. Ten candles per stream are sent every 60 seconds by default. Tick direction, approximate delta and spread statistics are sampled once per second.

## Server configuration

Set the same secret value in both places:

1. Render environment variable for `fxpilot-orderflow-engine`: `MT4_BRIDGE_TOKEN`.
2. Advisor input: `ApiToken`.

The advisor posts to:

`https://fxpilot-orderflow-engine.onrender.com/api/mt4/batch`

Do not put the token in the URL.

The persistent stream registry is stored at:

`$FXPILOT_ORDERFLOW_DATA_DIR/mt4_streams.json`

## MT4 installation

1. Copy `FXPilot_MT4_Bridge.mq4` to `MQL4/Experts`.
2. Compile it in MetaEditor.
3. In MT4 open Tools -> Options -> Expert Advisors.
4. Enable WebRequest for `https://fxpilot-orderflow-engine.onrender.com`.
5. Attach the advisor to one chart only.
6. Enter `ApiToken` and enable AutoTrading.
7. If the broker uses suffixes, set `BrokerSymbolsCsv`, for example `EURUSD.a,GBPUSD.a,USDJPY.a,XAUUSD.a`.

Diagnostics:

- `GET /api/mt4/status` reports all 20 symbol/timeframe streams.
- `GET /api/orderflow/source/status?symbol=EURUSD` reports which source was selected.
- `GET /api/orderflow/latest?symbol=EURUSD` returns the current OrderFlow snapshot.

Paid Databento Live, options feeds and futures subscriptions are not required by this bridge.
