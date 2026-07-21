from __future__ import annotations
import os
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from app.services.historical_storage.models import HistoricalDownloadRequest, LocalImportRequest
from app.services.historical_storage.storage import HistoricalStorageService

router=APIRouter()

def svc(): return HistoricalStorageService()

def require_ops_token(x_ops_token: str | None = Header(default=None)):
    expected=os.getenv('FXPILOT_ORDERFLOW_OPS_TOKEN')
    if not expected or x_ops_token != expected:
        raise HTTPException(status_code=401, detail='OPS token required in X-OPS-Token header')

@router.get('/ready')
def ready():
    s=svc(); return {'status':'ready','catalog_total':len(s.catalog.datasets)}

@router.get('/api/historical/datasets')
def list_datasets(provider: str|None=None,dataset: str|None=None,schema: str|None=None,symbol: str|None=None,status: str|None=None):
    return {'datasets':[d.model_dump(mode='json') for d in svc().catalog.list(provider=provider,dataset=dataset,schema=schema,symbol=symbol,status=status)]}

@router.get('/api/historical/datasets/{dataset_id}')
def get_dataset(dataset_id: str):
    d=svc().catalog.get(dataset_id)
    if not d: raise HTTPException(404,'dataset not found')
    return d

@router.get('/api/historical/catalog')
def catalog(): return svc().catalog.raw()

@router.get('/api/historical/debug')
def debug():
    s=svc(); return {'data_root':str(s.root),'directories':{k:str(v) for k,v in s.dirs.items()},'datasets':len(s.catalog.datasets),'databento_api_key_configured':bool(os.getenv('DATABENTO_API_KEY')),'api_keys_exposed':False,'historical_only':True,'live_streaming_enabled':False}

@router.post('/api/ops/historical/estimate', dependencies=[Depends(require_ops_token)])
def estimate(req: HistoricalDownloadRequest): return svc().estimate(req)

@router.post('/api/ops/historical/download', dependencies=[Depends(require_ops_token)])
def download(req: HistoricalDownloadRequest): return svc().download(req)

@router.post('/api/ops/historical/import', dependencies=[Depends(require_ops_token)])
def import_file(req: LocalImportRequest, allow_outside_root: bool = Query(default=False)):
    return svc().import_file(req, allow_outside_root=allow_outside_root)

@router.post('/api/ops/historical/validate/{dataset_id}', dependencies=[Depends(require_ops_token)])
def validate(dataset_id: str): return svc().validate_dataset(dataset_id)

@router.post('/api/ops/historical/rebuild-catalog', dependencies=[Depends(require_ops_token)])
def rebuild():
    s=svc(); s.catalog.save(); return s.catalog.raw()

@router.delete('/api/ops/historical/datasets/{dataset_id}', dependencies=[Depends(require_ops_token)])
def delete(dataset_id: str):
    s=svc(); d=s.catalog.get(dataset_id)
    if not d: raise HTTPException(404,'dataset not found')
    s.catalog.remove(dataset_id); return {'deleted':dataset_id}
