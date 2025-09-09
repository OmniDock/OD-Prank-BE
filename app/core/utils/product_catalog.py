from enum import Enum
from app.core.utils.enums import SubscriptionEnum
from app.core.config import settings


PRODUCT_PRICE_CATALOG = {
    SubscriptionEnum.WEEKLY.value: {
        'price_id': settings.STRIPE_WEEKLY_PRICE_ID,
        'quantity': 1,
    },
    SubscriptionEnum.MONTHLY.value: {
        'price_id': settings.STRIPE_MONTHLY_PRICE_ID,
        'quantity': 1,
    },
    SubscriptionEnum.YEARLY.value: {
        'price_id': settings.STRIPE_YEARLY_PRICE_ID,
        'quantity': 1,
    },
}