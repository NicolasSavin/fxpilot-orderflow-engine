from fastapi import FastAPI
from app.api.routes_databento_debug import router as databento_debug_router
from app.api.routes_debug import router as debug_router
from app.api.routes_health import router as health_router
from app.api.routes_historical import router as historical_router
from app.api.routes_orderflow import router as orderflow_router
from app.api.routes_replays import router as replays_router

app = FastAPI(title="FXPilot OrderFlow Engine", version="1.0.0")
app.include_router(health_router)
app.include_router(orderflow_router)
app.include_router(debug_router)
app.include_router(databento_debug_router)
app.include_router(historical_router)
app.include_router(replays_router)
