def calculate_poc(volume_by_price: dict[float, float]) -> float:
    return max(volume_by_price, key=volume_by_price.get) if volume_by_price else 0
