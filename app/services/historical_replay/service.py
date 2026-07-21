from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from app.services.historical_storage.storage import HistoricalStorageService
from .models import HistoricalReplayRequest, HistoricalReplayState, ReplayStatus, ReplayMode
from .readers import reader_for, CapabilityError
from .replay_engine import run_replay
from .storage import ReplayStorage

class HistoricalReplayService:
    def __init__(self, storage_service: HistoricalStorageService|None=None, replay_storage: ReplayStorage|None=None):
        self.historical=storage_service or HistoricalStorageService(); self.storage=replay_storage or ReplayStorage(self.historical.root)
    def create(self, req: HistoricalReplayRequest):
        ds=self.historical.catalog.get(req.dataset_id)
        if not ds: raise KeyError(req.dataset_id)
        rid=uuid4().hex[:16]; state=HistoricalReplayState(replay_id=rid,dataset_id=ds.id,status=ReplayStatus.READY,mode=req.mode,symbol=req.symbol or ds.symbol,start_at=req.start_at,end_at=req.end_at,rows_total=ds.record_count,request=req.model_dump(mode='json'))
        try: reader_for(ds).inspect(ds)
        except CapabilityError as exc: state.status=ReplayStatus.FAILED; state.last_error=str(exc)
        self.storage.save_state(state); return state
    def list(self): return list(self.storage.states().values())
    def get(self,rid): return self.storage.states().get(rid)
    def result(self,rid): return self.storage.results().get(rid)
    def snapshots(self,rid): return self.storage.snapshots(rid)
    def start(self,rid):
        st=self.get(rid); 
        if not st: raise KeyError(rid)
        ds=self.historical.catalog.get(st.dataset_id); return run_replay(ds,st,self.storage,max_rows=None)
    def step(self,rid, rows:int|None=None):
        st=self.get(rid); 
        if not st: raise KeyError(rid)
        ds=self.historical.catalog.get(st.dataset_id); return run_replay(ds,st,self.storage,max_rows=rows or int(st.request.get('chunk_size',1000)))
    def pause(self,rid):
        st=self.get(rid); 
        if not st: raise KeyError(rid)
        st.status=ReplayStatus.PAUSED; self.storage.save_state(st); return st
    def resume(self,rid): return self.step(rid)
    def cancel(self,rid):
        st=self.get(rid); 
        if not st: raise KeyError(rid)
        st.status=ReplayStatus.CANCELLED; st.completed_at=datetime.now(timezone.utc); self.storage.save_state(st); return st
    def delete(self,rid): self.storage.delete(rid); return {'deleted':rid}
    def debug(self):
        states=self.storage.states(); results=self.storage.results()
        return {'replays':len(states),'results':len(results),'diagnostics':[{'replay_id':s.replay_id,'selected_dataset':s.dataset_id,'rows_scanned':s.cursor,'rows_skipped':s.rows_skipped,'malformed_rows':s.malformed_rows,'duplicates':s.duplicate_rows,'first_and_last_timestamps':[None,s.current_event_time],'last_exception':s.last_error,'build_time':'persisted','side_classification_mode':'exchange_or_unknown_proxy_marked','calculators_executed':['delta','cumdelta','volume_profile','value_area','vwap','absorption','market_state'],'calculators_unavailable':['dom_when_no_book_data']} for s in states.values()]}
