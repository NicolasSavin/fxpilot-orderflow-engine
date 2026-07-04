from typing import Any

from app.models.orderflow import (
    AbsorptionResult,
    CumDeltaResult,
    DOMResult,
    MarketStateResult,
    VWAPResult,
    VolumeProfileResult,
)

HIGH_VOLUME_RATIO = 1.2
WEAK_PRICE_CHANGE_PERCENT = 0.15
TREND_DISTANCE_PERCENT = 0.05


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _side_from_bias(*biases: str) -> str:
    bullish = sum(1 for bias in biases if bias == "bullish")
    bearish = sum(1 for bias in biases if bias == "bearish")
    if bullish > bearish:
        return "bullish"
    if bearish > bullish:
        return "bearish"
    return "neutral"


def _trend_strength(vwap: VWAPResult, cumdelta: CumDeltaResult, dom: DOMResult) -> str:
    score = 0
    if abs(vwap.distance_percent) >= TREND_DISTANCE_PERCENT:
        score += 1
    if cumdelta.delta_momentum == "strengthening":
        score += 1
    if dom.dom_pressure in {"bullish", "bearish"}:
        score += 1
    if score >= 3:
        return "strong"
    if score >= 2:
        return "moderate"
    if score == 1:
        return "weak"
    return "none"


def calculate_market_state_result(
    *,
    price: float,
    volume: float,
    volume_profile: VolumeProfileResult,
    cumdelta: CumDeltaResult,
    vwap: VWAPResult,
    dom: DOMResult,
    absorption: AbsorptionResult,
    average_volume: float | None = None,
    price_change_percent: float = 0.0,
) -> MarketStateResult:
    """Combine order-flow calculator outputs into a professional market state.

    This function is a pure library helper: it has no provider, API, storage, UI,
    or FastAPI dependencies. Callers are expected to pass already-computed
    Volume Profile, CumDelta, VWAP, DOM, and Absorption/Exhaustion results.
    """
    reasons: list[str] = []
    candidates: dict[str, float] = {
        "accumulation": 0.0,
        "distribution": 0.0,
        "trend": 0.0,
        "range": 0.0,
        "expansion": 0.0,
        "exhaustion": 0.0,
    }

    has_value_area = volume_profile.vah > volume_profile.val > 0
    in_value_area = has_value_area and volume_profile.val <= price <= volume_profile.vah
    above_vah = has_value_area and price > volume_profile.vah
    below_val = has_value_area and price < volume_profile.val
    outside_value_area = above_vah or below_val
    high_volume = volume > 0 and (
        volume_profile.total_volume > 0 and volume >= volume_profile.total_volume * 0.2
        if average_volume is None
        else volume >= average_volume * HIGH_VOLUME_RATIO
    )
    weak_price_direction = abs(price_change_percent) <= WEAK_PRICE_CHANGE_PERCENT
    no_absorption = not absorption.bullish_absorption and not absorption.bearish_absorption
    exhaustion_signal = absorption.exhaustion not in {"none", "unavailable"}
    absorption_signal = absorption.bullish_absorption or absorption.bearish_absorption
    delta_bullish = cumdelta.bias == "bullish" or cumdelta.delta_slope == "rising" or cumdelta.current_cumdelta > 0
    delta_bearish = cumdelta.bias == "bearish" or cumdelta.delta_slope == "falling" or cumdelta.current_cumdelta < 0
    vwap_bullish = vwap.price_position == "above_vwap" or vwap.bias == "bullish"
    vwap_bearish = vwap.price_position == "below_vwap" or vwap.bias == "bearish"
    dom_bullish = dom.dom_pressure == "bullish"
    dom_bearish = dom.dom_pressure == "bearish"

    if exhaustion_signal:
        candidates["exhaustion"] += 0.75 + absorption.confidence * 0.25
        reasons.append(f"exhaustion module signaled {absorption.exhaustion}")
    elif absorption_signal:
        candidates["exhaustion"] += 0.55 + absorption.confidence * 0.2
        reasons.append(f"absorption module signaled {absorption.reason}")

    if in_value_area:
        candidates["range"] += 0.45
        reasons.append("price is inside the Volume Profile value area")
    if in_value_area and high_volume and delta_bullish and weak_price_direction:
        candidates["accumulation"] += 0.8
        reasons.append("value-area trading with high volume, rising/bullish CumDelta, and weak price direction")
    if in_value_area and high_volume and delta_bearish and weak_price_direction:
        candidates["distribution"] += 0.8
        reasons.append("value-area trading with high volume, falling/bearish CumDelta, and weak price direction")

    bullish_trend_votes = [vwap_bullish, delta_bullish, dom_bullish, no_absorption]
    bearish_trend_votes = [vwap_bearish, delta_bearish, dom_bearish, no_absorption]
    if sum(bullish_trend_votes) >= 3 or sum(bearish_trend_votes) >= 3:
        candidates["trend"] += 0.2 * max(sum(bullish_trend_votes), sum(bearish_trend_votes))
        reasons.append("VWAP position, CumDelta, DOM pressure, and lack of absorption align for trend")

    if outside_value_area and high_volume and (delta_bullish or delta_bearish):
        candidates["expansion"] += 0.75
        reasons.append("price broke outside VAH/VAL on high volume with Delta confirmation")
        if (above_vah and delta_bullish) or (below_val and delta_bearish):
            candidates["expansion"] += 0.15
            reasons.append("breakout direction is confirmed by CumDelta")

    if candidates["range"] and not high_volume and not outside_value_area:
        candidates["range"] += 0.2
        reasons.append("no high-volume value-area initiative or value-area breakout is present")

    market_state, score = max(candidates.items(), key=lambda item: item[1])
    if score <= 0:
        market_state = "unknown"
        reasons.append("insufficient combined evidence for a classified state")

    initiative_side = _side_from_bias(cumdelta.bias, dom.dom_pressure, vwap.bias)
    if market_state == "expansion":
        initiative_side = "bullish" if above_vah else "bearish" if below_val else initiative_side
    responsive_side = "bearish" if initiative_side == "bullish" else "bullish" if initiative_side == "bearish" else "neutral"
    if sum(bullish_trend_votes) > sum(bearish_trend_votes):
        trend_direction = "bullish"
    elif sum(bearish_trend_votes) > sum(bullish_trend_votes):
        trend_direction = "bearish"
    else:
        trend_direction = "neutral"

    return MarketStateResult(
        market_state=market_state,
        trend_direction=trend_direction,
        trend_strength=_trend_strength(vwap, cumdelta, dom) if market_state in {"trend", "expansion"} else "none",
        acceptance=(
            "inside_value_area"
            if in_value_area
            else "above_value_area"
            if above_vah
            else "below_value_area"
            if below_val
            else "unknown"
        ),
        rejection=(
            "none" if not outside_value_area else "rejected_lower_value" if above_vah else "rejected_upper_value"
        ),
        initiative_side=initiative_side,
        responsive_side=responsive_side,
        confidence=_clamp(score),
        reasons=reasons,
        debug={
            "candidates": {key: round(value, 4) for key, value in candidates.items()},
            "inputs": {
                "price": price,
                "volume": volume,
                "average_volume": average_volume,
                "price_change_percent": price_change_percent,
                "in_value_area": in_value_area,
                "outside_value_area": outside_value_area,
                "high_volume": high_volume,
                "weak_price_direction": weak_price_direction,
                "delta_bullish": delta_bullish,
                "delta_bearish": delta_bearish,
                "vwap_bullish": vwap_bullish,
                "vwap_bearish": vwap_bearish,
                "dom_pressure": dom.dom_pressure,
                "absorption_reason": absorption.reason,
            },
        },
    )


# Backward-compatible legacy helper used by the existing service layer.
def calculate_market_state(
    candles: list[Any], delta: float, cumdelta: float, volume: float, vah: float, val: float
) -> dict:
    if not candles:
        return {
            "market_state": "unknown",
            "orderflow_bias": "neutral",
            "continuation_probability": 0.45,
            "reversal_probability": 0.35,
            "exhaustion": "unavailable",
        }
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
