from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.models.market import Trade

import scripts.databento_smoke_test as smoke


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_smoke_script_handles_missing_api_key(monkeypatch, capsys):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)

    exit_code = smoke.main(["--symbol", "EURUSD", "--start", "2026-07-01T00:00:00", "--end", "2026-07-01T01:00:00"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert smoke.MISSING_API_KEY_MESSAGE in captured.err
    assert "Traceback" not in captured.err


def test_smoke_script_handles_missing_sdk(monkeypatch, capsys):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    monkeypatch.setattr(smoke.importlib.util, "find_spec", lambda name: None if name == "databento" else object())

    exit_code = smoke.main(["--symbol", "EURUSD", "--start", "2026-07-01T00:00:00", "--end", "2026-07-01T01:00:00"])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert smoke.MISSING_SDK_MESSAGE in captured.err
    assert "Traceback" not in captured.err


def test_smoke_script_formats_output(monkeypatch, capsys):
    monkeypatch.setenv("DATABENTO_API_KEY", "test-key")
    monkeypatch.setattr(smoke.importlib.util, "find_spec", lambda name: object())

    async def fake_collect_snapshot(symbol, start, end):
        return {
            "symbol": symbol,
            "futures_symbol": "6E",
            "window": {"start": start, "end": end},
            "trade_count": 1,
            "last_trade": Trade(
                symbol="6E",
                timestamp=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
                price=1.145,
                size=2,
                side="buy",
            ),
            "volume_profile": {"total_volume": 2, "poc": 1.145},
            "cumdelta": {"current_cumdelta": 2, "bias": "bullish"},
            "vwap": {"current_vwap": 1.145},
            "market_state": {"market_state": "trend"},
        }

    monkeypatch.setattr(smoke, "collect_snapshot", fake_collect_snapshot)

    exit_code = smoke.main(["--symbol", "EURUSD", "--start", "2026-07-01T00:00:00", "--end", "2026-07-01T01:00:00"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"symbol": "EURUSD"' in captured.out
    assert '"trade_count": 1' in captured.out
    assert '"volume_profile"' in captured.out
    assert '"cumdelta"' in captured.out
    assert '"vwap"' in captured.out
    assert '"market_state"' in captured.out
    assert '"timestamp": "2026-07-01T00:00:00Z"' in captured.out
