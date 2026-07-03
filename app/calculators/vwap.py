from app.models.market import Trade


def calculate_vwap(trades: list[Trade]) -> float:
    volume = sum(t.size for t in trades)
    return sum(t.price * t.size for t in trades) / volume if volume else 0
