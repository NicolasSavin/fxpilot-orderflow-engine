# CumDelta Engine

CumDelta (cumulative delta) is the running sum of aggressive buy volume minus aggressive sell volume. It is an order-flow measure used to understand whether traded volume is being lifted on the ask or hit on the bid over time.

This repository implements CumDelta as a pure calculation library in `app/calculators/cumdelta.py`. It is independent from FastAPI, Databento, REST endpoints, Docker, and UI code.

## Data model

`CumDeltaPoint` stores one calculated point:

- `timestamp`
- `symbol`
- `delta`
- `cumdelta`
- `buy_volume`
- `sell_volume`
- `total_volume`

`CumDeltaResult` stores the latest engine state:

- current delta and cumulative delta
- session cumulative delta
- rolling cumulative delta
- buy, sell, and total volume
- delta slope
- delta momentum
- divergence
- bias

## Session CumDelta

Session CumDelta is the cumulative sum of delta values inside the active trading session.

Use `reset_session=True` when a new session starts. The engine clears the symbol's session points and starts the next cumulative value from the supplied update or trade.

The backward-compatible API is still available:

```python
from app.calculators.cumdelta import update_cumdelta

value = update_cumdelta("6E", 5, reset_session=False)
```

## Rolling CumDelta

Rolling CumDelta is calculated over the latest `N` CumDelta points. The default rolling window is `100` points. It can be changed when constructing the engine:

```python
from app.calculators.cumdelta import CumDeltaEngine

engine = CumDeltaEngine(rolling_window=50)
```

Rolling values are useful for local order-flow pressure because they focus on recent trades or aggregated points instead of the whole session.

## Delta slope

Delta slope describes the latest CumDelta direction:

- `rising`: latest CumDelta is above the previous point
- `falling`: latest CumDelta is below the previous point
- `flat`: latest CumDelta is unchanged, or there is not enough history

## Delta momentum

Delta momentum describes whether the latest CumDelta change is accelerating or decelerating in the same direction:

- `strengthening`: absolute CumDelta change is larger than the previous change
- `weakening`: absolute CumDelta change is smaller than the previous change
- `neutral`: insufficient history, flat movement, or a direction flip

## Divergence

The engine detects simple price/CumDelta divergence when price is provided with each update or trade.

Bullish divergence:

- price makes a lower low
- CumDelta makes a higher low

Bearish divergence:

- price makes a higher high
- CumDelta makes a lower high

If there is not enough price-tagged history, the engine returns `none`.

## Bias

Bias is intentionally simple:

- `bullish`: CumDelta slope is `rising` and the current delta is positive
- `bearish`: CumDelta slope is `falling` and the current delta is negative
- `neutral`: all other states

## Limitations

- Divergence detection is intentionally simple and uses recent extrema from available price-tagged points; it is not a full swing/pivot engine.
- Unknown trade side classification uses a basic tick rule when processing `Trade` objects.
- Rolling CumDelta operates on stored points, which may be individual trades or caller-provided aggregated updates.
- Session boundaries must be supplied by the caller with `reset_session=True`.
