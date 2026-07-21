from __future__ import annotations
from datetime import datetime, timezone, timedelta
import time
from app.calculators.cumdelta import CumDeltaEngine
from app.calculators.delta import calculate_delta
from app.calculators.vwap import VWAPEngine
from app.models.market import Candle, Trade
from app.services.engine import engine
from app.storage.memory_store import store
from .models import HistoricalReplayResult, HistoricalReplayState, ReplayProvenance, ReplayStatus, ReplayCandle
from .normalizer import normalize_row, provenance_defaults, to_trade
from .readers import reader_for

INTERVALS=(1,5,60,300)
def candle_key(ts,sec): return ts.replace(microsecond=0) - timedelta(seconds=ts.second%sec if sec<60 else ((ts.minute*60+ts.second)%sec))

def build_candles(trades:list[Trade], volume_type:str, is_proxy:bool, interval:int=60):
    buckets={}
    for t in trades:
        k=candle_key(t.timestamp,interval); b=buckets.setdefault(k,[]); b.append(t)
    out=[]
    for k,ts in sorted(buckets.items()):
        vol=sum(t.size for t in ts); buy=sum(t.size for t in ts if t.side=='buy'); sell=sum(t.size for t in ts if t.side=='sell')
        out.append(ReplayCandle(open=ts[0].price,high=max(t.price for t in ts),low=min(t.price for t in ts),close=ts[-1].price,volume=vol,trade_count=len(ts),buy_volume=buy,sell_volume=sell,delta=buy-sell,start_at=k,end_at=k+timedelta(seconds=interval),volume_type=volume_type,is_proxy=is_proxy))
    return out

def run_replay(ds, state:HistoricalReplayState, storage, *, max_rows:int|None=None):
    req=state.request; start=time.monotonic(); state.status=ReplayStatus.RUNNING; state.started_at=state.started_at or datetime.now(timezone.utc)
    provd=provenance_defaults(ds); warnings=list(state.warnings); rows=[]; malformed=0
    reader=reader_for(ds); scanned=0
    for row in reader.iter_rows(ds, state.start_at, state.end_at):
        scanned+=1
        if scanned<=state.cursor: continue
        nt,ws=normalize_row(row,ds); warnings.extend(ws)
        if nt is None: malformed+=1; continue
        if state.start_at and nt.event_time<state.start_at: continue
        if state.end_at and nt.event_time>state.end_at: continue
        rows.append(nt)
        if max_rows and len(rows)>=max_rows: break
    if not rows and state.rows_processed==0:
        state.status=ReplayStatus.FAILED; state.last_error='no replayable rows'; storage.save_state(state); raise ValueError('no replayable rows')
    out_of_order=sum(1 for a,b in zip(rows,rows[1:]) if (a.event_time,a.sequence,a.trade_id)>(b.event_time,b.sequence,b.trade_id))
    rows.sort(key=lambda r:(r.event_time,r.sequence,r.trade_id))
    seen=set(); trades=[]; dup=0
    for nt in rows:
        key=(nt.source,nt.instrument_id,nt.sequence,nt.trade_id,nt.event_time.isoformat())
        if key in seen: dup+=1; continue
        seen.add(key); trades.append(to_trade(nt))
    symbol=req.get('symbol') or ds.symbol
    if req.get('reset_session') and state.rows_processed==0:
        store.trades[symbol]=[]; store.books[symbol]=[]; store.candles[symbol]=[]; store.reset_cumdelta_session(symbol); VWAPEngine(memory_store=store).reset_session(symbol)
    elif not req.get('reset_session') and store.trades.get(symbol) and trades and trades[0].timestamp < store.trades[symbol][-1].timestamp:
        state.status=ReplayStatus.FAILED; state.last_error='backward-time append rejected'; storage.save_state(state); raise ValueError(state.last_error)
    candles_ext=build_candles(trades,provd['volume_type'],provd['is_proxy'])
    candles=[Candle(symbol=symbol,timestamp=c.start_at,open=c.open,high=c.high,low=c.low,close=c.close,volume=c.volume) for c in candles_ext]
    store.ingest(symbol,trades=trades,book=[],candles=candles)
    d=calculate_delta(trades); CumDeltaEngine(memory_store=store).update(symbol,d['delta'],timestamp=trades[-1].timestamp if trades else None,buy_volume=d['buy_volume'],sell_volume=d['sell_volume'],total_volume=sum(t.size for t in trades)) if trades else None
    snap=engine._build_snapshot(requested_symbol=symbol,futures=symbol,trades=store.trades.get(symbol,[]),book=[],candles=store.candles.get(symbol,[]),provider_name='databento' if ds.provider=='databento' else 'mock',status='ok',timestamp=trades[-1].timestamp if trades else None,provider_debug={'source':'historical_replay','dataset_id':ds.id,'reader':reader.name,'calculators_executed':['delta','cumdelta','volume_profile','value_area','vwap','absorption','market_state'],'calculators_unavailable':['dom:no_book_data'],'out_of_order_records':out_of_order,'volume_type':provd['volume_type'],'is_proxy':provd['is_proxy']})
    if req.get('persist_snapshots') and trades: storage.append_snapshot(state.replay_id,snap.model_dump(mode='json'))
    processed=len(trades); state.rows_processed+=processed; state.cursor=scanned; state.malformed_rows+=malformed; state.duplicate_rows+=dup; state.rows_skipped+=malformed; state.current_event_time=trades[-1].timestamp if trades else state.current_event_time
    state.rows_total=state.rows_total or getattr(ds,'record_count',0); state.progress_percent=round(min(100,100*state.cursor/max(state.rows_total or state.cursor or 1,1)),2)
    complete = max_rows is None or state.cursor >= (state.rows_total or scanned)
    if req.get('mode')=='STEP' and max_rows: complete = state.cursor >= (state.rows_total or scanned)
    state.status=ReplayStatus.COMPLETED if complete else ReplayStatus.PAUSED; state.completed_at=datetime.now(timezone.utc) if complete else None; state.warnings=sorted(set(warnings))[:50]; storage.save_state(state)
    prov=ReplayProvenance(dataset_id=ds.id,replay_mode=req.get('mode','BATCH'),normalization_warnings=state.warnings,**provd)
    result=HistoricalReplayResult(replay_id=state.replay_id,dataset_id=ds.id,symbol=symbol,status=state.status,trades_processed=state.rows_processed,candles_built=len(store.candles.get(symbol,[])),first_event_time=store.trades.get(symbol,[None])[0].timestamp if store.trades.get(symbol) else None,last_event_time=state.current_event_time,duration_ms=int((time.monotonic()-start)*1000),final_snapshot=snap.model_dump(mode='json'),snapshot_count=len(storage.snapshots(state.replay_id)),provenance=prov,warnings=state.warnings,errors=[] if state.status!=ReplayStatus.FAILED else [state.last_error or 'failed'])
    storage.save_result(result); return result
