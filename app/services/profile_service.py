from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import Credits

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_repo = ProfileRepository(db)

    
    async def get_profile(self, user: AuthUser) -> UserProfile:
        try:
            profile = await self.profile_repo.ensure_user_profile(user)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile: {str(e)}")
    
    async def update_credits(self, user: AuthUser, prank_credit_amount: int, call_credit_amount: int) -> UserProfile:
        try:
            profile = await self.profile_repo.ensure_user_profile(user)
            profile.prank_credits += prank_credit_amount
            profile.call_credits += call_credit_amount
            await self.db.commit()
            await self.db.refresh(profile)
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update credits: {str(e)}")
    
    async def get_credits(self, user: AuthUser) -> Credits:
        try:
            profile = await self.profile_repo.ensure_user_profile(user)
            prank_credits = profile.prank_credits 
            call_credits = profile.call_credits
            return Credits(prank_credit_amount=prank_credits, call_credit_amount=call_credits)
        except Exception as e:
            raise Exception(f"Failed to get credits: {str(e)}")