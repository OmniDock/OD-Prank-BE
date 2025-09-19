from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from sqlalchemy import text
from uuid import UUID

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

    async def lock_user_profile_by_id(self, user_id: str | UUID) -> UserProfile:
        try:
            lookup_id = user_id
            if isinstance(user_id, str):
                try:
                    lookup_id = UUID(user_id)
                except ValueError:
                    lookup_id = user_id
            result = await self.db.execute(
                select(UserProfile).where(UserProfile.user_id == lookup_id).with_for_update()
            )
            profile = result.scalar_one_or_none()
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to lock user profile: {str(e)}")
    
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
            auth_user_query = text("SELECT id, email FROM auth.users WHERE email = :email")
            auth_result = await self.db.execute(auth_user_query, {"email": email})
            row = auth_result.fetchone()
            if not row:
                raise Exception(f"Auth user not found for email: {email}")
            # Row supports attribute or index access depending on driver
            user_id = getattr(row, "id", None) or row[0]
            user_email = getattr(row, "email", None) or row[1]
            return AuthUser(user_id=user_id, email=user_email, metadata={})
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get auth user by email: {str(e)}")

    async def _get_auth_user_by_id(self, user_id: str) -> AuthUser:
        try:
            auth_user_query = text("SELECT id, email FROM auth.users WHERE id = :user_id")
            auth_result = await self.db.execute(auth_user_query, {"user_id": user_id})
            row = auth_result.fetchone()
            if not row:
                raise Exception(f"Auth user not found for id: {user_id}")
            uid = getattr(row, "id", None) or row[0]
            email = getattr(row, "email", None) or row[1]
            return AuthUser(user_id=uid, email=email, metadata={})
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to get auth user by id: {str(e)}")
