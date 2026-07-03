from typing import Literal
from pydantic import BaseModel

ProviderStatus = Literal["ok", "unavailable", "not_configured"]
ProviderName = Literal["mock", "databento"]


class ProviderStatusResponse(BaseModel):
    provider: str
    databento_configured: bool
    live_enabled: bool = False
    historical_enabled: bool = False
