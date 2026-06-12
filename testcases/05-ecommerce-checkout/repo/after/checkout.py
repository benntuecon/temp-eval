"""Checkout flow — retail storefront team.

Logging configuration belongs to the application entrypoint, not this
library module.
"""

import logging

logger = logging.getLogger(__name__)

# Nexus states only; the tax service owns the full table (TAX-310).
TAX_RATES = {"CA": 0.0725, "NY": 0.04, "TX": 0.0625, "WA": 0.065}

SHIPPING_TIERS = (
    (0, 4_999, 799),
    (5_000, 9_999, 499),
    (10_000, None, 0),  # free shipping over $100
)

ACTIVE_COUPONS = {"SAVE10": 10, "VIP20": 20}


class OutOfStockError(Exception):
    pass


def estimate_tax_cents(subtotal_cents, state):
    return int(subtotal_cents * TAX_RATES.get(state, 0.0))


def estimate_shipping_cents(subtotal_cents):
    for low, high, cost in SHIPPING_TIERS:
        if high is None or low <= subtotal_cents <= high:
            return cost
    return SHIPPING_TIERS[0][2]


def apply_coupon(total_cents, code):
    pct = ACTIVE_COUPONS.get(code)
    if pct is None:
        logger.warning("coupon rejected, unknown code: code=%s", code)
        return total_cents
    return total_cents * (100 - pct) // 100


def place_order(cart, customer_id):
    logger.info("checkout started: customer_id=%s items=%d", customer_id, len(cart))

    total = 0
    for item in cart:
        if item["qty"] > item["stock"]:
            # Log-or-raise: the exception carries the SKU, the API layer
            # that handles it owns the ERROR log. One failure, one record.
            raise OutOfStockError(item["sku"])
        total += item["price_cents"] * item["qty"]

    logger.debug(
        "cart priced: customer_id=%s items=%d total_cents=%d",
        customer_id, len(cart), total,
    )

    order_id = _reserve_inventory(cart)

    logger.info(
        "order placed: order_id=%s customer_id=%s total_cents=%d",
        order_id, customer_id, total,
    )
    return {"order_id": order_id, "total_cents": total}


def _reserve_inventory(cart):
    if any(i["qty"] <= 0 for i in cart):
        raise ValueError("non-positive quantity in cart")
    return "ord-" + str(sum(i["qty"] for i in cart))
