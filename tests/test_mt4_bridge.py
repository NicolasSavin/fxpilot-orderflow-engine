from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_mt4_bridge
from app.storage.memory_store import store


def make_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("MT4_BRIDGE_TOKEN", "secret")
    monkeypatch.setattr(routes_mt4_bridge, "STREAMS_PATH", tmp_path / "mt4_streams.json")
    store.trades.clear()
    store.books.clear()
    store.candles.clear()
    store.cumdelta.clear()
    store.latest_snapshots.clear()
    store.live_snapshots.clear()
    store.cache_snapshots.clear()
    app = FastAPI()
    app.include_router(routes_mt4_bridge.router)
    return TestClient(app)


def payload() -> dict:
    return {
        "schema_version": "2.0",
        "source": "mt4",
        "symbol": "EURUSD",
        "broker_symbol": "EURUSD.a",
        "timeframe": "M15",
        "sent_at": 1786262400,
        "broker": "Demo Broker",
        "account": "12345",
        "candles": [
            {"time": 1786261500, "open": 1.10, "high": 1.20, "low": 1.00, "close": 1.15, "tick_volume": 42}
        ],
        "ticks": {
            "samples": 60,
            "up_ticks": 20,
            "down_ticks": 15,
            "unchanged_ticks": 25,
            "delta": 5,
            "spread_avg_points": 12,
            "spread_max_points": 18,
            "last_bid": 1.1499,
            "last_ask": 1.1501,
        },
    }


def test_batch_requires_token(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    assert client.post("/api/mt4/batch", json=payload()).status_code == 401


def test_batch_publishes_mt4_snapshot_and_status(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post("/api/mt4/batch", json=payload(), headers={"X-FXPilot-MT4-Token": "secret"})
    assert response.status_code == 200
    assert response.json()["stream"] == "EURUSD:M15"
    assert response.json()["data_source"] == "mt4_live"

    status = client.get("/api/mt4/status")
    assert status.status_code == 200
    body = status.json()
    assert body["expected_streams"] == 20
    assert body["received_streams"] == 1
    row = next(item for item in body["streams"] if item["stream"] == "EURUSD:M15")
    assert row["broker_symbol"] == "EURUSD.a"
    assert row["candle_count"] == 1


def test_batch_rejects_unsupported_market(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    data = payload()
    data["symbol"] = "BTCUSD"
    assert client.post("/api/mt4/batch", json=data, headers={"X-FXPilot-MT4-Token": "secret"}).status_code == 422

    data = payload()
    data["timeframe"] = "M1"
    assert client.post("/api/mt4/batch", json=data, headers={"X-FXPilot-MT4-Token": "secret"}).status_code == 422
