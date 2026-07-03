from pydantic import BaseModel, Field
from fastapi import APIRouter
from app.models.market import BookLevel, Candle, Trade
from app.models.orderflow import OrderFlowSnapshot
from app.services.engine import engine
from app.services.symbol_mapper import to_futures_symbol
from app.storage.memory_store import store

router = APIRouter(prefix="/api/orderflow")

class IngestPayload(BaseModel):
    symbol: str
    trades: list[Trade] = Field(default_factory=list)
    book: list[BookLevel] = Field(default_factory=list)
    candles: list[Candle] = Field(default_factory=list)

@router.get("/latest", response_model=OrderFlowSnapshot)
async def latest(symbol: str = "EURUSD"):
    return await engine.latest(symbol)

@router.post("/ingest")
def ingest(payload: IngestPayload):
    futures = to_futures_symbol(payload.symbol)
    store.ingest(futures, payload.trades, payload.book, payload.candles)
    return {"status": "ok", "symbol": payload.symbol, "futures_symbol": futures, "trades": len(payload.trades), "book_levels": len(payload.book), "candles": len(payload.candles)}
