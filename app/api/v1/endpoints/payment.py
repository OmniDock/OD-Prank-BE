from fastapi import APIRouter, HTTPException, Request
from app.core.logging import console_logger
import stripe
import dotenv
import os

router = APIRouter(tags=["payment"])
dotenv.load_dotenv()
STRIPE_RETURN_URL = os.getenv("STRIPE_RETURN_URL")


#need to link to customer
@router.post("/checkout/create-session")
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            ui_mode="embedded",                # <— embedded form
            mode="subscription",               # <— create a subscription
            line_items=[{
                "price": 'price_1S3ZW6I5YzUifOCtWGUGBcCi',
                "quantity": 1
            }],
            # customer=body.customerId,          # optional, if you map users->customers
            return_url=STRIPE_RETURN_URL + "/{CHECKOUT_SESSION_ID}",
            # Optional niceties:
            automatic_tax={"enabled": True},
            allow_promotion_codes=True,
            consent_collection={"terms_of_service": "required"},
        )
        # IMPORTANT: return the client_secret for the client to mount checkout
        return {"client_secret": session["client_secret"], "id": session["id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('checkout/session-status')
def session_status(session_id: str):
  session = stripe.checkout.Session.retrieve(session_id)

  return {"status": session.status, "customer_email": session.customer_details.email}