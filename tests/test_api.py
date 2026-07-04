from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models.market import Candle
from app.services.engine import calculate_rvol

client = TestClient(app)


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fxpilot-orderflow-engine"}


def test_latest_snapshot_returns_valid_schema():
    response = client.get("/api/orderflow/latest?symbol=EURUSD")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "EURUSD"
    assert data["futures_symbol"] == "6E"
    assert data["provider"] == "mock"
    assert data["provider_status"] == "ok"
    assert data["orderflow_available"] is True
    assert data["rvol"] > 0
    assert data["debug"]["rvol_reason"] is None
    for key in [
        "delta",
        "cumdelta",
        "poc",
        "vah",
        "val",
        "vwap",
        "rvol",
        "dom_pressure",
        "absorption",
        "market_state",
        "orderflow_bias",
        "continuation_probability",
        "reversal_probability",
    ]:
        assert key in data


def test_provider_status_reports_databento_configuration(monkeypatch):
    monkeypatch.setenv("ORDERFLOW_PROVIDER", "databento")
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    get_settings.cache_clear()

    response = client.get("/api/orderflow/provider/status")

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json() == {
        "provider": "databento",
        "api_key_present": True,
        "historical_supported": True,
        "live_supported": False,
        "status": "ok",
    }


def test_ingest_accepts_market_payload():
    payload = {
        "symbol": "EURUSD",
        "trades": [
            {"symbol": "6E", "price": 1.145, "size": 10, "side": "buy"},
            {"symbol": "6E", "price": 1.14505, "size": 5, "side": "sell"},
        ],
        "book": [{"price": 1.145, "bid_size": 100, "ask_size": 80}],
        "candles": [
            {"symbol": "6E", "open": 1.144, "high": 1.146, "low": 1.143, "close": 1.145, "volume": 1000},
            {"symbol": "6E", "open": 1.145, "high": 1.147, "low": 1.144, "close": 1.146, "volume": 1500},
        ],
    }

    response = client.post("/api/orderflow/ingest", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "symbol": "EURUSD",
        "futures_symbol": "6E",
        "trades": 2,
        "book_levels": 1,
        "candles": 2,
    }


def test_symbols_returns_supported_fx_symbols():
    response = client.get("/api/orderflow/symbols")
    assert response.status_code == 200
    assert response.json() == ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]


def test_rvol_without_history_returns_reason():
    candle = Candle(symbol="6E", open=1, high=1, low=1, close=1, volume=100)
    assert calculate_rvol([candle], 100) == (0, "not_enough_history")


def test_databento_debug_endpoint(monkeypatch):
    async def fake_debug(self, symbol="6E", *, lookback_hours=72, end=None):
        return {
            "configured": True,
            "sdk_available": True,
            "connection": "ok",
            "dataset": "GLBX.MDP3",
            "symbols_supported": ["6E", "6B", "6J", "GC"],
            "historical_available": True,
            "message": "Databento historical connection established.",
            "symbol": symbol,
            "lookback_hours": lookback_hours,
        }

    monkeypatch.setattr("app.providers.databento_provider.DatabentoProvider.debug_historical_connection", fake_debug)

    response = client.get("/api/debug/databento?symbol=6E&lookback_hours=24")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "sdk_available": True,
        "connection": "ok",
        "dataset": "GLBX.MDP3",
        "symbols_supported": ["6E", "6B", "6J", "GC"],
        "historical_available": True,
        "message": "Databento historical connection established.",
        "symbol": "6E",
        "lookback_hours": 24,
    }


def test_latest_includes_databento_provider_debug(monkeypatch):
    from app.api import routes_orderflow
    from app.providers.databento_provider import DatabentoProvider

    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(DatabentoProvider, "sdk_available", property(lambda self: True))

    class BrokenTimeseries:
        def get_range(self, **kwargs):
            raise RuntimeError("dataset_unavailable: GLBX.MDP3 rejected 6E")

    class BrokenClient:
        timeseries = BrokenTimeseries()

    original_provider = routes_orderflow.engine.provider
    routes_orderflow.engine.provider = DatabentoProvider(client=BrokenClient())
    try:
        response = client.get("/api/orderflow/latest?symbol=EURUSD")
    finally:
        routes_orderflow.engine.provider = original_provider
        get_settings.cache_clear()

    assert response.status_code == 200
    data = response.json()
    assert data["provider_status"] == "unavailable"
    assert data["provider_debug"]["provider"] == "databento"
    assert data["provider_debug"]["configured"] is True
    assert data["provider_debug"]["api_key_exists"] is True
    assert data["provider_debug"]["sdk_available"] is True
    assert data["provider_debug"]["sdk_loaded"] is True
    assert data["provider_debug"]["dataset"] == "GLBX.MDP3"
    assert data["provider_debug"]["requested_symbol"] == "EURUSD"
    assert data["provider_debug"]["mapped_symbol"] == "6E"
    assert data["provider_debug"]["symbol_mapping_succeeded"] is True
    assert data["provider_debug"]["request_sent"] is True
    assert data["provider_debug"]["trades_loaded"] == 0
    assert data["provider_debug"]["trades_returned"] == 0
    assert data["provider_debug"]["calculators_executed"] is True
    assert data["provider_debug"]["exception"] == "dataset_unavailable: GLBX.MDP3 rejected 6E"
    assert data["provider_debug"]["reason"] == "dataset_unavailable: GLBX.MDP3 rejected 6E"


def test_live_tick_ingestion_updates_latest_snapshot():
    from app.storage.memory_store import store

    for collection in [store.trades, store.books, store.candles, store.cumdelta, store.cumdelta_points, store.latest_snapshots, store.live_snapshots, store.cache_snapshots]:
        collection.pop("6B", None)
    store.cumdelta_last_price.pop("6B", None)

    first = {
        "symbol": "GBPUSD",
        "bid": 1.2700,
        "ask": 1.2702,
        "last": 1.2702,
        "volume": 10,
        "timestamp": "2026-07-04T12:00:00Z",
    }
    second = {
        "symbol": "GBPUSD",
        "bid": 1.2703,
        "ask": 1.2705,
        "last": 1.2705,
        "volume": 5,
        "timestamp": "2026-07-04T12:00:01Z",
    }

    first_response = client.post("/api/orderflow/live", json=first)
    second_response = client.post("/api/orderflow/live", json=second)
    latest_response = client.get("/api/orderflow/latest?symbol=GBPUSD")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["data_source"] == "mt4_live"
    assert latest["data_source_label"] == "MT4 Live"
    assert latest["data_source_quality"] == 75
    assert latest["symbol"] == "GBPUSD"
    assert latest["futures_symbol"] == "6B"
    assert latest["delta"] == 15
    assert latest["cumdelta"] == 15
    assert latest["volume"] == 15
    assert latest["vwap"] == (1.2702 * 10 + 1.2705 * 5) / 15
    assert latest["poc"] == 1.2702
    assert latest["provider_debug"]["source"] == "live_mt4_bridge"
    assert latest["debug"]["profile_levels"] == 2
    assert "orderflow_bias" in latest
    assert "market_state" in latest
