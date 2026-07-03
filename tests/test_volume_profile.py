from app.calculators.poc import calculate_poc
from app.calculators.volume_profile import calculate_volume_profile
from app.models.market import Trade


def test_volume_profile_and_poc():
    trades = [Trade(symbol="6E", price=1.00001, size=5), Trade(symbol="6E", price=1.00005, size=10), Trade(symbol="6E", price=1.00005, size=2)]
    profile = calculate_volume_profile(trades, 0.00005)
    assert profile["total_volume"] == 17
    assert profile["poc"] == 1.00005
    assert calculate_poc(profile["volume_by_price"]) == 1.00005
