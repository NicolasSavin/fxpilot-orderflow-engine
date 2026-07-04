from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.config import get_settings
from app.models.orderflow import OrderFlowSnapshot
from app.services.symbol_mapper import to_futures_symbol
from app.storage.memory_store import store

DataSource = Literal["databento", "mt4_live", "cache", "unavailable"]

SOURCE_LABELS: dict[DataSource, str] = {
    "databento": "Databento",
    "mt4_live": "MT4 Live",
    "cache": "Cache",
    "unavailable": "Unavailable",
}

SOURCE_QUALITY: dict[DataSource, int] = {
    "databento": 100,
    "mt4_live": 75,
    "cache": 25,
    "unavailable": 0,
}


@dataclass(frozen=True)
class SourceDecision:
    source: DataSource
    snapshot: OrderFlowSnapshot | None
    reason: str
    age_seconds: float | None = None


class SourceManager:
    """Centralized OrderFlow provider-selection policy.

    Selection is intentionally strict and priority ordered:
    Databento -> MT4 Live -> Cache -> Unavailable.
    MT4 snapshots are only considered when Databento cannot provide a usable
    OrderFlow snapshot for the requested symbol.
    """

    cache_fresh_seconds = 15 * 60

    @property
    def mt4_fresh_seconds(self) -> int:
        return get_settings().mt4_live_fresh_seconds

    def age_seconds(self, snapshot: OrderFlowSnapshot | None, now: datetime | None = None) -> float | None:
        if snapshot is None:
            return None
        now = now or datetime.now(timezone.utc)
        timestamp = snapshot.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return max(0.0, (now - timestamp).total_seconds())

    def databento_available(self, snapshot: OrderFlowSnapshot | None) -> bool:
        return (
            snapshot is not None
            and snapshot.provider == "databento"
            and snapshot.provider_status == "ok"
            and snapshot.orderflow_available is True
            and snapshot.volume > 0
        )

    def choose(
        self,
        *,
        databento: OrderFlowSnapshot | None = None,
        mt4_live: OrderFlowSnapshot | None = None,
        cache: OrderFlowSnapshot | None = None,
        now: datetime | None = None,
    ) -> SourceDecision:
        now = now or datetime.now(timezone.utc)
        if self.databento_available(databento):
            return SourceDecision("databento", databento, "databento_orderflow_available", self.age_seconds(databento, now))

        mt4_age = self.age_seconds(mt4_live, now)
        if mt4_live is not None and mt4_age is not None and mt4_age <= self.mt4_fresh_seconds:
            return SourceDecision("mt4_live", mt4_live, "databento_unusable_mt4_live_fresh", mt4_age)

        cache_age = self.age_seconds(cache, now)
        if cache is not None and cache_age is not None and cache_age <= self.cache_fresh_seconds:
            return SourceDecision("cache", cache, "databento_unusable_mt4_stale_or_missing_cache_available", cache_age)

        return SourceDecision("unavailable", None, self._unavailable_reason(databento, mt4_age, cache_age), None)

    def select_best_snapshot(
        self,
        symbol: str,
        databento_snapshot: OrderFlowSnapshot | None = None,
        *,
        now: datetime | None = None,
    ) -> SourceDecision:
        """Select the best snapshot for a symbol using the global in-memory store."""
        futures = to_futures_symbol(symbol)
        return self.choose(
            databento=databento_snapshot,
            mt4_live=store.live_snapshot(futures),
            cache=store.cache_snapshot(futures),
            now=now,
        )

    def _unavailable_reason(
        self,
        databento: OrderFlowSnapshot | None,
        mt4_age: float | None,
        cache_age: float | None,
    ) -> str:
        reasons: list[str] = []
        if databento is None:
            reasons.append("databento_unavailable")
        elif databento.provider_status != "ok":
            reasons.append(f"databento_{databento.provider_status}")
        elif not databento.orderflow_available:
            reasons.append("databento_orderflow_unavailable")
        elif databento.volume <= 0:
            reasons.append("databento_zero_volume")
        if mt4_age is None:
            reasons.append("mt4_missing")
        elif mt4_age > self.mt4_fresh_seconds:
            reasons.append("mt4_stale")
        if cache_age is None:
            reasons.append("cache_missing")
        elif cache_age > self.cache_fresh_seconds:
            reasons.append("cache_stale")
        return ";".join(reasons) or "no_available_source"

    def apply_metadata(
        self,
        snapshot: OrderFlowSnapshot,
        source: DataSource,
        *,
        reason: str,
        age_seconds: float | None = None,
    ) -> OrderFlowSnapshot:
        return snapshot.model_copy(
            update={
                "data_source": source,
                "data_source_label": SOURCE_LABELS[source],
                "data_source_quality": SOURCE_QUALITY[source],
                "data_source_status": "ok" if source != "unavailable" else "unavailable",
                "data_source_age_seconds": age_seconds,
                "data_source_reason": reason,
            }
        )

    def status_block(self, snapshot: OrderFlowSnapshot | None, now: datetime | None = None) -> dict:
        age = self.age_seconds(snapshot, now)
        return {
            "available": snapshot is not None,
            "provider": snapshot.provider if snapshot else None,
            "provider_status": snapshot.provider_status if snapshot else None,
            "volume": snapshot.volume if snapshot else 0,
            "age_seconds": age,
            "data_source": snapshot.data_source if snapshot else None,
            "fresh": age is not None and age <= self.mt4_fresh_seconds if snapshot and snapshot.data_source == "mt4_live" else snapshot is not None,
        }


source_manager = SourceManager()
