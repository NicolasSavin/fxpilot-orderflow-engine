from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from app.services.historical_storage.paths import data_root
from .models import HistoricalReplayState, HistoricalReplayResult

class ReplayStorage:
    def __init__(self, root: Path|None=None):
        self.root=(root or data_root())/'replays'; self.snapdir=self.root/'snapshots'; self.snapdir.mkdir(parents=True,exist_ok=True)
        self.states_path=self.root/'replay_states.json'; self.results_path=self.root/'replay_results.json'
    def _load(self,path):
        if not path.exists(): return {}
        return json.loads(path.read_text() or '{}')
    def _atomic(self,path,payload):
        path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix='.',suffix='.tmp',dir=str(path.parent))
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(payload,f,indent=2,sort_keys=True); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    def states(self): return {k:HistoricalReplayState.model_validate(v) for k,v in self._load(self.states_path).items()}
    def results(self): return {k:HistoricalReplayResult.model_validate(v) for k,v in self._load(self.results_path).items()}
    def save_state(self,state):
        d=self._load(self.states_path); d[state.replay_id]=state.model_dump(mode='json'); self._atomic(self.states_path,d)
    def save_result(self,result):
        d=self._load(self.results_path); d[result.replay_id]=result.model_dump(mode='json'); self._atomic(self.results_path,d)
    def append_snapshot(self,replay_id,snapshot):
        with open(self.snapdir/(replay_id+'.jsonl'),'a',encoding='utf-8') as f: f.write(json.dumps(snapshot,default=str)+'\n')
    def snapshots(self,replay_id,limit=1000):
        p=self.snapdir/(replay_id+'.jsonl')
        if not p.exists(): return []
        out=[]
        for line in p.read_text().splitlines()[:limit]:
            try: out.append(json.loads(line))
            except Exception: pass
        return out
    def delete(self,replay_id):
        s=self._load(self.states_path); r=self._load(self.results_path); s.pop(replay_id,None); r.pop(replay_id,None); self._atomic(self.states_path,s); self._atomic(self.results_path,r)
