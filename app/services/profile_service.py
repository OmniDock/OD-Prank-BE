from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select


class ProfileService:
    @staticmethod
    async def ensure_user_profile(user: AuthUser, db: AsyncSession) -> UserProfile:
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user.id)
        )
        profile = result.scalar_one_or_none()        
        if not profile:
            profile = UserProfile(user_id=user.id, user_email=user.email)
            db.add(profile)
            await db.commit()
        return profile