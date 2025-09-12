import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from app.core.logging import console_logger
from app.core.config import settings
from app.core.auth import get_current_user, AuthUser
from app.core.database import get_db_session
from app.models.user_profile import UserProfile
from sqlalchemy import select, text
from app.core.utils.product_catalog import PRODUCT_PRICE_CATALOG, PRODUCT_CATALOG
# Initialize Stripe with the secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payment"])

@router.post("/checkout/create-session")
def create_checkout_session(request: dict, user: AuthUser = Depends(get_current_user)):
    user_email = user.email
    customers = stripe.Customer.list(email=user_email, limit=1)
    params = {
        "ui_mode": "embedded",
        "mode": "subscription",
        "return_url": settings.STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}",
        "automatic_tax": {"enabled": True},
    }

    if customers.data:
        customer_id = customers.data[0].id
        params["customer"] = customer_id
    else:
        params["customer_email"] = user_email
        
    try:
        sub_type = request.get("subscription_type")
        price_id = PRODUCT_PRICE_CATALOG[sub_type]['price_id']
        quantity = PRODUCT_PRICE_CATALOG[sub_type]['quantity']
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
        print('products_list', products_list)
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
    subscription_id = session['subscription']
    
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
    
    # Map price_id back to your catalog key
    catalog_key = None
    for key, value in PRODUCT_PRICE_CATALOG.items():
        if value['price_id'] == price_id:
            catalog_key = key
            break
    
    # Get user from database using email
    async for db_session in get_db_session():
        try:
            # First, get the user_id from Supabase auth system using email
            auth_user_query = text("SELECT id FROM auth.users WHERE email = :email")
            auth_result = await db_session.execute(auth_user_query, {"email": customer_email})
            auth_user = auth_result.fetchone()
            
            user = None
            if auth_user:
                user_id = auth_user[0]  # Get the UUID from the result
                
                # Now get the UserProfile using the user_id
                profile_query = select(UserProfile).where(UserProfile.user_id == user_id)
                profile_result = await db_session.execute(profile_query)
                user = profile_result.scalar_one_or_none()
                
                console_logger.info(f"Found auth user with ID: {user_id} for email: {customer_email}")
            else:
                console_logger.warning(f"No auth user found with email: {customer_email}")
            
            if user:
                console_logger.info(f"Payment successful - User Profile ID: {user.profile_uuid}, Email: {customer_email}, Price ID: {price_id}, Product ID: {product_id}, Catalog Key: {catalog_key}, Mode: {mode}")
                
                # Update user's subscription status in your database
                user.subscription_id = subscription_id
                user.subscription_type = catalog_key
                await db_session.commit()
                
                console_logger.info(f"Updated user {user.profile_uuid} subscription: {catalog_key}")
                
            else:
                console_logger.warning(f"Payment successful but no UserProfile found for email: {customer_email}")
                
        except Exception as e:
            console_logger.error(f"Error processing payment for {customer_email}: {str(e)}")
        finally:
            break  
