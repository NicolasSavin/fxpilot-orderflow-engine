# Volume Profile Engine

## Purpose

The Volume Profile engine is a pure calculation library. It consumes normalized trade objects and produces a price-level volume distribution that can be reused for historical batches and live Databento trade streams without depending on FastAPI, REST, UI, Docker, or a data provider.

## Input data

`calculate_volume_profile(trades, tick_size, value_area_percent=0.70)` accepts:

- `trades`: ordered `Trade` records with `price`, `size`, and optional `side` (`buy`, `sell`, or `unknown`).
- `tick_size`: the minimum price increment for the instrument.
- `value_area_percent`: target share of total volume for the value area. The professional default is `0.70`.

All prices are converted to integer tick indexes with decimal arithmetic before aggregation. This avoids direct floating-point price comparison and ensures all profile levels align to `tick_size`.

## Output data

The result contains:

- `profile_levels`: sorted price levels. Each level contains `price`, `total_volume`, `buy_volume`, `sell_volume`, `delta`, and `trades_count`.
- `total_volume`: sum of all level volumes.
- `buy_volume`: sum of aggressive buy volume.
- `sell_volume`: sum of aggressive sell volume.
- `delta`: `buy_volume - sell_volume`.
- `poc`: Point of Control, the price level with the highest total volume.
- `vah`: Value Area High.
- `val`: Value Area Low.
- `hvn_levels`: High Volume Nodes, detected as local maxima.
- `lvn_levels`: Low Volume Nodes, detected as local minima.

Backward-compatible `volume_by_price` and `profile` mappings are also returned for existing calculation callers.

## Algorithm

1. Validate `tick_size` and convert every trade price into an integer tick index.
2. Aggregate trades by tick index.
3. For each level, accumulate total volume, buy volume, sell volume, delta, and trade count.
4. Select POC as the level with maximum `total_volume`.
5. Build the 70% Value Area using the classic expansion algorithm:
   - Start at POC.
   - Compare the adjacent level above and below the current area.
   - Include the side with the larger volume.
   - Repeat until accumulated volume reaches at least 70% of total volume or no levels remain.
6. Detect HVN levels as local volume maxima compared with neighboring levels.
7. Detect LVN levels as local volume minima compared with neighboring levels.

## Complexity

Let `n` be the number of trades and `m` the number of distinct price levels.

- Price normalization and aggregation: `O(n)`.
- Sorting price levels: `O(m log m)`.
- POC, Value Area, HVN, and LVN scans: `O(m)`.
- Total complexity: `O(n + m log m)`.
- Memory complexity: `O(m)`.
