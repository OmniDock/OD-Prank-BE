from fastapi import APIRouter
from app.api.v1.endpoints import health, profile

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])