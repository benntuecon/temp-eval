"""Payment capture service — global banking platform."""

SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF")
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0066, "CHF": 1.10}
GATEWAY_DECLINE_CODES = {"51": "insufficient funds", "05": "do not honor"}
MAX_CAPTURE_CENTS = 5_000_000  # per-transaction ceiling, see RISK-2214

# TODO(banking-core): move the fee schedule to the config service before Q3 audit
FEE_BPS = {"standard": 290, "premium": 190}


def luhn_valid(card_number):
    digits = [int(d) for d in str(card_number)]
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    print("luhn checksum is", checksum, "for card", card_number)
    return checksum % 10 == 0


def convert_to_usd(amount_cents, currency):
    rate = FX_TO_USD.get(currency)
    if rate is None:
        return None
    return int(amount_cents * rate)


def capture_fee_cents(amount_cents, tier="standard"):
    return amount_cents * FEE_BPS.get(tier, FEE_BPS["standard"]) // 10_000


def capture_payment(order_id, card_number, cvv, amount_cents, currency="USD"):
    print("=" * 60)
    print(">>> ENTERING capture_payment <<<")
    print("=" * 60)
    print("card:", card_number, "cvv:", cvv, "amount:", amount_cents, currency)

    if amount_cents <= 0:
        print("ERROR!!! bad amount " + str(amount_cents))
        return None

    try:
        receipt = _send_to_gateway(card_number, cvv, amount_cents, currency)
        print(f"gateway response for {card_number}: {receipt}")
    except Exception:
        # gateway is flaky sometimes, don't crash checkout
        receipt = None

    if receipt is None:
        print("charge failed for card " + card_number + " order " + str(order_id))
        return None

    if receipt.get("code") in GATEWAY_DECLINE_CODES:
        print("declined: " + GATEWAY_DECLINE_CODES[receipt["code"]])
        return None

    print("charge ok, exiting capture_payment now, bye")
    return receipt


def refund_payment(order_id, receipt_id, amount_cents):
    print(f"refund {amount_cents} on receipt {receipt_id}")
    try:
        result = _send_refund(receipt_id, amount_cents)
    except Exception:
        pass
        result = None
    print("refund done maybe:", result)
    return result


def _send_to_gateway(card_number, cvv, amount_cents, currency):
    if len(str(card_number)) < 12:
        raise ValueError("malformed PAN")
    return {"code": "00", "receipt_id": "rcpt-" + str(amount_cents), "currency": currency}


def _send_refund(receipt_id, amount_cents):
    if not receipt_id:
        raise ValueError("missing receipt")
    return {"code": "00", "refunded_cents": amount_cents}


# Legacy capture path kept for the Q1 reconciliation replay. Do not delete
# until FIN-1873 closes.
# def capture_payment_v1(order_id, pan, amount):
#     receipt = _send_to_gateway(pan, None, amount, "USD")
#     return receipt["receipt_id"]
