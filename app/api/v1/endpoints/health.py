from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/")
async def health():
    """Basic health check"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
