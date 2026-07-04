from typing import Literal

from app.models.market import Candle
from app.models.orderflow import AbsorptionResult

Signal = Literal["bullish", "bearish", "none", "unavailable"]


def _bounded_confidence(matched: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, matched / total)), 2)


def analyze_absorption(
    candles: list[Candle],
    delta: float,
    volume: float | None = None,
    deltas: list[float] | None = None,
    strong_delta_ratio: float = 0.25,
) -> AbsorptionResult:
    """Analyze absorption and exhaustion from candle, delta, and volume history.

    The function is intentionally provider-agnostic: callers may pass historical or
    live Databento-derived candles/deltas later, but no provider code is used here.
    """
    debug: dict[str, object] = {
        "candles_count": len(candles),
        "delta": delta,
        "volume": volume,
        "strong_delta_ratio": strong_delta_ratio,
    }

    if len(candles) < 2:
        return AbsorptionResult(
            confidence=0.0,
            reason="insufficient_data",
            debug={**debug, "required_candles": 2},
        )

    current = candles[-1]
    previous = candles[-2]
    effective_volume = current.volume if volume is None else volume
    if effective_volume <= 0:
        return AbsorptionResult(
            confidence=0.0,
            reason="invalid_volume",
            debug={**debug, "effective_volume": effective_volume},
        )
    midpoint = (current.high + current.low) / 2
    strong_threshold = effective_volume * strong_delta_ratio if effective_volume > 0 else 0
    strong_negative_delta = effective_volume > 0 and delta <= -strong_threshold
    strong_positive_delta = effective_volume > 0 and delta >= strong_threshold
    no_new_low = current.low >= previous.low
    no_new_high = current.high <= previous.high
    close_above_midpoint = current.close > midpoint
    close_below_midpoint = current.close < midpoint

    bullish_absorption_conditions = [strong_negative_delta, no_new_low, close_above_midpoint]
    bearish_absorption_conditions = [strong_positive_delta, no_new_high, close_below_midpoint]
    bullish_absorption_score = _bounded_confidence(sum(bullish_absorption_conditions), 3)
    bearish_absorption_score = _bounded_confidence(sum(bearish_absorption_conditions), 3)
    bullish_absorption = all(bullish_absorption_conditions)
    bearish_absorption = all(bearish_absorption_conditions)

    delta_history = [*deltas, delta] if deltas is not None else [delta]
    has_delta_history = len(delta_history) >= 2
    previous_delta = delta_history[-2] if has_delta_history else None
    new_high = current.high > previous.high
    new_low = current.low < previous.low
    bullish_delta_not_confirming = has_delta_history and delta <= previous_delta
    bearish_delta_not_confirming = has_delta_history and delta >= previous_delta
    volume_decreasing = current.volume < previous.volume
    bullish_exhaustion_conditions = [new_high, bullish_delta_not_confirming, volume_decreasing]
    bearish_exhaustion_conditions = [new_low, bearish_delta_not_confirming, volume_decreasing]
    bullish_exhaustion = all(bullish_exhaustion_conditions)
    bearish_exhaustion = all(bearish_exhaustion_conditions)

    confidence = max(
        bullish_absorption_score,
        bearish_absorption_score,
        _bounded_confidence(sum(bullish_exhaustion_conditions), 3),
        _bounded_confidence(sum(bearish_exhaustion_conditions), 3),
    )

    if bullish_absorption:
        reason = "bullish_absorption"
    elif bearish_absorption:
        reason = "bearish_absorption"
    elif bullish_exhaustion:
        reason = "bullish_exhaustion"
    elif bearish_exhaustion:
        reason = "bearish_exhaustion"
    else:
        reason = "no_signal"

    return AbsorptionResult(
        bullish_absorption=bullish_absorption,
        bearish_absorption=bearish_absorption,
        exhaustion="bullish" if bullish_exhaustion else "bearish" if bearish_exhaustion else "none",
        confidence=confidence if reason != "no_signal" else 0.0,
        reason=reason,
        debug={
            **debug,
            "midpoint": midpoint,
            "effective_volume": effective_volume,
            "strong_delta_threshold": strong_threshold,
            "conditions": {
                "bullish_absorption": {
                    "strong_negative_delta": strong_negative_delta,
                    "no_new_low": no_new_low,
                    "close_above_midpoint": close_above_midpoint,
                },
                "bearish_absorption": {
                    "strong_positive_delta": strong_positive_delta,
                    "no_new_high": no_new_high,
                    "close_below_midpoint": close_below_midpoint,
                },
                "bullish_exhaustion": {
                    "new_high": new_high,
                    "delta_not_confirming": bullish_delta_not_confirming,
                    "volume_decreasing": volume_decreasing,
                },
                "bearish_exhaustion": {
                    "new_low": new_low,
                    "delta_not_confirming": bearish_delta_not_confirming,
                    "volume_decreasing": volume_decreasing,
                },
            },
        },
    )


def calculate_absorption(candles: list[Candle], delta: float, volume: float) -> Signal:
    """Return the legacy absorption string used by existing engine code."""
    result = analyze_absorption(candles=candles, delta=delta, volume=volume)
    if result.reason in {"insufficient_data", "invalid_volume"}:
        return "unavailable"
    if result.bullish_absorption:
        return "bullish"
    if result.bearish_absorption:
        return "bearish"
    return "none"
