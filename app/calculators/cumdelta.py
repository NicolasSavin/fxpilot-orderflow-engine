from datetime import datetime, timezone
from typing import Iterable

from app.models.market import Trade
from app.models.orderflow import CumDeltaPoint, CumDeltaResult
from app.storage.memory_store import MemoryStore, store

DEFAULT_ROLLING_WINDOW = 100
_FLAT_EPSILON = 1e-9


def _classify_trade(trade: Trade, previous_price: float | None) -> tuple[float, float, float]:
    side = trade.side
    if side == "unknown" and previous_price is not None:
        if trade.price > previous_price:
            side = "buy"
        elif trade.price < previous_price:
            side = "sell"

    if side == "buy":
        return trade.size, 0.0, trade.size
    if side == "sell":
        return 0.0, trade.size, -trade.size
    return 0.0, 0.0, 0.0


def _delta_slope(points: list[CumDeltaPoint]) -> str:
    if len(points) < 2:
        return "flat"
    change = points[-1].cumdelta - points[-2].cumdelta
    if change > _FLAT_EPSILON:
        return "rising"
    if change < -_FLAT_EPSILON:
        return "falling"
    return "flat"


def _delta_momentum(points: list[CumDeltaPoint]) -> str:
    if len(points) < 3:
        return "neutral"
    previous_change = points[-2].cumdelta - points[-3].cumdelta
    current_change = points[-1].cumdelta - points[-2].cumdelta
    if abs(current_change) <= _FLAT_EPSILON or abs(previous_change) <= _FLAT_EPSILON:
        return "neutral"
    if current_change * previous_change <= 0:
        return "neutral"
    if abs(current_change) > abs(previous_change):
        return "strengthening"
    if abs(current_change) < abs(previous_change):
        return "weakening"
    return "neutral"


def _divergence(points: list[CumDeltaPoint]) -> str:
    priced_points = [point for point in points if point.price is not None]
    if len(priced_points) < 4:
        return "none"

    previous = priced_points[:-1]
    latest = priced_points[-1]
    previous_low = min(previous, key=lambda point: point.price or 0)
    previous_high = max(previous, key=lambda point: point.price or 0)

    if (
        latest.price is not None
        and previous_low.price is not None
        and latest.price < previous_low.price
        and latest.cumdelta > previous_low.cumdelta
    ):
        return "bullish"
    if (
        latest.price is not None
        and previous_high.price is not None
        and latest.price > previous_high.price
        and latest.cumdelta < previous_high.cumdelta
    ):
        return "bearish"
    return "none"


def _bias(current_delta: float, slope: str) -> str:
    if slope == "rising" and current_delta > 0:
        return "bullish"
    if slope == "falling" and current_delta < 0:
        return "bearish"
    return "neutral"


class CumDeltaEngine:
    """Stateful cumulative-delta calculator for historical and live trade streams."""

    def __init__(self, memory_store: MemoryStore = store, rolling_window: int = DEFAULT_ROLLING_WINDOW) -> None:
        if rolling_window <= 0:
            raise ValueError("rolling_window must be greater than zero")
        self.memory_store = memory_store
        self.rolling_window = rolling_window

    def update(
        self,
        symbol: str,
        delta: float,
        *,
        timestamp: datetime | None = None,
        price: float | None = None,
        buy_volume: float = 0.0,
        sell_volume: float = 0.0,
        total_volume: float | None = None,
        reset_session: bool = False,
    ) -> CumDeltaResult:
        if reset_session:
            self.memory_store.reset_cumdelta_session(symbol)

        timestamp = timestamp or datetime.now(timezone.utc)
        total_volume = abs(delta) if total_volume is None else total_volume
        cumdelta = self.memory_store.cumdelta.get(symbol, 0.0) + delta
        self.memory_store.cumdelta[symbol] = cumdelta

        point = CumDeltaPoint(
            timestamp=timestamp,
            symbol=symbol,
            delta=delta,
            cumdelta=cumdelta,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            total_volume=total_volume,
            price=price,
        )
        self.memory_store.cumdelta_points.setdefault(symbol, []).append(point)
        return self._result(symbol)

    def process_trade(self, trade: Trade, *, reset_session: bool = False) -> CumDeltaResult:
        previous_price = self.memory_store.cumdelta_last_price.get(trade.symbol)
        buy_volume, sell_volume, delta = _classify_trade(trade, previous_price)
        self.memory_store.cumdelta_last_price[trade.symbol] = trade.price
        return self.update(
            trade.symbol,
            delta,
            timestamp=trade.timestamp,
            price=trade.price,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            total_volume=trade.size,
            reset_session=reset_session,
        )

    def process_trades(self, trades: Iterable[Trade], *, reset_session: bool = False) -> CumDeltaResult | None:
        result: CumDeltaResult | None = None
        for index, trade in enumerate(trades):
            result = self.process_trade(trade, reset_session=reset_session and index == 0)
        return result

    def _result(self, symbol: str) -> CumDeltaResult:
        points = self.memory_store.cumdelta_points.get(symbol, [])
        if not points:
            return CumDeltaResult(symbol=symbol)
        latest = points[-1]
        rolling_points = points[-self.rolling_window :]
        slope = _delta_slope(points)
        return CumDeltaResult(
            symbol=symbol,
            current_delta=latest.delta,
            current_cumdelta=latest.cumdelta,
            session_cumdelta=latest.cumdelta,
            rolling_cumdelta=sum(point.delta for point in rolling_points),
            buy_volume=sum(point.buy_volume for point in rolling_points),
            sell_volume=sum(point.sell_volume for point in rolling_points),
            total_volume=sum(point.total_volume for point in rolling_points),
            delta_slope=slope,
            delta_momentum=_delta_momentum(points),
            divergence=_divergence(points),
            bias=_bias(latest.delta, slope),
        )


def calculate_cumdelta(
    trades: Iterable[Trade],
    *,
    reset_session: bool = False,
    memory_store: MemoryStore = store,
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
) -> CumDeltaResult | None:
    return CumDeltaEngine(memory_store=memory_store, rolling_window=rolling_window).process_trades(
        trades, reset_session=reset_session
    )


def update_cumdelta(symbol: str, delta: float, reset_session: bool = False, memory_store: MemoryStore = store) -> float:
    """Backward-compatible cumulative-delta update API."""
    result = CumDeltaEngine(memory_store=memory_store).update(symbol, delta, reset_session=reset_session)
    return result.current_cumdelta
