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

PRODUCT_CATALOG = {
    SubscriptionEnum.WEEKLY.value: {
        'id': SubscriptionEnum.WEEKLY.value,
        'tagline': "For weekly users",
        'price': None,
        'interval': None,
        'features': [
            "3 active scenarios",
            "15 calls per week",
            "basic voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
    },
    SubscriptionEnum.MONTHLY.value: {
        'id': SubscriptionEnum.MONTHLY.value,
        'tagline': "For prankster",
        'price': None,
        'interval': None,
        'features': [
            "5 active scenarios",
            "100 calls per week",
            "access to all voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
    },
    SubscriptionEnum.YEARLY.value: {
        'id': SubscriptionEnum.YEARLY.value,
        'tagline': "For true pranksters",
        'price': None,
        'interval': None,
        'features': [
            "unlimited active scenarios",
            "unlimited calls",
            "access to all voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
    },
}