"""Email/SMS notification dispatcher — growth & comms team."""

import logging
import time

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

TEMPLATES = {
    "welcome": "Welcome to the platform, {name}!",
    "winback": "We miss you, {name} — here's 15% off.",
    "receipt": "Your order {order_id} is confirmed.",
}

# Local quiet hours per region; campaign sends pause inside the window (GRW-55).
QUIET_HOURS = {"NA": (22, 8), "EU": (21, 7), "APAC": (23, 9)}


def _mask_email(email):
    """a***@example.com — enough to investigate, not enough to leak PII."""
    if "@" not in email:
        return "<invalid>"
    local, domain = email.split("@", 1)
    return (local[:1] + "***@" + domain) if local else "***@" + domain


def render_template(template_key, context):
    template = TEMPLATES.get(template_key, "")
    return template.format(**context)


def in_quiet_hours(region, hour):
    start, end = QUIET_HOURS.get(region, (22, 8))
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def normalize_phone(phone):
    digits = "".join(c for c in str(phone) if c.isdigit())
    return "+" + digits if digits else ""


def send_campaign(campaign_id, recipients):
    logger.info(
        "campaign dispatch started: campaign_id=%s recipients=%d",
        campaign_id, len(recipients),
    )

    sent = 0
    for r in recipients:
        if _send_with_retry(campaign_id, r):
            sent += 1

    logger.info(
        "campaign dispatch finished: campaign_id=%s sent=%d failed=%d",
        campaign_id, sent, len(recipients) - sent,
    )
    return sent


def _send_with_retry(campaign_id, recipient):
    masked = _mask_email(recipient["email"])
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _deliver(recipient)
            logger.debug(
                "delivered: campaign_id=%s recipient=%s attempt=%d",
                campaign_id, masked, attempt,
            )
            return True
        except Exception:
            # Per-attempt failures are retry noise; keep them at DEBUG and
            # reserve WARNING for the final give-up.
            logger.debug(
                "delivery attempt failed: campaign_id=%s recipient=%s attempt=%d/%d",
                campaign_id, masked, attempt, MAX_RETRIES, exc_info=True,
            )
            time.sleep(0)  # backoff stub

    logger.warning(
        "delivery abandoned after retries: campaign_id=%s recipient=%s template=%s attempts=%d",
        campaign_id, masked, recipient.get("template"), MAX_RETRIES,
    )
    return False


def _deliver(recipient):
    if "@" not in recipient["email"]:
        raise ValueError("bad email address")
