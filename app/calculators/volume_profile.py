from decimal import Decimal, ROUND_HALF_UP

from app.models.market import Trade
from app.models.orderflow import VolumeProfileLevel, VolumeProfileResult


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def price_to_tick(price: float, tick_size: float) -> int:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    return int((_to_decimal(price) / _to_decimal(tick_size)).to_integral_value(rounding=ROUND_HALF_UP))


def price_level(price: float, tick_size: float) -> float:
    tick = price_to_tick(price, tick_size)
    return float(_to_decimal(tick) * _to_decimal(tick_size))


def _side_for_trade(trade: Trade, previous_price: float | None) -> str:
    if trade.side != "unknown":
        return trade.side
    if previous_price is None:
        return "unknown"
    current_tick = _to_decimal(trade.price)
    previous_tick = _to_decimal(previous_price)
    if current_tick > previous_tick:
        return "buy"
    if current_tick < previous_tick:
        return "sell"
    return "unknown"


def _local_extrema(levels: list[VolumeProfileLevel], *, find_maxima: bool) -> list[float]:
    extrema: list[float] = []
    for index, level in enumerate(levels):
        left = levels[index - 1].total_volume if index > 0 else None
        right = levels[index + 1].total_volume if index < len(levels) - 1 else None
        neighbours = [volume for volume in (left, right) if volume is not None]
        if not neighbours:
            continue
        if find_maxima and all(level.total_volume > volume for volume in neighbours):
            extrema.append(level.price)
        if not find_maxima and all(level.total_volume < volume for volume in neighbours):
            extrema.append(level.price)
    return extrema


def _calculate_value_area(levels: list[VolumeProfileLevel], poc_index: int, percent: float) -> tuple[float, float]:
    if not levels:
        return 0, 0
    total_volume = sum(level.total_volume for level in levels)
    target_volume = total_volume * percent
    low = high = poc_index
    accumulated = levels[poc_index].total_volume

    while accumulated < target_volume and (low > 0 or high < len(levels) - 1):
        down_volume = levels[low - 1].total_volume if low > 0 else None
        up_volume = levels[high + 1].total_volume if high < len(levels) - 1 else None

        if up_volume is None:
            low -= 1
            accumulated += down_volume or 0
        elif down_volume is None:
            high += 1
            accumulated += up_volume
        elif up_volume >= down_volume:
            high += 1
            accumulated += up_volume
        else:
            low -= 1
            accumulated += down_volume

    return levels[high].price, levels[low].price


def calculate_volume_profile(trades: list[Trade], tick_size: float, value_area_percent: float = 0.70) -> dict:
    levels_by_tick: dict[int, VolumeProfileLevel] = {}
    previous_price: float | None = None

    for trade in trades:
        tick = price_to_tick(trade.price, tick_size)
        price = float(_to_decimal(tick) * _to_decimal(tick_size))
        level = levels_by_tick.setdefault(
            tick,
            VolumeProfileLevel(price=price, total_volume=0, buy_volume=0, sell_volume=0, delta=0, trades_count=0),
        )
        level.total_volume += trade.size
        level.trades_count += 1

        side = _side_for_trade(trade, previous_price)
        if side == "buy":
            level.buy_volume += trade.size
        elif side == "sell":
            level.sell_volume += trade.size
        level.delta = level.buy_volume - level.sell_volume
        previous_price = trade.price

    profile_levels = [levels_by_tick[tick] for tick in sorted(levels_by_tick)]
    total_volume = sum(level.total_volume for level in profile_levels)
    buy_volume = sum(level.buy_volume for level in profile_levels)
    sell_volume = sum(level.sell_volume for level in profile_levels)

    if profile_levels:
        poc_index = max(range(len(profile_levels)), key=lambda index: (profile_levels[index].total_volume, -abs(index)))
        poc = profile_levels[poc_index].price
        vah, val = _calculate_value_area(profile_levels, poc_index, value_area_percent)
    else:
        poc = vah = val = 0

    result = VolumeProfileResult(
        profile_levels=profile_levels,
        total_volume=total_volume,
        buy_volume=buy_volume,
        sell_volume=sell_volume,
        delta=buy_volume - sell_volume,
        poc=poc,
        vah=vah,
        val=val,
        hvn_levels=_local_extrema(profile_levels, find_maxima=True),
        lvn_levels=_local_extrema(profile_levels, find_maxima=False),
    )
    volume_by_price = {level.price: level.total_volume for level in result.profile_levels}
    return {
        **result.model_dump(),
        "volume_by_price": volume_by_price,
        "profile": volume_by_price,
    }
