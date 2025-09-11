from enum import Enum
from app.core.utils.enums import ProductNameEnum
from app.core.config import settings


PRODUCT_PRICE_CATALOG = {
    ProductNameEnum.WEEKLY.value: {
        'price_id': settings.STRIPE_WEEKLY_PRICE_ID,
        'quantity': 1,
    },
    ProductNameEnum.MONTHLY.value: {
        'price_id': settings.STRIPE_MONTHLY_PRICE_ID,
        'quantity': 1,
    },
    ProductNameEnum.SINGLE.value: {
        'price_id': settings.STRIPE_SINGLE_PRICE_ID,
        'quantity': 1,
    },
}

PRODUCT_CATALOG = {
    ProductNameEnum.SINGLE.value: {
        'stripe_product_id': settings.STRIPE_SINGLE_PRODUCT_ID,
        'tagline': "Ein Prank",
        'price': None,
        'interval': None,
        'features': [
            "Ein Prank Call",
        ],
        'ctaLabel': "Jetzt Kaufen",
        'ctaHref': "",
    },
    ProductNameEnum.WEEKLY.value: {
        'stripe_product_id': settings.STRIPE_WEEKLY_PRODUCT_ID,
        'tagline': "For weekly users",
        'price': None,
        'interval': None,
        'prank_amount': 5,
        'features': [
            "3 active scenarios",
            "15 calls per week",
            "basic voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
    },
    ProductNameEnum.MONTHLY.value: {
        'stripe_product_id': settings.STRIPE_MONTHLY_PRODUCT_ID,
        'tagline': "For prankster",
        'price': None,
        'interval': None,
        'prank_amount': 35,
        'features': [
            "5 active scenarios",
            "100 calls per week",
            "access to all voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
    },
}