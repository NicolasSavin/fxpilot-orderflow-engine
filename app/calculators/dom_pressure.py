from app.models.market import BookLevel


def calculate_dom_pressure(book: list[BookLevel]) -> dict:
    if not book:
        return {"dom_pressure": "unavailable", "imbalance": 0}
    bid_total = sum(level.bid_size for level in book)
    ask_total = sum(level.ask_size for level in book)
    total = bid_total + ask_total
    if total <= 0:
        return {"dom_pressure": "unavailable", "imbalance": 0}
    pressure = bid_total / total
    label = "bullish" if pressure > 0.58 else "bearish" if pressure < 0.42 else "neutral"
    return {"dom_pressure": label, "imbalance": round(pressure - 0.5, 4)}
