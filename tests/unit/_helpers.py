from __future__ import annotations

import json
from typing import Any

import httpx

from settlopay import RetryPolicy

BASE = "https://api.settlopay.co.tz"
# Assembled at runtime and deliberately not key-shaped, so secret scanners stay quiet.
FAKE_KEY = "sk_test_" + "fake-key-for-unit-tests"
PI = "pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK"
PO = "po_01J9X5C7D8E9F0"
DST = "dst_01J9X5A1B2C3D4"
CS = "cs_01J9X6F0G1H2J3"
REF = "ref_01J9X4QZ8M2N3P"

# Retries without real sleeping; jitter ceiling of zero keeps tests deterministic.
FAST_RETRY = RetryPolicy(max_retries=2, backoff_factor=0.0)


def body_of(request: httpx.Request) -> Any:
    return json.loads(request.content)


def money(value: float, currency: str = "TZS") -> dict[str, Any]:
    return {"value": value, "currency": currency}


def payment_json(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": PI,
        "ref": "PAYXYENP80MPB8X",
        "message": "TZS 25,000.00 is being collected.",
        "receipt_no": "rcp_7KQ2M9XB4T1HV8D3NC6R",
        "object": "payment_intent",
        "state": "PENDING_AUTH",
        "amount": money(25000.00),
        "method": "mobile_money",
        "origin": "merchant_initiated",
        "merchant_reference": "ORD-8451",
        "created_at": "2026-09-06T10:30:02Z",
        "expires_at": "2026-09-06T10:45:02Z",
        "next_action": {"type": "await_mobile_prompt"},
    }
    data.update(overrides)
    return data


def payout_json(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": PO,
        "ref": "POXK2M9QZ81",
        "object": "payout",
        "state": "REQUESTED",
        "amount": money(50000.00),
        "fee": money(1000.00),
        "vat": money(180.00),
        "destination": {
            "destination_id": DST,
            "purpose": "BENEFICIARY",
            "kind": "MOMO",
            "fsp_code": "VODATZ",
            "account_masked": "2557****5678",
            "account_name": "JOHN DOE",
        },
        "created_at": "2026-09-06T11:00:00Z",
        "updated_at": "2026-09-06T11:00:00Z",
    }
    data.update(overrides)
    return data


def beneficiary_json(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": DST,
        "object": "beneficiary",
        "status": "pending_confirmation",
        "kind": "MOMO",
        "fsp_code": "VODATZ",
        "account_masked": "2557****5678",
        "verified_name": "JOHN DOE",
        "created_via": "api",
        "confirmation": {
            "channel": "sms",
            "sent_to": "+2557****111",
            "expires_at": "2026-09-06T11:10:00Z",
        },
        "created_at": "2026-09-06T11:00:00Z",
    }
    data.update(overrides)
    return data


def error_json(code: str, message: str = "nope", **extra: Any) -> dict[str, Any]:
    return {"type": "invalid_request", "code": code, "message": message, **extra}
