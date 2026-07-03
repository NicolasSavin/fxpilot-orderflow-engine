from app.models.market import Candle


def calculate_absorption(candles: list[Candle], delta: float, volume: float) -> str:
    if not candles or volume <= 0:
        return "unavailable"
    candle = candles[-1]
    midpoint = (candle.high + candle.low) / 2
    strong = abs(delta) > volume * 0.25
    if strong and delta < 0 and candle.close > midpoint and candle.low >= min(c.low for c in candles[-3:]):
        return "bullish"
    if strong and delta > 0 and candle.close < midpoint and candle.high <= max(c.high for c in candles[-3:]):
        return "bearish"
    return "none"
