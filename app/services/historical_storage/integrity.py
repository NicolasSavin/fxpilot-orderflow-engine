from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
import pandas as pd

REQUIRED_COLUMNS = {'timestamp','symbol','price','size','side','trade_id','sequence'}

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def read_table(path: Path, fmt: str) -> pd.DataFrame:
    if fmt == 'csv': return pd.read_csv(path)
    if fmt == 'parquet': return pd.read_parquet(path)
    if fmt.startswith('dbn'):
        if path.stat().st_size == 0: raise ValueError('empty DBN file')
        return pd.DataFrame()
    raise ValueError(f'unsupported format: {fmt}')

def validate_file(path: Path, fmt: str, expected_checksum: str | None = None) -> dict[str, Any]:
    result={'valid':False,'warnings':[],'errors':[],'record_count':0,'duplicate_trade_ids':0,'duplicate_sequences':0,'malformed_records':0,'timestamps_ordered':True}
    if not path.exists(): result['errors'].append('file does not exist'); return result
    if path.stat().st_size <= 0: result['errors'].append('file is empty'); return result
    checksum=sha256_file(path); result['checksum_sha256']=checksum
    if expected_checksum and checksum != expected_checksum: result['errors'].append('checksum mismatch')
    try: df=read_table(path, fmt)
    except Exception as exc: result['errors'].append(f'format not readable: {exc}'); return result
    if fmt.startswith('dbn'):
        result['valid']=not result['errors']; return result
    missing=sorted(REQUIRED_COLUMNS-set(df.columns))
    if missing: result['errors'].append(f'missing required columns: {missing}'); return result
    result['record_count']=int(len(df))
    bad_price = pd.to_numeric(df['price'], errors='coerce').le(0) | pd.to_numeric(df['price'], errors='coerce').isna()
    bad_size = pd.to_numeric(df['size'], errors='coerce').lt(0) | pd.to_numeric(df['size'], errors='coerce').isna()
    bad_symbol = df['symbol'].isna() | (df['symbol'].astype(str).str.len()==0)
    result['malformed_records']=int((bad_price|bad_size|bad_symbol).sum())
    if bad_price.any(): result['errors'].append('prices must be positive')
    if bad_size.any(): result['errors'].append('sizes must be non-negative')
    if bad_symbol.any(): result['errors'].append('symbol values must be present')
    ts=pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
    if ts.isna().any(): result['errors'].append('timestamps must be parseable')
    elif not ts.is_monotonic_increasing:
        result['timestamps_ordered']=False; result['warnings'].append('timestamps are not ordered')
    result['duplicate_trade_ids']=int(df['trade_id'].duplicated().sum())
    result['duplicate_sequences']=int(df['sequence'].duplicated().sum())
    result['valid']=not result['errors']
    return result
