import hashlib
import hmac
import json

from app.config import app_settings
from app.enums.paystack import PAYSTACK_METADATA_CONDITION

_CHARGE_SUCCESS_EXAMPLE = {
    "event": "charge.success",
    "data": {
        "id": 6500307117,
        "domain": "test",
        "status": "success",
        "reference": "Bc1a046ffcec5",
        "amount": 5000,
        "message": None,
        "gateway_response": "Successful",
        "gateway_response_code": "approved",
        "response_code": "00",
        "paid_at": "2026-08-28T06:13:17.000Z",
        "created_at": "2026-08-28T06:12:46.000Z",
        "channel": "card",
        "currency": "NGN",
        "ip_address": "102.204.77.82",
        "metadata": {
            "webhook_condition": PAYSTACK_METADATA_CONDITION.CARD_APPROVED.value,
            "extra_data": {
                "user_id": "5dfdfb3d-504b-4688-8d2e-8ef8afc3e2b1",
                "chat_id": "08119995541",
            },
        },
        "fees_breakdown": None,
        "log": None,
        "fees": 75,
        "fees_split": None,
        "authorization": {
            "authorization_code": "AUTH_4rh770k9om",
            "bin": "408408",
            "last4": "4081",
            "exp_month": "12",
            "exp_year": "2030",
            "channel": "card",
            "card_type": "visa ",
            "bank": "TEST BANK",
            "country_code": "NG",
            "brand": "visa",
            "reusable": True,
            "signature": "SIG_KGcumQ2THYWT6nePq4tz",
            "account_name": None,
            "receiver_bank_account_number": None,
            "receiver_bank": None,
        },
        "customer": {
            "id": 394497576,
            "first_name": None,
            "last_name": None,
            "email": "abimbolaolayemiwhyte@gmail.com",
            "customer_code": "CUS_z8m71o32dcrn0fe",
            "phone": None,
            "metadata": None,
            "risk_action": "default",
            "international_format_phone": None,
        },
        "plan": {},
        "subaccount": {},
        "split": {},
        "order_id": None,
        "paidAt": "2026-08-28T06:13:17.000Z",
        "requested_amount": 5000,
        "pos_transaction_data": None,
        "source": {
            "type": "api",
            "source": "merchant_api",
            "entry_point": "transaction_initialize",
            "identifier": None,
        },
    },
}
# Pre-compute so Swagger pre-fills the matching signature for the example body above.
_EXAMPLE_BODY_BYTES = json.dumps(
    _CHARGE_SUCCESS_EXAMPLE, separators=(",", ":")
).encode()

_EXAMPLE_SIGNATURE = hmac.new(
    app_settings.PAYSTACK_SECRET_KEY.encode(),
    _EXAMPLE_BODY_BYTES,
    hashlib.sha512,
).hexdigest()

WEBHOOK_OPENAPI_EXTRA: dict = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "authorization": {
                                    "type": "object",
                                    "properties": {
                                        "authorization_code": {"type": "string"},
                                        "reusable": {"type": "boolean"},
                                        "last4": {"type": "string"},
                                        "card_type": {"type": "string"},
                                        "bank": {"type": "string"},
                                    },
                                },
                                "customer": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"},
                                        "customer_code": {"type": "string"},
                                    },
                                },
                                "metadata": {
                                    "type": "object",
                                    "properties": {"chat_id": {"type": "string"}},
                                },
                            },
                        },
                    },
                },
                "example": _CHARGE_SUCCESS_EXAMPLE,
            }
        },
    },
}
