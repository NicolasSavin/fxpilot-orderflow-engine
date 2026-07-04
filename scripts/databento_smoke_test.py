#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.calculators.cumdelta import CumDeltaEngine
from app.calculators.market_state import calculate_market_state_result
from app.calculators.volume_profile import calculate_volume_profile
from app.calculators.vwap import calculate_vwap_result
from app.config import get_settings
from app.models.orderflow import AbsorptionResult, DOMResult, VolumeProfileResult
from app.providers.databento_provider import DatabentoProvider

MISSING_API_KEY_MESSAGE = "DATABENTO_API_KEY is not configured"
MISSING_SDK_MESSAGE = "databento package is not installed. Run pip install databento"


def parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Databento historical smoke test through the OrderFlow Engine.")
    parser.add_argument("--symbol", required=True, help="FXPilot symbol, for example EURUSD, GBPUSD, USDJPY, or XAUUSD.")
    parser.add_argument("--start", required=True, help="UTC start time, for example 2026-07-01T00:00:00.")
    parser.add_argument("--end", required=True, help="UTC end time, for example 2026-07-01T01:00:00.")
    return parser


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


async def collect_snapshot(symbol: str, start: datetime, end: datetime) -> dict[str, Any]:
    provider = DatabentoProvider()
    trades = await provider.get_recent_trades(symbol, start=start, end=end)
    futures_symbol = trades[0].symbol if trades else symbol
    settings = get_settings()
    tick_size = settings.tick_size_for(futures_symbol)

    volume_profile_dict = calculate_volume_profile(trades, tick_size=tick_size, value_area_percent=settings.value_area_percent)
    volume_profile = VolumeProfileResult(**{key: volume_profile_dict[key] for key in VolumeProfileResult.model_fields if key in volume_profile_dict})
    cumdelta = CumDeltaEngine().process_trades(trades, reset_session=True)
    if cumdelta is None:
        from app.models.orderflow import CumDeltaResult

        cumdelta = CumDeltaResult(symbol=futures_symbol)
    vwap = calculate_vwap_result(trades, cumdelta_bias=cumdelta.bias)
    dom = DOMResult()
    absorption = AbsorptionResult(exhaustion="unavailable", reason="not_run_in_historical_smoke_test")
    last_price = trades[-1].price if trades else 0.0
    total_volume = sum(trade.size for trade in trades)
    first_price = trades[0].price if trades else last_price
    price_change_percent = ((last_price - first_price) / first_price * 100) if first_price else 0.0
    market_state = calculate_market_state_result(
        price=last_price,
        volume=trades[-1].size if trades else 0.0,
        volume_profile=volume_profile,
        cumdelta=cumdelta,
        vwap=vwap,
        dom=dom,
        absorption=absorption,
        average_volume=(total_volume / len(trades)) if trades else None,
        price_change_percent=price_change_percent,
    )

    return {
        "symbol": symbol,
        "futures_symbol": futures_symbol,
        "provider": provider.status(),
        "window": {"start": start, "end": end},
        "trade_count": len(trades),
        "last_trade": trades[-1] if trades else None,
        "volume_profile": volume_profile,
        "cumdelta": cumdelta,
        "vwap": vwap,
        "market_state": market_state,
    }


def validate_environment() -> int | None:
    load_dotenv(ROOT / ".env")
    get_settings.cache_clear()
    if not get_settings().databento_api_key:
        print(MISSING_API_KEY_MESSAGE, file=sys.stderr)
        return 2
    if importlib.util.find_spec("databento") is None:
        print(MISSING_SDK_MESSAGE, file=sys.stderr)
        return 3
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    error_code = validate_environment()
    if error_code is not None:
        return error_code
    start = parse_datetime(args.start)
    end = parse_datetime(args.end)
    snapshot = asyncio.run(collect_snapshot(args.symbol, start, end))
    print(json.dumps(to_jsonable(snapshot), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
