from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.services.preview_tts_service import PreviewTTSService
from app.core.utils.voices_catalog import get_voices_catalog
from app.core.middleware import RequestLoggingMiddleware, ErrorHandlingMiddleware
from app.services.cache_service import CacheService 
from app.services.telnyx.handler import preload_background_noise_from_supabase


@asynccontextmanager
async def lifespan(app: FastAPI):

    # # Startup: Initialize Global Cache (class-level)
    cache = await CacheService.get_global()
    app.state.cache = cache

    # Startup: Ensure voice previews
    service = PreviewTTSService()
    catalog = get_voices_catalog()
    await service.ensure_previews_for_catalog(catalog)

    # Startup: Preload background noise
    #await preload_background_noise_from_supabase()

    yield

    # Shutdown: close global cache
    await CacheService.close_global()

app = FastAPI(
    title="Omnidock Prank Call Backend",
    description="Backend for the Omnidock Prank Call App",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
