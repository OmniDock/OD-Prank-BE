from fastapi import APIRouter
from app.api.v1.endpoints import health, profile, scenario, tts, audio_preload

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(scenario.router, prefix="/scenario", tags=["scenario"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(audio_preload.router, prefix="/audio-preload", tags=["audio-preload"])