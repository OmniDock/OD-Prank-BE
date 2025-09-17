import stripe
from fastapi import APIRouter, HTTPException, Request, Depends, Body
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
from app.services.payment_service import PaymentService

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payment"])
@router.post("/checkout/create-session")
def create_checkout_session(request = Body(...), user: AuthUser = Depends(get_current_user)):
    user_email = user.email
    customers = stripe.Customer.list(email=user_email, limit=1)
    quantity = int(request.get("quantity", 1))
    return_url = settings.STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}"
    params = {
        "ui_mode": "embedded",
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
        
        price_id = PRODUCT_PRICE_CATALOG[product_type]['price_id']
        
        if product_type == ProductNameEnum.SINGLE.value:
            # Single product (one-time payment)
            params["mode"] = 'payment'
            return_url += '?type=purchase'

            if quantity > 1:
                # Use price_data to set custom description for multiple items
                params["line_items"] = [{
                    "price": price_id,
                    "quantity": quantity,
                }]
            else:
                # Use existing price for single item
                params["line_items"] = [{
                    "price": price_id,
                    "quantity": 1
                }]
        else:
            # Subscription product
            return_url += '?type=subscription'
            params["mode"] = 'subscription'
            params["line_items"] = [{
                "price": price_id,
                "quantity": 1
            }]
        params["return_url"] = return_url
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
                # Update catalog entry with Stripe data
                catalog_entry['price'] = stripe_price
        
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
        async for db_session in get_db_session():
            payment_service = PaymentService(db_session)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event['type']
    data = event['data']
    data_object = data['object']
    
    #First time purchase
    if event_type == 'checkout.session.completed':
        await payment_service.handle_purchase(session=data_object, mode=data_object['mode'])
    #Subscription payment
    elif event_type == 'invoice.paid':
        await payment_service.handle_subscription_payment(data_object=data_object)
    #Subscription deleted
    elif event_type == 'customer.subscription.deleted':
        await payment_service.handle_subscription_deleted(data_object=data_object)


    
    return {"status": "success"}

