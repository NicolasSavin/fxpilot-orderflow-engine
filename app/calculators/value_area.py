from app.models.market import Trade
from app.calculators.volume_profile import calculate_volume_profile


def calculate_value_area(volume_by_price: dict[float, float], percent: float = 0.70) -> dict:
    trades = [Trade(symbol="VALUE_AREA", price=price, size=volume) for price, volume in volume_by_price.items()]
    if not trades:
        return {"vah": 0, "val": 0, "hvn_levels": [], "lvn_levels": []}
    prices = sorted(volume_by_price)
    tick_size = min((round(prices[index + 1] - prices[index], 10) for index in range(len(prices) - 1)), default=1.0)
    profile = calculate_volume_profile(trades, tick_size, percent)
    return {"vah": profile["vah"], "val": profile["val"], "hvn_levels": profile["hvn_levels"], "lvn_levels": profile["lvn_levels"]}
