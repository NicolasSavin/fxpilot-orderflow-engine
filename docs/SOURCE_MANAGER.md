# OrderFlow Source Manager

The OrderFlow Engine automatically selects the best available data source for each requested symbol without changing scoring, market-state, or AI logic.

## Priority

Sources are evaluated in this order:

1. **Databento CME** (`databento`) when the Databento provider status is `ok` and the snapshot has `volume > 0`.
2. **MT4 Bridge** (`mt4_live`) when a live snapshot exists and is no older than 30 seconds.
3. **Historical Cache** (`cache`) when a cached snapshot exists and is no older than 15 minutes.
4. **Unavailable** (`unavailable`) when no valid Databento, MT4 live, or cache snapshot exists.

## Source Quality

Each `OrderFlowSnapshot` includes metadata that the website can use to show data provenance and confidence:

| Source | Label | Quality |
| --- | --- | ---: |
| `databento` | `Databento CME` | 5 |
| `mt4_live` | `MT4 Bridge` | 3 |
| `cache` | `Historical Cache` | 1 |
| `unavailable` | `Unavailable` | 0 |

The metadata fields are:

- `data_source`
- `data_source_label`
- `data_source_quality`
- `data_source_status`
- `data_source_age_seconds`
- `data_source_reason`

## Fallback Behavior

`GET /api/orderflow/latest?symbol=EURUSD` first attempts the configured provider. A Databento result is selected only when it is healthy and has real volume. If Databento is unavailable, not configured, unlicensed for the requested data, or returns zero volume, the engine falls back to a fresh MT4 live snapshot. If MT4 live data is stale or missing, the engine falls back to the latest cache snapshot. If no source is available, the endpoint still returns a backward-compatible `OrderFlowSnapshot` with `data_source="unavailable"`.

`POST /api/orderflow/live` stores the most recent MT4 Bridge snapshot per symbol. Subsequent `/api/orderflow/latest` calls will return that MT4 snapshot when Databento is not providing valid data and the live snapshot is fresh.

## Debugging Source Selection

Use:

```http
GET /api/orderflow/source/status?symbol=EURUSD
```

The response includes the active source, source-specific availability blocks for Databento, MT4 live, and cache, plus the decision reason.

## Website Display Guidance

The website should display `data_source_label` near order-flow values and can use `data_source_quality` for visual severity:

- Quality `5`: primary/healthy styling.
- Quality `3`: live fallback styling.
- Quality `1`: stale or historical fallback warning.
- Quality `0`: unavailable/error state.

For troubleshooting or tooltips, display `data_source_age_seconds` and `data_source_reason`.
