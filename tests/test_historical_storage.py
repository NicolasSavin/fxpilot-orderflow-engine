from __future__ import annotations
from datetime import datetime, timezone
import hashlib, os
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.historical_storage.integrity import sha256_file
from app.services.historical_storage.models import HistoricalDownloadRequest, LocalImportRequest, NormalizedTrade
from app.services.historical_storage.storage import HistoricalStorageService

START=datetime(2026,1,1,tzinfo=timezone.utc); END=datetime(2026,1,2,tzinfo=timezone.utc)

def req(force=False):
    return HistoricalDownloadRequest(provider='mock',dataset='GLBX.MDP3',schema='trades',symbols=['6E.FUT'],start_at=START,end_at=END,output_format='parquet',force=force)

def fixture(path):
    pd.DataFrame([{'timestamp':START.isoformat(),'symbol':'6E.FUT','price':1.1,'size':2,'side':'B','trade_id':'t1','sequence':1}]).to_csv(path,index=False)

def test_mock_dataset_stored_and_cataloged(tmp_path):
    s=HistoricalStorageService(tmp_path); d=s.download(req())
    assert d.record_count==5 and d.checksum_sha256 and s.catalog.get(d.id)

def test_identical_request_deduplicated(tmp_path):
    s=HistoricalStorageService(tmp_path); a=s.download(req()); b=s.download(req())
    assert a.id==b.id and len(list((tmp_path/'mock').glob('*.parquet')))==1

def test_force_replaces_controlled_same_id(tmp_path):
    s=HistoricalStorageService(tmp_path); a=s.download(req()); b=s.download(req(True))
    assert a.id==b.id and b.metadata['forced_generation'] is True

def test_checksum_calculated_correctly(tmp_path):
    p=tmp_path/'x.csv'; p.write_text('abc')
    assert sha256_file(p)==hashlib.sha256(b'abc').hexdigest()

def test_corrupt_file_quarantined(tmp_path):
    p=tmp_path/'bad.csv'; p.write_text('not,a,trade\n1,2,3\n')
    s=HistoricalStorageService(tmp_path)
    with pytest.raises(ValueError): s.import_file(LocalImportRequest(file_path=str(p),symbol='6E.FUT',start_at=START,end_at=END), allow_outside_root=True)
    assert list((tmp_path/'quarantine').iterdir())

def test_csv_local_import(tmp_path):
    p=tmp_path/'ok.csv'; fixture(p); s=HistoricalStorageService(tmp_path); d=s.import_file(LocalImportRequest(file_path=str(p),symbol='6E.FUT',start_at=START,end_at=END), allow_outside_root=True)
    assert d.source_format=='csv' and d.record_count==1

def test_parquet_local_import(tmp_path):
    p=tmp_path/'ok.parquet'; pd.read_csv(tmp_path/'missing.csv') if False else None
    pd.DataFrame([{'timestamp':START.isoformat(),'symbol':'6E.FUT','price':1.1,'size':2,'side':'B','trade_id':'t1','sequence':1}]).to_parquet(p,index=False)
    d=HistoricalStorageService(tmp_path).import_file(LocalImportRequest(file_path=str(p),symbol='6E.FUT',start_at=START,end_at=END), allow_outside_root=True)
    assert d.source_format=='parquet'

def test_missing_required_columns_rejected(tmp_path):
    p=tmp_path/'bad.csv'; p.write_text('timestamp,symbol\n2026-01-01T00:00:00Z,6E.FUT\n')
    with pytest.raises(ValueError): HistoricalStorageService(tmp_path).import_file(LocalImportRequest(file_path=str(p),symbol='6E.FUT',start_at=START,end_at=END), allow_outside_root=True)

def test_path_traversal_rejected(tmp_path):
    outside=tmp_path.parent/'outside.csv'; fixture(outside)
    with pytest.raises(ValueError): HistoricalStorageService(tmp_path).import_file(LocalImportRequest(file_path=str(outside),symbol='6E.FUT',start_at=START,end_at=END))

def test_catalog_survives_restart(tmp_path):
    s=HistoricalStorageService(tmp_path); d=s.download(req())
    assert HistoricalStorageService(tmp_path).catalog.get(d.id)

def test_failed_atomic_write_preserves_previous_catalog(tmp_path, monkeypatch):
    s=HistoricalStorageService(tmp_path); d=s.download(req())
    from app.services.historical_storage import catalog as cat
    monkeypatch.setattr(cat, 'atomic_write_text', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    with pytest.raises(RuntimeError): s.catalog.save()
    assert HistoricalStorageService(tmp_path).catalog.get(d.id)

def test_ops_token_required(tmp_path, monkeypatch):
    monkeypatch.setenv('FXPILOT_ORDERFLOW_DATA_DIR', str(tmp_path)); monkeypatch.setenv('FXPILOT_ORDERFLOW_OPS_TOKEN','secret')
    c=TestClient(app)
    assert c.post('/api/ops/historical/estimate', json=req().model_dump(mode='json')).status_code==401
    assert c.post('/api/ops/historical/estimate', headers={'X-OPS-Token':'secret'}, json=req().model_dump(mode='json')).status_code==200

def test_databento_key_not_exposed_in_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv('FXPILOT_ORDERFLOW_DATA_DIR', str(tmp_path)); monkeypatch.setenv('DATABENTO_API_KEY','SECRETKEY')
    data=TestClient(app).get('/api/historical/debug').json()
    assert 'SECRETKEY' not in str(data) and data['databento_api_key_configured'] is True

def test_no_network_call_default_tests(monkeypatch, tmp_path):
    import socket
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    assert HistoricalStorageService(tmp_path).download(req()).provider=='mock'

def test_no_live_databento_streaming_client_used():
    import pathlib
    text='\n'.join(p.read_text(errors='ignore') for p in pathlib.Path('app/services/historical_storage').rglob('*.py'))
    assert 'Live(' not in text and 'live.' not in text.lower()

def test_normalized_trade_contract_validates_fixture_record():
    t=NormalizedTrade(event_time=START,receive_time=START,symbol='6E.FUT',price=1.1,size=1,side='B',trade_id='t1',sequence=1,source='mock')
    assert t.symbol=='6E.FUT'
