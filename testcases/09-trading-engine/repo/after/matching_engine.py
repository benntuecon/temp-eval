"""Order matching engine — fintech trading desk."""

import logging

logger = logging.getLogger(__name__)

BOOK = {"bids": [], "asks": []}

TICK_SIZE = 0.01
MAX_ORDER_QTY = 1_000_000

# Circuit-breaker bands per venue rulebook §4.2 (TRD-991).
PRICE_BAND_PCT = 0.10


def round_to_tick(price):
    return round(price / TICK_SIZE) * TICK_SIZE


def validate_order(order):
    if order.get("qty", 0) > MAX_ORDER_QTY:
        logger.warning(
            "order rejected, qty above limit: order_id=%s qty=%d max=%d",
            order.get("order_id"), order["qty"], MAX_ORDER_QTY,
        )
        return False
    if order.get("price", 0) <= 0:
        logger.warning(
            "order rejected, non-positive price: order_id=%s price=%s",
            order.get("order_id"), order.get("price"),
        )
        return False
    return True


def book_depth():
    depth = {side: len(BOOK[side]) for side in BOOK}
    logger.debug("book depth: bids=%d asks=%d", depth["bids"], depth["asks"])
    return depth


def submit_order(order):
    order_id = order.get("order_id")

    if order["qty"] <= 0:
        logger.warning(
            "order rejected, non-positive qty: order_id=%s qty=%d", order_id, order["qty"]
        )
        return []

    side = "bids" if order["side"] == "buy" else "asks"
    book_side = "asks" if side == "bids" else "bids"

    fills = []
    filled_qty = 0
    for resting in list(BOOK[book_side]):
        if _crosses(order, resting):
            qty = min(order["qty"], resting["qty"])
            fills.append({"price": resting["price"], "qty": qty})
            filled_qty += qty
            order["qty"] -= qty
            resting["qty"] -= qty
            # Hot path: per-fill detail stays at DEBUG, lazily formatted.
            logger.debug(
                "fill: order_id=%s against=%s qty=%d price=%s",
                order_id, resting.get("order_id"), qty, resting["price"],
            )
            if resting["qty"] == 0:
                BOOK[book_side].remove(resting)
            if order["qty"] == 0:
                break

    if order["qty"] > 0:
        BOOK[side].append(order)

    logger.info(
        "order processed: order_id=%s side=%s fills=%d filled_qty=%d rested_qty=%d",
        order_id, order["side"], len(fills), filled_qty, order["qty"],
    )

    try:
        _publish_fills(fills)
    except Exception:
        # Settlement now lags the book — on-call must act, hence ERROR.
        logger.exception(
            "fill publication failed: order_id=%s unpublished_fills=%d",
            order_id, len(fills),
        )

    return fills


def _crosses(incoming, resting):
    if incoming["side"] == "buy":
        return incoming["price"] >= resting["price"]
    return incoming["price"] <= resting["price"]


def _publish_fills(fills):
    if len(fills) > 100:
        raise RuntimeError("downstream queue full")
