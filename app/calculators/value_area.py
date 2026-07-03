def calculate_value_area(volume_by_price: dict[float, float], percent: float = 0.70) -> dict:
    if not volume_by_price:
        return {"vah": 0, "val": 0, "hvn_levels": [], "lvn_levels": []}
    levels = sorted(volume_by_price)
    volumes = [volume_by_price[level] for level in levels]
    total = sum(volumes)
    poc = max(volume_by_price, key=volume_by_price.get)
    idx = levels.index(poc)
    included = {idx}
    accumulated = volume_by_price[poc]
    low = high = idx
    while accumulated < total * percent and (low > 0 or high < len(levels) - 1):
        down_vol = volume_by_price[levels[low - 1]] if low > 0 else -1
        up_vol = volume_by_price[levels[high + 1]] if high < len(levels) - 1 else -1
        if up_vol >= down_vol and high < len(levels) - 1:
            high += 1
            included.add(high)
            accumulated += up_vol
        elif low > 0:
            low -= 1
            included.add(low)
            accumulated += down_vol
    mean = sum(volumes) / len(volumes)
    variance = sum((volume - mean) ** 2 for volume in volumes) / len(volumes)
    std = variance ** 0.5
    hvn = [level for level in levels if volume_by_price[level] > mean + std][:5]
    lvn = [level for level in levels if volume_by_price[level] < mean - std][:5]
    return {"vah": levels[max(included)], "val": levels[min(included)], "hvn_levels": hvn, "lvn_levels": lvn}
