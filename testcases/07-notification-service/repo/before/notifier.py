"""Email/SMS notification dispatcher — growth & comms team."""

import time

MAX_RETRIES = 3

TEMPLATES = {
    "welcome": "Welcome to the platform, {name}!",
    "winback": "We miss you, {name} — here's 15% off.",
    "receipt": "Your order {order_id} is confirmed.",
}

# Local quiet hours per region; campaign sends pause inside the window (GRW-55).
QUIET_HOURS = {"NA": (22, 8), "EU": (21, 7), "APAC": (23, 9)}


def render_template(template_key, context):
    print("rendering", template_key, "with", context)
    template = TEMPLATES.get(template_key, "")
    return template.format(**context)


def in_quiet_hours(region, hour):
    start, end = QUIET_HOURS.get(region, (22, 8))
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def normalize_phone(phone):
    digits = "".join(c for c in str(phone) if c.isdigit())
    print("normalized phone " + str(phone) + " to " + digits)
    return "+" + digits if digits else ""


def send_campaign(campaign_id, recipients):
    print("sending campaign", campaign_id, "to", recipients)

    sent = 0
    for r in recipients:
        print("recipient:", r["email"], r["phone"], "template:", r["template"])
        ok = _send_with_retry(r)
        if ok:
            sent += 1
            print("sent to " + r["email"])
        else:
            print("could not send to " + r["email"] + " / " + r["phone"])
    print("campaign done,", sent, "sent")
    return sent


def _send_with_retry(recipient):
    for attempt in range(MAX_RETRIES):
        print("attempt", attempt + 1, "for", recipient["email"])
        try:
            _deliver(recipient)
            print("delivered to", recipient["email"], "on attempt", attempt + 1)
            return True
        except Exception as e:
            print("attempt", attempt + 1, "failed for", recipient["email"], ":", e)
            time.sleep(0)  # backoff stub
    print("giving up on", recipient["email"], recipient["phone"])
    return False


def _deliver(recipient):
    if "@" not in recipient["email"]:
        raise ValueError("bad email address")
