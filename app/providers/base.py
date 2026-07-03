from abc import ABC, abstractmethod
from datetime import datetime
from collections.abc import AsyncIterator
from app.models.market import BookLevel, Trade


class ProviderNotConfiguredError(RuntimeError):
    code = "provider_not_configured"


class BaseMarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def get_recent_trades(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> list[Trade]: ...

    @abstractmethod
    async def get_recent_book(self, symbol: str) -> list[BookLevel]: ...

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, start: datetime | None = None, end: datetime | None = None) -> list[dict]: ...

    @abstractmethod
    async def stream_trades(self, symbol: str) -> AsyncIterator[Trade]: ...
