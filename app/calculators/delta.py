from app.models.market import Trade


def calculate_delta(trades: list[Trade]) -> dict[str, float]:
    delta = buy_volume = sell_volume = unknown_volume = 0.0
    previous_price: float | None = None
    for trade in trades:
        side = trade.side
        if side == "unknown" and previous_price is not None:
            if trade.price > previous_price:
                side = "buy"
            elif trade.price < previous_price:
                side = "sell"
        if side == "buy":
            buy_volume += trade.size
            delta += trade.size
        elif side == "sell":
            sell_volume += trade.size
            delta -= trade.size
        else:
            unknown_volume += trade.size
        previous_price = trade.price
    return {"delta": delta, "buy_volume": buy_volume, "sell_volume": sell_volume, "unknown_volume": unknown_volume}
