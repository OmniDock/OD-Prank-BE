from fastapi import APIRouter, HTTPException, Request, Depends
from app.core.logging import console_logger
from app.core.config import settings
from app.core.auth import get_current_user, AuthUser
import stripe
from app.core.utils.product_catalog import PRODUCT_PRICE_CATALOG, PRODUCT_CATALOG
# Initialize Stripe with the secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payment"])


#need to link to customer
@router.post("/checkout/create-session")
def create_checkout_session(request: dict):
    sub_type = request.get("subscription_type")
    print(sub_type)
    print(PRODUCT_PRICE_CATALOG[sub_type])
    try:
        sub_type = request.get("subscription_type")
        price_id = PRODUCT_PRICE_CATALOG[sub_type]['price_id']
        quantity = PRODUCT_PRICE_CATALOG[sub_type]['quantity']
        session = stripe.checkout.Session.create(
            ui_mode="embedded",                # <— embedded form
            mode="subscription",               # <— create a subscription
            line_items=[{
                "price": price_id,
                "quantity": quantity
            }],
            # customer=body.customerId,          # optional, if you map users->customers
            return_url=settings.STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}",
            # Optional niceties:
            automatic_tax={"enabled": True},
            allow_promotion_codes=True,
            # consent_collection={"terms_of_service": "required"}
        )
        # IMPORTANT: return the client_secret for the client to mount checkout
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
        
        # Query Stripe for each product using the stripe_product_id from catalog
        for catalog_key, catalog_entry in updated_catalog.items():
            stripe_product_id = catalog_entry['stripe_product_id']
            
            # Get product from Stripe
            product = stripe.Product.retrieve(stripe_product_id)
            
            # Get all prices for this product
            prices = stripe.Price.list(product=product.id, active=True)
            
            # Format price information
            price_list = []
            stripe_price = None
            stripe_interval = None
            
            for price in prices.data:
                price_info = {
                    "unit_amount": price.unit_amount,
                    "currency": price.currency,
                    "recurring": {
                        "interval": price.recurring.interval if price.recurring else None,
                        "interval_count": price.recurring.interval_count if price.recurring else None
                    } if price.recurring else None,
                    "type": price.type,
                    "nickname": price.nickname
                }
                price_list.append(price_info)
                
                # Store the first price for catalog update
                if stripe_price is None:
                    stripe_price = price.unit_amount / 100  # Convert from cents
                    stripe_interval = price.recurring.interval if price.recurring else None
            
            # Update catalog entry with Stripe data
            catalog_entry['price'] = stripe_price
            catalog_entry['interval'] = stripe_interval
        
        # Convert catalog to list of dictionaries, excluding stripe_product_id and id
        products_list = []
        for catalog_key, catalog_entry in updated_catalog.items():
            # Create a copy without stripe_product_id and id, then add catalog_key as id
            filtered_entry = {'id' : catalog_key}
            filtered_entry.update({k: v for k, v in catalog_entry.items() if k not in ['stripe_product_id', 'id']})
            products_list.append(filtered_entry)
        return {"products": products_list}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))