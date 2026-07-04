from typing import Iterable

from app.models.market import BookLevel, OrderBookLevel
from app.models.orderflow import DOMResult

BULLISH_IMBALANCE_THRESHOLD = 0.58
BEARISH_IMBALANCE_THRESHOLD = 0.42
THIN_LIQUIDITY_RATIO = 0.65


def _normalize_book(book: Iterable[BookLevel | OrderBookLevel]) -> list[OrderBookLevel]:
    levels: list[OrderBookLevel] = []
    for index, level in enumerate(book):
        level_index = getattr(level, "level_index", index)
        levels.append(
            OrderBookLevel(
                price=level.price,
                bid_size=level.bid_size,
                ask_size=level.ask_size,
                level_index=level_index,
            )
        )
    return levels


def calculate_dom_engine(book: list[BookLevel | OrderBookLevel]) -> DOMResult:
    levels = _normalize_book(book)
    if not levels:
        return DOMResult(
            dom_pressure="unavailable",
            debug={"reason": "empty_book", "levels": 0},
        )

    bid_total = sum(level.bid_size for level in levels)
    ask_total = sum(level.ask_size for level in levels)
    total_liquidity = bid_total + ask_total
    if total_liquidity <= 0:
        return DOMResult(
            bid_total=bid_total,
            ask_total=ask_total,
            total_liquidity=total_liquidity,
            dom_pressure="unavailable",
            debug={"reason": "zero_liquidity", "levels": len(levels)},
        )

    imbalance_ratio = bid_total / total_liquidity
    if imbalance_ratio > BULLISH_IMBALANCE_THRESHOLD:
        dom_pressure = "bullish"
    elif imbalance_ratio < BEARISH_IMBALANCE_THRESHOLD:
        dom_pressure = "bearish"
    else:
        dom_pressure = "neutral"

    strongest_bid_level = max(levels, key=lambda level: level.bid_size)
    strongest_ask_level = max(levels, key=lambda level: level.ask_size)
    liquidity_below = bid_total
    liquidity_above = ask_total

    largest_bid = strongest_bid_level.bid_size
    largest_ask = strongest_ask_level.ask_size
    average_level_size = total_liquidity / (len(levels) * 2)
    if largest_bid <= 0 and largest_ask <= 0:
        wall_side = "none"
        wall_price = None
        wall_strength = 0
    elif largest_bid >= largest_ask:
        wall_side = "bid"
        wall_price = strongest_bid_level.price
        wall_strength = largest_bid / average_level_size if average_level_size > 0 else 0
    else:
        wall_side = "ask"
        wall_price = strongest_ask_level.price
        wall_strength = largest_ask / average_level_size if average_level_size > 0 else 0

    thin_liquidity_side = "none"
    if liquidity_above < liquidity_below * THIN_LIQUIDITY_RATIO:
        thin_liquidity_side = "above"
    elif liquidity_below < liquidity_above * THIN_LIQUIDITY_RATIO:
        thin_liquidity_side = "below"

    return DOMResult(
        bid_total=bid_total,
        ask_total=ask_total,
        total_liquidity=total_liquidity,
        imbalance_ratio=imbalance_ratio,
        dom_pressure=dom_pressure,
        strongest_bid_level=strongest_bid_level,
        strongest_ask_level=strongest_ask_level,
        liquidity_above=liquidity_above,
        liquidity_below=liquidity_below,
        liquidity_wall_side=wall_side,
        liquidity_wall_price=wall_price,
        liquidity_wall_strength=round(wall_strength, 4),
        thin_liquidity_side=thin_liquidity_side,
        debug={
            "levels": len(levels),
            "bullish_threshold": BULLISH_IMBALANCE_THRESHOLD,
            "bearish_threshold": BEARISH_IMBALANCE_THRESHOLD,
            "thin_liquidity_ratio": THIN_LIQUIDITY_RATIO,
            "average_level_size": round(average_level_size, 4),
        },
    )


def calculate_dom_pressure(book: list[BookLevel | OrderBookLevel]) -> dict:
    result = calculate_dom_engine(book)
    if result.dom_pressure == "unavailable":
        return {"dom_pressure": "unavailable", "imbalance": 0}
    return {"dom_pressure": result.dom_pressure, "imbalance": round(result.imbalance_ratio - 0.5, 4)}
