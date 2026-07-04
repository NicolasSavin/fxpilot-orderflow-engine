# Professional VWAP Engine

The VWAP engine is a pure calculation library for trade streams. It has no REST, UI, FastAPI, Databento, Docker, or provider dependencies.

## Session VWAP

Session VWAP is the classic volume-weighted average price over all trades currently held for a symbol session:

```text
Σ(price × volume) / Σ(volume)
```

`VWAPEngine.process_trade()` and `VWAPEngine.process_trades()` append trades to the in-memory session and return `VWAPResult`. `current_vwap` and `session_vwap` represent the current full-session VWAP.

## Rolling VWAP

Rolling VWAP is calculated over the last `N` trades. The default `rolling_window` is `100`, and it can be overridden when constructing `VWAPEngine` or calling `calculate_vwap_result()`.

## Anchored VWAP

Anchored VWAP is calculated from a caller-provided timestamp forward. Pass `anchor_timestamp` to `VWAPEngine` or to an individual calculation call. Trades before the anchor are excluded from `anchored_vwap`; when no anchor is supplied, anchored VWAP matches session VWAP.

## Distance and position

`VWAPResult` includes:

- `distance_to_vwap`: `price - session_vwap`
- `distance_percent`: `(distance_to_vwap / session_vwap) × 100`
- `price_position`: `above_vwap`, `below_vwap`, or `at_vwap`

Price position uses a configurable tolerance (`price_tolerance`, default `1e-9`) so near-equal prices can be classified as `at_vwap`.

## Bias

Bias combines price location with a CumDelta bias supplied by the caller:

- price above VWAP and CumDelta `bullish` → `bullish`
- price below VWAP and CumDelta `bearish` → `bearish`
- all other combinations → `neutral`

The VWAP engine does not calculate CumDelta itself; it accepts the CumDelta state as input to keep VWAP independent and reusable.

## Usage

```python
from app.calculators.vwap import VWAPEngine
from app.models.market import Trade

engine = VWAPEngine(rolling_window=100)
result = engine.process_trade(Trade(symbol="6E", price=1.08, size=10), cumdelta_bias="bullish")

print(result.session_vwap)
print(result.rolling_vwap)
print(result.anchored_vwap)
print(result.bias)
```

For stateless one-off calculations, use `calculate_vwap_result(trades)`.

## Limitations

- The engine relies on the caller to define session boundaries and call `reset_session=True` or `reset_session()` when needed.
- It stores trades in memory through `MemoryStore`; persistence and pruning are the caller's responsibility.
- Anchors are timestamp-based and use the trade timestamps exactly as provided.
- The engine does not fetch market data and does not infer CumDelta; those are separate responsibilities.
