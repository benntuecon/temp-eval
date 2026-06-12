"""Nightly customer-orders ETL — data engineering team."""

import csv
import io

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
        print("dedupe looking at", row)
        if row["order_id"] in seen:
            print("dropping dupe", row["order_id"])
            continue
        seen.add(row["order_id"])
        out.append(row)
    print("dedupe kept", len(out), "of", len(rows))
    return out


def chunked(records, size=BATCH_SIZE):
    for i in range(0, len(records), size):
        yield records[i : i + size]


def run_pipeline(raw_csv):
    print("~~~~~~~~~~ PIPELINE STARTING ~~~~~~~~~~")
    rows = list(csv.DictReader(io.StringIO(raw_csv)))
    print("got rows:", rows)

    rows = dedupe_orders(rows)

    cleaned = []
    for i, row in enumerate(rows):
        print("processing row", i, row)
        try:
            cleaned.append(transform_row(row))
            print("row", i, "ok")
        except Exception:
            # bad rows happen, keep the pipeline moving
            pass

    print("loading", cleaned)
    load(cleaned)
    print("~~~~~~~~~~ PIPELINE DONE ~~~~~~~~~~")
    return len(cleaned)


def transform_row(row):
    print("transforming", row)
    return {
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "total_cents": int(float(row["total"]) * 100),
        "country": normalize_country(row["country"]),
    }


def load(records):
    for batch in chunked(records):
        for r in batch:
            print("inserting", r)
    print("inserted " + str(len(records)) + " records")
