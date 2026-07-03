from fastapi import APIRouter
from app.services.engine import engine
router = APIRouter(prefix="/api/orderflow")

@router.get("/debug")
def debug():
    return engine.debug()

@router.get("/provider/status")
def provider_status():
    return engine.provider_status()
