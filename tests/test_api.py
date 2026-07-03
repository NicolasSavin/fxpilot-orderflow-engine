from fastapi.testclient import TestClient
from app.main import app

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
    for key in ["delta", "cumdelta", "poc", "vah", "val", "vwap", "rvol", "dom_pressure", "absorption", "market_state", "orderflow_bias", "continuation_probability", "reversal_probability"]:
        assert key in data
