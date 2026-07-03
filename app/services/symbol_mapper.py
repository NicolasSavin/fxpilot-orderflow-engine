FX_TO_FUTURES = {"EURUSD": "6E", "GBPUSD": "6B", "USDJPY": "6J", "XAUUSD": "GC"}
FUTURES_TO_FX = {value: key for key, value in FX_TO_FUTURES.items()}


def to_futures_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    return FX_TO_FUTURES.get(normalized, normalized)


def to_fx_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    return FUTURES_TO_FX.get(normalized, normalized)


def supported_symbols() -> list[str]:
    return sorted(set(FX_TO_FUTURES) | set(FUTURES_TO_FX))
