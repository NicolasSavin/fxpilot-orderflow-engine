from app.models.market import Candle


def ohlcv_to_candles(symbol: str, rows: list[dict]) -> list[Candle]:
    return [Candle(symbol=symbol, **row) for row in rows]
