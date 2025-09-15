import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from app.core.logging import console_logger
from app.core.config import settings
from app.core.auth import get_current_user, AuthUser
from app.core.database import get_db_session
from app.services.profile_service import ProfileService
from app.models.user_profile import UserProfile
from sqlalchemy import select, text
from app.core.utils.product_catalog import PRODUCT_PRICE_CATALOG, PRODUCT_CATALOG, get_product_name_by_product_id
from app.core.utils.enums import ProductNameEnum
from app.schemas.payment import CheckoutSessionParams, LineItem

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payment"])
@router.post("/checkout/create-session")
def create_checkout_session(request: dict, user: AuthUser = Depends(get_current_user)):
    user_email = user.email
    customers = stripe.Customer.list(email=user_email, limit=1)
    params = {
        "ui_mode": "embedded",
        "return_url": settings.STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}",
        "automatic_tax": {"enabled": True},
    }

    if customers.data:
        customer_id = customers.data[0].id
        params["customer"] = customer_id
    else:
        params["customer_email"] = user_email
        
    try:
        product_type = request.get("product_type",None)
        if product_type not in PRODUCT_PRICE_CATALOG:
            raise HTTPException(status_code=400, detail=f"Invalid product type: {product_type}")
        
        mode = 'payment' if product_type == ProductNameEnum.SINGLE.value else 'subscription'
        price_id = PRODUCT_PRICE_CATALOG[product_type]['price_id']
        quantity = PRODUCT_PRICE_CATALOG[product_type]['quantity']
        params["mode"] = mode
        params["line_items"] = [{
            "price": price_id,
            "quantity": quantity
        }]
        session = stripe.checkout.Session.create(**params)
        return {"client_secret": session["client_secret"], "id": session["id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/checkout/customer-id")
def get_customer_id(email: str):
    try:
        # First, try to find an existing customer by email
        customers = stripe.Customer.list(email=email, limit=1)
        
        if customers.data:
            # Customer exists, return the ID
            customer_id = customers.data[0].id
            return {"customer_id": customer_id, "message": "Existing customer found"}
        else:
            # Customer doesn't exist, create a new one
            customer = stripe.Customer.create(email=email)
            return {"customer_id": customer.id, "message": "New customer created"}
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/checkout/session-status')
def session_status(session_id: str):
  session = stripe.checkout.Session.retrieve(session_id)

  return {"status": session.status, "customer_email": session.customer_details.email}


@router.get('/product-info')
def get_products():
    try:
        # Create a copy of the product catalog to modify
        updated_catalog = PRODUCT_CATALOG.copy()
        
        # Query Stripe using price IDs from PRODUCT_PRICE_CATALOG
        for catalog_key, catalog_entry in updated_catalog.items():
            # Get the price ID from PRODUCT_PRICE_CATALOG using the same key
            if catalog_key in PRODUCT_PRICE_CATALOG:
                price_id = PRODUCT_PRICE_CATALOG[catalog_key]['price_id']
                
                # Get price details from Stripe
                price_data = stripe.Price.retrieve(price_id)
                
                stripe_price = price_data.unit_amount / 100
                stripe_interval = price_data.recurring.interval if price_data.recurring else None
                
                # Update catalog entry with Stripe data
                catalog_entry['price'] = stripe_price
                catalog_entry['interval'] = stripe_interval
        
        # Convert catalog to list of dictionaries
        products_list = []
        for catalog_key, catalog_entry in updated_catalog.items():
            filtered_entry = {'id': catalog_key}
            filtered_entry.update({k: v for k, v in catalog_entry.items() if k not in ['stripe_product_id']})
            products_list.append(filtered_entry)
        return {"products": products_list}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        mode = session['mode'] 
        await handle_successful_payment(session=session, mode=mode)
    
    return {"status": "success"}

async def handle_successful_payment(session, mode):
    customer_email = session['customer_details']['email']
    subscription_id = session.get('subscription', None)
    next_billing_date = None
    
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
        
        # Get next billing date from subscription
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                next_billing_date = subscription.get('current_period_end')
                if next_billing_date:
                    console_logger.info(f"Next billing date for subscription {subscription_id}: {next_billing_date}")
                    
                    # Convert to readable format for logging
                    from datetime import datetime
                    readable_date = datetime.fromtimestamp(next_billing_date).strftime("%Y-%m-%d %H:%M:%S")
                    console_logger.info(f"Readable next billing date: {readable_date}")
                else:
                    console_logger.warning(f"No current_period_end found for subscription {subscription_id}")
            except stripe.error.StripeError as e:
                console_logger.error(f"Error retrieving subscription {subscription_id}: {e}")
                next_billing_date = None
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
        
    
    async for db_session in get_db_session():
        profile_service = ProfileService(db_session)
        await profile_service.update_user_profile_after_payment(
            customer_email=customer_email, 
            product_id=product_id, 
            subscription_id=subscription_id,
            next_billing_date=next_billing_date
            )