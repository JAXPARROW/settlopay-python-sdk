"""Exception hierarchy for the Settlo Pay SDK.

Every exception raised by the SDK derives from :class:`SettloError`::

    SettloError
    ├── ConfigurationError          bad client setup (missing key, non-HTTPS URL, ...)
    ├── ValidationError             input rejected before any request was sent
    ├── WebhookVerificationError    webhook signature/timestamp check failed
    ├── UnexpectedResponseError     2xx response the SDK could not parse
    ├── APIConnectionError          network failure, no HTTP response received
    │   └── APITimeoutError
    └── APIError                    the API answered with an error status
        ├── InvalidRequestError         400  (also a ValidationError)
        ├── AuthenticationError         401
        ├── PaymentFailedError          402
        ├── PermissionDeniedError       403
        ├── NotFoundError               404
        ├── ConflictError               409
        │   └── IdempotencyConflictError
        ├── UnprocessableEntityError    422  (business declines)
        ├── RateLimitError              429
        └── ServerError                 5xx
            ├── ProviderError           502 / 504
            └── ServiceUnavailableError 503

Branch on :attr:`APIError.code` (for example ``"insufficient_funds"``) for
fine-grained handling, and quote :attr:`APIError.request_id` to Settlo support.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "ConfigurationError",
    "ConflictError",
    "IdempotencyConflictError",
    "InvalidRequestError",
    "NotFoundError",
    "PaymentFailedError",
    "PermissionDeniedError",
    "ProviderError",
    "RateLimitError",
    "ServerError",
    "ServiceUnavailableError",
    "SettloError",
    "UnexpectedResponseError",
    "UnprocessableEntityError",
    "ValidationError",
    "WebhookVerificationError",
]


class SettloError(Exception):
    """Base class for every error raised by the SDK.

    Example:
        >>> try:
        ...     client.payouts.create(amount=50_000)
        ... except SettloError as exc:
        ...     print(exc.message)
    """

    def __init__(self, message: str, *, param: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        #: The request parameter the error refers to, when known (e.g. ``"amount.value"``).
        self.param = param


class ConfigurationError(SettloError, ValueError):
    """The client was configured incorrectly (missing API key, insecure base URL, ...)."""


class ValidationError(SettloError, ValueError):
    """An input was rejected.

    Raised locally, before any network request, when an argument is invalid. The
    API's own ``400`` responses raise :class:`InvalidRequestError`, which is also a
    subclass, so ``except ValidationError`` catches both.
    """


class WebhookVerificationError(SettloError):
    """A webhook's ``Settlo-Signature`` header is missing, malformed, stale or wrong."""


class UnexpectedResponseError(SettloError):
    """The API returned a successful status but a body the SDK could not parse."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class APIConnectionError(SettloError):
    """No HTTP response was received (DNS, TLS, connection reset, ...)."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


class APIError(SettloError):
    """The API returned an error response.

    Attributes:
        status_code: HTTP status code.
        code: Machine-readable Settlo error code, e.g. ``"insufficient_funds"``.
        type: Error category, e.g. ``"business_decline"``.
        param: The offending parameter, if the API named one.
        request_id: Settlo request id; quote it when contacting support.
        retry_after: Seconds to wait before retrying, from ``Retry-After``.
        body: The decoded JSON error body (never contains your API key).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        type: str | None = None,  # mirrors the API field name
        param: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, param=param)
        self.status_code = status_code
        self.code = code
        self.type = type
        self.request_id = request_id
        self.retry_after = retry_after
        self.body: Mapping[str, Any] = body or {}

    def __str__(self) -> str:
        label = f"{self.status_code} {self.code}" if self.code else str(self.status_code)
        suffix = f" (request_id={self.request_id})" if self.request_id else ""
        return f"[{label}] {self.message}{suffix}"


class InvalidRequestError(APIError, ValidationError):
    """400: the API rejected the request parameters (e.g. ``parameter_invalid``)."""


class AuthenticationError(APIError):
    """401: the API key is missing or invalid (``authentication_required``)."""


class PaymentFailedError(APIError):
    """402: the payment could not be created (``payment_failed``)."""


class PermissionDeniedError(APIError):
    """403: missing scope (``permission_denied``) or account cannot transact
    (``merchant_not_transactable``)."""


class NotFoundError(APIError):
    """404: the resource does not exist (``resource_missing``)."""


class ConflictError(APIError):
    """409: state conflict (``state_invalid``, ``confirmation_not_pending``, ...)."""


class IdempotencyConflictError(ConflictError):
    """409 ``idempotency_conflict``: the key was reused with a different body, or the
    first request with that key is still in progress."""


class UnprocessableEntityError(APIError):
    """422: a business decline (``insufficient_funds``, ``payout_limit_exceeded``, ...)."""


class RateLimitError(APIError):
    """429: ``rate_limit_exceeded`` or ``confirmation_throttled``.
    See :attr:`retry_after`."""


class ServerError(APIError):
    """5xx: an error on Settlo's side (``api_error``)."""


class ProviderError(ServerError):
    """502 ``provider_error`` / 504 ``provider_timeout``: the payment network failed."""


class ServiceUnavailableError(ServerError):
    """503 ``service_unavailable`` / ``try_later``.

    For payouts, retry with a **new** ``Idempotency-Key``; the SDK never retries a
    503 on a request that carries an idempotency key.
    """


_BY_CODE: dict[str, type[APIError]] = {
    "idempotency_conflict": IdempotencyConflictError,
}

_BY_STATUS: dict[int, type[APIError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    402: PaymentFailedError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    429: RateLimitError,
    502: ProviderError,
    503: ServiceUnavailableError,
    504: ProviderError,
}


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return max(seconds, 0.0)


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def error_from_response(response: httpx.Response) -> APIError:
    """Build the matching :class:`APIError` subclass from an error response."""
    status = response.status_code
    try:
        decoded = response.json()
    except ValueError:
        decoded = None
    body: dict[str, Any] = decoded if isinstance(decoded, dict) else {}
    # The documented shape is flat; tolerate an ``{"error": {...}}`` envelope too.
    err = body["error"] if isinstance(body.get("error"), dict) else body

    code = _str_or_none(err.get("code"))
    message = _str_or_none(err.get("message")) or f"HTTP {status} from Settlo Pay"
    if status in (301, 302, 303, 307, 308):
        message = f"Unexpected redirect (HTTP {status}); redirects are never followed"

    cls = _BY_CODE.get(code or "") or _BY_STATUS.get(status)
    if cls is None:
        cls = ServerError if status >= 500 else APIError
    return cls(
        message,
        status_code=status,
        code=code,
        type=_str_or_none(err.get("type")),
        param=_str_or_none(err.get("param")),
        request_id=_str_or_none(err.get("request_id")) or response.headers.get("x-request-id"),
        retry_after=_parse_retry_after(response.headers.get("retry-after")),
        body=body,
    )
