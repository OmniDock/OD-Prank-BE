from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["analytics"])

@router.get("/summary")
async def analytics_summary(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        svc = AnalyticsService(db)
        return await svc.get_summary(user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute analytics: {str(e)}")