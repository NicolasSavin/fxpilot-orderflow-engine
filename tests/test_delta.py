from app.calculators.cumdelta import update_cumdelta
from app.calculators.delta import calculate_delta
from app.models.market import Trade
from app.storage.memory_store import MemoryStore


def test_delta_calculation_with_side_and_tick_rule():
    trades = [Trade(symbol="6E", price=1.0, size=10, side="buy"), Trade(symbol="6E", price=0.9, size=4, side="unknown"), Trade(symbol="6E", price=0.9, size=3, side="unknown")]
    result = calculate_delta(trades)
    assert result["delta"] == 6
    assert result["buy_volume"] == 10
    assert result["sell_volume"] == 4
    assert result["unknown_volume"] == 3


def test_cumdelta_update_and_reset():
    memory = MemoryStore()
    assert update_cumdelta("6E", 5, memory_store=memory) == 5
    assert update_cumdelta("6E", -2, memory_store=memory) == 3
    assert update_cumdelta("6E", 1, reset_session=True, memory_store=memory) == 1
