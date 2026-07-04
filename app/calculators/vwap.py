from datetime import datetime, timezone
from typing import Iterable

from app.models.market import Trade
from app.models.orderflow import VWAPResult
from app.storage.memory_store import MemoryStore, store

DEFAULT_ROLLING_WINDOW = 100
DEFAULT_PRICE_TOLERANCE = 1e-9


def _weighted_vwap(trades: Iterable[Trade]) -> float:
    total_volume = 0.0
    total_notional = 0.0
    for trade in trades:
        total_volume += trade.size
        total_notional += trade.price * trade.size
    return total_notional / total_volume if total_volume else 0.0


def _position(price: float, vwap: float, tolerance: float) -> str:
    distance = price - vwap
    if abs(distance) <= tolerance:
        return "at_vwap"
    if distance > 0:
        return "above_vwap"
    return "below_vwap"


def _bias(price: float, vwap: float, cumdelta_bias: str, tolerance: float) -> str:
    position = _position(price, vwap, tolerance)
    if position == "above_vwap" and cumdelta_bias == "bullish":
        return "bullish"
    if position == "below_vwap" and cumdelta_bias == "bearish":
        return "bearish"
    return "neutral"


class VWAPEngine:
    """Stateful VWAP calculator independent from providers, APIs, and UI layers."""

    def __init__(
        self,
        memory_store: MemoryStore = store,
        *,
        rolling_window: int = DEFAULT_ROLLING_WINDOW,
        anchor_timestamp: datetime | None = None,
        price_tolerance: float = DEFAULT_PRICE_TOLERANCE,
    ) -> None:
        if rolling_window <= 0:
            raise ValueError("rolling_window must be greater than zero")
        if price_tolerance < 0:
            raise ValueError("price_tolerance must be non-negative")
        self.memory_store = memory_store
        if not hasattr(self.memory_store, "session_vwap"):
            self.memory_store.session_vwap = {}
        if not hasattr(self.memory_store, "rolling_vwap"):
            self.memory_store.rolling_vwap = {}
        self.rolling_window = rolling_window
        self.anchor_timestamp = anchor_timestamp
        self.price_tolerance = price_tolerance

    def reset_session(self, symbol: str) -> None:
        self.memory_store.trades[symbol] = []
        self.memory_store.session_vwap.pop(symbol, None)
        self.memory_store.rolling_vwap.pop(symbol, None)

    def process_trade(
        self,
        trade: Trade,
        *,
        cumdelta_bias: str = "neutral",
        anchor_timestamp: datetime | None = None,
        reset_session: bool = False,
    ) -> VWAPResult:
        return self.process_trades(
            [trade],
            cumdelta_bias=cumdelta_bias,
            anchor_timestamp=anchor_timestamp,
            reset_session=reset_session,
        )

    def process_trades(
        self,
        trades: Iterable[Trade],
        *,
        cumdelta_bias: str = "neutral",
        anchor_timestamp: datetime | None = None,
        reset_session: bool = False,
    ) -> VWAPResult:
        trades = list(trades)
        symbol = trades[-1].symbol if trades else ""
        if reset_session and symbol:
            self.reset_session(symbol)
        if trades:
            self.memory_store.trades.setdefault(symbol, []).extend(trades)
        return self.result(symbol, cumdelta_bias=cumdelta_bias, anchor_timestamp=anchor_timestamp)

    def result(
        self,
        symbol: str,
        *,
        price: float | None = None,
        cumdelta_bias: str = "neutral",
        anchor_timestamp: datetime | None = None,
    ) -> VWAPResult:
        session_trades = self.memory_store.trades.get(symbol, [])
        if not session_trades:
            return VWAPResult(symbol=symbol)

        current_price = session_trades[-1].price if price is None else price
        session_vwap = _weighted_vwap(session_trades)
        rolling_vwap = _weighted_vwap(session_trades[-self.rolling_window :])
        anchor = anchor_timestamp or self.anchor_timestamp
        anchored_trades = [trade for trade in session_trades if anchor is None or trade.timestamp >= anchor]
        anchored_vwap = _weighted_vwap(anchored_trades)
        distance = current_price - session_vwap
        distance_percent = (distance / session_vwap) * 100 if session_vwap else 0.0

        self.memory_store.session_vwap[symbol] = session_vwap
        self.memory_store.rolling_vwap[symbol] = rolling_vwap

        return VWAPResult(
            symbol=symbol,
            timestamp=session_trades[-1].timestamp,
            current_vwap=session_vwap,
            session_vwap=session_vwap,
            rolling_vwap=rolling_vwap,
            anchored_vwap=anchored_vwap,
            distance_to_vwap=distance,
            distance_percent=distance_percent,
            price_position=_position(current_price, session_vwap, self.price_tolerance),
            bias=_bias(current_price, session_vwap, cumdelta_bias, self.price_tolerance),
        )


def calculate_vwap(trades: list[Trade]) -> float:
    return _weighted_vwap(trades)


def calculate_vwap_result(
    trades: Iterable[Trade],
    *,
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
    anchor_timestamp: datetime | None = None,
    cumdelta_bias: str = "neutral",
    price_tolerance: float = DEFAULT_PRICE_TOLERANCE,
    memory_store: MemoryStore | None = None,
) -> VWAPResult:
    engine = VWAPEngine(
        memory_store=memory_store or MemoryStore(),
        rolling_window=rolling_window,
        anchor_timestamp=anchor_timestamp,
        price_tolerance=price_tolerance,
    )
    return engine.process_trades(trades, cumdelta_bias=cumdelta_bias)
