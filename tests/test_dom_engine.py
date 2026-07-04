from app.calculators.dom_pressure import calculate_dom_engine, calculate_dom_pressure
from app.models.market import BookLevel, OrderBookLevel


def test_bullish_dom_pressure():
    result = calculate_dom_engine([OrderBookLevel(price=100, bid_size=80, ask_size=20, level_index=0)])
    assert result.dom_pressure == "bullish"
    assert result.imbalance_ratio == 0.8


def test_bearish_dom_pressure():
    result = calculate_dom_engine([OrderBookLevel(price=100, bid_size=20, ask_size=80, level_index=0)])
    assert result.dom_pressure == "bearish"
    assert result.imbalance_ratio == 0.2


def test_neutral_dom_pressure():
    result = calculate_dom_engine([OrderBookLevel(price=100, bid_size=50, ask_size=50, level_index=0)])
    assert result.dom_pressure == "neutral"
    assert result.imbalance_ratio == 0.5


def test_strongest_bid():
    result = calculate_dom_engine([
        OrderBookLevel(price=99.5, bid_size=40, ask_size=10, level_index=0),
        OrderBookLevel(price=99.0, bid_size=90, ask_size=20, level_index=1),
    ])
    assert result.strongest_bid_level is not None
    assert result.strongest_bid_level.price == 99.0
    assert result.strongest_bid_level.bid_size == 90


def test_strongest_ask():
    result = calculate_dom_engine([
        OrderBookLevel(price=100.5, bid_size=10, ask_size=45, level_index=0),
        OrderBookLevel(price=101.0, bid_size=20, ask_size=95, level_index=1),
    ])
    assert result.strongest_ask_level is not None
    assert result.strongest_ask_level.price == 101.0
    assert result.strongest_ask_level.ask_size == 95


def test_liquidity_wall():
    result = calculate_dom_engine([
        OrderBookLevel(price=99.5, bid_size=20, ask_size=25, level_index=0),
        OrderBookLevel(price=99.0, bid_size=120, ask_size=30, level_index=1),
        OrderBookLevel(price=100.5, bid_size=15, ask_size=40, level_index=2),
    ])
    assert result.liquidity_wall_side == "bid"
    assert result.liquidity_wall_price == 99.0
    assert result.liquidity_wall_strength > 1


def test_thin_liquidity():
    result = calculate_dom_engine([
        OrderBookLevel(price=99.5, bid_size=120, ask_size=20, level_index=0),
        OrderBookLevel(price=99.0, bid_size=80, ask_size=15, level_index=1),
    ])
    assert result.liquidity_below == 200
    assert result.liquidity_above == 35
    assert result.thin_liquidity_side == "above"


def test_empty_book_unavailable_and_legacy_compatible():
    result = calculate_dom_engine([])
    assert result.dom_pressure == "unavailable"
    assert result.debug["reason"] == "empty_book"
    assert calculate_dom_pressure([]) == {"dom_pressure": "unavailable", "imbalance": 0}


def test_legacy_calculate_dom_pressure_uses_new_engine_with_book_level():
    result = calculate_dom_pressure([BookLevel(price=100, bid_size=80, ask_size=20)])
    assert result == {"dom_pressure": "bullish", "imbalance": 0.3}
