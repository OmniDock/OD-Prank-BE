import stripe
from app.core.database import AsyncSession
from app.models.user_profile import UserProfile
from app.core.auth import AuthUser
from sqlalchemy import select
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import CreditResponse
from app.core.utils.product_catalog import PRODUCT_CATALOG, get_product_name_by_product_id, get_product_name_by_price_id
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
        
    async def user_subscription_status(self, user: AuthUser) -> dict:
        user_email = user.email
        
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            console_logger.error(f"No customer found with email: {user_email}")
            return {'is_subscribed': False}
        else:
            customer = customers.data[0]
        if len(customers.data) > 1:
            console_logger.error(f"Multiple customers found while checking subscription status for email: {user_email}.Taking first with id {customer.id}")

        active_subscriptions = stripe.Subscription.list(customer=customer.id, status='active')
        has_active_subscription = len(active_subscriptions.data) > 0        
        
        return {'is_subscribed': has_active_subscription}


    async def update_user_profile_after_payment(self, customer_email: str,price_id: str, subscription_id: str, quantity: int = 1) -> None:
        #price_1S8NnAI5YzUifOCt4sDST62b 7 
        #price_1S8NnmI5YzUifOCtxmxEDo34 10
        catalog_key = None
        subscription_type = None
        console_logger.info(f"Updating user profile after payment: {customer_email}, {price_id}, {subscription_id}, {quantity}")
        catalog_key = get_product_name_by_price_id(price_id)
        product_data = PRODUCT_CATALOG[catalog_key]
        prank_increment = product_data.get('prank_amount', 0)
        call_increment = product_data.get('call_amount', 0)
        if catalog_key in ['weekly', 'monthly']:
            subscription_type = catalog_key
        elif catalog_key is None:
            raise ValueError(f"Product ID {price_id} not found in product catalog")
        
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(customer_email)
            profile.prank_credits += prank_increment * quantity
            profile.call_credits += call_increment * quantity
            if subscription_type:
                profile.subscription_id = subscription_id
                profile.subscription_type = subscription_type
            await self.db.commit()
            await self.db.refresh(profile)
        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
        
    async def update_user_profile_after_subscription_payment(self, customer_email: str, product_id: str,subscription_id: str) -> None:
        catalog_key = None
        subscription_type = None
        catalog_key = get_product_name_by_product_id(product_id)
        product_data = PRODUCT_CATALOG[catalog_key]
        prank_increment = product_data.get('prank_amount', 0)
        call_increment = product_data.get('call_amount', 0)
        if catalog_key in ['weekly', 'monthly']:
            subscription_type = catalog_key
        else:
            console_logger.error(f"Subscrption type {catalog_key} not found in product catalog")

        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(customer_email)
            profile.prank_credits += prank_increment
            profile.call_credits += call_increment
            profile_sub_id = profile.subscription_id

            if not profile_sub_id:
                profile.subscription_id = subscription_id
            elif profile_sub_id != subscription_id:
                console_logger.error(f"Subscription ID mismatch: profile subscription ID {profile_sub_id} != payment subscription ID {subscription_id} for user {customer_email}")
            if not profile.subscription_type:
                profile.subscription_type = subscription_type
            elif profile.subscription_type != subscription_type:
                console_logger.error(f"Subscription type mismatch: profile subscription type {profile.subscription_type} != payment subscription type {subscription_type} for user {customer_email}")

            await self.db.commit()
            await self.db.refresh(profile)
            console_logger.info(f"Profile {profile.profile_uuid} updated with {prank_increment} prank credits and {call_increment} call credits")

        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile: {str(e)}")
            

    async def update_user_profile_after_subscription_deleted(self, customer_email: str, product_id: str, subscription_id: str) -> None:
        subscription_type = get_product_name_by_product_id(product_id)
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(customer_email)
            profile.subscription_id = None
            profile.subscription_type = None
            await self.db.commit()
            await self.db.refresh(profile)
            console_logger.info(f"Profile {profile.profile_uuid} updated with subscription ID {subscription_id} and subscription type {subscription_type}")

            if profile.subscription_id != subscription_id:
                console_logger.error(f'Subscription ID mismatch for Subscription Deleted: profile subscription ID "{profile.subscription_id}" != cancelation subscription ID "{subscription_id}" for user {customer_email}')
            
            if profile.subscription_type != subscription_type:
                console_logger.error(f'Subscription type mismatch for Subscription Deleted: profile subscription type "{profile.subscription_type}" != cancelation subscription type "{subscription_type}" for user {customer_email}')

        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to update profile {customer_email}: {str(e)}")


    async def get_or_create_profile_by_email(self, email: str) -> UserProfile:
        try:
            profile = await self.profile_repo.get_or_create_user_profile_by_email(email)
            return profile
        except Exception as e:
            raise Exception(f"Failed to get profile by email: {str(e)}")
        
