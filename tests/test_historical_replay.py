from datetime import datetime, timezone
from pathlib import Path

import csv
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.historical_storage.models import HistoricalDataset, DatasetStatus
from app.services.historical_storage.storage import HistoricalStorageService
from app.services.historical_replay import HistoricalReplayRequest, HistoricalReplayService, ReplayMode
from app.services.historical_replay.storage import ReplayStorage
from app.storage.memory_store import store


def _dataset(tmp_path: Path, fmt='csv', rows=None, provider='mock', metadata=None):
    rows = rows or [
        {'event_time':'2026-01-01T00:00:00Z','receive_time':'2026-01-01T00:00:00Z','symbol':'EURUSD','instrument_id':'1','price':1.1,'size':10,'side':'B','trade_id':'a','sequence':1},
        {'event_time':'2026-01-01T00:00:01Z','receive_time':'2026-01-01T00:00:01Z','symbol':'EURUSD','instrument_id':'1','price':1.2,'size':5,'side':'S','trade_id':'b','sequence':2},
    ]
    path=tmp_path/f'data.{fmt}'
    if fmt=='parquet':
        pd = pytest.importorskip('pandas')
        pd.DataFrame(rows).to_parquet(path)
    else:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return HistoricalDataset(id='ds-'+fmt,provider=provider,dataset='test',schema='trades',symbol='EURUSD',instrument_id='1',start_at=datetime(2026,1,1,tzinfo=timezone.utc),end_at=datetime(2026,1,2,tzinfo=timezone.utc),source_format=fmt,stored_format=fmt,file_path=str(path),file_size_bytes=path.stat().st_size,checksum_sha256='x',record_count=len(rows),status=DatasetStatus.VALIDATED,metadata=metadata or {'mock': provider=='mock'})

@pytest.fixture()
def replay_svc(tmp_path, monkeypatch):
    monkeypatch.setenv('FXPILOT_ORDERFLOW_DATA_DIR', str(tmp_path))
    hs = HistoricalStorageService(tmp_path)
    store.trades.clear()
    store.books.clear()
    store.candles.clear()
    store.cumdelta.clear()
    store.cumdelta_points.clear()
    return HistoricalReplayService(hs, ReplayStorage(tmp_path))

def test_replay_cataloged_mock_csv_dataset(replay_svc, tmp_path):
    ds = _dataset(tmp_path, 'csv')
    replay_svc.historical.catalog.upsert(ds)
    st=replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id, mode=ReplayMode.BATCH, persist_snapshots=True))
    res=replay_svc.start(st.replay_id)
    assert res.status == 'COMPLETED'
    assert res.final_snapshot['debug']['source'] == 'historical_replay'
    assert res.provenance.data_quality == 'mock'


def test_replay_parquet_dataset(replay_svc, tmp_path):
    ds = _dataset(tmp_path, 'parquet')
    replay_svc.historical.catalog.upsert(ds)
    st=replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id))
    assert replay_svc.start(st.replay_id).trades_processed == 2


def test_deduplicates_and_sorts_rows(replay_svc, tmp_path):
    rows=[
        {'event_time':'2026-01-01T00:00:02Z','symbol':'EURUSD','instrument_id':'1','price':1.3,'size':1,'side':'B','trade_id':'c','sequence':3},
        {'event_time':'2026-01-01T00:00:01Z','symbol':'EURUSD','instrument_id':'1','price':1.2,'size':1,'side':'B','trade_id':'b','sequence':2},
        {'event_time':'2026-01-01T00:00:01Z','symbol':'EURUSD','instrument_id':'1','price':1.2,'size':1,'side':'B','trade_id':'b','sequence':2},
    ]
    ds = _dataset(tmp_path, 'csv', rows=rows)
    replay_svc.historical.catalog.upsert(ds)
    st=replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id))
    res = replay_svc.start(st.replay_id)
    st2 = replay_svc.get(st.replay_id)
    assert res.trades_processed == 2
    assert st2.duplicate_rows == 1
    assert res.final_snapshot['provider_debug']['out_of_order_records'] == 1


def test_time_window_and_step_resume(replay_svc, tmp_path):
    ds = _dataset(tmp_path, 'csv')
    replay_svc.historical.catalog.upsert(ds)
    st=replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id, mode=ReplayMode.STEP, chunk_size=1, start_at=datetime(2026,1,1,0,0,1,tzinfo=timezone.utc)))
    r1=replay_svc.step(st.replay_id, rows=1)
    assert r1.trades_processed == 1
    assert replay_svc.get(st.replay_id).cursor >= 2


def test_append_rejects_backward_timestamp(replay_svc, tmp_path):
    ds = _dataset(tmp_path, 'csv')
    replay_svc.historical.catalog.upsert(ds)
    replay_svc.start(replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id, reset_session=True)).replay_id)
    st=replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id, reset_session=False))
    with pytest.raises(ValueError, match='backward-time'):
        replay_svc.start(st.replay_id)


def test_missing_side_and_broker_volume_marked_proxy(replay_svc, tmp_path):
    rows=[{'event_time':'2026-01-01T00:00:00Z','symbol':'EURUSD','instrument_id':'1','price':1.1,'size':1,'trade_id':'a','sequence':1}]
    ds=_dataset(tmp_path,'csv',rows=rows,provider='local_file',metadata={'volume_type':'broker_tick_volume'})
    replay_svc.historical.catalog.upsert(ds)
    res=replay_svc.start(replay_svc.create(HistoricalReplayRequest(dataset_id=ds.id)).replay_id)
    assert res.provenance.is_proxy is True
    assert res.provenance.is_exchange_volume is False
    assert res.provenance.volume_type == 'broker_tick_volume'
    assert 'dom:no_book_data' in res.final_snapshot['provider_debug']['calculators_unavailable']


def test_ops_token_required(monkeypatch, tmp_path):
    monkeypatch.setenv('FXPILOT_ORDERFLOW_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FXPILOT_ORDERFLOW_OPS_TOKEN', 'secret')
    c=TestClient(app)
    assert c.post('/api/ops/replays', json={'dataset_id':'missing'}).status_code == 401
