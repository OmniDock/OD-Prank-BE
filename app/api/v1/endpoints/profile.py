from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, AuthUser

router = APIRouter()

@router.get("/")
async def get_profile(user: AuthUser = Depends(get_current_user)):
    return user