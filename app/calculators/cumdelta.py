from app.storage.memory_store import MemoryStore, store


def update_cumdelta(symbol: str, delta: float, reset_session: bool = False, memory_store: MemoryStore = store) -> float:
    return memory_store.update_cumdelta(symbol, delta, reset=reset_session)
