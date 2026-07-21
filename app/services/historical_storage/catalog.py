from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from .models import HistoricalDataset
from .paths import atomic_write_text, ensure_dirs

class HistoricalCatalog:
    schema_version='1.0'
    def __init__(self, root: Path | None=None):
        self.dirs=ensure_dirs(root); self.path=self.dirs['catalogs']/'historical_catalog.json'; self.datasets: dict[str,HistoricalDataset]={}; self.load()
    def load(self):
        if self.path.exists():
            data=json.loads(self.path.read_text(encoding='utf-8'))
            self.datasets={d['id']:HistoricalDataset.model_validate(d) for d in data.get('datasets',[])}
    def save(self):
        payload={'schema_version':self.schema_version,'datasets':[d.model_dump(mode='json') for d in self.datasets.values()],'total':len(self.datasets),'generated_at':datetime.now(timezone.utc).isoformat(),'diagnostics':{'catalog_path':str(self.path),'api_keys_exposed':False}}
        atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True))
    def upsert(self,d:HistoricalDataset): self.datasets[d.id]=d; self.save()
    def get(self,id:str): return self.datasets.get(id)
    def remove(self,id:str): self.datasets.pop(id,None); self.save()
    def list(self, **filters: Any):
        vals=list(self.datasets.values())
        for k,v in filters.items():
            if v is not None and k in {'provider','dataset','schema','symbol','status'}: vals=[d for d in vals if str(getattr(d,k))==str(v)]
        return vals
    def raw(self): self.load(); return json.loads(self.path.read_text()) if self.path.exists() else {'schema_version':self.schema_version,'datasets':[],'total':0,'diagnostics':{}}
