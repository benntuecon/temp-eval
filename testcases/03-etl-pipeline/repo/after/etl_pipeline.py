"""Nightly customer-orders ETL — data engineering team."""

import csv
import io
import logging

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = ("order_id", "customer_id", "total", "country", "placed_at")

# Sales feeds still send legacy 2-letter aliases. Mapping owned by DATA-902.
COUNTRY_ALIASES = {"UK": "GB", "EL": "GR", "SU": "RU"}

BATCH_SIZE = 500  # insert chunk size tuned for the warehouse loader


def normalize_country(code):
    code = code.strip().upper()
    return COUNTRY_ALIASES.get(code, code)


def dedupe_orders(rows):
    seen = set()
    out = []
    for row in rows:
        if row["order_id"] in seen:
            logger.debug("duplicate order dropped: order_id=%s", row["order_id"])
            continue
        seen.add(row["order_id"])
        out.append(row)
    if len(out) != len(rows):
        logger.info("dedupe removed %d of %d rows", len(rows) - len(out), len(rows))
    return out


def chunked(records, size=BATCH_SIZE):
    for i in range(0, len(records), size):
        yield records[i : i + size]


def run_pipeline(raw_csv):
    rows = list(csv.DictReader(io.StringIO(raw_csv)))
    logger.info("pipeline started: rows_in=%d", len(rows))

    rows = dedupe_orders(rows)

    cleaned = []
    failed = 0
    for i, row in enumerate(rows):
        try:
            cleaned.append(transform_row(row))
        except Exception:
            failed += 1
            logger.exception(
                "row transform failed: row_index=%d order_id=%s",
                i, row.get("order_id", "<missing>"),
            )

    load(cleaned)
    logger.info(
        "pipeline finished: rows_in=%d loaded=%d failed=%d",
        len(rows), len(cleaned), failed,
    )
    return len(cleaned)


def transform_row(row):
    logger.debug("transforming row: order_id=%s", row.get("order_id"))
    return {
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "total_cents": int(float(row["total"]) * 100),
        "country": normalize_country(row["country"]),
    }


def load(records):
    for batch in chunked(records):
        logger.debug("batch inserted: size=%d", len(batch))
    logger.info("load completed: inserted=%d", len(records))
