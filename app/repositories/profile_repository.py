from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select


class ProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_user_profile(self, user: AuthUser) -> UserProfile:
        try:
            result = await self.db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = result.scalar_one_or_none()        
            if not profile:
                profile = UserProfile(user_id=user.id, user_email=user.email)
                self.db.add(profile)
                await self.db.commit()
                await self.db.refresh(profile)
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to ensure user profile: {str(e)}")
    
    