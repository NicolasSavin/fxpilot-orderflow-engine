from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.models.market import OrderBookLevel


class VolumeProfileLevel(BaseModel):
    price: float
    total_volume: float = 0
    buy_volume: float = 0
    sell_volume: float = 0
    delta: float = 0
    trades_count: int = 0


class VolumeProfileResult(BaseModel):
    profile_levels: list[VolumeProfileLevel] = Field(default_factory=list)
    total_volume: float = 0
    buy_volume: float = 0
    sell_volume: float = 0
    delta: float = 0
    poc: float = 0
    vah: float = 0
    val: float = 0
    hvn_levels: list[float] = Field(default_factory=list)
    lvn_levels: list[float] = Field(default_factory=list)


class CumDeltaPoint(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    delta: float = 0
    cumdelta: float = 0
    buy_volume: float = 0
    sell_volume: float = 0
    total_volume: float = 0
    price: float | None = None


class CumDeltaResult(BaseModel):
    symbol: str
    current_delta: float = 0
    current_cumdelta: float = 0
    session_cumdelta: float = 0
    rolling_cumdelta: float = 0
    buy_volume: float = 0
    sell_volume: float = 0
    total_volume: float = 0
    delta_slope: Literal["rising", "falling", "flat"] = "flat"
    delta_momentum: Literal["strengthening", "weakening", "neutral"] = "neutral"
    divergence: Literal["bullish", "bearish", "none"] = "none"
    bias: Literal["bullish", "bearish", "neutral"] = "neutral"


class DOMResult(BaseModel):
    bid_total: float = 0
    ask_total: float = 0
    total_liquidity: float = 0
    imbalance_ratio: float = 0
    dom_pressure: Literal["bullish", "bearish", "neutral", "unavailable"] = "unavailable"
    strongest_bid_level: OrderBookLevel | None = None
    strongest_ask_level: OrderBookLevel | None = None
    liquidity_above: float = 0
    liquidity_below: float = 0
    liquidity_wall_side: Literal["bid", "ask", "none"] = "none"
    liquidity_wall_price: float | None = None
    liquidity_wall_strength: float = 0
    thin_liquidity_side: Literal["above", "below", "none"] = "none"
    debug: dict[str, Any] = Field(default_factory=dict)


class VWAPResult(BaseModel):
    symbol: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_vwap: float = 0
    session_vwap: float = 0
    rolling_vwap: float = 0
    anchored_vwap: float = 0
    distance_to_vwap: float = 0
    distance_percent: float = 0
    price_position: Literal["above_vwap", "below_vwap", "at_vwap"] = "at_vwap"
    bias: Literal["bullish", "bearish", "neutral"] = "neutral"


class OrderFlowSnapshot(BaseModel):
    symbol: str
    futures_symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: Literal["mock", "databento"]
    provider_status: Literal["ok", "unavailable", "not_configured"]
    delta: float = 0
    cumdelta: float = 0
    volume: float = 0
    rvol: float = 0
    vwap: float = 0
    poc: float = 0
    vah: float = 0
    val: float = 0
    hvn_levels: list[float] = Field(default_factory=list)
    lvn_levels: list[float] = Field(default_factory=list)
    dom_pressure: Literal["bullish", "bearish", "neutral", "unavailable"] = "unavailable"
    imbalance: float = 0
    absorption: Literal["bullish", "bearish", "none", "unavailable"] = "unavailable"
    exhaustion: Literal["bullish", "bearish", "none", "unavailable"] = "unavailable"
    market_state: Literal["accumulation", "distribution", "trend", "range", "expansion", "exhaustion", "unknown"] = "unknown"
    orderflow_bias: Literal["bullish", "bearish", "neutral"] = "neutral"
    continuation_probability: float = 0
    reversal_probability: float = 0
    orderflow_provider: str | None = None
    orderflow_available: bool = False
    debug: dict[str, Any] = Field(default_factory=dict)
