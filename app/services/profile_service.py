from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import CreditResponse
from app.core.utils.product_catalog import PRODUCT_CATALOG
from app.core.logging import console_logger

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
    
    async def get_credits(self, user: AuthUser) -> CreditResponse:
        try:
            profile = await self.profile_repo.ensure_user_profile(user)
            prank_credits = profile.prank_credits 
            call_credits = profile.call_credits
            return CreditResponse(prank_credit_amount=prank_credits, call_credit_amount=call_credits)
        except Exception as e:
            raise Exception(f"Failed to get credits: {str(e)}")
        
    async def update_user_profile_after_payment(self, customer_email: str, product_id: str, subscription_id: str) -> None:
        catalog_key = None
        prank_increment = 0
        call_increment = 0
        subscription_type = None
        for key, value in PRODUCT_CATALOG.items():
            if value['stripe_product_id'] == product_id:
                catalog_key = key
                prank_increment = value.get('prank_amount', 0)
                call_increment = value.get('call_amount', 0)
                if catalog_key in ['weekly', 'monthly']:
                    subscription_type = catalog_key
                break

        if catalog_key is None:
            raise ValueError(f"Product ID {product_id} not found in product catalog")
        try:
            profile = await self.profile_repo.ensure_user_profile_by_email(customer_email)
            profile.subscription_id = subscription_id
            profile.subscription_type = subscription_type
            profile.prank_credits += prank_increment
            profile.call_credits += call_increment
            await self.db.commit()
            await self.db.refresh(profile)
            console_logger.info(f"Profile {profile.profile_uuid} updated with {prank_increment} prank credits and {call_increment} call credits")
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
        
        
    async def get_or_create_profile_by_email(self, email: str) -> UserProfile:
        try:
            profile = await self.profile_repo.ensure_user_profile_by_email(email)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile by email: {str(e)}")
        
