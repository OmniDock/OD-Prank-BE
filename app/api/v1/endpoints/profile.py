from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.profile_service import ProfileService

profile_service = ProfileService()
router = APIRouter(tags=["profile"])

@router.get("/")
async def get_profile(user: AuthUser = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)):
    try:
        return await profile_service.ensure_user_profile(user=user, db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






