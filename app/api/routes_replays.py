import os
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from app.services.historical_replay import HistoricalReplayRequest, HistoricalReplayService
router=APIRouter()
def svc(): return HistoricalReplayService()
def require_ops_token(x_ops_token: str | None = Header(default=None)):
    expected=os.getenv('FXPILOT_ORDERFLOW_OPS_TOKEN')
    if not expected or x_ops_token != expected: raise HTTPException(status_code=401, detail='OPS token required in X-OPS-Token header')
@router.get('/api/replays')
def list_replays(): return {'replays':[s.model_dump(mode='json') for s in svc().list()]}
@router.get('/api/replays/debug')
def debug(): return svc().debug()
@router.get('/api/replays/{replay_id}')
def get_replay(replay_id:str):
    s=svc().get(replay_id)
    if not s: raise HTTPException(404,'replay not found')
    return s
@router.get('/api/replays/{replay_id}/result')
def result(replay_id:str):
    r=svc().result(replay_id)
    if not r: raise HTTPException(404,'replay result not found')
    return r
@router.get('/api/replays/{replay_id}/snapshots')
def snapshots(replay_id:str): return {'snapshots':svc().snapshots(replay_id)}
@router.post('/api/ops/replays', dependencies=[Depends(require_ops_token)])
def create(req:HistoricalReplayRequest): return svc().create(req)
@router.post('/api/ops/replays/{replay_id}/start', dependencies=[Depends(require_ops_token)])
def start(replay_id:str): return svc().start(replay_id)
@router.post('/api/ops/replays/{replay_id}/step', dependencies=[Depends(require_ops_token)])
def step(replay_id:str, rows:int|None=Query(default=None)): return svc().step(replay_id,rows)
@router.post('/api/ops/replays/{replay_id}/pause', dependencies=[Depends(require_ops_token)])
def pause(replay_id:str): return svc().pause(replay_id)
@router.post('/api/ops/replays/{replay_id}/resume', dependencies=[Depends(require_ops_token)])
def resume(replay_id:str): return svc().resume(replay_id)
@router.post('/api/ops/replays/{replay_id}/cancel', dependencies=[Depends(require_ops_token)])
def cancel(replay_id:str): return svc().cancel(replay_id)
@router.delete('/api/ops/replays/{replay_id}', dependencies=[Depends(require_ops_token)])
def delete(replay_id:str): return svc().delete(replay_id)
