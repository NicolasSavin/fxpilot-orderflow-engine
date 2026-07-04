from datetime import datetime, timezone

import asyncio

import pytest

from app.config import get_settings
from app.providers.databento_provider import DatabentoProvider
from app.services.symbol_mapper import to_futures_symbol


class FakeDatabentoResponse:
    def __init__(self, rows):
        self.rows = rows

    def to_df(self):
        import pandas as pd

        return pd.DataFrame(self.rows)


class FakeTimeseries:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_range(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.timeseries = FakeTimeseries(response)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_symbol_mapper_maps_required_fx_symbols():
    assert to_futures_symbol("EURUSD") == "6E"
    assert to_futures_symbol("GBPUSD") == "6B"
    assert to_futures_symbol("USDJPY") == "6J"
    assert to_futures_symbol("XAUUSD") == "GC"


def test_missing_api_key_returns_not_configured(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    provider = DatabentoProvider()

    assert asyncio.run(provider.get_recent_trades("EURUSD")) == []
    assert asyncio.run(provider.get_ohlcv("EURUSD", "1m")) == []
    assert provider.status() == {
        "provider": "databento",
        "api_key_present": False,
        "historical_supported": False,
        "live_supported": False,
        "status": "not_configured",
    }


def test_get_recent_trades_normalizes_databento_response(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    rows = [{"ts_event": datetime(2026, 1, 1, tzinfo=timezone.utc), "price": 1_145_000_000, "size": 3, "side": "B"}]
    client = FakeClient(FakeDatabentoResponse(rows))
    provider = DatabentoProvider(client=client)

    trades = asyncio.run(provider.get_recent_trades("EURUSD"))

    assert provider.provider_status == "ok"
    assert client.timeseries.calls[0]["symbols"] == ["6E"]
    assert client.timeseries.calls[0]["schema"] == "trades"
    assert trades[0].symbol == "6E"
    assert trades[0].price == 1.145
    assert trades[0].size == 3
    assert trades[0].side == "buy"


def test_get_ohlcv_normalizes_databento_response(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    rows = [{"ts_event": datetime(2026, 1, 1, tzinfo=timezone.utc), "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]
    client = FakeClient(FakeDatabentoResponse(rows))
    provider = DatabentoProvider(client=client)

    candles = asyncio.run(provider.get_ohlcv("XAUUSD", "1m"))

    assert client.timeseries.calls[0]["symbols"] == ["GC"]
    assert client.timeseries.calls[0]["schema"] == "ohlcv-1m"
    assert candles[0].symbol == "GC"
    assert candles[0].open == 10
    assert candles[0].high == 12
    assert candles[0].low == 9
    assert candles[0].close == 11
    assert candles[0].volume == 100


def test_databento_failure_returns_unavailable(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")

    class BrokenTimeseries:
        def get_range(self, **kwargs):
            raise RuntimeError("databento unavailable")

    class BrokenClient:
        timeseries = BrokenTimeseries()

    provider = DatabentoProvider(client=BrokenClient())

    assert asyncio.run(provider.get_recent_trades("EURUSD")) == []
    assert provider.status()["status"] == "unavailable"


def test_debug_historical_connection_reports_trade_summary(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    monkeypatch.setattr(DatabentoProvider, "sdk_available", property(lambda self: True))
    rows = [
        {"ts_event": datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc), "price": 1_140_000_000, "size": 2, "side": "B"},
        {"ts_event": datetime(2026, 7, 1, 10, 1, tzinfo=timezone.utc), "price": 1_145_000_000, "size": 3, "side": "A"},
    ]
    client = FakeClient(FakeDatabentoResponse(rows))
    provider = DatabentoProvider(client=client)

    result = asyncio.run(
        provider.debug_historical_connection(
            end=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert result["configured"] is True
    assert result["sdk_available"] is True
    assert result["connection"] == "ok"
    assert result["dataset"] == "GLBX.MDP3"
    assert result["symbols_supported"] == ["6E", "6B", "6J", "GC"]
    assert result["historical_available"] is True
    assert result["message"] == "Databento historical connection established."
    assert result["trades"] == {
        "count": 2,
        "first_time": "2026-07-01T10:00:00Z",
        "last_time": "2026-07-01T10:01:00Z",
        "price_range": {"min": 1.14, "max": 1.145},
        "total_volume": 5.0,
    }
    assert client.timeseries.calls[0]["dataset"] == "GLBX.MDP3"
    assert client.timeseries.calls[0]["symbols"] == ["6E"]
    assert client.timeseries.calls[0]["schema"] == "trades"


def test_debug_historical_connection_reports_empty_window(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    monkeypatch.setattr(DatabentoProvider, "sdk_available", property(lambda self: True))
    provider = DatabentoProvider(client=FakeClient(FakeDatabentoResponse([])))

    result = asyncio.run(provider.debug_historical_connection())

    assert result["connection"] == "ok"
    assert result["historical_available"] is False
    assert "no trades were returned" in result["message"]


def test_debug_historical_connection_reports_missing_sdk(monkeypatch):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    monkeypatch.setattr(DatabentoProvider, "sdk_available", property(lambda self: False))
    provider = DatabentoProvider()

    result = asyncio.run(provider.debug_historical_connection())

    assert result["configured"] is True
    assert result["sdk_available"] is False
    assert result["connection"] == "sdk_unavailable"
    assert result["historical_available"] is False
    assert "databento package is not installed" in result["message"]
