# Professional Market State Engine

`app.calculators.market_state.calculate_market_state_result` is a pure library module that combines existing order-flow calculator outputs into a single market-state classification. It does not depend on FastAPI, REST endpoints, Databento, Docker, UI code, or the main FXPilot service layer.

## Inputs

The engine consumes already-calculated model results:

- `VolumeProfileResult`: Value Area High (`vah`), Value Area Low (`val`), POC, total volume, HVN/LVN context.
- `CumDeltaResult`: current/session cumulative delta, slope, momentum, divergence, and bias.
- `VWAPResult`: current VWAP, price position relative to VWAP, distance, and VWAP/delta bias.
- `DOMResult`: DOM pressure, imbalance, liquidity walls, and thin liquidity context.
- `AbsorptionResult`: absorption and exhaustion signals with confidence and debug details.

Callers also pass the current `price`, current `volume`, optional `average_volume`, and optional `price_change_percent`.

## Output

The engine returns `MarketStateResult` with:

- `market_state`: `accumulation`, `distribution`, `trend`, `range`, `expansion`, `exhaustion`, or `unknown`.
- `trend_direction`: `bullish`, `bearish`, or `neutral`.
- `trend_strength`: `strong`, `moderate`, `weak`, or `none`.
- `acceptance`: whether price is inside, above, or below the value area.
- `rejection`: contextual value-area rejection if price is outside VAH/VAL.
- `initiative_side`: side currently initiating activity.
- `responsive_side`: opposing responsive side.
- `confidence`: normalized `0..1` confidence score.
- `reasons`: human-readable reasons for the selected state.
- `debug`: candidate scores and normalized input flags.

## Classification Philosophy

The engine intentionally uses combinations of signals instead of a single indicator. Every classified state requires multiple dimensions of evidence from value area, volume, delta, VWAP, DOM, or absorption/exhaustion.

### Trend

Trend is selected when most directional signals align:

- price is above/below VWAP,
- CumDelta confirms the same side,
- DOM pressure confirms the same side,
- absorption is not blocking the move.

### Accumulation

Accumulation is selected when price trades inside the value area with evidence of passive buying:

- price remains within `VAL..VAH`,
- volume is high versus `average_volume`,
- CumDelta is rising or bullish,
- price direction is weak, suggesting position building instead of vertical markup.

### Distribution

Distribution mirrors accumulation with selling pressure:

- price remains within `VAL..VAH`,
- volume is high versus `average_volume`,
- CumDelta is falling or bearish,
- price direction is weak, suggesting inventory transfer rather than clean markdown.

### Expansion

Expansion is selected when value-area boundaries are broken with participation:

- price breaks above `VAH` or below `VAL`,
- volume is high,
- CumDelta confirms the breakout direction.

### Exhaustion

Exhaustion is selected when the absorption/exhaustion module reports exhaustion or strong absorption. This state can override otherwise constructive trend or expansion signals because exhaustion represents failure or late-stage continuation risk.

### Range

Range is selected when price is accepted inside the value area and there is no high-volume initiative or confirmed value-area breakout.

### Unknown

Unknown is returned when the combined inputs do not provide enough evidence for a stable classification.

## Example

```python
from app.calculators.market_state import calculate_market_state_result

result = calculate_market_state_result(
    price=107.0,
    volume=1500,
    average_volume=1000,
    volume_profile=volume_profile_result,
    cumdelta=cumdelta_result,
    vwap=vwap_result,
    dom=dom_result,
    absorption=absorption_result,
)

print(result.market_state, result.confidence, result.reasons)
```

## Notes

- The module is deterministic and side-effect free.
- The legacy `calculate_market_state` helper remains available for existing internal compatibility.
- The engine can be unit-tested with synthetic model objects and does not require market data providers.
