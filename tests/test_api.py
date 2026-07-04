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
        "databento_configured": True,
        "live_enabled": False,
        "historical_enabled": False,
        "historical_reason": "not_implemented",
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
