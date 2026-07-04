from datetime import datetime, timedelta, timezone

from app.models.orderflow import OrderFlowSnapshot
from app.services.source_manager import source_manager


def snapshot(*, provider="databento", status="ok", volume=10, timestamp=None, source="unavailable"):
    return OrderFlowSnapshot(
        symbol="EURUSD",
        futures_symbol="6E",
        timestamp=timestamp or datetime.now(timezone.utc),
        provider=provider,
        provider_status=status,
        volume=volume,
        orderflow_available=status == "ok",
        data_source=source,
    )


def test_databento_available_selected():
    db = snapshot(provider="databento", status="ok", volume=25)

    decision = source_manager.choose(databento=db)
    selected = source_manager.apply_metadata(db, decision.source, reason=decision.reason, age_seconds=decision.age_seconds)

    assert decision.source == "databento"
    assert selected.data_source == "databento"
    assert selected.data_source_label == "Databento"
    assert selected.data_source_quality == 100
    assert selected.data_source_status == "ok"


def test_databento_unavailable_mt4_live_fresh_selected():
    now = datetime.now(timezone.utc)
    db = snapshot(provider="databento", status="unavailable", volume=0, timestamp=now)
    mt4 = snapshot(provider="mock", status="ok", volume=5, timestamp=now - timedelta(seconds=10))

    decision = source_manager.choose(databento=db, mt4_live=mt4, now=now)

    assert decision.source == "mt4_live"
    assert decision.reason == "databento_unusable_mt4_live_fresh"


def test_databento_unavailable_mt4_stale_cache_exists_selected():
    now = datetime.now(timezone.utc)
    db = snapshot(provider="databento", status="unavailable", volume=0, timestamp=now)
    mt4 = snapshot(provider="mock", status="ok", volume=5, timestamp=now - timedelta(seconds=31))
    cache = snapshot(provider="databento", status="ok", volume=20, timestamp=now - timedelta(minutes=5), source="databento")

    decision = source_manager.choose(databento=db, mt4_live=mt4, cache=cache, now=now)

    assert decision.source == "cache"
    assert decision.reason == "databento_unusable_mt4_stale_or_missing_cache_available"


def test_all_unavailable_returns_unavailable():
    now = datetime.now(timezone.utc)
    db = snapshot(provider="databento", status="unavailable", volume=0, timestamp=now)
    mt4 = snapshot(provider="mock", status="ok", volume=5, timestamp=now - timedelta(minutes=2))
    cache = snapshot(provider="databento", status="ok", volume=20, timestamp=now - timedelta(minutes=20))

    decision = source_manager.choose(databento=db, mt4_live=mt4, cache=cache, now=now)

    assert decision.source == "unavailable"
    assert decision.snapshot is None


def test_source_metadata_included_in_snapshot():
    snap = snapshot(provider="mock", status="ok", volume=5)

    selected = source_manager.apply_metadata(snap, "mt4_live", reason="databento_unusable_mt4_live_fresh", age_seconds=4.0)

    assert selected.data_source == "mt4_live"
    assert selected.data_source_label == "MT4 Live"
    assert selected.data_source_quality == 75
    assert selected.data_source_status == "ok"
    assert selected.data_source_age_seconds == 4.0
    assert selected.data_source_reason == "databento_unusable_mt4_live_fresh"
