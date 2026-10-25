"""Client-side input validation.

Everything here runs before any network I/O, so a bad argument never reaches the
API (or the payment network). Rules follow the Settlo Pay API reference.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from .exceptions import ValidationError

AmountLike = int | float | str | Decimal

_TWO_PLACES = Decimal("0.01")
_MAX_AMOUNT = Decimal("1000000000000")  # 1e12; far above any real cap, guards float precision
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_TZ_PHONE = re.compile(r"^\+255[0-9]{9}$")
_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ID_BODY = re.compile(r"^[A-Za-z0-9]{1,100}$")
_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,120}$")
_CURSOR = re.compile(r"^[\x21-\x7e]{1,1024}$")
_FSP_CODE = re.compile(r"^[A-Z0-9]{2,16}$")
_MOMO_ACCOUNT = re.compile(r"^255[0-9]{9}$")
_BANK_ACCOUNT = re.compile(r"^[A-Za-z0-9]{6,32}$")
_CONFIRMATION_CODE = re.compile(r"^[0-9]{6}$")
_API_VERSION = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _fail(param: str, message: str) -> ValidationError:
    return ValidationError(f"{param}: {message}", param=param)


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def amount(value: AmountLike, *, param: str = "amount", whole: bool = False) -> Decimal:
    """Return ``value`` as a positive :class:`Decimal` with at most two decimal places."""
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        raise _fail(param, "must be an int, Decimal, or numeric string")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _fail(param, "must be finite")
        value = repr(value)  # shortest round-trip form, avoids binary float noise
    try:
        dec = Decimal(value)
    except InvalidOperation:
        raise _fail(param, "is not a valid number") from None
    if not dec.is_finite():
        raise _fail(param, "must be finite")
    if dec <= 0:
        raise _fail(param, "must be greater than zero")
    if dec > _MAX_AMOUNT:
        raise _fail(param, "is unreasonably large")
    if dec != dec.quantize(_TWO_PLACES):
        raise _fail(param, "allows at most 2 decimal places")
    if whole and dec != dec.to_integral_value():
        raise _fail(param, "must be whole shillings for this payment method")
    return dec.quantize(_TWO_PLACES)


def number(value: Decimal) -> int | float:
    """JSON number for a validated amount: ``25000`` rather than ``25000.0``."""
    return int(value) if value == value.to_integral_value() else float(value)


def money(value: Decimal, currency_code: str) -> dict[str, Any]:
    """Serialise an amount to the API's ``{"value": ..., "currency": ...}`` shape."""
    return {"value": number(value), "currency": currency_code}


def currency(value: str, *, allowed: Collection[str] | None = None) -> str:
    value = _enum_value(value)
    if not isinstance(value, str) or not _CURRENCY.match(value):
        raise _fail("currency", "must be a 3-letter upper-case ISO 4217 code, e.g. 'TZS'")
    if allowed is not None and value not in allowed:
        raise _fail("currency", f"must be one of {sorted(allowed)}")
    return value


def text(value: Any, *, param: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise _fail(param, "must be a string")
    if not value.strip():
        raise _fail(param, "must not be empty")
    if len(value) > max_len:
        raise _fail(param, f"must be at most {max_len} characters")
    if _CONTROL_CHARS.search(value):
        raise _fail(param, "must not contain control characters")
    return value


def optional_text(value: Any, *, param: str, max_len: int) -> str | None:
    return None if value is None else text(value, param=param, max_len=max_len)


def choice(value: Any, choices: Collection[str], *, param: str) -> str:
    value = _enum_value(value)
    if not isinstance(value, str) or value not in choices:
        raise _fail(param, f"must be one of {sorted(choices)}")
    return value


def optional_choice(value: Any, choices: Collection[str], *, param: str) -> str | None:
    return None if value is None else choice(value, choices, param=param)


def tz_phone(value: Any, *, param: str = "phone") -> str:
    if not isinstance(value, str) or not _TZ_PHONE.match(value):
        raise _fail(param, "must be E.164 starting with +255, e.g. '+255712345678'")
    return value


def e164_phone(value: Any, *, param: str) -> str:
    if not isinstance(value, str) or not _E164.match(value):
        raise _fail(param, "must be an E.164 phone number, e.g. '+255712345678'")
    return value


def email(value: Any, *, param: str) -> str:
    if not isinstance(value, str) or len(value) > 254 or not _EMAIL.match(value):
        raise _fail(param, "must be a valid email address")
    return value


def url(value: Any, *, param: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or _CONTROL_CHARS.search(value):
        raise _fail(param, "must be an absolute http(s) URL")
    if any(ch.isspace() for ch in value):
        raise _fail(param, "must not contain whitespace")
    parts = urlsplit(value)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise _fail(param, "must be an absolute http(s) URL")
    return value


def optional_url(value: Any, *, param: str) -> str | None:
    return None if value is None else url(value, param=param)


def resource_id(value: Any, prefix: str, *, param: str = "id") -> str:
    """Validate a Settlo object id such as ``pi_01J9X...``.

    Strict matching also keeps user input from altering the request path.
    """
    if not isinstance(value, str) or not value.startswith(prefix):
        raise _fail(param, f"must be a Settlo id starting with '{prefix}'")
    if not _ID_BODY.match(value[len(prefix) :]):
        raise _fail(param, "contains invalid characters")
    return value


def idempotency_key(value: str | None, *, scope: str) -> str:
    """Return a validated idempotency key, generating a random one when ``None``."""
    if value is None:
        return f"{scope}-{uuid.uuid4()}"
    if not isinstance(value, str) or not _IDEMPOTENCY_KEY.match(value):
        raise _fail("idempotency_key", "must be 1-120 printable ASCII characters without spaces")
    if value.startswith("refund:"):
        raise _fail("idempotency_key", "keys starting with 'refund:' are reserved by Settlo")
    return value


def metadata(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or not all(isinstance(k, str) for k in value):
        raise _fail("metadata", "must be a mapping with string keys")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        raise _fail("metadata", "must be JSON-serialisable") from None
    return dict(value)


def page_limit(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise _fail("limit", "must be an integer between 1 and 100")
    return value


def cursor(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _CURSOR.match(value):
        raise _fail("cursor", "must be the next_cursor value from a previous page")
    return value


def future_datetime(value: Any, *, param: str, min_ahead: timedelta, max_ahead: timedelta) -> str:
    if not isinstance(value, datetime):
        raise _fail(param, "must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise _fail(param, "must be timezone-aware")
    ahead = value - datetime.now(timezone.utc)
    slack = timedelta(seconds=30)  # tolerate small clock differences
    if ahead < min_ahead - slack or ahead > max_ahead + slack:
        raise _fail(param, f"must be between {min_ahead} and {max_ahead} from now")
    return value.isoformat()


def fsp_code(value: Any) -> str:
    if not isinstance(value, str) or not _FSP_CODE.match(value):
        raise _fail("fsp_code", "must be an upper-case bank/network code, e.g. 'VODATZ'")
    return value


def account_number(value: Any, *, kind: str) -> str:
    pattern, hint = (
        (_MOMO_ACCOUNT, "'255' followed by nine digits, no '+'")
        if kind == "MOMO"
        else (_BANK_ACCOUNT, "6-32 letters or digits")
    )
    if not isinstance(value, str) or not pattern.match(value):
        raise _fail("account_number", f"for {kind} must be {hint}")
    return value


def confirmation_code(value: Any) -> str:
    if not isinstance(value, str) or not _CONFIRMATION_CODE.match(value):
        raise _fail("code", "must be the 6-digit confirmation code (as a string)")
    return value


def api_version(value: Any) -> str:
    if not isinstance(value, str) or not _API_VERSION.match(value):
        raise _fail("api_version", "must look like '2026-04-29'")
    return value


def token_list(value: Any, *, param: str) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, Sequence) or not value:
        raise _fail(param, "must be a non-empty list of strings")
    items = [_enum_value(v) for v in value]
    if not all(isinstance(v, str) and _TOKEN.match(v) for v in items):
        raise _fail(param, "items must be lower-case identifiers, e.g. 'mobile_money'")
    return items


def compact(**fields: Any) -> dict[str, Any]:
    """Drop ``None`` values so optional fields are omitted from the request."""
    return {k: v for k, v in fields.items() if v is not None}
