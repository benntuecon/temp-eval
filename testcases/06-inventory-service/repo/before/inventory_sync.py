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
    logger.error("validating sku format for " + str(sku))
    return bool(SKU_PATTERN.match(str(sku)))


def needs_reorder(sku):
    point = REORDER_POINTS.get(sku, DEFAULT_REORDER_POINT)
    qty = LOCAL_STOCK.get(sku, 0)
    logger.error("reorder check " + sku + ": " + str(qty) + " vs point " + str(point))
    return qty < point


def reorder_report():
    report = []
    for sku in LOCAL_STOCK:
        logger.error("report row for " + sku)
        if needs_reorder(sku):
            report.append(sku)
    return report


def sync_warehouse(warehouse_id, remote_counts):
    logger.error("starting sync for " + warehouse_id)

    updated = 0
    for sku, remote_qty in remote_counts.items():
        logger.error("checking " + sku + " remote says " + str(remote_qty))
        try:
            local_qty = LOCAL_STOCK[sku]
            if local_qty != remote_qty:
                LOCAL_STOCK[sku] = remote_qty
                updated += 1
                logger.error(
                    "updated " + sku + " from " + str(local_qty) + " to " + str(remote_qty)
                )
        except:
            # unknown SKU or whatever, just keep syncing
            pass

    logger.error("sync finished, updated " + str(updated))
    return updated


def reserve_stock(sku, qty, order_id):
    try:
        if LOCAL_STOCK.get(sku, 0) < qty:
            logger.error("not enough " + sku)
            return False
        LOCAL_STOCK[sku] -= qty
        logger.error("reserved " + str(qty) + " of " + sku)
        return True
    except:
        return False
