from fastapi import APIRouter, Depends, HTTPException, Body
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.profile_service import ProfileService
router = APIRouter(tags=["profile"])

@router.get("/")
async def get_profile(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    try:
        profile_service = ProfileService(db=db)
        return await profile_service.get_profile(user=user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get-credits")
async def get_credits(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    try:
        profile_service = ProfileService(db=db)
        return await profile_service.get_credits(user=user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-credits")
async def update_credits(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session), request: dict = Body(...)):
    try:
        prank_credit_amount = request.get("prank_credit_amount", 0)
        call_credit_amount = request.get("call_credit_amount", 0)
        profile_service = ProfileService(db=db)
        return await profile_service.update_credits(user=user, prank_credit_amount=prank_credit_amount, call_credit_amount=call_credit_amount)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))