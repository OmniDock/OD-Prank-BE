from fastapi import APIRouter
from app.api.v1.endpoints import health, profile, scenario, tts, telnyx, analytics, voice_line, blacklist, design_chat, payment

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(scenario.router, prefix="/scenario", tags=["scenario"])
api_router.include_router(design_chat.router, prefix="/design-chat", tags=["design-chat"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(telnyx.router, prefix="/telnyx", tags=["telnyx"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(voice_line.router, prefix="/voice-lines", tags=["voice-lines"])
api_router.include_router(blacklist.router, prefix="/blacklist", tags=["blacklist"])
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])