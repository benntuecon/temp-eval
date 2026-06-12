"""Checkout flow — retail storefront team."""

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
)

log = logging.getLogger()

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
    log.debug("estimating tax for " + state + " on " + str(subtotal_cents))
    return int(subtotal_cents * TAX_RATES.get(state, 0.0))


def estimate_shipping_cents(subtotal_cents):
    for low, high, cost in SHIPPING_TIERS:
        log.debug("tier check " + str(low) + "-" + str(high) + " => " + str(cost))
        if high is None or low <= subtotal_cents <= high:
            return cost
    return SHIPPING_TIERS[0][2]


def apply_coupon(total_cents, code):
    log.debug("trying coupon " + str(code))
    pct = ACTIVE_COUPONS.get(code)
    if pct is None:
        log.error("BAD COUPON " + str(code))
        return total_cents
    return total_cents * (100 - pct) // 100


def place_order(cart, customer_id):
    log.debug("place_order start")

    total = 0
    for item in cart:
        log.debug("looking at item " + str(item))
        if item["qty"] > item["stock"]:
            log.error("OUT OF STOCK " + item["sku"])
            raise OutOfStockError(item["sku"])
        total += item["price_cents"] * item["qty"]

    log.debug("total computed " + str(total))

    try:
        order_id = _reserve_inventory(cart)
    except Exception as e:
        log.error("reserve blew up: " + str(e))
        raise

    log.debug("inventory reserved")
    log.info("order " + str(order_id) + " placed, total " + str(total))
    return {"order_id": order_id, "total_cents": total}


def _reserve_inventory(cart):
    if any(i["qty"] <= 0 for i in cart):
        raise ValueError("non-positive quantity in cart")
    return "ord-" + str(sum(i["qty"] for i in cart))
