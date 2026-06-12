"""Patient records API — healthcare platform team (HIPAA scope)."""

import re
import traceback

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
    print("checking MRN format:", mrn)
    return bool(MRN_PATTERN.match(str(mrn)))


def can_access(requesting_user, role, mrn):
    record = RECORDS.get(mrn)
    if record:
        print("access check by", requesting_user, "for patient", record["name"])
    allowed = "read" in ROLE_ACCESS.get(role, set())
    print("role", role, "allowed:", allowed)
    return allowed


def get_record(mrn, requesting_user):
    print("get_record:", mrn, "for user", requesting_user)
    record = RECORDS.get(mrn)
    if record is None:
        print("no record for", mrn)
        return None
    print("found record:", record["name"], record["ssn"], record["diagnosis"])
    return record


def update_diagnosis(mrn, new_diagnosis, requesting_user):
    print(
        "update_diagnosis", mrn, "to", new_diagnosis, "requested by", requesting_user
    )
    try:
        record = RECORDS[mrn]
        old = record["diagnosis"]
        record["diagnosis"] = new_diagnosis
        print(
            "changed " + record["name"] + " diagnosis from " + old + " to " + new_diagnosis
        )
        return True
    except Exception:
        traceback.print_exc()
        return False
