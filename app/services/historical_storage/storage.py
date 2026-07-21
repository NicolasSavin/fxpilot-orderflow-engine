from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, os, shutil, tempfile
from pathlib import Path
from .catalog import HistoricalCatalog
from .downloader import provider_for
from .integrity import sha256_file, validate_file
from .models import DatasetStatus, HistoricalDataset, HistoricalDownloadRequest, LocalImportRequest
from .paths import assert_within, atomic_write_text, ensure_dirs, safe_component

class HistoricalStorageService:
    def __init__(self, root: Path | None=None):
        self.dirs=ensure_dirs(root); self.root=self.dirs['raw'].parent; self.catalog=HistoricalCatalog(self.root)
    def idempotency_key(self, req: HistoricalDownloadRequest) -> str:
        payload={'provider':req.provider,'dataset':req.dataset,'schema':req.schema,'symbols':sorted(req.symbols),'start_at':req.start_at.isoformat(),'end_at':req.end_at.isoformat(),'encoding':req.encoding,'output_format':req.output_format}
        return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
    def filename(self, req, symbol):
        s=req.start_at.strftime('%Y-%m-%dT%H%M%SZ'); e=req.end_at.strftime('%Y-%m-%dT%H%M%SZ')
        return '__'.join(map(safe_component,[req.provider,req.dataset,req.schema,symbol,s,e]))+'.'+req.output_format
    def estimate(self, req): return provider_for(req.provider).estimate(req)
    def download(self, req: HistoricalDownloadRequest) -> HistoricalDataset:
        did=self.idempotency_key(req); existing=self.catalog.get(did)
        if existing and existing.status==DatasetStatus.VALIDATED and Path(existing.file_path).exists() and not req.force: return existing
        symbol=','.join(sorted(req.symbols)); final=self.dirs['mock' if req.provider=='mock' else 'raw']/self.filename(req, safe_component(symbol))
        fd,tmp=tempfile.mkstemp(prefix='download-',suffix='.'+req.output_format,dir=str(final.parent)); os.close(fd); tmp_path=Path(tmp)
        try:
            meta=provider_for(req.provider).download(req,tmp_path)
            validation=validate_file(tmp_path, req.output_format)
            if not validation['valid']:
                q=self._quarantine(tmp_path, did, req.output_format); raise ValueError(f'invalid dataset quarantined at {q}: {validation["errors"]}')
            os.replace(tmp_path, final)
            checksum=sha256_file(final); now=datetime.now(timezone.utc)
            ds=HistoricalDataset(id=did,provider=req.provider,dataset=req.dataset,schema=req.schema,symbol=symbol,start_at=req.start_at,end_at=req.end_at,encoding=req.encoding,compression=req.compression,source_format=req.output_format,stored_format=req.output_format,file_path=str(final),file_size_bytes=final.stat().st_size,checksum_sha256=checksum,record_count=validation['record_count'],status=DatasetStatus.VALIDATED,created_at=now,updated_at=now,metadata={**req.metadata,**meta,'mock':req.provider=='mock','idempotency_key':did,'forced_generation':req.force})
            self.catalog.upsert(ds); self._manifest(ds, req.model_dump(mode='json'), validation); return ds
        except Exception:
            if tmp_path.exists(): tmp_path.unlink()
            raise
    def import_file(self, req: LocalImportRequest, allow_outside_root: bool=False) -> HistoricalDataset:
        src=Path(req.file_path)
        if not allow_outside_root: src=assert_within(src, self.root)
        src=src.resolve(); suffix='.dbn.zst' if src.name.endswith('.dbn.zst') else src.suffix.lower().lstrip('.')
        if suffix not in {'csv','parquet','dbn','dbn.zst'}: raise ValueError('unsupported import format')
        checksum=sha256_file(src)
        for d in self.catalog.datasets.values():
            if d.checksum_sha256==checksum: return d
        did=hashlib.sha256((checksum+req.symbol+req.dataset).encode()).hexdigest()[:24]
        final=self.dirs['raw']/(safe_component(did)+'__'+safe_component(src.name))
        fd,tmp=tempfile.mkstemp(prefix='import-',suffix='.'+suffix,dir=str(final.parent)); os.close(fd); tmp_path=Path(tmp)
        try:
            shutil.copyfile(src,tmp_path); validation=validate_file(tmp_path, suffix)
            if not validation['valid']:
                q=self._quarantine(tmp_path,did,suffix); raise ValueError(f'invalid dataset quarantined at {q}: {validation["errors"]}')
            os.replace(tmp_path, final); now=datetime.now(timezone.utc)
            ds=HistoricalDataset(id=did,provider=req.provider,dataset=req.dataset,schema=req.schema,symbol=req.symbol,start_at=req.start_at,end_at=req.end_at,encoding='utf-8',source_format=suffix,stored_format=suffix,file_path=str(final),file_size_bytes=final.stat().st_size,checksum_sha256=checksum,record_count=validation['record_count'],status=DatasetStatus.VALIDATED,created_at=now,updated_at=now,metadata={**req.metadata,'original_filename':src.name})
            self.catalog.upsert(ds); self._manifest(ds, req.model_dump(mode='json'), validation); return ds
        except Exception:
            if tmp_path.exists(): tmp_path.unlink()
            raise
    def validate_dataset(self,did):
        ds=self.catalog.get(did); 
        if not ds: raise KeyError(did)
        v=validate_file(Path(ds.file_path), ds.stored_format, ds.checksum_sha256)
        ds.status=DatasetStatus.VALIDATED if v['valid'] else DatasetStatus.QUARANTINED; ds.updated_at=datetime.now(timezone.utc)
        if not v['valid']: ds.file_path=str(self._quarantine(Path(ds.file_path), did, ds.stored_format))
        self.catalog.upsert(ds); self._manifest(ds, {'revalidation':True}, v); return {'dataset':ds,'validation':v}
    def _quarantine(self,path,did,fmt):
        q=self.dirs['quarantine']/(safe_component(did)+'.'+fmt); 
        if path.exists(): os.replace(path,q)
        return q
    def _manifest(self,ds,request,validation):
        payload={'original_request':request,'file_metadata':ds.model_dump(mode='json'),'checksum':ds.checksum_sha256,'record_count':ds.record_count,'validation_results':validation,'warnings':validation.get('warnings',[]),'errors':validation.get('errors',[]),'created_at':datetime.now(timezone.utc).isoformat(),'provider_version':ds.metadata.get('provider_version')}
        payload=json.loads(json.dumps(payload)); payload.get('original_request',{}).pop('api_key',None)
        atomic_write_text(self.dirs['manifests']/(ds.id+'.json'), json.dumps(payload,indent=2,sort_keys=True))
