
import stripe
from fastapi import Depends
from app.core.database import get_db_session
from app.services.profile_service import ProfileService
from app.core.logging import console_logger

class PaymentService:
    def __init__(self, db_session):
        self.db_session = db_session
        self.profile_service = ProfileService(db_session)

    async def handle_purchase(self,session, mode):
        customer_email = session['customer_details']['email']
        subscription_id = session.get('subscription', None)
        
        # Get the price ID from the session
        if mode == 'subscription':
            # For subscription payments, get from line items
            line_items = session.get('line_items', {}).get('data', [])
            if line_items:
                price_id = line_items[0]['price']['id']
                product_id = line_items[0]['price']['product']  # Stripe product ID
            else:
                # Alternative: get from subscription object
                subscription = stripe.Subscription.retrieve(subscription_id)
                price_id = subscription['items']['data'][0]['price']['id']
                product_id = subscription['items']['data'][0]['price']['product']
        else:
            # For one-time payments
            line_items = session.get('line_items', {}).get('data', [])
            if line_items:
                price_id = line_items[0]['price']['id']
                product_id = line_items[0]['price']['product']
            else:
                # If line_items are not in the session, retrieve them separately
                line_items = stripe.checkout.Session.list_line_items(session['id'])
                price_id = line_items['data'][0]['price']['id']
                product_id = line_items['data'][0]['price']['product']
            
    async def handle_subscription_payment(self, data_object: dict):
        customer_email = data_object.get('customer_email')

        line_items = data_object.get('lines', {}).get('data', [])
        if not line_items:
            console_logger.error("No line items found in invoice data")
            raise Exception("No line items found in invoice data")
        
        line_item = line_items[0]        
        sub_id = line_item.get('parent', {}).get('subscription_item_details', {}).get('subscription')
        subscription_item_id = line_item.get('parent', {}).get('subscription_item_details', {}).get('subscription_item')            
        price_id = line_item.get('pricing', {}).get('price_details', {}).get('price')
        product_id = line_item.get('pricing', {}).get('price_details', {}).get('product')

        if not sub_id or not product_id:
            raise Exception("No subscription ID or product ID found in invoice data")
        
        await self.profile_service.update_user_profile_after_subscription_payment(
            customer_email=customer_email, 
            product_id=product_id, 
            subscription_id=sub_id
        )
    
    async def handle_subscription_deleted(self, data_object: dict):
        customer_id = data_object.get('customer')
        
        customer = stripe.Customer.retrieve(customer_id)
        customer_email = customer.email

        subscriptions = stripe.Subscription.list(customer=customer_id, status='all')        
        deleted_subscriptions = [sub for sub in subscriptions.data if sub.status == 'canceled']
        
        if not deleted_subscriptions:
            console_logger.error(f"No deleted subscriptions found for customer: {customer_email}")
            return
            
        most_recent_deleted = max(deleted_subscriptions, key=lambda x: x.created)

        sub_id = most_recent_deleted.id
        items_data = most_recent_deleted.get('items', {}).get('data', [])
        product_id = items_data[0].get('price', {}).get('product') if items_data else None

        await self.profile_service.update_user_profile_after_subscription_deleted(
            customer_email=customer_email, 
            product_id=product_id, 
            subscription_id=sub_id
        )
        
        console_logger.info(f"Subscription deleted - customer_email: {customer_email}, subscription_id: {sub_id}, product_id: {product_id}")
        
    