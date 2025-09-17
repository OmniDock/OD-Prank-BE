from enum import Enum
from app.core.utils.enums import ProductNameEnum, ProductTypes
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
        'stripe_price_id': settings.STRIPE_SINGLE_PRICE_ID,
        'tagline': None,
        'price': None,
        'interval': 'Prank',
        'prank_amount': 1,
        'call_amount': 1,
        'features': [
            "Ein Prank Call",
        ],
        'ctaLabel': "Jetzt Kaufen",
        'ctaHref': "",
        'type': ProductTypes.ONE_TIME.value,
        'display_name': "Einzelne Pranks",
    },
    ProductNameEnum.WEEKLY.value: {
        'stripe_product_id': settings.STRIPE_WEEKLY_PRODUCT_ID,
        'stripe_price_id': settings.STRIPE_WEEKLY_PRICE_ID,
        'tagline': None,
        'price': None,
        'interval': 'Woche',
        'prank_amount': 5,
        'call_amount': 5,
        'features': [
            "3 active scenarios",
            "15 calls per week",
            "basic voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
        'type': ProductTypes.SUBSCRIPTION.value,
        'display_name': "Wöchentliches Abo",
    },
    ProductNameEnum.MONTHLY.value: {
        'stripe_product_id': settings.STRIPE_MONTHLY_PRODUCT_ID,
        'stripe_price_id': settings.STRIPE_MONTHLY_PRICE_ID,
        'tagline': None,
        'price': None,
        'interval': 'Monat',
        'prank_amount': 35,
        'call_amount': 40,
        'features': [
            "5 active scenarios",
            "100 calls per week",
            "access to all voices"
        ],
        'ctaLabel': "Get Started",
        'ctaHref': "",
        'type': ProductTypes.SUBSCRIPTION.value,
        'display_name': "Monatliches Abo",
    },
}




def get_product_name_by_product_id(stripe_product_id: str) -> str:
    for product_name, product_info in PRODUCT_CATALOG.items():
        if product_info['stripe_product_id'] == stripe_product_id:
            return product_name
    return 'unknown'

def get_product_name_by_price_id(stripe_price_id: str) -> str:
    for product_name, product_info in PRODUCT_CATALOG.items():
        if product_info['stripe_price_id'] == stripe_price_id:
            return product_name
    return 'unknown'
