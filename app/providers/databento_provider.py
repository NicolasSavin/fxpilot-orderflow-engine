from __future__ import annotations

import asyncio
import importlib
import importlib.util
import re
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
        self.last_exception: str | None = None
        self.last_request_sent = False
        self.last_trades_loaded = 0
        self.last_history_loaded = False
        self.last_debug: dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def historical_supported(self) -> bool:
        return self.configured and self.provider_status != "unavailable"

    @property
    def live_supported(self) -> bool:
        return False

    @property
    def sdk_available(self) -> bool:
        return importlib.util.find_spec("databento") is not None

    @property
    def symbols_supported(self) -> list[str]:
        return ["6E", "6B", "6J", "GC"]

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

    def diagnostic_snapshot(self, requested_symbol: str, mapped_symbol: str, *, calculators_executed: bool = False) -> dict[str, Any]:
        mapping_succeeded = requested_symbol.upper() != mapped_symbol.upper() or mapped_symbol.upper() in self.symbols_supported
        reason = None
        if not self.configured:
            reason = "api_key_missing"
        elif not self.sdk_available:
            reason = "sdk_unavailable"
        elif self.last_exception:
            reason = self.last_exception
        elif self.provider_status == "unavailable":
            reason = "provider_unavailable"
        elif not self.last_request_sent:
            reason = "request_not_sent"
        elif self.last_trades_loaded == 0:
            reason = "no_trades_returned"
        return {
            "provider": self.name,
            "configured": self.configured,
            "api_key_exists": self.configured,
            "sdk_available": self.sdk_available,
            "sdk_loaded": self.sdk_available,
            "dataset": self.dataset,
            "requested_symbol": requested_symbol,
            "mapped_symbol": mapped_symbol,
            "symbol_mapping_succeeded": mapping_succeeded,
            "request_sent": self.last_request_sent,
            "history_loaded": self.last_history_loaded,
            "trades_loaded": self.last_trades_loaded,
            "trades_returned": self.last_trades_loaded,
            "calculators_executed": calculators_executed,
            "exception": self.last_exception,
            "reason": reason,
        }

    def _get_client(self) -> Any | None:
        if not self.configured:
            self.provider_status = "not_configured"
            return None
        if self._client is None:
            try:
                databento = importlib.import_module("databento")
                self._client = databento.Historical(self.api_key)
            except Exception as exc:
                self.provider_status = "unavailable"
                self.last_exception = str(exc)
                return None
        return self._client

    def _get_range(self, *, schema: str, symbol: str, start: datetime, end: datetime) -> Any:
        client = self._get_client()
        if client is None:
            return []
        self.last_request_sent = True
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
            self.last_exception = None
            self.last_request_sent = False
            self.last_trades_loaded = 0
            return []
        if start is None or end is None:
            start, end = self._default_window()
        try:
            self.last_exception = None
            response = await asyncio.to_thread(self._get_range, schema=self.trades_schema, symbol=symbol, start=start, end=end)
            rows = self._records(response)
            trades = [self._trade_from_row(symbol, row) for row in rows]
            self.last_trades_loaded = len(trades)
            self.last_history_loaded = len(trades) > 0
            if self.provider_status != "unavailable":
                self.provider_status = "ok"
            return trades
        except Exception as exc:
            self.provider_status = "unavailable" if self.configured else "not_configured"
            self.last_exception = str(exc)
            self.last_trades_loaded = 0
            self.last_history_loaded = False
            return []

    async def get_recent_book(self, symbol: str) -> list[BookLevel]:
        return []

    async def get_ohlcv(self, symbol: str, timeframe: str, start=None, end=None) -> list[Candle]:
        if not self.configured:
            self.provider_status = "not_configured"
            self.last_exception = None
            return []
        if start is None or end is None:
            start, end = self._default_window(minutes=120)
        schema = f"ohlcv-{timeframe}"
        try:
            response = await asyncio.to_thread(self._get_range, schema=schema, symbol=symbol, start=start, end=end)
            if self.provider_status != "unavailable":
                self.provider_status = "ok"
            return [self._candle_from_row(symbol, row) for row in self._records(response)]
        except Exception as exc:
            self.provider_status = "unavailable" if self.configured else "not_configured"
            self.last_exception = str(exc)
            return []

    @staticmethod
    def _parse_available_end(error: Exception) -> datetime | None:
        text = str(error)
        if "data_end_after_available_end" not in text and "available_end" not in text:
            return None
        match = re.search(r"available_end[\s=:]+['\"]?([^'\"\s,}]+)", text)
        if not match:
            return None
        try:
            parsed = pd.to_datetime(match.group(1), utc=True)
        except Exception:
            return None
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _trade_summary(trades: list[Trade]) -> dict[str, Any] | None:
        if not trades:
            return None
        prices = [trade.price for trade in trades]
        return {
            "count": len(trades),
            "first_time": DatabentoProvider._format_timestamp(trades[0].timestamp),
            "last_time": DatabentoProvider._format_timestamp(trades[-1].timestamp),
            "price_range": {"min": min(prices), "max": max(prices)},
            "total_volume": sum(trade.size for trade in trades),
        }

    async def debug_historical_connection(
        self,
        symbol: str = "6E",
        *,
        lookback_hours: int = 72,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        configured = self.configured
        sdk_available = self.sdk_available
        base: dict[str, Any] = {
            "configured": configured,
            "sdk_available": sdk_available,
            "connection": "not_checked",
            "dataset": self.dataset,
            "symbols_supported": self.symbols_supported,
            "historical_available": False,
        }
        if not configured:
            self.provider_status = "not_configured"
            return {**base, "connection": "not_configured", "message": "DATABENTO_API_KEY is not configured."}
        if not sdk_available:
            self.provider_status = "unavailable"
            return {**base, "connection": "sdk_unavailable", "message": "databento package is not installed."}

        end_time = (end or (datetime.now(timezone.utc) - timedelta(minutes=30))).astimezone(timezone.utc)
        start_time = end_time - timedelta(hours=lookback_hours)
        retry_used = False
        futures_symbol = to_futures_symbol(symbol)
        try:
            response = await asyncio.to_thread(
                self._get_range,
                schema=self.trades_schema,
                symbol=futures_symbol,
                start=start_time,
                end=end_time,
            )
        except Exception as exc:
            available_end = self._parse_available_end(exc)
            if available_end is None:
                self.provider_status = "unavailable"
                return {
                    **base,
                    "connection": "error",
                    "symbol": futures_symbol,
                    "window": {
                        "start": self._format_timestamp(start_time),
                        "end": self._format_timestamp(end_time),
                    },
                    "actual_start": self._format_timestamp(start_time),
                    "actual_end": self._format_timestamp(end_time),
                    "retry_used": retry_used,
                    "message": f"Databento historical connection failed: {exc}",
                }
            retry_used = True
            end_time = (available_end - timedelta(minutes=1)).astimezone(timezone.utc)
            start_time = end_time - timedelta(hours=lookback_hours)
            try:
                response = await asyncio.to_thread(
                    self._get_range,
                    schema=self.trades_schema,
                    symbol=futures_symbol,
                    start=start_time,
                    end=end_time,
                )
            except Exception as retry_exc:
                self.provider_status = "unavailable"
                return {
                    **base,
                    "connection": "error",
                    "symbol": futures_symbol,
                    "window": {
                        "start": self._format_timestamp(start_time),
                        "end": self._format_timestamp(end_time),
                    },
                    "actual_start": self._format_timestamp(start_time),
                    "actual_end": self._format_timestamp(end_time),
                    "retry_used": retry_used,
                    "message": f"Databento historical connection failed: {retry_exc}",
                }

        rows = self._records(response)
        trades = [self._trade_from_row(futures_symbol, row) for row in rows]
        self.provider_status = "ok"
        window = {"start": self._format_timestamp(start_time), "end": self._format_timestamp(end_time)}
        summary = self._trade_summary(trades)
        if summary is None:
            return {
                **base,
                "connection": "ok",
                "symbol": futures_symbol,
                "window": window,
                "actual_start": self._format_timestamp(start_time),
                "actual_end": self._format_timestamp(end_time),
                "retry_used": retry_used,
                "message": "Databento historical connection established, but no trades were returned for the requested symbol and time window.",
            }
        return {
            **base,
            "connection": "ok",
            "symbol": futures_symbol,
            "window": window,
            "actual_start": self._format_timestamp(start_time),
            "actual_end": self._format_timestamp(end_time),
            "retry_used": retry_used,
            "historical_available": True,
            "trades": summary,
            "message": "Databento historical connection established.",
        }

    async def stream_trades(self, symbol: str) -> AsyncIterator[Trade]:
        if False:
            yield Trade(symbol=to_futures_symbol(symbol), price=0, size=0)
