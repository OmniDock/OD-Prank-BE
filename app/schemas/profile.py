from pydantic import BaseModel, field_validator
from typing import Optional

class CreditResponse(BaseModel):
    prank_credit_amount: int
    call_credit_amount: int
    
    @field_validator('prank_credit_amount', 'call_credit_amount')
    @classmethod
    def ensure_non_negative(cls, v):
        if v < 0:
            raise ValueError('Credit amounts cannot be negative')
        return v 
    
