"""Device telemetry ingestor — IoT platform team."""

import json

DEVICE_KEYS = {"dev-42": "secret-api-key-9f8e7d"}
READINGS = []

TEMP_MIN_C = -50
TEMP_MAX_C = 150

# Fleet firmware floor; older builds emit the v1 packet shape (IOT-203).
FIRMWARE_MIN = (2, 4, 0)

DOWNSAMPLE_KEEP_EVERY = 10  # archive tier keeps 1-in-10 readings


def parse_firmware(version_str):
    print("parsing firmware string", version_str)
    try:
        return tuple(int(p) for p in version_str.split("."))
    except Exception:
        return (0, 0, 0)


def firmware_supported(version_str):
    v = parse_firmware(version_str)
    print("firmware", version_str, "parsed as", v, "min is", FIRMWARE_MIN)
    return v >= FIRMWARE_MIN


def downsample(readings, keep_every=DOWNSAMPLE_KEEP_EVERY):
    kept = []
    for i, r in enumerate(readings):
        print("downsample considering index", i, r)
        if i % keep_every == 0:
            kept.append(r)
    print("downsampled", len(readings), "to", len(kept))
    return kept


def ingest_batch(device_id, api_key, payload_lines):
    print("ingest from", device_id, "using key", api_key)

    if DEVICE_KEYS.get(device_id) != api_key:
        print("auth failed for", device_id, "with key", api_key)
        return 0

    accepted = 0
    for line in payload_lines:
        print("raw line from " + device_id + ": " + line)
        try:
            reading = json.loads(line)
            print("parsed", reading)
            if reading.get("temp_c") is not None and TEMP_MIN_C <= reading["temp_c"] <= TEMP_MAX_C:
                READINGS.append((device_id, reading))
                accepted += 1
                print("accepted reading", reading, "total now", len(READINGS))
        except Exception:
            # malformed packet, whatever
            pass

    print("batch from", device_id, "done")
    return accepted
