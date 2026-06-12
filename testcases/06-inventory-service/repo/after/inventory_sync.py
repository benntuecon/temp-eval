"""Warehouse inventory sync — logistics team."""

import logging
import re

logger = logging.getLogger(__name__)

LOCAL_STOCK = {"SKU-1": 10, "SKU-2": 0}

SKU_PATTERN = re.compile(r"^SKU-\d+$")

# Reorder thresholds negotiated with procurement, reviewed quarterly (LOG-118).
REORDER_POINTS = {"SKU-1": 5, "SKU-2": 20}
DEFAULT_REORDER_POINT = 10


def valid_sku(sku):
    return bool(SKU_PATTERN.match(str(sku)))


def needs_reorder(sku):
    point = REORDER_POINTS.get(sku, DEFAULT_REORDER_POINT)
    return LOCAL_STOCK.get(sku, 0) < point


def reorder_report():
    report = [sku for sku in LOCAL_STOCK if needs_reorder(sku)]
    if report:
        logger.info("reorder needed: skus=%d", len(report))
    return report


def sync_warehouse(warehouse_id, remote_counts):
    logger.info(
        "warehouse sync started: warehouse_id=%s skus=%d",
        warehouse_id, len(remote_counts),
    )

    updated = 0
    unknown = 0
    for sku, remote_qty in remote_counts.items():
        try:
            local_qty = LOCAL_STOCK[sku]
        except KeyError:
            unknown += 1
            logger.warning(
                "unknown SKU skipped: warehouse_id=%s sku=%s remote_qty=%d",
                warehouse_id, sku, remote_qty,
            )
            continue

        if local_qty != remote_qty:
            LOCAL_STOCK[sku] = remote_qty
            updated += 1
            logger.debug(
                "stock corrected: warehouse_id=%s sku=%s local=%d remote=%d",
                warehouse_id, sku, local_qty, remote_qty,
            )

    logger.info(
        "warehouse sync finished: warehouse_id=%s updated=%d unknown=%d",
        warehouse_id, updated, unknown,
    )
    return updated


def reserve_stock(sku, qty, order_id):
    available = LOCAL_STOCK.get(sku, 0)
    if available < qty:
        logger.warning(
            "reservation rejected, insufficient stock: order_id=%s sku=%s requested=%d available=%d",
            order_id, sku, qty, available,
        )
        return False

    LOCAL_STOCK[sku] -= qty
    logger.info("stock reserved: order_id=%s sku=%s qty=%d", order_id, sku, qty)
    return True
