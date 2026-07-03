from fastapi import FastAPI
from app.api.routes_debug import router as debug_router
from app.api.routes_health import router as health_router
from app.api.routes_orderflow import router as orderflow_router

app = FastAPI(title="FXPilot OrderFlow Engine", version="1.0.0")
app.include_router(health_router)
app.include_router(orderflow_router)
app.include_router(debug_router)
