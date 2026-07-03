from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

TradeSide = Literal["buy", "sell", "unknown"]


class Trade(BaseModel):
    symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price: float
    size: float
    side: TradeSide = "unknown"


class BookLevel(BaseModel):
    price: float
    bid_size: float = 0
    ask_size: float = 0


class Candle(BaseModel):
    symbol: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    open: float
    high: float
    low: float
    close: float
    volume: float
