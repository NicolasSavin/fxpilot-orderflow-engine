from app.calculators.absorption import analyze_absorption, calculate_absorption
from app.models.market import Candle


def candle(open=100, high=105, low=95, close=100, volume=1000):
    return Candle(symbol="6E", open=open, high=high, low=low, close=close, volume=volume)


def test_bullish_absorption():
    candles = [candle(low=94, high=104, close=99), candle(low=95, high=103, close=101, volume=1000)]

    result = analyze_absorption(candles, delta=-400, volume=1000)

    assert result.bullish_absorption is True
    assert result.bearish_absorption is False
    assert result.reason == "bullish_absorption"
    assert result.confidence == 1
    assert calculate_absorption(candles, -400, 1000) == "bullish"


def test_bearish_absorption():
    candles = [candle(high=106, low=96, close=101), candle(high=105, low=97, close=99, volume=1000)]

    result = analyze_absorption(candles, delta=400, volume=1000)

    assert result.bearish_absorption is True
    assert result.bullish_absorption is False
    assert result.reason == "bearish_absorption"
    assert result.confidence == 1
    assert calculate_absorption(candles, 400, 1000) == "bearish"


def test_bullish_exhaustion():
    candles = [candle(high=105, low=95, close=104, volume=1200), candle(high=106, low=96, close=105, volume=800)]

    result = analyze_absorption(candles, delta=50, volume=800, deltas=[200])

    assert result.exhaustion == "bullish"
    assert result.reason == "bullish_exhaustion"
    assert result.confidence == 1


def test_bearish_exhaustion():
    candles = [candle(high=105, low=95, close=96, volume=1200), candle(high=104, low=94, close=95, volume=800)]

    result = analyze_absorption(candles, delta=-50, volume=800, deltas=[-200])

    assert result.exhaustion == "bearish"
    assert result.reason == "bearish_exhaustion"
    assert result.confidence == 1


def test_no_signal():
    candles = [candle(high=105, low=95, close=100, volume=1000), candle(high=106, low=94, close=100, volume=1200)]

    result = analyze_absorption(candles, delta=10, volume=1200, deltas=[5])

    assert result.bullish_absorption is False
    assert result.bearish_absorption is False
    assert result.exhaustion == "none"
    assert result.reason == "no_signal"
    assert result.confidence == 0
    assert calculate_absorption(candles, 10, 1200) == "none"


def test_insufficient_data():
    result = analyze_absorption([candle()], delta=-400, volume=1000)

    assert result.reason == "insufficient_data"
    assert result.confidence == 0
    assert calculate_absorption([], -400, 1000) == "unavailable"
