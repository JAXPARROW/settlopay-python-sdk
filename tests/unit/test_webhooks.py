from __future__ import annotations

import json
import time

import pytest

from settlopay import WebhookVerificationError, WebhookVerifier, verify_webhook
from settlopay.webhooks import compute_signature

SECRET = "whsec_" + "unit-test-secret"
EVENT = {
    "id": "0198f6f0-9c1d-7e2f-8a3b-4c5d6e7f8a9b",
    "type": "payment_intent.succeeded",
    "api_version": "2026-04-29",
    "created": "2026-09-06T10:30:46Z",
    "data": {"id": "pi_01J9X4", "state": "SUCCEEDED", "amount": 25000.0, "currency": "TZS"},
    "delivery": {"id": "dlv_1", "attempt": 1},
}
BODY = json.dumps(EVENT).encode()


def _header(body: bytes = BODY, ts: int | None = None, secret: str = SECRET) -> str:
    ts = int(time.time()) if ts is None else ts
    return f"t={ts},v1={compute_signature(body, ts, secret)}"


def test_valid_signature_returns_event() -> None:
    event = verify_webhook(BODY, _header(), SECRET)
    assert event.type == "payment_intent.succeeded"
    assert event.data["state"] == "SUCCEEDED"
    assert event.delivery is not None
    assert event.delivery.attempt == 1


def test_str_payload_and_verifier_class() -> None:
    assert WebhookVerifier(SECRET).verify(BODY.decode(), _header()).id == EVENT["id"]


def test_multiple_v1_values_any_match() -> None:
    ts = int(time.time())
    header = f"t={ts},v1={'0' * 64},v1={compute_signature(BODY, ts, SECRET)}"
    verify_webhook(BODY, header, SECRET)


@pytest.mark.parametrize(
    ("body", "header_factory"),
    [
        (BODY + b" ", lambda: _header()),  # body tampered after signing
        (BODY, lambda: _header(secret="whsec_" + "other-secret")),
        (BODY, lambda: _header(ts=int(time.time()) - 301)),  # stale (replay)
        (BODY, lambda: _header(ts=int(time.time()) + 301)),  # from the future
        (BODY, lambda: "v1=abc"),
        (BODY, lambda: f"t={int(time.time())}"),
        (BODY, lambda: "t=notanumber,v1=abc"),
        (BODY, lambda: ""),
    ],
)
def test_rejections(body: bytes, header_factory: object) -> None:
    with pytest.raises(WebhookVerificationError):
        verify_webhook(body, header_factory(), SECRET)  # type: ignore[operator]


def test_missing_header() -> None:
    with pytest.raises(WebhookVerificationError):
        verify_webhook(BODY, None, SECRET)


def test_signed_but_not_an_event() -> None:
    body = b'{"hello": "world"}'
    with pytest.raises(WebhookVerificationError, match="valid Settlo event"):
        verify_webhook(body, _header(body), SECRET)


@pytest.mark.parametrize("secret", ["", "sk_live_x", "whsec_"])
def test_bad_secret(secret: str) -> None:
    with pytest.raises(WebhookVerificationError):
        verify_webhook(BODY, _header(), secret)
