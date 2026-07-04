from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator, Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.config import get_settings
from app.models.market import BookLevel, Candle, Trade
from app.providers.base import BaseMarketDataProvider
from app.services.symbol_mapper import to_futures_symbol


class DatabentoProvider(BaseMarketDataProvider):
    name = "databento"
    dataset = "GLBX.MDP3"
    trades_schema = "trades"
    ohlcv_schema = "ohlcv-1m"

    def __init__(self, client: Any | None = None) -> None:
        self.api_key = get_settings().databento_api_key
        self._client = client
        self.provider_status = "ok" if self.configured else "not_configured"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def historical_supported(self) -> bool:
        return self.configured and self.provider_status != "unavailable"

    @property
    def live_supported(self) -> bool:
        return False

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "api_key_present": self.configured,
            "historical_supported": self.historical_supported,
            "live_supported": self.live_supported,
            "status": self.provider_status,
        }

    def _default_window(self, minutes: int = 30) -> tuple[datetime, datetime]:
        end = datetime.now(timezone.utc)
        return end - timedelta(minutes=minutes), end

    def _get_client(self) -> Any | None:
        if not self.configured:
            self.provider_status = "not_configured"
            return None
        if self._client is None:
            try:
                databento = importlib.import_module("databento")
                self._client = databento.Historical(self.api_key)
            except Exception:
                self.provider_status = "unavailable"
                return None
        return self._client

    def _get_range(self, *, schema: str, symbol: str, start: datetime, end: datetime) -> Any:
        client = self._get_client()
        if client is None:
            return []
        return client.timeseries.get_range(
            dataset=self.dataset,
            symbols=[to_futures_symbol(symbol)],
            stype_in="raw_symbol",
            schema=schema,
            start=start,
            end=end,
        )

    @staticmethod
    def _records(response: Any) -> list[dict[str, Any]]:
        if response is None:
            return []
        if isinstance(response, pd.DataFrame):
            return response.reset_index().to_dict("records")
        if hasattr(response, "to_df"):
            return DatabentoProvider._records(response.to_df())
        if isinstance(response, Iterable) and not isinstance(response, (str, bytes, dict)):
            return [item if isinstance(item, dict) else vars(item) for item in response]
        if isinstance(response, dict):
            return [response]
        return []

    @staticmethod
    def _field(row: dict[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            if name in row and row[name] is not None:
                return row[name]
        return default

    @staticmethod
    def _timestamp(row: dict[str, Any]) -> datetime:
        value = DatabentoProvider._field(row, "timestamp", "ts_event", "ts_recv", "time")
        if value is None:
            return datetime.now(timezone.utc)
        parsed = pd.to_datetime(value, utc=True)
        return parsed.to_pydatetime()

    @staticmethod
    def _price(value: Any) -> float:
        if value is None:
            return 0.0
        price = float(value)
        return price / 1_000_000_000 if abs(price) > 1_000_000 else price

    @staticmethod
    def _side(row: dict[str, Any]) -> str:
        side = str(DatabentoProvider._field(row, "side", "aggressor_side", default="unknown")).lower()
        return {"b": "buy", "a": "sell", "ask": "buy", "bid": "sell"}.get(side, side if side in {"buy", "sell"} else "unknown")

    def _trade_from_row(self, symbol: str, row: dict[str, Any]) -> Trade:
        return Trade(
            symbol=to_futures_symbol(symbol),
            timestamp=self._timestamp(row),
            price=self._price(self._field(row, "price", "px", "close", default=0)),
            size=float(self._field(row, "size", "qty", "volume", default=0)),
            side=self._side(row),
        )

    def _candle_from_row(self, symbol: str, row: dict[str, Any]) -> Candle:
        return Candle(
            symbol=to_futures_symbol(symbol),
            timestamp=self._timestamp(row),
            open=self._price(self._field(row, "open", "open_price", default=0)),
            high=self._price(self._field(row, "high", "high_price", default=0)),
            low=self._price(self._field(row, "low", "low_price", default=0)),
            close=self._price(self._field(row, "close", "close_price", default=0)),
            volume=float(self._field(row, "volume", default=0)),
        )

    async def get_recent_trades(self, symbol: str, start=None, end=None) -> list[Trade]:
        if not self.configured:
            self.provider_status = "not_configured"
            return []
        if start is None or end is None:
            start, end = self._default_window()
        try:
            response = await asyncio.to_thread(self._get_range, schema=self.trades_schema, symbol=symbol, start=start, end=end)
            if self.provider_status != "unavailable":
                self.provider_status = "ok"
            return [self._trade_from_row(symbol, row) for row in self._records(response)]
        except Exception:
            self.provider_status = "unavailable" if self.configured else "not_configured"
            return []

    async def get_recent_book(self, symbol: str) -> list[BookLevel]:
        return []

    async def get_ohlcv(self, symbol: str, timeframe: str, start=None, end=None) -> list[Candle]:
        if not self.configured:
            self.provider_status = "not_configured"
            return []
        if start is None or end is None:
            start, end = self._default_window(minutes=120)
        schema = f"ohlcv-{timeframe}"
        try:
            response = await asyncio.to_thread(self._get_range, schema=schema, symbol=symbol, start=start, end=end)
            if self.provider_status != "unavailable":
                self.provider_status = "ok"
            return [self._candle_from_row(symbol, row) for row in self._records(response)]
        except Exception:
            self.provider_status = "unavailable" if self.configured else "not_configured"
            return []

    async def stream_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if False:
            yield Trade(symbol=to_futures_symbol(symbol), price=0, size=0)
