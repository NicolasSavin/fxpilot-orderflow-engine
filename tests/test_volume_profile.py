from app.calculators.poc import calculate_poc
from app.calculators.volume_profile import calculate_volume_profile, price_level
from app.models.market import Trade


def test_volume_profile_normalizes_prices_and_calculates_poc():
    trades = [
        Trade(symbol="6E", price=1.00001, size=5, side="buy"),
        Trade(symbol="6E", price=1.00005, size=10, side="sell"),
        Trade(symbol="6E", price=1.00005, size=2, side="buy"),
    ]
    profile = calculate_volume_profile(trades, 0.00005)
    assert profile["total_volume"] == 17
    assert profile["poc"] == 1.00005
    assert calculate_poc(profile["volume_by_price"]) == 1.00005
    assert price_level(1.00001, 0.00005) == 1.0
    assert profile["profile_levels"][0]["trades_count"] == 1
    assert profile["profile_levels"][1]["trades_count"] == 2


def test_volume_profile_buy_sell_and_delta_per_level_and_total():
    trades = [
        Trade(symbol="6E", price=1.0, size=7, side="buy"),
        Trade(symbol="6E", price=1.0, size=2, side="sell"),
        Trade(symbol="6E", price=1.1, size=4, side="sell"),
        Trade(symbol="6E", price=1.2, size=3, side="buy"),
    ]
    profile = calculate_volume_profile(trades, 0.1)
    levels = {level["price"]: level for level in profile["profile_levels"]}
    assert profile["buy_volume"] == 10
    assert profile["sell_volume"] == 6
    assert profile["delta"] == 4
    assert levels[1.0]["buy_volume"] == 7
    assert levels[1.0]["sell_volume"] == 2
    assert levels[1.0]["delta"] == 5


def test_value_area_vah_val_classic_70_percent_expansion():
    trades = [
        Trade(symbol="6E", price=1.0, size=10),
        Trade(symbol="6E", price=1.1, size=40),
        Trade(symbol="6E", price=1.2, size=100),
        Trade(symbol="6E", price=1.3, size=30),
        Trade(symbol="6E", price=1.4, size=20),
    ]
    profile = calculate_volume_profile(trades, 0.1)
    assert profile["poc"] == 1.2
    assert profile["vah"] == 1.3
    assert profile["val"] == 1.1


def test_hvn_and_lvn_are_local_volume_extrema():
    trades = [
        Trade(symbol="6E", price=1.0, size=10),
        Trade(symbol="6E", price=1.1, size=40),
        Trade(symbol="6E", price=1.2, size=15),
        Trade(symbol="6E", price=1.3, size=50),
        Trade(symbol="6E", price=1.4, size=20),
    ]
    profile = calculate_volume_profile(trades, 0.1)
    assert profile["hvn_levels"] == [1.1, 1.3]
    assert profile["lvn_levels"] == [1.0, 1.2, 1.4]
