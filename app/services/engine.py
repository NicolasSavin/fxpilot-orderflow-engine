from datetime import datetime, timezone
from app.calculators.absorption import calculate_absorption
from app.calculators.cumdelta import update_cumdelta
from app.calculators.delta import calculate_delta
from app.calculators.dom_pressure import calculate_dom_pressure
from app.calculators.market_state import calculate_market_state
from app.calculators.value_area import calculate_value_area
from app.calculators.volume_profile import calculate_volume_profile
from app.calculators.vwap import calculate_vwap
from app.config import get_settings
from app.models.market import Candle
from app.models.orderflow import OrderFlowSnapshot
from app.providers.base import ProviderNotConfiguredError
from app.providers.databento_provider import DatabentoProvider
from app.providers.mock_provider import MockProvider
from app.services.normalizer import ohlcv_to_candles
from app.services.symbol_mapper import supported_symbols, to_futures_symbol, to_fx_symbol
from app.storage.memory_store import store


def build_provider():
    return DatabentoProvider() if get_settings().orderflow_provider.lower() == "databento" else MockProvider()


class OrderFlowEngine:
    def __init__(self) -> None:
        self.provider = build_provider()

    async def latest(self, symbol: str) -> OrderFlowSnapshot:
        settings = get_settings(); futures = to_futures_symbol(symbol); fx = to_fx_symbol(futures); status = "ok"
        try:
            trades = store.trades.get(futures) or await self.provider.get_recent_trades(futures)
            book = store.books.get(futures) or await self.provider.get_recent_book(futures)
            ohlcv = await self.provider.get_ohlcv(futures, "1m")
        except ProviderNotConfiguredError:
            trades, book, ohlcv, status = [], [], [], "not_configured"
        candles = store.candles.get(futures) or ohlcv_to_candles(futures, ohlcv)
        if not candles and trades:
            candles = [Candle(symbol=futures, timestamp=trades[-1].timestamp, open=trades[0].price, high=max(t.price for t in trades), low=min(t.price for t in trades), close=trades[-1].price, volume=sum(t.size for t in trades))]
        delta = calculate_delta(trades)
        cumdelta = update_cumdelta(futures, delta["delta"])
        profile = calculate_volume_profile(trades, settings.tick_size_for(futures))
        va = calculate_value_area(profile["volume_by_price"], settings.value_area_percent)
        dom = calculate_dom_pressure(book)
        absorption = calculate_absorption(candles, delta["delta"], profile["total_volume"])
        state = calculate_market_state(candles, delta["delta"], cumdelta, profile["total_volume"], va["vah"], va["val"])
        snapshot = OrderFlowSnapshot(
            symbol=fx, futures_symbol=futures, timestamp=datetime.now(timezone.utc), provider=self.provider.name, provider_status=status,
            delta=delta["delta"], cumdelta=cumdelta, volume=profile["total_volume"], rvol=1.0 if profile["total_volume"] else 0,
            vwap=calculate_vwap(trades), poc=profile["poc"], vah=va["vah"], val=va["val"], hvn_levels=va["hvn_levels"], lvn_levels=va["lvn_levels"],
            dom_pressure=dom["dom_pressure"], imbalance=dom["imbalance"], absorption=absorption, **state,
            orderflow_provider=self.provider.name, orderflow_available=status == "ok",
            debug={"buy_volume": delta["buy_volume"], "sell_volume": delta["sell_volume"], "unknown_volume": delta["unknown_volume"], "profile_levels": len(profile["volume_by_price"])}
        )
        store.last_update = snapshot.timestamp
        return snapshot

    def debug(self) -> dict:
        return {"provider": self.provider.name, "symbols": supported_symbols(), "store_size": store.store_size, "last_update": store.last_update}

    def provider_status(self) -> dict:
        databento = DatabentoProvider()
        return {"provider": self.provider.name, "databento_configured": databento.configured, "live_enabled": False, "historical_enabled": False}


engine = OrderFlowEngine()
