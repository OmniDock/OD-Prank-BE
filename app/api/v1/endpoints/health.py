from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.core.database import async_session_maker
from app.core.config import settings
import httpx
import asyncio
from datetime import datetime

router = APIRouter()

@router.get("/")
async def health():
    """Basic health check"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@router.get("/detailed")
async def detailed_health():
    """Detailed health check including database and Supabase connectivity"""
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database connectivity
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
            health_status["services"]["database"] = {
                "status": "healthy",
                "message": "Database connection successful"
            }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Check Supabase API connectivity
    try:
        timeout = httpx.Timeout(5.0)  # 5 second timeout
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.SUPABASE_URL}/rest/v1/", 
                                      headers={"apikey": settings.SUPABASE_ANON_KEY})
            if response.status_code in [200, 401]:  # 401 is expected without proper auth
                health_status["services"]["supabase_api"] = {
                    "status": "healthy",
                    "message": "Supabase API reachable"
                }
            else:
                health_status["services"]["supabase_api"] = {
                    "status": "unhealthy", 
                    "message": f"Supabase API returned status {response.status_code}"
                }
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["supabase_api"] = {
            "status": "unhealthy",
            "message": f"Supabase API unreachable: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Check Supabase Auth
    try:
        timeout = httpx.Timeout(5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{settings.SUPABASE_URL}/auth/v1/settings",
                                      headers={"apikey": settings.SUPABASE_ANON_KEY})
            if response.status_code == 200:
                health_status["services"]["supabase_auth"] = {
                    "status": "healthy",
                    "message": "Supabase Auth service healthy"
                }
            else:
                health_status["services"]["supabase_auth"] = {
                    "status": "unhealthy",
                    "message": f"Supabase Auth returned status {response.status_code}"
                }
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["supabase_auth"] = {
            "status": "unhealthy", 
            "message": f"Supabase Auth unreachable: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Overall status
    if health_status["status"] == "degraded":
        # Return 503 if any service is down but keep the response
        return health_status
    
    return health_status

