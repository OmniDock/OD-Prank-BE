from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import CreditResponse
from app.core.utils.product_catalog import PRODUCT_CATALOG, get_product_name_by_product_id
from app.core.logging import console_logger

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_repo = ProfileRepository(db)

    
    async def get_profile(self, user: AuthUser) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile(user)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile: {str(e)}")
    
    async def update_credits(self, user: AuthUser, prank_credit_amount: int, call_credit_amount: int) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile(user)
            profile.prank_credits += prank_credit_amount
            profile.call_credits += call_credit_amount
            await self.db.commit()
            await self.db.refresh(profile)
            return profile
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update credits: {str(e)}")
    
    async def update_user_credits_by_id(self, user_id: str, prank_credit_amount: int, call_credit_amount: int) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_id(user_id)
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
            profile = await self.profile_repo.get_or_create_user_profile(user)
            prank_credits = profile.prank_credits 
            call_credits = profile.call_credits
            return CreditResponse(prank_credit_amount=prank_credits, call_credit_amount=call_credits)
        except Exception as e:
            raise Exception(f"Failed to get credits: {str(e)}")
        
    async def update_user_profile_after_payment(self, customer_email: str, product_id: str, subscription_id: str, next_billing_date: int = None) -> None:
        catalog_key = None
        prank_increment = 0
        call_increment = 0
        subscription_type = None
        product_name = get_product_name_by_product_id(product_id)
        product_data = PRODUCT_CATALOG[product_name]
        catalog_key = product_name
        prank_increment = product_data.get('prank_amount', 0)
        call_increment = product_data.get('call_amount', 0)
        if catalog_key in ['weekly', 'monthly']:
            subscription_type = catalog_key

        if catalog_key is None:
            raise ValueError(f"Product ID {product_id} not found in product catalog")
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(customer_email)
            profile.prank_credits += prank_increment
            profile.call_credits += call_increment
            if subscription_type:
                profile.subscription_id = subscription_id
                profile.subscription_type = subscription_type
            if next_billing_date:
                profile.next_billing_date = next_billing_date
            await self.db.commit()
            await self.db.refresh(profile)
            console_logger.info(f"Profile {profile.profile_uuid} updated with {prank_increment} prank credits and {call_increment} call credits")
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
    
    async def update_user_profile_after_cancel(self, auth_user: AuthUser, cancel_at: int) -> None:
        try:
            profile = await self.profile_repo.get_or_create_user_profile(auth_user)
            profile.cancel_at = cancel_at
            await self.db.commit()
            await self.db.refresh(profile)
            console_logger.info(f"Profile {profile.profile_uuid} updated with cancel_at {cancel_at}")
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
        
    async def get_or_create_profile_by_email(self, email: str) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(email)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile by email: {str(e)}")
        
    async def get_profile_by_id(self, user_id: str) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_id(user_id)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile by id: {str(e)}")