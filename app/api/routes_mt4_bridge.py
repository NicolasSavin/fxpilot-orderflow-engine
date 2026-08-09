from __future__ import annotations

import hmac
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.calculators.cumdelta import CumDeltaEngine
from app.models.market import BookLevel, Candle, Trade
from app.services.engine import engine
from app.services.source_manager import source_manager
from app.services.symbol_mapper import to_futures_symbol
from app.storage.memory_store import store

router = APIRouter(prefix="/api/mt4", tags=["mt4-bridge"])

SUPPORTED_SYMBOLS = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD"}
SUPPORTED_TIMEFRAMES = {"M15", "H1", "H4", "D1", "W1"}
DATA_DIR = Path(os.getenv("FXPILOT_ORDERFLOW_DATA_DIR", "./data")).expanduser().resolve()
STREAMS_PATH = DATA_DIR / "mt4_streams.json"
STORE_LOCK = Lock()


class MT4Candle(BaseModel):
    time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "MT4Candle":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is below OHLC values")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is above OHLC values")
        return self


class TickStats(BaseModel):
    samples: int = Field(default=0, ge=0)
    up_ticks: int = Field(default=0, ge=0)
    down_ticks: int = Field(default=0, ge=0)
    unchanged_ticks: int = Field(default=0, ge=0)
    delta: int = 0
    spread_avg_points: float | None = Field(default=None, ge=0)
    spread_max_points: float | None = Field(default=None, ge=0)
    last_bid: float = Field(gt=0)
    last_ask: float = Field(gt=0)


class MT4Batch(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    source: Literal["mt4"] = "mt4"
    symbol: str
    broker_symbol: str = ""
    timeframe: str
    sent_at: int = Field(gt=0)
    broker: str = ""
    account: str = ""
    candles: list[MT4Candle] = Field(min_length=1, max_length=100)
    ticks: TickStats

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        normalized = value.upper().replace("/", "").replace("-", "").strip()
        if normalized not in SUPPORTED_SYMBOLS:
            raise ValueError("unsupported symbol")
        return normalized

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in SUPPORTED_TIMEFRAMES:
            raise ValueError("unsupported timeframe")
        return normalized


class MT4BatchEnvelope(BaseModel):
    packets: list[MT4Batch] = Field(min_length=1, max_length=20)


def _authenticate(token: str | None) -> None:
    expected = os.getenv("MT4_BRIDGE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="MT4_BRIDGE_TOKEN is not configured")
    supplied = str(token or "").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _read_streams() -> dict:
    try:
        payload = json.loads(STREAMS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_streams(payload: dict) -> None:
    STREAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mt4_streams.", suffix=".tmp", dir=str(STREAMS_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(STREAMS_PATH)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _publish_snapshot(payload: MT4Batch):
    futures = to_futures_symbol(payload.symbol)
    timestamp = datetime.now(timezone.utc)
    candles = [
        Candle(
            symbol=futures,
            timestamp=datetime.fromtimestamp(item.time, timezone.utc),
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            volume=float(item.tick_volume),
        )
        for item in payload.candles
    ]
    ticks = payload.ticks
    trades: list[Trade] = []
    if ticks.up_ticks:
        trades.append(Trade(symbol=futures, timestamp=timestamp, price=ticks.last_ask, size=float(ticks.up_ticks), side="buy"))
    if ticks.down_ticks:
        trades.append(Trade(symbol=futures, timestamp=timestamp, price=ticks.last_bid, size=float(ticks.down_ticks), side="sell"))
    if not trades:
        trades.append(Trade(symbol=futures, timestamp=timestamp, price=(ticks.last_bid + ticks.last_ask) / 2, size=max(float(ticks.samples), 1.0), side="unknown"))

    book = [
        BookLevel(price=ticks.last_bid, bid_size=float(ticks.down_ticks), ask_size=0),
        BookLevel(price=ticks.last_ask, bid_size=0, ask_size=float(ticks.up_ticks)),
    ]
    store.ingest(futures, trades=trades, book=book, candles=candles)
    store.trades[futures] = store.trades.get(futures, [])[-2000:]
    store.candles[futures] = store.candles.get(futures, [])[-500:]
    delta_engine = CumDeltaEngine(memory_store=store)
    for trade in trades:
        delta_engine.process_trade(trade)

    snapshot = engine._build_snapshot(
        requested_symbol=payload.symbol,
        futures=futures,
        trades=store.trades.get(futures, []),
        book=store.books.get(futures, []),
        candles=store.candles.get(futures, []),
        provider_name=engine.provider.name,
        status="ok",
        timestamp=timestamp,
        provider_debug={
            "provider": engine.provider.name,
            "source": "mt4_multitimeframe_bridge",
            "broker_symbol": payload.broker_symbol,
            "timeframe": payload.timeframe,
            "samples": ticks.samples,
            "calculators_executed": True,
        },
    )
    snapshot = source_manager.apply_metadata(snapshot, "mt4_live", reason="mt4_batch_ingested", age_seconds=0)
    store.set_mt4_live_snapshot(futures, snapshot)
    return snapshot


@router.post("/batch")
def ingest_mt4_batch(
    payload: MT4Batch,
    x_fxpilot_mt4_token: Annotated[str | None, Header()] = None,
) -> dict:
    _authenticate(x_fxpilot_mt4_token)
    snapshot = _publish_snapshot(payload) if payload.timeframe == "M15" else None
    received_at = datetime.now(timezone.utc)
    stream_key = f"{payload.symbol}:{payload.timeframe}"
    with STORE_LOCK:
        registry = _read_streams()
        streams = registry.get("streams") if isinstance(registry.get("streams"), dict) else {}
        item = payload.model_dump()
        item["received_at"] = received_at.isoformat()
        if snapshot is not None:
            item["snapshot"] = snapshot.model_dump(mode="json")
        streams[stream_key] = item
        _write_streams({"schema_version": "2.0", "updated_at": received_at.isoformat(), "streams": streams})
    return {
        "ok": True,
        "stream": stream_key,
        "candles_received": len(payload.candles),
        "data_source": snapshot.data_source if snapshot is not None else "mt4_multitimeframe",
        "orderflow_snapshot_updated": snapshot is not None,
        "received_at": received_at.isoformat(),
    }


@router.post("/batch-all")
def ingest_mt4_batch_all(
    payload: MT4BatchEnvelope,
    x_fxpilot_mt4_token: Annotated[str | None, Header()] = None,
) -> dict:
    _authenticate(x_fxpilot_mt4_token)
    results = []
    for packet in payload.packets:
        result = ingest_mt4_batch(packet, x_fxpilot_mt4_token)
        results.append(result)
    return {
        "ok": all(bool(item.get("ok")) for item in results),
        "packets_received": len(results),
        "streams": [item.get("stream") for item in results],
        "results": results,
    }


@router.get("/timeframes/{symbol}")
def mt4_timeframes(symbol: str) -> dict:
    normalized = symbol.upper().replace("/", "").replace("-", "").strip()
    if normalized not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=404, detail="unsupported symbol")
    registry = _read_streams()
    streams = registry.get("streams") if isinstance(registry.get("streams"), dict) else {}
    items = [
        streams[key]
        for timeframe in ("M15", "H1", "H4", "D1", "W1")
        if (key := f"{normalized}:{timeframe}") in streams
    ]
    return {
        "symbol": normalized,
        "expected_timeframes": ["M15", "H1", "H4", "D1", "W1"],
        "received_timeframes": [item.get("timeframe") for item in items],
        "items": items,
        "updated_at": registry.get("updated_at"),
    }


@router.get("/status")
def mt4_status() -> dict:
    registry = _read_streams()
    streams = registry.get("streams") if isinstance(registry.get("streams"), dict) else {}
    now = datetime.now(timezone.utc)
    rows = []
    for symbol in ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD"):
        for timeframe in ("M15", "H1", "H4", "D1", "W1"):
            key = f"{symbol}:{timeframe}"
            item = streams.get(key) if isinstance(streams.get(key), dict) else {}
            received_at = item.get("received_at")
            age = None
            if received_at:
                try:
                    age = max(0, int((now - datetime.fromisoformat(received_at)).total_seconds()))
                except (TypeError, ValueError):
                    pass
            rows.append({
                "stream": key,
                "symbol": symbol,
                "timeframe": timeframe,
                "status": "online" if age is not None and age <= 180 else "stale" if received_at else "waiting",
                "age_seconds": age,
                "received_at": received_at,
                "broker_symbol": item.get("broker_symbol"),
                "tick_samples": (item.get("ticks") or {}).get("samples", 0),
                "candle_count": len(item.get("candles") or []),
            })
    return {
        "schema_version": "2.0",
        "expected_streams": 20,
        "received_streams": sum(1 for row in rows if row["received_at"]),
        "online_streams": sum(1 for row in rows if row["status"] == "online"),
        "updated_at": registry.get("updated_at"),
        "streams": rows,
    }
