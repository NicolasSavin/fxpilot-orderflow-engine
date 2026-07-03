from collections.abc import AsyncIterator
from app.config import get_settings
from app.models.market import BookLevel, Trade
from app.providers.base import BaseMarketDataProvider, ProviderNotConfiguredError


class DatabentoProvider(BaseMarketDataProvider):
    name = "databento"

    def __init__(self) -> None:
        self.api_key = get_settings().databento_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise ProviderNotConfiguredError("provider_not_configured: DATABENTO_API_KEY is not set")

    async def get_recent_trades(self, symbol: str, start=None, end=None) -> list[Trade]:
        self._ensure_configured(); return []

    async def get_recent_book(self, symbol: str) -> list[BookLevel]:
        self._ensure_configured(); return []

    async def get_ohlcv(self, symbol: str, timeframe: str, start=None, end=None) -> list[dict]:
        self._ensure_configured(); return []

    async def stream_trades(self, symbol: str) -> AsyncIterator[Trade]:
        self._ensure_configured()
        if False:
            yield Trade(symbol=symbol, price=0, size=0)
