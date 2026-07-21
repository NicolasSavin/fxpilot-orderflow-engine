from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Iterator, Protocol
from app.services.historical_storage.models import HistoricalDataset

class CapabilityError(RuntimeError): pass
class DatasetReader(Protocol):
    name: str
    def supports(self, dataset: HistoricalDataset) -> bool: ...
    def iter_rows(self, dataset: HistoricalDataset, start_at=None, end_at=None) -> Iterator[dict[str, Any]]: ...
    def count_rows(self, dataset: HistoricalDataset, start_at=None, end_at=None) -> int: ...
    def inspect(self, dataset: HistoricalDataset) -> dict[str, Any]: ...

class CsvDatasetReader:
    name='csv'
    def supports(self,dataset): return dataset.stored_format.lower()=='csv' or Path(dataset.file_path).suffix.lower()=='.csv'
    def iter_rows(self,dataset,start_at=None,end_at=None):
        with open(dataset.file_path,newline='',encoding=dataset.encoding or 'utf-8') as f:
            for row in csv.DictReader(f): yield dict(row)
    def count_rows(self,dataset,start_at=None,end_at=None):
        with open(dataset.file_path,encoding=dataset.encoding or 'utf-8') as f: return max(sum(1 for _ in f)-1,0)
    def inspect(self,dataset):
        with open(dataset.file_path,newline='',encoding=dataset.encoding or 'utf-8') as f: return {'reader':self.name,'columns':(next(csv.reader(f),[]) or []),'capability':'ok'}

class ParquetDatasetReader:
    name='parquet'
    def supports(self,dataset): return dataset.stored_format.lower()=='parquet' or Path(dataset.file_path).suffix.lower()=='.parquet'
    def _pd(self):
        try: import pandas as pd; return pd
        except Exception as exc: raise CapabilityError(f'parquet support requires pandas/pyarrow: {exc}')
    def iter_rows(self,dataset,start_at=None,end_at=None):
        pd=self._pd(); pf=pd.read_parquet(dataset.file_path)
        for row in pf.to_dict(orient='records'): yield row
    def count_rows(self,dataset,start_at=None,end_at=None):
        try: import pyarrow.parquet as pq; return pq.ParquetFile(dataset.file_path).metadata.num_rows
        except Exception: return sum(1 for _ in self.iter_rows(dataset,start_at,end_at))
    def inspect(self,dataset):
        pd=self._pd(); return {'reader':self.name,'columns':list(pd.read_parquet(dataset.file_path).columns),'capability':'ok'}

class DbnDatasetReader:
    name='dbn'
    def supports(self,dataset): return dataset.stored_format.lower() in {'dbn','dbn.zst'} or dataset.file_path.endswith(('.dbn','.dbn.zst'))
    def _db(self):
        try: import databento as db; return db
        except Exception as exc: raise CapabilityError(f'DBN replay support unavailable; install databento SDK: {exc}')
    def iter_rows(self,dataset,start_at=None,end_at=None):
        db=self._db(); data=db.DBNStore.from_file(dataset.file_path)
        for record in data: yield record.__dict__ if hasattr(record,'__dict__') else dict(record)
    def count_rows(self,dataset,start_at=None,end_at=None): return sum(1 for _ in self.iter_rows(dataset,start_at,end_at))
    def inspect(self,dataset): self._db(); return {'reader':self.name,'columns':[],'capability':'ok'}

READERS=[CsvDatasetReader(),ParquetDatasetReader(),DbnDatasetReader()]
def reader_for(dataset):
    for r in READERS:
        if r.supports(dataset): return r
    raise CapabilityError(f'unsupported dataset format: {dataset.stored_format}')
