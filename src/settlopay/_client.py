"""Public sync and async clients."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from types import TracebackType

import httpx

from ._base import (
    API_VERSION,
    DEFAULT_BASE_URL,
    BaseClient,
    Parser,
    RequestOptions,
    RetryPolicy,
    T,
)
from .exceptions import APIError
from .resources import (
    AsyncBalanceResource,
    AsyncBeneficiaries,
    AsyncCheckoutSessions,
    AsyncPayments,
    AsyncPayouts,
    AsyncQrCodeResource,
    AsyncRefunds,
    BalanceResource,
    Beneficiaries,
    CheckoutSessions,
    Payments,
    Payouts,
    QrCodeResource,
    Refunds,
)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SettloPay(BaseClient):
    """Synchronous Settlo Pay client.

    Settlo has **no sandbox**: ``sk_test_`` and ``sk_live_`` keys both move real money.

    Args:
        api_key: Secret key. Defaults to the ``SETTLO_API_KEY`` environment variable.
        base_url: API root; must be ``https://``.
        api_version: Value of the ``Settlo-Version`` header. ``None`` omits the header
            (the account's current version is used). Defaults to the version this
            SDK was built against.
        timeout: Seconds, or an :class:`httpx.Timeout`.
        max_retries: Shortcut for ``retry=RetryPolicy(max_retries=...)``.
        retry: Full retry configuration; see :class:`RetryPolicy`.
        http_client: Bring your own :class:`httpx.Client` (proxies, custom TLS).
            You are then responsible for keeping TLS verification on, and for closing it.

    Example:
        >>> from settlopay import SettloPay
        >>> with SettloPay() as client:  # reads SETTLO_API_KEY
        ...     print(client.balance.retrieve().amount.value)
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str | None = API_VERSION,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int | None = None,
        retry: RetryPolicy | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key,
            base_url=base_url,
            api_version=api_version,
            retry=retry,
            max_retries=max_retries,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=False)
        self._sleep: Callable[[float], None] = time.sleep

        self.payments = Payments(self)
        self.refunds = Refunds(self)
        self.payouts = Payouts(self)
        self.beneficiaries = Beneficiaries(self)
        self.balance = BalanceResource(self)
        self.checkout_sessions = CheckoutSessions(self)
        self.qr_code = QrCodeResource(self)

    def _request(self, opts: RequestOptions, parser: Parser[T]) -> T:
        attempt = 0
        while True:
            error: Exception
            try:
                response = self._http.request(
                    **self._build_args(opts), auth=self._auth, follow_redirects=False
                )
            except httpx.TransportError as exc:
                error = exc
            else:
                self._log_response(opts, response, attempt)
                try:
                    data = self._decode(response)
                except APIError as exc:
                    error = exc
                else:
                    return self._parse(parser, data, response.status_code)

            delay = self.retry.delay(attempt, opts, error)
            if delay is None:
                if isinstance(error, httpx.TransportError):
                    raise self._wrap_transport_error(error, opts) from error
                raise error
            self._log_retry(opts, error, delay, attempt)
            self._sleep(delay)
            attempt += 1

    def close(self) -> None:
        """Close the underlying HTTP connection pool (unless you supplied it).

        Example:
            >>> client = SettloPay()
            >>> client.close()
        """
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> SettloPay:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncSettloPay(BaseClient):
    """Asynchronous Settlo Pay client. Same arguments as :class:`SettloPay`.

    Example:
        >>> from settlopay import AsyncSettloPay
        >>> async with AsyncSettloPay() as client:
        ...     balance = await client.balance.retrieve()
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str | None = API_VERSION,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int | None = None,
        retry: RetryPolicy | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key,
            base_url=base_url,
            api_version=api_version,
            retry=retry,
            max_retries=max_retries,
        )
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

        self.payments = AsyncPayments(self)
        self.refunds = AsyncRefunds(self)
        self.payouts = AsyncPayouts(self)
        self.beneficiaries = AsyncBeneficiaries(self)
        self.balance = AsyncBalanceResource(self)
        self.checkout_sessions = AsyncCheckoutSessions(self)
        self.qr_code = AsyncQrCodeResource(self)

    async def _request(self, opts: RequestOptions, parser: Parser[T]) -> T:
        attempt = 0
        while True:
            error: Exception
            try:
                response = await self._http.request(
                    **self._build_args(opts), auth=self._auth, follow_redirects=False
                )
            except httpx.TransportError as exc:
                error = exc
            else:
                self._log_response(opts, response, attempt)
                try:
                    data = self._decode(response)
                except APIError as exc:
                    error = exc
                else:
                    return self._parse(parser, data, response.status_code)

            delay = self.retry.delay(attempt, opts, error)
            if delay is None:
                if isinstance(error, httpx.TransportError):
                    raise self._wrap_transport_error(error, opts) from error
                raise error
            self._log_retry(opts, error, delay, attempt)
            await self._sleep(delay)
            attempt += 1

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool (unless you supplied it).

        Example:
            >>> await client.aclose()
        """
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncSettloPay:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
