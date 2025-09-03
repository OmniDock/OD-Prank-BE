from fastapi import APIRouter, Body, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.core.database import AsyncSession, get_db_session
from app.repositories.blacklist_repository import BlacklistRepository
from app.core.utils.phone import to_e164


router = APIRouter(tags=["blacklist"])  # unauthenticated


class BlacklistRequest(BaseModel):
    phone_number: str = Field(..., description="Raw phone number (any format)")
    region: str = Field("DE", description="Default region for parsing if no country code")


class BlacklistResponse(BaseModel):
    success: bool
    phone_number_e164: str | None = None
    error: str | None = None


@router.post("/add", response_model=BlacklistResponse)
async def add_to_blacklist(
    payload: BlacklistRequest = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BlacklistRepository(db_session)
        phone = await repo.add(payload.phone_number, payload.region)
        return BlacklistResponse(success=True, phone_number_e164=phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/remove", response_model=BlacklistResponse)
async def remove_from_blacklist(
    payload: BlacklistRequest = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BlacklistRepository(db_session)
        phone = await repo.remove(payload.phone_number, payload.region)
        return BlacklistResponse(success=True, phone_number_e164=phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class BlacklistCheckResponse(BaseModel):
    phone_number_e164: str
    blacklisted: bool


@router.get("/check", response_model=BlacklistCheckResponse)
async def check_blacklist(
    phone_number: str = Query(..., description="Raw phone number (any format)"),
    region: str = Query("DE", description="Default region"),
    db_session: AsyncSession = Depends(get_db_session),
):
    repo = BlacklistRepository(db_session)
    try:
        phone_e164 = phone_number if phone_number.startswith("+") else to_e164(phone_number, region)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    blacklisted = await repo.is_blacklisted(phone_e164)
    return BlacklistCheckResponse(phone_number_e164=phone_e164, blacklisted=blacklisted)


