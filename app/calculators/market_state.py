from app.models.market import Candle


def calculate_market_state(candles: list[Candle], delta: float, cumdelta: float, volume: float, vah: float, val: float) -> dict:
    if not candles:
        return {"market_state": "unknown", "orderflow_bias": "neutral", "continuation_probability": 0.45, "reversal_probability": 0.35, "exhaustion": "unavailable"}
    c = candles[-1]
    direction = c.close - c.open
    avg_volume = sum(x.volume for x in candles) / len(candles)
    high_volume = volume >= avg_volume
    in_range = val <= c.close <= vah if vah and val else False
    aligned = (direction > 0 and delta > 0) or (direction < 0 and delta < 0)
    exhaustion = "none"
    state = "unknown"
    if in_range:
        state = "range"
        if high_volume and delta > 0 and cumdelta > 0:
            state = "accumulation"
        elif high_volume and delta < 0 and cumdelta < 0:
            state = "distribution"
    if aligned and abs(direction) > 0:
        state = "trend"
    if vah and (c.close > vah or c.close < val) and high_volume:
        state = "expansion"
    recent = candles[-5:]
    if len(recent) >= 3:
        if c.high >= max(x.high for x in recent) and delta <= 0:
            state, exhaustion = "exhaustion", "bearish"
        elif c.low <= min(x.low for x in recent) and delta >= 0:
            state, exhaustion = "exhaustion", "bullish"
    bias = "bullish" if delta > 0 and cumdelta >= 0 else "bearish" if delta < 0 and cumdelta <= 0 else "neutral"
    continuation = 0.65 if state in {"trend", "expansion"} and bias != "neutral" else 0.5
    reversal = 0.65 if state == "exhaustion" else 0.35
    return {"market_state": state, "orderflow_bias": bias, "continuation_probability": continuation, "reversal_probability": reversal, "exhaustion": exhaustion}
