from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.models.orderflow import OrderFlowSnapshot

DataSource = Literal["databento", "mt4_live", "cache", "unavailable"]

SOURCE_LABELS: dict[DataSource, str] = {
    "databento": "Databento CME",
    "mt4_live": "MT4 Bridge",
    "cache": "Historical Cache",
    "unavailable": "Unavailable",
}

SOURCE_QUALITY: dict[DataSource, int] = {
    "databento": 5,
    "mt4_live": 3,
    "cache": 1,
    "unavailable": 0,
}


@dataclass(frozen=True)
class SourceDecision:
    source: DataSource
    snapshot: OrderFlowSnapshot | None
    reason: str
    age_seconds: float | None = None


class SourceManager:
    """Chooses the best order-flow source for a symbol."""

    mt4_fresh_seconds = 30
    cache_fresh_seconds = 15 * 60

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
            return SourceDecision("databento", databento, "databento_ok_with_volume", self.age_seconds(databento, now))

        mt4_age = self.age_seconds(mt4_live, now)
        if mt4_live is not None and mt4_age is not None and mt4_age <= self.mt4_fresh_seconds:
            return SourceDecision("mt4_live", mt4_live, "mt4_live_snapshot_fresh", mt4_age)

        cache_age = self.age_seconds(cache, now)
        if cache is not None and cache_age is not None and cache_age <= self.cache_fresh_seconds:
            return SourceDecision("cache", cache, "cache_snapshot_available", cache_age)

        if databento is None:
            reason = "databento_unavailable"
        elif databento.provider_status != "ok":
            reason = f"databento_{databento.provider_status}"
        elif databento.volume <= 0:
            reason = "databento_zero_volume"
        else:
            reason = "no_available_source"
        return SourceDecision("unavailable", None, reason, None)

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
        }


source_manager = SourceManager()
