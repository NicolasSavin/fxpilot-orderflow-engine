from app.models.market import Trade


def price_level(price: float, tick_size: float) -> float:
    return round(round(price / tick_size) * tick_size, 10)


def calculate_volume_profile(trades: list[Trade], tick_size: float) -> dict:
    volume_by_price: dict[float, float] = {}
    for trade in trades:
        level = price_level(trade.price, tick_size)
        volume_by_price[level] = volume_by_price.get(level, 0) + trade.size
    total_volume = sum(volume_by_price.values())
    poc = max(volume_by_price, key=volume_by_price.get) if volume_by_price else 0
    sorted_profile = dict(sorted(volume_by_price.items()))
    return {"volume_by_price": sorted_profile, "total_volume": total_volume, "poc": poc, "profile": sorted_profile}
