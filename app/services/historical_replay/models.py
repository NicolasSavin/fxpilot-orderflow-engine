from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

class ReplayStatus(StrEnum):
    CREATED='CREATED'; VALIDATING='VALIDATING'; READY='READY'; RUNNING='RUNNING'; PAUSED='PAUSED'; COMPLETED='COMPLETED'; CANCELLED='CANCELLED'; FAILED='FAILED'
class ReplayMode(StrEnum):
    BATCH='BATCH'; STEP='STEP'; TIMED='TIMED'
class VolumeType(StrEnum):
    EXCHANGE_TRADE_VOLUME='exchange_trade_volume'; BROKER_TICK_VOLUME='broker_tick_volume'; SYNTHETIC='synthetic'; UNKNOWN='unknown'

class ReplayProvenance(BaseModel):
    dataset_id: str; provider: str; venue: str | None = None; source_format: str; data_quality: str = 'unknown'
    volume_type: str = VolumeType.UNKNOWN; is_proxy: bool = True; is_exchange_volume: bool = False
    replay_mode: ReplayMode; normalization_warnings: list[str] = Field(default_factory=list)

class HistoricalReplayRequest(BaseModel):
    dataset_id: str; symbol: str | None = None; start_at: datetime | None = None; end_at: datetime | None = None
    mode: ReplayMode = ReplayMode.BATCH; playback_speed: float = 1.0; chunk_size: int = Field(default=1000, ge=1, le=100000)
    reset_session: bool = True; persist_snapshots: bool = False; metadata: dict[str, Any] = Field(default_factory=dict)

class ReplayCandle(BaseModel):
    open: float; high: float; low: float; close: float; volume: float; trade_count: int
    buy_volume: float = 0; sell_volume: float = 0; delta: float = 0; start_at: datetime; end_at: datetime
    volume_type: str; is_proxy: bool

class HistoricalReplayState(BaseModel):
    replay_id: str; dataset_id: str; status: ReplayStatus = ReplayStatus.CREATED; mode: ReplayMode; symbol: str | None = None
    start_at: datetime | None = None; end_at: datetime | None = None; rows_total: int = 0; rows_processed: int = 0
    rows_skipped: int = 0; malformed_rows: int = 0; duplicate_rows: int = 0; current_event_time: datetime | None = None
    progress_percent: float = 0; started_at: datetime | None = None; completed_at: datetime | None = None
    last_error: str | None = None; warnings: list[str] = Field(default_factory=list); cursor: int = 0
    request: dict[str, Any] = Field(default_factory=dict)

class HistoricalReplayResult(BaseModel):
    replay_id: str; dataset_id: str; symbol: str; status: ReplayStatus; trades_processed: int = 0; candles_built: int = 0
    first_event_time: datetime | None = None; last_event_time: datetime | None = None; duration_ms: int = 0
    final_snapshot: dict[str, Any] | None = None; snapshot_count: int = 0; provenance: ReplayProvenance
    warnings: list[str] = Field(default_factory=list); errors: list[str] = Field(default_factory=list)
