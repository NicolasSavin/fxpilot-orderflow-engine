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
from app.models.market import BookLevel, Candle, Trade
from app.models.orderflow import OrderFlowSnapshot
from app.providers.base import ProviderNotConfiguredError
from app.providers.databento_provider import DatabentoProvider
from app.providers.mock_provider import MockProvider
from app.services.normalizer import ohlcv_to_candles
from app.services.source_manager import source_manager
from app.services.symbol_mapper import supported_symbols, to_futures_symbol, to_fx_symbol
from app.storage.memory_store import store


def calculate_rvol(candles: list[Candle], current_volume: float) -> tuple[float, str | None]:
    if len(candles) >= 2:
        previous_volumes = [c.volume for c in candles[:-1] if c.volume > 0]
        if previous_volumes:
            average_volume = sum(previous_volumes) / len(previous_volumes)
            if average_volume > 0:
                return round(candles[-1].volume / average_volume, 4), None
    return 0, "not_enough_history"


def build_provider():
    return DatabentoProvider() if get_settings().orderflow_provider.lower() == "databento" else MockProvider()


class OrderFlowEngine:
    def __init__(self) -> None:
        self.provider = build_provider()

    def _build_snapshot(
        self,
        *,
        requested_symbol: str,
        futures: str,
        trades: list[Trade],
        book: list[BookLevel],
        candles: list[Candle],
        provider_name: str,
        status: str,
        provider_debug: dict,
        timestamp: datetime | None = None,
    ) -> OrderFlowSnapshot:
        settings = get_settings()
        fx = to_fx_symbol(futures)
        delta = calculate_delta(trades)
        cumdelta = store.cumdelta.get(futures, 0.0)
        profile = calculate_volume_profile(trades, settings.tick_size_for(futures))
        va = calculate_value_area(profile["volume_by_price"], settings.value_area_percent)
        dom = calculate_dom_pressure(book)
        absorption = calculate_absorption(candles, delta["delta"], profile["total_volume"])
        rvol, rvol_reason = calculate_rvol(candles, profile["total_volume"])
        state = calculate_market_state(candles, delta["delta"], cumdelta, profile["total_volume"], va["vah"], va["val"])
        return OrderFlowSnapshot(
            symbol=fx, futures_symbol=futures, timestamp=timestamp or datetime.now(timezone.utc), provider=provider_name, provider_status=status, provider_debug=provider_debug,
            delta=delta["delta"], cumdelta=cumdelta, volume=profile["total_volume"], rvol=rvol,
            vwap=calculate_vwap(trades), poc=profile["poc"], vah=va["vah"], val=va["val"], hvn_levels=va["hvn_levels"], lvn_levels=va["lvn_levels"],
            dom_pressure=dom["dom_pressure"], imbalance=dom["imbalance"], absorption=absorption, **state,
            orderflow_provider=provider_name, orderflow_available=status == "ok",
            debug={"buy_volume": delta["buy_volume"], "sell_volume": delta["sell_volume"], "unknown_volume": delta["unknown_volume"], "profile_levels": len(profile["volume_by_price"]), "rvol_reason": rvol_reason, "source": provider_debug.get("source")},
        )

    def ingest_live_tick(self, *, symbol: str, bid: float, ask: float, last: float, volume: float, timestamp: datetime) -> OrderFlowSnapshot:
        futures = to_futures_symbol(symbol)
        previous_trades = store.trades.get(futures, [])
        previous_price = previous_trades[-1].price if previous_trades else None
        side = "buy" if last >= ask else "sell" if last <= bid else "unknown"
        if side == "unknown" and previous_price is not None:
            side = "buy" if last > previous_price else "sell" if last < previous_price else "unknown"
        trade = Trade(symbol=futures, timestamp=timestamp, price=last, size=volume, side=side)
        spread_volume = volume / 2 if volume else 0
        book = [BookLevel(price=bid, bid_size=spread_volume, ask_size=0), BookLevel(price=ask, bid_size=0, ask_size=spread_volume)]
        candle = Candle(symbol=futures, timestamp=timestamp, open=previous_price if previous_price is not None else last, high=max(previous_price if previous_price is not None else last, last), low=min(previous_price if previous_price is not None else last, last), close=last, volume=volume)
        store.ingest(futures, trades=[trade], book=book, candles=[candle])
        from app.calculators.cumdelta import CumDeltaEngine
        CumDeltaEngine(memory_store=store).process_trade(trade)
        snapshot = self._build_snapshot(
            requested_symbol=symbol, futures=futures, trades=store.trades.get(futures, []), book=store.books.get(futures, []), candles=store.candles.get(futures, []),
            provider_name=self.provider.name, status="ok", timestamp=timestamp,
            provider_debug={"provider": self.provider.name, "source": "live_mt4_bridge", "requested_symbol": symbol, "mapped_symbol": futures, "trades_loaded": len(store.trades.get(futures, [])), "calculators_executed": True},
        )
        snapshot = source_manager.apply_metadata(snapshot, "mt4_live", reason="mt4_live_snapshot_ingested", age_seconds=0)
        store.set_live_snapshot(futures, snapshot)
        store.set_cache_snapshot(futures, snapshot)
        return snapshot

    async def latest(self, symbol: str) -> OrderFlowSnapshot:
        futures = to_futures_symbol(symbol)
        databento_snapshot: OrderFlowSnapshot | None = None
        provider_exception: str | None = None

        try:
            trades = await self.provider.get_recent_trades(futures)
            book = await self.provider.get_recent_book(futures)
            ohlcv = await self.provider.get_ohlcv(futures, "1m")
            status = getattr(self.provider, "provider_status", "ok")
        except ProviderNotConfiguredError as exc:
            trades, book, ohlcv, status = [], [], [], "not_configured"
            provider_exception = str(exc) or "provider_not_configured"
        except Exception as exc:
            trades, book, ohlcv, status = [], [], [], "unavailable"
            provider_exception = str(exc)

        candles = ohlcv_to_candles(futures, ohlcv)
        if not candles and trades:
            candles = [Candle(symbol=futures, timestamp=trades[-1].timestamp, open=trades[0].price, high=max(t.price for t in trades), low=min(t.price for t in trades), close=trades[-1].price, volume=sum(t.size for t in trades))]
        delta = calculate_delta(trades)
        cumdelta = update_cumdelta(futures, delta["delta"])
        profile = calculate_volume_profile(trades, get_settings().tick_size_for(futures))

        if hasattr(self.provider, "diagnostic_snapshot"):
            provider_debug = self.provider.diagnostic_snapshot(symbol, futures, calculators_executed=True)
        else:
            provider_debug = {
                "provider": self.provider.name, "configured": True, "api_key_exists": False, "sdk_available": False,
                "sdk_loaded": False, "requested_symbol": symbol, "mapped_symbol": futures, "symbol_mapping_succeeded": True,
                "request_sent": True, "history_loaded": bool(trades or ohlcv), "trades_loaded": len(trades),
                "trades_returned": len(trades), "calculators_executed": True, "exception": provider_exception, "reason": provider_exception,
            }
        if provider_exception and not provider_debug.get("exception"):
            provider_debug["exception"] = provider_exception
            provider_debug["reason"] = provider_exception

        databento_snapshot = self._build_snapshot(
            requested_symbol=symbol, futures=futures, trades=trades, book=book, candles=candles,
            provider_name=self.provider.name, status=status, provider_debug=provider_debug
        )

        decision = source_manager.choose(
            databento=databento_snapshot,
            mt4_live=store.live_snapshot(futures),
            cache=store.cache_snapshot(futures),
        )
        if decision.snapshot is not None:
            selected = source_manager.apply_metadata(
                decision.snapshot, decision.source, reason=decision.reason, age_seconds=decision.age_seconds
            )
            if decision.source == "databento":
                store.set_cache_snapshot(futures, selected)
            return selected

        unavailable = source_manager.apply_metadata(
            databento_snapshot, "unavailable", reason=decision.reason, age_seconds=decision.age_seconds
        )
        store.last_update = unavailable.timestamp
        return unavailable

    def source_status(self, symbol: str) -> dict:
        futures = to_futures_symbol(symbol)
        databento = store.cache_snapshot(futures)
        if databento is not None and databento.data_source != "databento":
            databento = None
        live = store.live_snapshot(futures)
        cache = store.cache_snapshot(futures)
        decision = source_manager.choose(databento=databento, mt4_live=live, cache=cache)
        return {
            "symbol": to_fx_symbol(futures),
            "active_source": decision.source,
            "databento": source_manager.status_block(databento),
            "mt4_live": source_manager.status_block(live),
            "cache": source_manager.status_block(cache),
            "decision_reason": decision.reason,
        }

    def debug(self) -> dict:
        return {"provider": self.provider.name, "symbols": supported_symbols(), "store_size": store.store_size, "last_update": store.last_update}

    def provider_status(self) -> dict:
        settings = get_settings()
        provider = DatabentoProvider() if settings.orderflow_provider.lower() == "databento" else self.provider
        if hasattr(provider, "status"):
            return provider.status()
        return {
            "provider": provider.name,
            "api_key_present": False,
            "historical_supported": True,
            "live_supported": False,
            "status": "ok",
        }


engine = OrderFlowEngine()
