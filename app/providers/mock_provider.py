import random
from datetime import datetime, timedelta, timezone
from collections.abc import AsyncIterator
from app.models.market import BookLevel, Trade
from app.providers.base import BaseMarketDataProvider
from app.services.symbol_mapper import to_futures_symbol

BASE = {"6E": 1.1452, "6B": 1.3120, "6J": 0.0069, "GC": 2350.0}
TICK = {"6E": 0.00005, "6B": 0.0001, "6J": 0.0000005, "GC": 0.1}


class MockProvider(BaseMarketDataProvider):
    name = "mock"

    async def get_recent_trades(self, symbol: str, start=None, end=None) -> list[Trade]:
        fut = to_futures_symbol(symbol)
        rng = random.Random(fut)
        price = BASE.get(fut, 1.0)
        tick = TICK.get(fut, 0.0001)
        now = datetime.now(timezone.utc)
        trades = []
        for i in range(160):
            price += rng.choice([-2, -1, 0, 1, 2]) * tick
            side = rng.choices(["buy", "sell", "unknown"], weights=[45, 45, 10])[0]
            trades.append(Trade(symbol=fut, timestamp=now - timedelta(seconds=160 - i), price=round(price, 10), size=rng.randint(1, 25), side=side))
        return trades

    async def get_recent_book(self, symbol: str) -> list[BookLevel]:
        fut = to_futures_symbol(symbol); base = BASE.get(fut, 1.0); tick = TICK.get(fut, 0.0001); rng = random.Random(f"book-{fut}")
        return [BookLevel(price=round(base + (i - 5) * tick, 10), bid_size=rng.randint(20, 180), ask_size=rng.randint(20, 180)) for i in range(10)]

    async def get_ohlcv(self, symbol: str, timeframe: str, start=None, end=None) -> list[dict]:
        trades = await self.get_recent_trades(symbol, start, end)
        return [{"timestamp": trades[0].timestamp, "open": trades[0].price, "high": max(t.price for t in trades), "low": min(t.price for t in trades), "close": trades[-1].price, "volume": sum(t.size for t in trades)}]

    async def stream_trades(self, symbol: str) -> AsyncIterator[Trade]:
        for trade in await self.get_recent_trades(symbol):
            yield trade
