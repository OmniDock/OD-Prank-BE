from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from sqlalchemy import text

class ProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_user_profile(self, user: AuthUser) -> UserProfile:
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
            raise Exception(f"Failed to get or create user profile: {str(e)}")
    
    async def get_or_create_user_profile_by_email(self, email: str) -> UserProfile:
        try:
            result = await self.db.execute(
                select(UserProfile).where(UserProfile.user_email == email)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                auth_user = await self._get_auth_user_by_email(email)
                profile = UserProfile(user_email=email, user_id=auth_user.id)
                self.db.add(profile)
                await self.db.commit()
                await self.db.refresh(profile)
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get or create user profile by email: {str(e)}")

    
    async def get_or_create_user_profile_by_id(self, user_id: str) -> UserProfile:
        try:
            result = await self.db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                auth_user = await self._get_auth_user_by_id(user_id)
                profile = UserProfile(user_id=user_id, user_email=auth_user.email)
                self.db.add(profile)
                await self.db.commit()
                await self.db.refresh(profile)
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get or create user profile by id: {str(e)}")
        
    async def _get_auth_user_by_email(self, email: str) -> AuthUser:
        try:
            auth_user_query = text("SELECT id FROM auth.users WHERE email = :email")
            auth_result = await self.db.execute(auth_user_query, {"email": email})
            auth_user = auth_result.fetchone()
            user_id = auth_user.id
            user_metadata = auth_user.metadata
            return AuthUser(user_id=user_id, email=email, metadata=user_metadata)
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get auth user by email: {str(e)}")

    async def _get_auth_user_by_id(self, user_id: str) -> AuthUser:
        try:
            auth_user_query = text("SELECT id FROM auth.users WHERE id = :user_id")
            auth_result = await self.db.execute(auth_user_query, {"user_id": user_id})
            auth_user = auth_result.fetchone()
            user_id = auth_user.id
            email = auth_user.email
            user_metadata = auth_user.metadata
            return AuthUser(user_id=user_id, email=email, metadata=user_metadata)
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get auth user by id: {str(e)}")