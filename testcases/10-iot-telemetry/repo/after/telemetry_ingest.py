"""Device telemetry ingestor — IoT platform team."""

import json
import logging

logger = logging.getLogger(__name__)

DEVICE_KEYS = {"dev-42": "secret-api-key-9f8e7d"}
READINGS = []

TEMP_MIN_C = -50
TEMP_MAX_C = 150

# Fleet firmware floor; older builds emit the v1 packet shape (IOT-203).
FIRMWARE_MIN = (2, 4, 0)

DOWNSAMPLE_KEEP_EVERY = 10  # archive tier keeps 1-in-10 readings


def parse_firmware(version_str):
    try:
        return tuple(int(p) for p in version_str.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def firmware_supported(version_str):
    return parse_firmware(version_str) >= FIRMWARE_MIN


def downsample(readings, keep_every=DOWNSAMPLE_KEEP_EVERY):
    return [r for i, r in enumerate(readings) if i % keep_every == 0]


def ingest_batch(device_id, api_key, payload_lines):
    # API keys are credentials — they never appear in logs, valid or not.
    if DEVICE_KEYS.get(device_id) != api_key:
        logger.warning("ingest auth failed: device_id=%s", device_id)
        return 0

    accepted = 0
    malformed = 0
    out_of_range = 0
    for line in payload_lines:
        try:
            reading = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            logger.debug(
                "malformed packet dropped: device_id=%s bytes=%d", device_id, len(line)
            )
            continue

        temp = reading.get("temp_c")
        if temp is not None and TEMP_MIN_C <= temp <= TEMP_MAX_C:
            READINGS.append((device_id, reading))
            accepted += 1
        else:
            out_of_range += 1
            logger.debug(
                "reading out of range: device_id=%s temp_c=%s", device_id, temp
            )

    if malformed or out_of_range:
        # One WARNING per batch, not per packet — a chatty device cannot
        # flood the log.
        logger.warning(
            "batch had dropped readings: device_id=%s malformed=%d out_of_range=%d",
            device_id, malformed, out_of_range,
        )

    logger.info(
        "batch ingested: device_id=%s received=%d accepted=%d",
        device_id, len(payload_lines), accepted,
    )
    return accepted
