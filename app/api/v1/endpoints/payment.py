from fastapi import APIRouter, HTTPException, Request, Depends
from app.core.logging import console_logger
from app.core.config import settings
from app.core.auth import get_current_user, AuthUser
import stripe

# Initialize Stripe with the secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payment"])


#need to link to customer
@router.post("/checkout/create-session")
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            ui_mode="embedded",                # <— embedded form
            mode="subscription",               # <— create a subscription
            line_items=[{
                "price": settings.STRIPE_WEEKLY_PRICE_ID,
                "quantity": 1
            }],
            # customer=body.customerId,          # optional, if you map users->customers
            return_url=settings.STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}",
            # Optional niceties:
            automatic_tax={"enabled": True},
            allow_promotion_codes=True,
            # consent_collection={"terms_of_service": "required"},
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