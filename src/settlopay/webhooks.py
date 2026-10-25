"""Webhook signature verification.

Settlo signs each delivery with ``Settlo-Signature: t=<unix seconds>,v1=<hex>``,
where ``v1 = HMAC-SHA256(secret, f"{t}." + raw_body)`` and ``secret`` is the full
``whsec_...`` string. Always verify against the **raw** request bytes, before any
JSON parsing, and deduplicate on ``Settlo-Event-Id`` (retries reuse it).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import NoReturn

import pydantic

from .exceptions import WebhookVerificationError
from .models import WebhookEvent

__all__ = [
    "EVENT_ID_HEADER",
    "SIGNATURE_HEADER",
    "WebhookVerifier",
    "compute_signature",
    "verify_webhook",
]

SIGNATURE_HEADER = "Settlo-Signature"
EVENT_ID_HEADER = "Settlo-Event-Id"
DEFAULT_TOLERANCE = 300  # seconds; the documented replay window


def _as_bytes(payload: bytes | str) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else payload


def _check_secret(secret: str) -> None:
    if not isinstance(secret, str) or not secret.startswith("whsec_") or len(secret) < 12:
        raise WebhookVerificationError("Webhook secret must be the full 'whsec_...' string")


def compute_signature(payload: bytes | str, timestamp: int | str, secret: str) -> str:
    """Return the hex ``v1`` signature for ``payload`` signed at ``timestamp``.

    Useful for tests that need a validly signed body.

    Example:
        >>> sig = compute_signature(b'{"id":"evt"}', 1767000000, "whsec_test_secret")
        >>> header = f"t=1767000000,v1={sig}"
    """
    _check_secret(secret)
    message = str(timestamp).encode("ascii") + b"." + _as_bytes(payload)
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _parse_header(header: str) -> tuple[int, list[str]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        if key == "t":
            if not value.isdigit():
                raise WebhookVerificationError("Settlo-Signature has a non-numeric timestamp")
            timestamp = int(value)
        elif key == "v1" and value:
            signatures.append(value)
    if timestamp is None or not signatures:
        raise WebhookVerificationError("Settlo-Signature header is missing t= or v1=")
    return timestamp, signatures


def verify_webhook(
    payload: bytes | str,
    signature_header: str | None,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: float | None = None,
) -> WebhookEvent:
    """Verify a webhook delivery and return the parsed event.

    Raises:
        WebhookVerificationError: header missing/malformed, timestamp outside
            ``tolerance`` seconds, signature mismatch, or body not a valid event.

    Example:
        >>> # Flask
        >>> event = verify_webhook(
        ...     request.get_data(),                       # raw bytes, not request.json
        ...     request.headers.get("Settlo-Signature"),
        ...     os.environ["SETTLO_WEBHOOK_SECRET"],
        ... )
        >>> if event.type == "payment_intent.succeeded":
        ...     fulfil(event.data["merchant_reference"])
    """
    _check_secret(secret)
    if not signature_header:
        raise WebhookVerificationError("Missing Settlo-Signature header")
    timestamp, signatures = _parse_header(signature_header)

    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        raise WebhookVerificationError("Webhook timestamp is outside the allowed tolerance")

    expected = compute_signature(payload, timestamp, secret)
    # Compare against every v1 value (covers secret rotation) in constant time.
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise WebhookVerificationError("Webhook signature does not match")

    try:
        return WebhookEvent.model_validate(json.loads(_as_bytes(payload)))
    except (ValueError, pydantic.ValidationError) as exc:
        raise WebhookVerificationError("Webhook body is not a valid Settlo event") from exc


class WebhookVerifier:
    """Holds a webhook secret (masked in ``repr``) and verifies deliveries.

    Example:
        >>> verifier = WebhookVerifier(os.environ["SETTLO_WEBHOOK_SECRET"])
        >>> event = verifier.verify(raw_body, headers["Settlo-Signature"])
    """

    __slots__ = ("_secret", "tolerance")

    def __init__(self, secret: str, *, tolerance: int = DEFAULT_TOLERANCE) -> None:
        _check_secret(secret)
        self._secret = secret
        self.tolerance = tolerance

    def verify(self, payload: bytes | str, signature_header: str | None) -> WebhookEvent:
        """Verify a delivery. See :func:`verify_webhook`.

        Example:
            >>> event = verifier.verify(request.body, request.headers["Settlo-Signature"])
        """
        return verify_webhook(payload, signature_header, self._secret, tolerance=self.tolerance)

    def __repr__(self) -> str:
        return "WebhookVerifier(secret='whsec_****')"

    def __reduce__(self) -> NoReturn:
        raise TypeError("WebhookVerifier cannot be pickled (it holds a secret)")
