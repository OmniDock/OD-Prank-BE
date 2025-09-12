from pydantic import BaseModel, field_validator
from typing import Optional

class Credits(BaseModel):
    prank_credit_amount: int
    call_credit_amount: int 
    
