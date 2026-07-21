from __future__ import annotations
import os, time
from pathlib import Path
from typing import Any
import pandas as pd
from .models import HistoricalDownloadRequest

class HistoricalProvider:
    name='base'
    def estimate(self, req: HistoricalDownloadRequest) -> dict[str, Any]: raise NotImplementedError
    def download(self, req: HistoricalDownloadRequest, destination: Path) -> dict[str, Any]: raise NotImplementedError

class MockHistoricalProvider(HistoricalProvider):
    name='mock'
    def estimate(self, req):
        return {'provider':'mock','dataset':req.dataset,'schema':req.schema,'symbols':req.symbols,'start':req.start_at,'end':req.end_at,'requested_duration':str(req.end_at-req.start_at),'estimated_request_size':'small deterministic fixture','cost_information':'none','warnings':['mock data only; not real Databento data'],'requires_confirmation':False}
    def download(self, req, destination: Path):
        rows=[]
        for sym in req.symbols:
            for i in range(5): rows.append({'timestamp':(req.start_at).isoformat(),'symbol':sym,'price':100.0+i,'size':i+1,'side':'B' if i%2==0 else 'S','trade_id':f'mock-{sym}-{i}','sequence':i+1})
        df=pd.DataFrame(rows); destination.parent.mkdir(parents=True, exist_ok=True)
        if req.output_format=='csv': df.to_csv(destination,index=False)
        elif req.output_format=='parquet': df.to_parquet(destination,index=False)
        else: destination.write_bytes(b'MOCK-DBN-FIXTURE\n')
        return {'provider_version':'mock-1','mock':True}

class DatabentoHistoricalProvider(HistoricalProvider):
    name='databento'
    def _key(self):
        key=os.getenv('DATABENTO_API_KEY','')
        if not key: raise RuntimeError('DATABENTO_API_KEY is required for explicit Databento historical downloads')
        return key
    def estimate(self, req):
        warnings=['Historical API only; no live streaming is used. Downloads may incur Databento costs.']
        return {'provider':'databento','dataset':req.dataset,'schema':req.schema,'symbols':req.symbols,'start':req.start_at,'end':req.end_at,'requested_duration':str(req.end_at-req.start_at),'estimated_request_size':None,'cost_information':None,'warnings':warnings,'requires_confirmation':True}
    def download(self, req, destination: Path):
        key=self._key()
        import databento as db
        client=db.Historical(key=key)
        last=None
        for attempt in range(3):
            try:
                data=client.timeseries.get_range(dataset=req.dataset,symbols=req.symbols,schema=req.schema,start=req.start_at.isoformat(),end=req.end_at.isoformat(),encoding=req.encoding)
                if req.output_format=='csv': data.to_csv(str(destination))
                elif req.output_format=='parquet': data.to_df().to_parquet(destination,index=False)
                else: data.to_file(str(destination))
                return {'provider_version':getattr(db,'__version__',None)}
            except Exception as exc:
                last=exc; time.sleep(0.5*(attempt+1))
        raise RuntimeError(f'Databento historical download failed after 3 attempts: {last}')

def provider_for(name: str) -> HistoricalProvider:
    if name=='mock': return MockHistoricalProvider()
    if name=='databento': return DatabentoHistoricalProvider()
    raise ValueError(f'unsupported provider: {name}')
