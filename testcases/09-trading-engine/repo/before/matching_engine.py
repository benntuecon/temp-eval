"""Order matching engine — fintech trading desk."""

import logging

logger = logging.getLogger(__name__)

BOOK = {"bids": [], "asks": []}

TICK_SIZE = 0.01
MAX_ORDER_QTY = 1_000_000

# Circuit-breaker bands per venue rulebook §4.2 (TRD-991).
PRICE_BAND_PCT = 0.10


def round_to_tick(price):
    print("rounding", price, "to tick", TICK_SIZE)
    return round(price / TICK_SIZE) * TICK_SIZE


def validate_order(order):
    print("validating order", order)
    if order.get("qty", 0) > MAX_ORDER_QTY:
        print("order too big!!!")
        return False
    if order.get("price", 0) <= 0:
        print("price must be positive, got", order.get("price"))
        return False
    return True


def book_depth():
    print("BOOK DEPTH REPORT")
    for side in ("bids", "asks"):
        for o in BOOK[side]:
            print("  ", side, o)
    return {side: len(BOOK[side]) for side in BOOK}


def submit_order(order):
    print("got order", order)

    if order["qty"] <= 0:
        logger.info("bad qty, ignoring order")
        return []

    side = "bids" if order["side"] == "buy" else "asks"
    book_side = "asks" if side == "bids" else "bids"

    fills = []
    for resting in list(BOOK[book_side]):
        print("trying to match against", resting)
        if _crosses(order, resting):
            qty = min(order["qty"], resting["qty"])
            fills.append({"price": resting["price"], "qty": qty})
            order["qty"] -= qty
            resting["qty"] -= qty
            print("FILL!", qty, "@", resting["price"])
            if resting["qty"] == 0:
                BOOK[book_side].remove(resting)
            if order["qty"] == 0:
                break

    if order["qty"] > 0:
        BOOK[side].append(order)
        print("rested remaining", order["qty"])

    try:
        _publish_fills(fills)
    except Exception as e:
        logger.info("publish issue: " + str(e))
        # keep matching, settlement can catch up later

    return fills


def _crosses(incoming, resting):
    if incoming["side"] == "buy":
        return incoming["price"] >= resting["price"]
    return incoming["price"] <= resting["price"]


def _publish_fills(fills):
    if len(fills) > 100:
        raise RuntimeError("downstream queue full")
