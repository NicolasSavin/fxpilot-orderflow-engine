from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

class DatasetStatus(StrEnum):
    REQUESTED='REQUESTED'; DOWNLOADING='DOWNLOADING'; STORED='STORED'; VALIDATED='VALIDATED'; INVALID='INVALID'; QUARANTINED='QUARANTINED'; FAILED='FAILED'

Provider = Literal['databento','mock','local_file']
OutputFormat = Literal['dbn','csv','parquet']

class HistoricalDataset(BaseModel):
    id: str
    provider: str
    dataset: str
    schema: str
    symbol: str
    instrument_id: str | None = None
    start_at: datetime
    end_at: datetime
    encoding: str = 'utf-8'
    compression: str | None = None
    source_format: str
    stored_format: str
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    record_count: int
    status: DatasetStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

class HistoricalDownloadRequest(BaseModel):
    provider: Provider
    dataset: str
    schema: str = 'trades'
    symbols: list[str]
    start_at: datetime
    end_at: datetime
    encoding: str = 'utf-8'
    compression: str | None = None
    output_format: OutputFormat = 'parquet'
    force: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator('symbols')
    @classmethod
    def symbols_required(cls, v):
        if not v: raise ValueError('at least one symbol is required')
        return v

class LocalImportRequest(BaseModel):
    file_path: str
    provider: Provider = 'local_file'
    dataset: str = 'local'
    schema: str = 'trades'
    symbol: str
    start_at: datetime
    end_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

class NormalizedTrade(BaseModel):
    event_time: datetime
    receive_time: datetime | None = None
    symbol: str
    instrument_id: str | None = None
    price: float
    size: float
    side: Literal['B','S','N','BUY','SELL']
    trade_id: str
    sequence: int
    source: str
    flags: dict[str, Any] = Field(default_factory=dict)
