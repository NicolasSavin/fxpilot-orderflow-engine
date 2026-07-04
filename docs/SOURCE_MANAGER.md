# OrderFlow Source Manager

The OrderFlow Engine uses `SourceManager.select_best_snapshot(symbol)` to choose a single snapshot for the UI. Selection is automatic: the website does not need to switch providers manually.

## Final Selection Priority

Sources are always evaluated in this order:

1. **Databento** (`databento`)
2. **MT4 Live Bridge** (`mt4_live`)
3. **Cached snapshot** (`cache`)
4. **Unavailable** (`unavailable`)

MT4 Live is strictly a fallback. If Databento returns a valid OrderFlow snapshot, MT4 must not override it, even if MT4 has a newer snapshot.

## Valid Databento Snapshot

Databento is selected when all of the following are true:

- `provider == "databento"`
- `provider_status == "ok"`
- `orderflow_available == true`
- `volume > 0`

If Databento is unavailable, not configured, missing subscription access, times out, raises an exception, returns `orderflow_available=false`, or returns no usable volume, the SourceManager automatically evaluates the MT4 Live Bridge.

## MT4 Live Fallback

MT4 Live is selected only when Databento is unusable and the in-memory MT4 snapshot is fresh. Freshness is configurable with:

```env
MT4_LIVE_FRESH_SECONDS=30
```

Successful `POST /api/orderflow/live` requests always update the in-memory live snapshot for the mapped futures symbol. That latest MT4 snapshot can then be selected by `GET /api/orderflow/latest` when Databento cannot provide usable OrderFlow.

## Cache Fallback

If Databento is unusable and MT4 is missing or stale, SourceManager falls back to the cached snapshot when one is available within the cache freshness window. Cached data is marked as `data_source="cache"` so consumers can distinguish it from primary or live fallback data.

## Snapshot Metadata

Every returned `OrderFlowSnapshot` includes provider-selection metadata:

- `data_source`
- `data_source_label`
- `data_source_quality`
- `data_source_status`
- `data_source_reason`
- `data_source_age_seconds`

| Source | `data_source` | Label | Quality |
| --- | --- | --- | ---: |
| Databento | `databento` | `Databento` | 100 |
| MT4 Live Bridge | `mt4_live` | `MT4 Live` | 75 |
| Cached snapshot | `cache` | `Cache` | 25 |
| Unavailable | `unavailable` | `Unavailable` | 0 |

## Diagnostics

Use:

```http
GET /api/orderflow/source/status?symbol=EURUSD
```

The response includes:

- `selected_source`
- `databento_status`
- `mt4_status`
- `cache_status`
- `last_mt4_update`
- `last_databento_update`
- `selection_reason`

Backward-compatible aliases are also retained for older clients: `active_source`, `databento`, `mt4_live`, `cache`, and `decision_reason`.

## Endpoint Behavior

`GET /api/orderflow/latest` calls the Databento provider first, then delegates all selection to SourceManager:

```text
Databento valid -> return Databento snapshot
Databento unusable + fresh MT4 -> return MT4 Live snapshot
Databento unusable + stale/missing MT4 + cache -> return Cache snapshot
No usable source -> return Unavailable snapshot
```

This keeps the UI simple: display `data_source_label` and use `data_source_quality`/`data_source_status` to style the result.
