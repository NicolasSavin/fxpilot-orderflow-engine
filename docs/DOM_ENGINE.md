# DOM / Order Book Imbalance Engine

The DOM engine is a pure calculation module for depth-of-market and order-book imbalance analysis. It is designed to work with normalized order-book levels and can later consume Databento MBP-1 or MBP-N data after provider-side normalization.

## DOM pressure

DOM pressure summarizes whether visible liquidity is skewed toward bids or asks:

- `bullish`: bid-side liquidity dominates the visible book.
- `bearish`: ask-side liquidity dominates the visible book.
- `neutral`: neither side has enough dominance.
- `unavailable`: the book is empty or has no visible liquidity.

The engine calculates:

```text
bid_total = sum(bid_size)
ask_total = sum(ask_size)
total_liquidity = bid_total + ask_total
```

## Imbalance ratio

`imbalance_ratio` measures the bid share of total visible liquidity:

```text
imbalance_ratio = bid_total / (bid_total + ask_total)
```

Classification thresholds:

- `imbalance_ratio > 0.58` -> `bullish`
- `imbalance_ratio < 0.42` -> `bearish`
- otherwise -> `neutral`

The legacy `calculate_dom_pressure(book)` API remains available and returns the compatible dictionary keys `dom_pressure` and `imbalance`. Internally it uses the new DOM engine.

## Liquidity wall

A liquidity wall is the largest visible single level on either side of the book. The engine identifies:

- `liquidity_wall_side`: `bid`, `ask`, or `none`
- `liquidity_wall_price`: price of the largest visible level
- `liquidity_wall_strength`: largest level size divided by the average visible side-level size

This is a relative measure, not a guarantee that the displayed size will remain in the market.

## Thin liquidity

Thin liquidity highlights the side where visible depth is noticeably weaker:

- `above`: ask-side liquidity is weak compared with bids.
- `below`: bid-side liquidity is weak compared with asks.
- `none`: no side is weak enough to flag.

The current implementation flags a side as thin when that side has less than 65% of the opposite side's total visible liquidity.

## Limitations

- The engine only analyzes visible book depth passed into the calculation.
- It does not infer hidden liquidity, iceberg orders, spoofing, or order cancellations.
- It does not connect to REST, UI, FastAPI, Docker, or Databento directly.
- MBP-1 data provides less depth context than MBP-N, so wall and thin-liquidity signals depend on the number of normalized levels provided.
- DOM pressure is a liquidity imbalance signal and should be combined with trade flow, volatility, and session context before use in execution logic.
