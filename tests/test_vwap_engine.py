from datetime import datetime, timedelta, timezone

import pytest

from app.calculators.vwap import VWAPEngine, calculate_vwap, calculate_vwap_result
from app.models.market import Trade
from app.storage.memory_store import MemoryStore


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def trade(price: float, size: float, minutes: int = 0, symbol: str = "6E") -> Trade:
    return Trade(symbol=symbol, timestamp=BASE_TIME + timedelta(minutes=minutes), price=price, size=size)


def test_session_vwap():
    result = calculate_vwap_result([trade(100, 2), trade(110, 3)])

    assert result.session_vwap == pytest.approx(106)
    assert result.current_vwap == pytest.approx(106)


def test_calculate_vwap_backward_compatible():
    assert calculate_vwap([trade(100, 1), trade(200, 1)]) == pytest.approx(150)


def test_rolling_vwap():
    engine = VWAPEngine(memory_store=MemoryStore(), rolling_window=2)
    result = engine.process_trades([trade(100, 1), trade(200, 1), trade(300, 2)])

    assert result.rolling_vwap == pytest.approx((200 * 1 + 300 * 2) / 3)


def test_anchored_vwap():
    anchor = BASE_TIME + timedelta(minutes=1)
    result = calculate_vwap_result(
        [trade(100, 10, 0), trade(120, 1, 1), trade(140, 3, 2)],
        anchor_timestamp=anchor,
    )

    assert result.anchored_vwap == pytest.approx((120 * 1 + 140 * 3) / 4)


def test_distance():
    result = calculate_vwap_result([trade(100, 1), trade(110, 1)])

    assert result.distance_to_vwap == pytest.approx(5)
    assert result.distance_percent == pytest.approx((5 / 105) * 100)


def test_price_position():
    engine = VWAPEngine(memory_store=MemoryStore(), price_tolerance=0.01)
    above = engine.process_trades([trade(100, 1), trade(102, 1)])
    at = engine.result("6E", price=101.005)
    below = engine.result("6E", price=100)

    assert above.price_position == "above_vwap"
    assert at.price_position == "at_vwap"
    assert below.price_position == "below_vwap"


def test_bullish_bias():
    result = calculate_vwap_result([trade(100, 1), trade(110, 1)], cumdelta_bias="bullish")

    assert result.bias == "bullish"


def test_bearish_bias():
    result = calculate_vwap_result([trade(110, 1), trade(100, 1)], cumdelta_bias="bearish")

    assert result.bias == "bearish"


def test_neutral_bias():
    bullish_delta_below_vwap = calculate_vwap_result([trade(110, 1), trade(100, 1)], cumdelta_bias="bullish")
    no_delta_confirmation = calculate_vwap_result([trade(100, 1), trade(110, 1)], cumdelta_bias="neutral")

    assert bullish_delta_below_vwap.bias == "neutral"
    assert no_delta_confirmation.bias == "neutral"


def test_memory_store_keeps_session_and_rolling_vwap():
    memory_store = MemoryStore()
    engine = VWAPEngine(memory_store=memory_store, rolling_window=1)
    engine.process_trades([trade(100, 1), trade(200, 1)])

    assert memory_store.session_vwap["6E"] == pytest.approx(150)
    assert memory_store.rolling_vwap["6E"] == pytest.approx(200)
