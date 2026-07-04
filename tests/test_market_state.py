from app.calculators.market_state import calculate_market_state_result
from app.models.orderflow import AbsorptionResult, CumDeltaResult, DOMResult, VWAPResult, VolumeProfileResult


def vp():
    return VolumeProfileResult(total_volume=5000, poc=100, vah=105, val=95)


def absorption(**kwargs):
    return AbsorptionResult(**kwargs)


def test_trend_requires_combined_vwap_delta_dom_confirmation():
    result = calculate_market_state_result(
        price=108,
        volume=900,
        average_volume=1000,
        volume_profile=vp(),
        cumdelta=CumDeltaResult(symbol="6E", current_delta=200, current_cumdelta=600, delta_slope="rising", bias="bullish"),
        vwap=VWAPResult(symbol="6E", current_vwap=103, distance_percent=4.85, price_position="above_vwap", bias="bullish"),
        dom=DOMResult(dom_pressure="bullish"),
        absorption=absorption(),
    )

    assert result.market_state == "trend"
    assert result.trend_direction == "bullish"
    assert result.initiative_side == "bullish"
    assert result.confidence >= 0.6
    assert any("align for trend" in reason for reason in result.reasons)


def test_accumulation_inside_value_area_high_volume_positive_delta_weak_price():
    result = calculate_market_state_result(
        price=101,
        volume=1300,
        average_volume=1000,
        price_change_percent=0.03,
        volume_profile=vp(),
        cumdelta=CumDeltaResult(symbol="6E", current_delta=300, current_cumdelta=800, delta_slope="rising", bias="bullish"),
        vwap=VWAPResult(symbol="6E", current_vwap=100, price_position="above_vwap", bias="bullish"),
        dom=DOMResult(dom_pressure="neutral"),
        absorption=absorption(),
    )

    assert result.market_state == "accumulation"
    assert result.acceptance == "inside_value_area"
    assert result.confidence == 0.8


def test_distribution_inside_value_area_high_volume_negative_delta_weak_price():
    result = calculate_market_state_result(
        price=99,
        volume=1300,
        average_volume=1000,
        price_change_percent=-0.02,
        volume_profile=vp(),
        cumdelta=CumDeltaResult(symbol="6E", current_delta=-250, current_cumdelta=-700, delta_slope="falling", bias="bearish"),
        vwap=VWAPResult(symbol="6E", current_vwap=100, price_position="below_vwap", bias="bearish"),
        dom=DOMResult(dom_pressure="neutral"),
        absorption=absorption(),
    )

    assert result.market_state == "distribution"
    assert result.initiative_side == "bearish"


def test_expansion_on_value_area_break_with_volume_and_delta_confirmation():
    result = calculate_market_state_result(
        price=107,
        volume=1500,
        average_volume=1000,
        volume_profile=vp(),
        cumdelta=CumDeltaResult(symbol="6E", current_delta=400, current_cumdelta=900, delta_slope="rising", bias="bullish"),
        vwap=VWAPResult(symbol="6E", current_vwap=102, distance_percent=4.9, price_position="above_vwap", bias="bullish"),
        dom=DOMResult(dom_pressure="bullish"),
        absorption=absorption(),
    )

    assert result.market_state == "expansion"
    assert result.acceptance == "above_value_area"
    assert result.rejection == "rejected_lower_value"
    assert result.initiative_side == "bullish"
    assert result.confidence == 0.9


def test_exhaustion_overrides_other_constructive_signals():
    result = calculate_market_state_result(
        price=107,
        volume=1500,
        average_volume=1000,
        volume_profile=vp(),
        cumdelta=CumDeltaResult(symbol="6E", current_delta=400, current_cumdelta=900, delta_slope="rising", bias="bullish"),
        vwap=VWAPResult(symbol="6E", current_vwap=102, distance_percent=4.9, price_position="above_vwap", bias="bullish"),
        dom=DOMResult(dom_pressure="bullish"),
        absorption=absorption(exhaustion="bullish", confidence=1, reason="bullish_exhaustion"),
    )

    assert result.market_state == "exhaustion"
    assert result.confidence == 1
    assert any("exhaustion module" in reason for reason in result.reasons)


def test_unknown_when_combined_inputs_have_no_evidence():
    result = calculate_market_state_result(
        price=100,
        volume=0,
        volume_profile=VolumeProfileResult(),
        cumdelta=CumDeltaResult(symbol="6E"),
        vwap=VWAPResult(symbol="6E"),
        dom=DOMResult(),
        absorption=absorption(),
    )

    assert result.market_state == "unknown"
    assert result.confidence == 0
