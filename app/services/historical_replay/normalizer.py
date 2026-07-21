from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.models.market import Trade
from app.services.historical_storage.models import HistoricalDataset, NormalizedTrade

ALIASES={'event_time':['event_time','ts_event','timestamp','time'],'receive_time':['receive_time','ts_recv','received_at'],'symbol':['symbol','raw_symbol'],'instrument_id':['instrument_id','instrument','instrument_key'],'price':['price','px','last'],'size':['size','qty','quantity','volume'],'side':['side','aggressor_side'],'trade_id':['trade_id','id','match_id'],'sequence':['sequence','seq']}

def _get(row,names):
    for n in names:
        if n in row and row[n] not in (None,''): return row[n]
    return None

def _dt(v):
    if isinstance(v,datetime): return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v,(int,float)): return datetime.fromtimestamp(v/1e9 if v>10_000_000_000 else v, timezone.utc)
    return datetime.fromisoformat(str(v).replace('Z','+00:00'))

def provenance_defaults(ds: HistoricalDataset):
    md=ds.metadata or {}; provider=ds.provider; quality='mock' if provider=='mock' or md.get('mock') else md.get('data_quality','unknown')
    schema=(ds.schema or '').lower(); fmt=(ds.stored_format or ds.source_format).lower()
    broker=provider in {'mt4','local_file'} and md.get('volume_type')=='broker_tick_volume'
    exchange=provider=='databento' and schema in {'trades','mbp-1','mbo'}
    volume_type=md.get('volume_type') or ('exchange_trade_volume' if exchange else 'broker_tick_volume' if broker else 'synthetic' if quality=='mock' else 'unknown')
    is_proxy=bool(md.get('is_proxy', provider!='databento' or quality=='mock'))
    return {'provider':provider,'venue':md.get('venue') or ds.dataset,'source_format':fmt,'data_quality':quality,'volume_type':volume_type,'is_proxy':is_proxy,'is_exchange_volume':volume_type=='exchange_trade_volume' and not is_proxy}

def normalize_row(row: dict[str,Any], ds: HistoricalDataset, proxy_classifier: bool=False) -> tuple[NormalizedTrade|None,list[str]]:
    warnings=[]
    try:
        event=_dt(_get(row,ALIASES['event_time'])); recv=_get(row,ALIASES['receive_time']); side_raw=_get(row,ALIASES['side'])
        side='N'
        if side_raw is not None:
            s=str(side_raw).strip().upper(); side='B' if s in {'B','BUY','1','A'} else 'S' if s in {'S','SELL','-1'} else 'N'
        else:
            warnings.append('missing_aggressor_side_proxy_marked')
        return NormalizedTrade(event_time=event,receive_time=_dt(recv) if recv else None,symbol=str(_get(row,ALIASES['symbol']) or ds.symbol),instrument_id=str(_get(row,ALIASES['instrument_id']) or ds.instrument_id or ''),price=float(_get(row,ALIASES['price'])),size=float(_get(row,ALIASES['size']) or 0),side=side,trade_id=str(_get(row,ALIASES['trade_id']) or ''),sequence=int(float(_get(row,ALIASES['sequence']) or 0)),source=ds.provider,flags={'proxy_side': side=='N','source_format':ds.stored_format}),warnings
    except Exception as exc:
        return None,[f'malformed_row:{exc}']

def to_trade(nt: NormalizedTrade) -> Trade:
    return Trade(symbol=nt.symbol,timestamp=nt.event_time,price=nt.price,size=nt.size,side='buy' if nt.side in {'B','BUY'} else 'sell' if nt.side in {'S','SELL'} else 'unknown')
