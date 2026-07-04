from fastapi import APIRouter, Query

from app.providers.databento_provider import DatabentoProvider

router = APIRouter(prefix="/api/debug")


@router.get("/databento")
async def databento_debug(
    symbol: str = Query(default="6E", description="Raw CME futures symbol to check, defaults to 6E."),
    lookback_hours: int = Query(default=72, ge=1, le=168, description="Historical lookup window in hours."),
):
    provider = DatabentoProvider()
    return await provider.debug_historical_connection(symbol=symbol, lookback_hours=lookback_hours)
