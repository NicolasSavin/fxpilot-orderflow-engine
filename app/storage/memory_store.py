from datetime import datetime, timezone
from app.models.market import BookLevel, Candle, Trade


class MemoryStore:
    def __init__(self) -> None:
        self.cumdelta: dict[str, float] = {}
        self.trades: dict[str, list[Trade]] = {}
        self.books: dict[str, list[BookLevel]] = {}
        self.candles: dict[str, list[Candle]] = {}
        self.last_update: datetime | None = None

    def update_cumdelta(self, symbol: str, delta: float, reset: bool = False) -> float:
        if reset:
            self.cumdelta[symbol] = 0
        self.cumdelta[symbol] = self.cumdelta.get(symbol, 0) + delta
        return self.cumdelta[symbol]

    def ingest(self, symbol: str, trades: list[Trade] | None = None, book: list[BookLevel] | None = None, candles: list[Candle] | None = None) -> None:
        if trades:
            self.trades.setdefault(symbol, []).extend(trades)
        if book is not None:
            self.books[symbol] = book
        if candles:
            self.candles.setdefault(symbol, []).extend(candles)
        self.last_update = datetime.now(timezone.utc)

    @property
    def store_size(self) -> int:
        return sum(len(v) for v in self.trades.values()) + sum(len(v) for v in self.books.values()) + sum(len(v) for v in self.candles.values())


store = MemoryStore()
