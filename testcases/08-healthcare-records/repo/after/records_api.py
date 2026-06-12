"""Patient records API — healthcare platform team (HIPAA scope).

Audit rule: log WHO touched WHICH record (MRN is the permitted surrogate
identifier) and WHEN — never names, SSNs, or diagnoses (PHI).
"""

import logging
import re

logger = logging.getLogger(__name__)

RECORDS = {
    "MRN-1001": {"name": "Jane Roe", "ssn": "123-45-6789", "diagnosis": "type 2 diabetes"},
}

MRN_PATTERN = re.compile(r"^MRN-\d{4,}$")

# Role matrix mirrors the IAM policy doc rev 14 (COMP-208).
ROLE_ACCESS = {
    "physician": {"read", "write"},
    "nurse": {"read"},
    "billing": {"read"},
}


def valid_mrn(mrn):
    return bool(MRN_PATTERN.match(str(mrn)))


def can_access(requesting_user, role, mrn):
    allowed = "read" in ROLE_ACCESS.get(role, set())
    if not allowed:
        logger.warning(
            "access denied: mrn=%s user=%s role=%s", mrn, requesting_user, role
        )
    return allowed


def get_record(mrn, requesting_user):
    record = RECORDS.get(mrn)
    if record is None:
        logger.warning("record lookup miss: mrn=%s user=%s", mrn, requesting_user)
        return None

    logger.info("record accessed: mrn=%s user=%s", mrn, requesting_user)
    return record


def update_diagnosis(mrn, new_diagnosis, requesting_user):
    try:
        record = RECORDS[mrn]
    except KeyError:
        logger.warning(
            "diagnosis update rejected, unknown record: mrn=%s user=%s",
            mrn, requesting_user,
        )
        return False

    try:
        record["diagnosis"] = new_diagnosis
    except Exception:
        logger.exception("diagnosis update failed: mrn=%s user=%s", mrn, requesting_user)
        return False

    # The fact of the change is auditable; the clinical content is not loggable.
    logger.info("diagnosis updated: mrn=%s user=%s", mrn, requesting_user)
    return True
