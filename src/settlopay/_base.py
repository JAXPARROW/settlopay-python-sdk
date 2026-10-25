"""Transport-agnostic client core: configuration, auth, retries, response handling."""

from __future__ import annotations

import json
import logging
import os
import platform
import random
import re
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field
from typing import Any, NoReturn, TypeVar
from urllib.parse import quote, urlsplit

import httpx
import pydantic

from . import _validation as v
from ._version import __version__
from .exceptions import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    ConfigurationError,
    UnexpectedResponseError,
    error_from_response,
)

logger = logging.getLogger("settlopay")
logger.addHandler(logging.NullHandler())

DEFAULT_BASE_URL = "https://api.settlopay.co.tz"
#: The API version this SDK's models were written against; sent as ``Settlo-Version``.
API_VERSION = "2026-04-29"
API_KEY_ENV_VAR = "SETTLO_API_KEY"

_API_KEY_RE = re.compile(r"^sk_(live|test)_[\x21-\x7e]{8,256}$")

T = TypeVar("T")
Parser = Callable[[Any], T]


class _ApiKey:
    """Holds the secret key. Its repr is masked and it refuses to be pickled."""

    __slots__ = ("_mode", "_value")

    def __init__(self, value: str | None) -> None:
        if value is None:
            value = os.environ.get(API_KEY_ENV_VAR)
        if not value:
            raise ConfigurationError(
                f"No API key provided. Pass api_key=... or set the {API_KEY_ENV_VAR} "
                "environment variable."
            )
        if not isinstance(value, str) or not _API_KEY_RE.match(value):
            # Never echo the value back: it may be a real secret with a typo.
            raise ConfigurationError(
                "API key has an unexpected format (expected 'sk_live_...' or 'sk_test_...')."
            )
        self._value = value
        self._mode = "live" if value.startswith("sk_live_") else "test"

    @property
    def mode(self) -> str:
        return self._mode

    def header_value(self) -> str:
        return "Bearer " + self._value

    def __repr__(self) -> str:
        return f"<ApiKey sk_{self._mode}_****>"

    __str__ = __repr__

    def __reduce__(self) -> NoReturn:
        raise TypeError("Settlo API keys cannot be pickled or copied")


class _BearerAuth(httpx.Auth):
    def __init__(self, key: _ApiKey) -> None:
        self._key = key

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = self._key.header_value()
        yield request

    def __repr__(self) -> str:
        return f"<_BearerAuth {self._key!r}>"


def _validate_base_url(base_url: str) -> str:
    if not isinstance(base_url, str):
        raise ConfigurationError("base_url must be a string")
    parts = urlsplit(base_url)
    if parts.scheme != "https":
        raise ConfigurationError("base_url must use https://; plain HTTP is refused")
    if not parts.hostname or parts.username or parts.password:
        raise ConfigurationError("base_url must be https://host[/path] without credentials")
    if parts.query or parts.fragment:
        raise ConfigurationError("base_url must not contain a query string or fragment")
    return base_url.rstrip("/")


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with full jitter.

    Retries happen only when they cannot cause a duplicate side effect:

    * connection failures before the request was sent: always;
    * ``429``: always, honouring ``Retry-After`` up to ``max_retry_after`` seconds;
    * timeouts, ``500``, ``502``, ``504``: only for requests that are safe to repeat
      (GETs, and creates, which always carry an ``Idempotency-Key``);
    * ``503``: only for safe requests *without* an idempotency key. Settlo asks for a
      new key after ``503 try_later`` on payouts, so the SDK raises instead.

    Example:
        >>> client = SettloPay(retry=RetryPolicy(max_retries=4, max_backoff=20))
    """

    max_retries: int = 2
    backoff_factor: float = 0.5
    max_backoff: float = 8.0
    max_retry_after: float = 60.0

    def __post_init__(self) -> None:
        if isinstance(self.max_retries, bool) or not 0 <= self.max_retries <= 10:
            raise ConfigurationError("max_retries must be between 0 and 10")
        if self.backoff_factor < 0 or self.max_backoff < 0 or self.max_retry_after < 0:
            raise ConfigurationError("backoff values must be non-negative")

    def backoff(self, attempt: int) -> float:
        ceiling = min(self.max_backoff, self.backoff_factor * (2**attempt))
        # Jitter only, not cryptography.
        return random.uniform(0, ceiling)  # noqa: S311  # nosec B311

    def delay(self, attempt: int, opts: RequestOptions, error: Exception) -> float | None:
        """Seconds to wait before retry number ``attempt + 1``, or ``None`` to give up."""
        if attempt >= self.max_retries:
            return None
        if isinstance(error, _NOT_SENT):
            return self.backoff(attempt)
        if isinstance(error, httpx.TransportError):
            return self.backoff(attempt) if opts.retry_safe else None
        if not isinstance(error, APIError):
            return None
        status = error.status_code
        if status == 429:
            if error.retry_after is None:
                return self.backoff(attempt)
            return error.retry_after if error.retry_after <= self.max_retry_after else None
        if not opts.retry_safe:
            return None
        if status in (500, 502, 504):
            return self.backoff(attempt)
        if status == 503 and opts.idempotency_key is None:
            if error.retry_after is not None and error.retry_after <= self.max_retry_after:
                return error.retry_after
            return self.backoff(attempt)
        return None


# The request never left the machine, so repeating it cannot duplicate anything.
_NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


@dataclass(frozen=True)
class RequestOptions:
    method: str
    path: str
    body: Mapping[str, Any] | None = None
    params: Mapping[str, Any] | None = None
    idempotency_key: str | None = None
    #: Whether repeating the request after an ambiguous failure is harmless.
    retry_safe: bool = False
    extra_headers: Mapping[str, str] = field(default_factory=dict)


def path(template: str, *ids: str) -> str:
    """Fill ``{}`` placeholders with URL-encoded (already validated) ids."""
    return template.format(*(quote(i, safe="") for i in ids))


M = TypeVar("M", bound=pydantic.BaseModel)


def model_parser(model: type[M]) -> Parser[M]:
    return model.model_validate


def _user_agent() -> str:
    return (
        f"settlopay-python/{__version__} httpx/{httpx.__version__} "
        f"python/{platform.python_version()}"
    )


class BaseClient:
    """Shared state and pure helpers for :class:`SettloPay` and :class:`AsyncSettloPay`."""

    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str,
        api_version: str | None,
        retry: RetryPolicy | None,
        max_retries: int | None,
    ) -> None:
        self._api_key = _ApiKey(api_key)
        self._auth = _BearerAuth(self._api_key)
        self.base_url = _validate_base_url(base_url)
        self.api_version = None if api_version is None else v.api_version(api_version)
        if retry is not None and max_retries is not None:
            raise ConfigurationError("pass either retry=RetryPolicy(...) or max_retries, not both")
        self.retry = retry or RetryPolicy(max_retries=2 if max_retries is None else max_retries)

    @property
    def mode(self) -> str:
        """``"live"`` or ``"test"``. Both move real money: Settlo has no sandbox."""
        return self._api_key.mode

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r}, api_key={self._api_key!r})"

    def __reduce__(self) -> NoReturn:
        raise TypeError(f"{type(self).__name__} cannot be pickled (it holds an API key)")

    def _headers(self, opts: RequestOptions) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": _user_agent()}
        if self.api_version:
            headers["Settlo-Version"] = self.api_version
        if opts.body is not None:
            headers["Content-Type"] = "application/json"
        if opts.idempotency_key is not None:
            headers["Idempotency-Key"] = opts.idempotency_key
        headers.update(opts.extra_headers)
        return headers

    def _build_args(self, opts: RequestOptions) -> dict[str, Any]:
        content = None
        if opts.body is not None:
            content = json.dumps(opts.body, separators=(",", ":"), allow_nan=False).encode()
        return {
            "method": opts.method,
            "url": self.base_url + opts.path,
            "params": {k: val for k, val in (opts.params or {}).items() if val is not None},
            "content": content,
            "headers": self._headers(opts),
        }

    @staticmethod
    def _decode(response: httpx.Response) -> Any:
        if not 200 <= response.status_code < 300:
            raise error_from_response(response)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise UnexpectedResponseError(
                "Settlo Pay returned a non-JSON success response",
                status_code=response.status_code,
            ) from None

    @staticmethod
    def _parse(parser: Parser[T], data: Any, status_code: int) -> T:
        try:
            return parser(data)
        except pydantic.ValidationError as exc:
            raise UnexpectedResponseError(
                f"Could not parse Settlo Pay response: {exc.error_count()} field error(s)",
                status_code=status_code,
            ) from exc

    @staticmethod
    def _wrap_transport_error(
        exc: httpx.TransportError, opts: RequestOptions
    ) -> APIConnectionError:
        cls = APITimeoutError if isinstance(exc, httpx.TimeoutException) else APIConnectionError
        return cls(f"{type(exc).__name__} during {opts.method} {opts.path}")

    @staticmethod
    def _log_response(opts: RequestOptions, response: httpx.Response, attempt: int) -> None:
        # Method, path and status only: never headers (API key) or bodies (customer PII).
        logger.debug(
            "%s %s -> %s (attempt %d, request_id=%s)",
            opts.method,
            opts.path,
            response.status_code,
            attempt + 1,
            response.headers.get("x-request-id", "-"),
        )

    @staticmethod
    def _log_retry(opts: RequestOptions, error: Exception, delay: float, attempt: int) -> None:
        reason = (
            f"HTTP {error.status_code}" if isinstance(error, APIError) else type(error).__name__
        )
        logger.info(
            "Retrying %s %s in %.2fs after %s (retry %d)",
            opts.method,
            opts.path,
            delay,
            reason,
            attempt + 1,
        )
