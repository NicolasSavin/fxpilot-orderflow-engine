from datetime import datetime, timezone
from threading import RLock
from app.models.market import BookLevel, Candle, Trade
from app.models.orderflow import CumDeltaPoint, OrderFlowSnapshot


class MemoryStore:
    def __init__(self) -> None:
        self.cumdelta: dict[str, float] = {}
        self.cumdelta_points: dict[str, list[CumDeltaPoint]] = {}
        self.cumdelta_last_price: dict[str, float] = {}
        self.trades: dict[str, list[Trade]] = {}
        self.books: dict[str, list[BookLevel]] = {}
        self.candles: dict[str, list[Candle]] = {}
        self.last_update: datetime | None = None
        self.latest_snapshots: dict[str, OrderFlowSnapshot] = {}
        self.live_snapshots: dict[str, OrderFlowSnapshot] = {}
        self.cache_snapshots: dict[str, OrderFlowSnapshot] = {}
        self._snapshot_lock = RLock()

    def reset_cumdelta_session(self, symbol: str) -> None:
        self.cumdelta[symbol] = 0
        self.cumdelta_points[symbol] = []
        self.cumdelta_last_price.pop(symbol, None)

    def update_cumdelta(self, symbol: str, delta: float, reset: bool = False) -> float:
        from app.calculators.cumdelta import update_cumdelta

        return update_cumdelta(symbol, delta, reset_session=reset, memory_store=self)

    def ingest(self, symbol: str, trades: list[Trade] | None = None, book: list[BookLevel] | None = None, candles: list[Candle] | None = None) -> None:
        if trades:
            self.trades.setdefault(symbol, []).extend(trades)
        if book is not None:
            self.books[symbol] = book
        if candles:
            self.candles.setdefault(symbol, []).extend(candles)
        self.last_update = datetime.now(timezone.utc)

    def set_latest_snapshot(self, symbol: str, snapshot: OrderFlowSnapshot) -> None:
        with self._snapshot_lock:
            self.latest_snapshots[symbol] = snapshot
            self.last_update = snapshot.timestamp

    def latest_snapshot(self, symbol: str) -> OrderFlowSnapshot | None:
        with self._snapshot_lock:
            return self.latest_snapshots.get(symbol)

    def set_live_snapshot(self, symbol: str, snapshot: OrderFlowSnapshot) -> None:
        with self._snapshot_lock:
            self.live_snapshots[symbol] = snapshot
            self.last_update = snapshot.timestamp

    def live_snapshot(self, symbol: str) -> OrderFlowSnapshot | None:
        with self._snapshot_lock:
            return self.live_snapshots.get(symbol)

    def set_cache_snapshot(self, symbol: str, snapshot: OrderFlowSnapshot) -> None:
        with self._snapshot_lock:
            self.cache_snapshots[symbol] = snapshot
            self.latest_snapshots[symbol] = snapshot
            self.last_update = snapshot.timestamp

    def cache_snapshot(self, symbol: str) -> OrderFlowSnapshot | None:
        with self._snapshot_lock:
            return self.cache_snapshots.get(symbol) or self.latest_snapshots.get(symbol)

    def set_mt4_live_snapshot(self, symbol: str, snapshot: OrderFlowSnapshot) -> None:
        """Atomically publish a successful MT4 live snapshot everywhere it is consumed."""
        with self._snapshot_lock:
            self.latest_snapshots[symbol] = snapshot
            self.live_snapshots[symbol] = snapshot
            self.cache_snapshots[symbol] = snapshot
            self.last_update = snapshot.timestamp

    @property
    def store_size(self) -> int:
        return sum(len(v) for v in self.trades.values()) + sum(len(v) for v in self.books.values()) + sum(len(v) for v in self.candles.values())


store = MemoryStore()
