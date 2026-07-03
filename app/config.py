from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    databento_api_key: str = ""
    orderflow_provider: str = "mock"
    orderflow_port: int = 8010
    value_area_percent: float = 0.70
    default_tick_size_6e: float = 0.00005
    default_tick_size_6b: float = 0.0001
    default_tick_size_6j: float = 0.0000005
    default_tick_size_gc: float = 0.1

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def tick_size_for(self, futures_symbol: str) -> float:
        return {
            "6E": self.default_tick_size_6e,
            "6B": self.default_tick_size_6b,
            "6J": self.default_tick_size_6j,
            "GC": self.default_tick_size_gc,
        }.get(futures_symbol.upper(), self.default_tick_size_6e)


@lru_cache
def get_settings() -> Settings:
    return Settings()
