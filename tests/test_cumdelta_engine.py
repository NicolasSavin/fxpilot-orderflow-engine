from datetime import datetime, timezone

from app.calculators.cumdelta import CumDeltaEngine
from app.models.market import Trade
from app.storage.memory_store import MemoryStore


def trade(symbol: str, price: float, size: float, side: str = "buy") -> Trade:
    return Trade(symbol=symbol, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), price=price, size=size, side=side)


def test_session_cumdelta():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 10, buy_volume=10, total_volume=10)
    result = engine.update("6E", -4, sell_volume=4, total_volume=4)

    assert result.session_cumdelta == 6
    assert result.current_cumdelta == 6


def test_reset_session():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 10)
    result = engine.update("6E", 3, reset_session=True)

    assert result.session_cumdelta == 3
    assert result.current_cumdelta == 3


def test_rolling_cumdelta():
    engine = CumDeltaEngine(memory_store=MemoryStore(), rolling_window=3)
    for delta in [1, 2, 3, 4]:
        result = engine.update("6E", delta)

    assert result.rolling_cumdelta == 9


def test_delta_slope():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 3)
    rising = engine.update("6E", 2)
    falling = engine.update("6E", -10)

    assert rising.delta_slope == "rising"
    assert falling.delta_slope == "falling"


def test_delta_momentum():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 1)
    engine.update("6E", 2)
    strengthening = engine.update("6E", 4)
    weakening = engine.update("6E", 1)

    assert strengthening.delta_momentum == "strengthening"
    assert weakening.delta_momentum == "weakening"


def test_bullish_divergence():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", -10, price=100)
    engine.update("6E", -10, price=98)
    engine.update("6E", 8, price=101)
    result = engine.update("6E", 5, price=97)

    assert result.divergence == "bullish"


def test_bearish_divergence():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 10, price=100)
    engine.update("6E", 10, price=102)
    engine.update("6E", -8, price=99)
    result = engine.update("6E", -5, price=103)

    assert result.divergence == "bearish"


def test_neutral_bias():
    engine = CumDeltaEngine(memory_store=MemoryStore())
    engine.update("6E", 10)
    result = engine.update("6E", -2)

    assert result.bias == "neutral"


def test_process_trade_stream_volumes():
    engine = CumDeltaEngine(memory_store=MemoryStore(), rolling_window=2)
    engine.process_trade(trade("6E", 1.0, 5, "buy"))
    result = engine.process_trade(trade("6E", 0.9, 3, "sell"))

    assert result.current_delta == -3
    assert result.buy_volume == 5
    assert result.sell_volume == 3
    assert result.total_volume == 8
