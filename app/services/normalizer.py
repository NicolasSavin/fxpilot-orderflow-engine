from app.models.market import Candle


def ohlcv_to_candles(symbol: str, rows: list[dict] | list[Candle]) -> list[Candle]:
    candles: list[Candle] = []
    for row in rows:
        if isinstance(row, Candle):
            candles.append(row if row.symbol else row.model_copy(update={"symbol": symbol}))
        else:
            candles.append(Candle(symbol=symbol, **row))
    return candles
