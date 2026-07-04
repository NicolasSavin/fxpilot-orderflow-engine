# Absorption & Exhaustion Engine

This module is a pure calculation library for detecting aggressive order-flow absorption and move exhaustion. It does not depend on REST, UI, FastAPI, Docker, or any data provider implementation.

## Absorption

Absorption describes a situation where aggressive market orders are present, but price fails to continue in the direction implied by that aggression. The implementation evaluates the latest candle against the previous candle and the current delta.

### Bullish absorption

Bullish absorption is detected when all conditions are true:

1. Delta is strongly negative: `delta <= -(volume * strong_delta_ratio)`.
2. Price does not make a new low: the latest low is greater than or equal to the previous low.
3. The latest close is above the middle of the latest candle range.

This suggests sell aggression is being absorbed by passive buyers.

### Bearish absorption

Bearish absorption is detected when all conditions are true:

1. Delta is strongly positive: `delta >= volume * strong_delta_ratio`.
2. Price does not make a new high: the latest high is less than or equal to the previous high.
3. The latest close is below the middle of the latest candle range.

This suggests buy aggression is being absorbed by passive sellers.

## Exhaustion

Exhaustion describes a new price extreme that is not confirmed by order-flow participation and occurs on declining volume.

### Bullish exhaustion

Bullish exhaustion is detected when all conditions are true:

1. Price makes a new high versus the previous candle.
2. Delta does not confirm the move: latest delta is less than or equal to the previous delta.
3. Latest candle volume is lower than previous candle volume.

### Bearish exhaustion

Bearish exhaustion is detected when all conditions are true:

1. Price makes a new low versus the previous candle.
2. Delta does not confirm the move: latest delta is greater than or equal to the previous delta.
3. Latest candle volume is lower than previous candle volume.

## Confidence

`AbsorptionResult.confidence` is normalized to `0..1`. For candidate setups it is based on the share of satisfied criteria. Fully confirmed signals have confidence `1.0`; no-signal and insufficient-data outcomes return `0.0`.

## Compatibility

`calculate_absorption(candles, delta, volume)` keeps the legacy return contract for existing engine code:

- `"bullish"`
- `"bearish"`
- `"none"`
- `"unavailable"`

For structured diagnostics, use `analyze_absorption(...)`, which returns `AbsorptionResult` with signal flags, exhaustion direction, confidence, reason, and debug details.

## Limitations

- The engine compares only the latest candle with the previous candle.
- Strong delta uses a configurable ratio threshold and should be calibrated per instrument/session.
- Exhaustion requires delta history. Without previous delta input, exhaustion cannot be fully confirmed.
- This module does not classify trades, request Databento data, or perform persistence; callers must provide normalized candles, delta, and volume inputs.
