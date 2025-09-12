from pydantic import BaseModel
from typing import Optional, List

class LineItem(BaseModel):
    price: str
    quantity: int = 1



class CheckoutSessionParams(BaseModel):
    ui_mode: str = "embedded"
    return_url: str
    automatic_tax: dict = {"enabled": True}
    mode: str
    line_items: List[LineItem]
    customer: Optional[str] = None
    customer_email: Optional[str] = None