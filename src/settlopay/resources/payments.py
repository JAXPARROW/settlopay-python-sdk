"""``/v1/payments``: collect money by mobile money, bank reference or QR."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from datetime import datetime, timedelta
from typing import Any

from .. import _validation as v
from .._base import RequestOptions, model_parser, path
from ..enums import MobileNetwork, PaymentMethod
from ..exceptions import ValidationError
from ..models import Page, Payment
from ._base import AsyncResource, SyncResource

_METHODS = frozenset(m.value for m in PaymentMethod)
_NETWORKS = frozenset(n.value for n in MobileNetwork)
_PREFIX = "pi_"


def _create(
    *,
    amount: v.AmountLike,
    method: str,
    currency: str,
    phone: str | None,
    network: str | None,
    expires_at: datetime | None,
    customer_id: str | None,
    merchant_reference: str | None,
    description: str | None,
    statement_descriptor: str | None,
    return_url: str | None,
    cancel_url: str | None,
    metadata: Mapping[str, Any] | None,
    idempotency_key: str | None,
) -> RequestOptions:
    method = v.choice(method, _METHODS, param="method")
    value = v.amount(amount, whole=method == PaymentMethod.QR)
    method_data = None
    if method == PaymentMethod.MOBILE_MONEY:
        if phone is None:
            raise ValidationError("phone: is required for mobile_money payments", param="phone")
        method_data = v.compact(
            phone=v.tz_phone(phone),
            network=v.optional_choice(network, _NETWORKS, param="network"),
        )
    elif phone is not None or network is not None:
        raise ValidationError("phone/network only apply to mobile_money payments", param="phone")
    if expires_at is not None and method != PaymentMethod.QR:
        raise ValidationError("expires_at only applies to qr payments", param="expires_at")

    body = v.compact(
        amount=v.money(value, v.currency(currency)),
        method=method,
        method_data=method_data,
        expires_at=None
        if expires_at is None
        else v.future_datetime(
            expires_at,
            param="expires_at",
            min_ahead=timedelta(minutes=5),
            max_ahead=timedelta(days=30),
        ),
        customer_id=v.optional_text(customer_id, param="customer_id", max_len=120),
        merchant_reference=v.optional_text(
            merchant_reference, param="merchant_reference", max_len=120
        ),
        description=v.optional_text(description, param="description", max_len=1000),
        statement_descriptor=v.optional_text(
            statement_descriptor, param="statement_descriptor", max_len=22
        ),
        return_url=v.optional_url(return_url, param="return_url"),
        cancel_url=v.optional_url(cancel_url, param="cancel_url"),
        metadata=v.metadata(metadata),
    )
    return RequestOptions(
        "POST",
        "/v1/payments",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="payment"),
        retry_safe=True,
    )


def _list(limit: int | None, cursor: str | None) -> RequestOptions:
    params = {"limit": v.page_limit(limit), "cursor": v.cursor(cursor)}
    return RequestOptions("GET", "/v1/payments", params=params, retry_safe=True)


def _retrieve(payment_id: str) -> RequestOptions:
    pid = v.resource_id(payment_id, _PREFIX, param="payment_id")
    return RequestOptions("GET", path("/v1/payments/{}", pid), retry_safe=True)


def _amend(payment_id: str, amount: v.AmountLike, currency: str) -> RequestOptions:
    pid = v.resource_id(payment_id, _PREFIX, param="payment_id")
    body = {"amount": v.money(v.amount(amount, whole=True), v.currency(currency))}
    # Setting a new total is idempotent ("same amount again: no change").
    return RequestOptions("PATCH", path("/v1/payments/{}", pid), body=body, retry_safe=True)


def _cancel(payment_id: str) -> RequestOptions:
    pid = v.resource_id(payment_id, _PREFIX, param="payment_id")
    return RequestOptions("POST", path("/v1/payments/{}/cancel", pid))


def _inquire(payment_id: str) -> RequestOptions:
    pid = v.resource_id(payment_id, _PREFIX, param="payment_id")
    return RequestOptions("POST", path("/v1/payments/{}/inquire", pid), retry_safe=True)


_parse = model_parser(Payment)
_parse_page = model_parser(Page[Payment])


class Payments(SyncResource):
    """Create and manage payments. Access as ``client.payments``."""

    def create(
        self,
        *,
        amount: v.AmountLike,
        method: PaymentMethod | str,
        currency: str = "TZS",
        phone: str | None = None,
        network: MobileNetwork | str | None = None,
        expires_at: datetime | None = None,
        customer_id: str | None = None,
        merchant_reference: str | None = None,
        description: str | None = None,
        statement_descriptor: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Payment:
        """Create a payment.

        ``mobile_money`` sends a prompt to ``phone`` (state ``PENDING_AUTH``);
        ``bank`` returns a reference to pay at a bank; ``qr`` returns a QR code
        (whole shillings only). A ``BLOCKED`` payment comes back with HTTP 201;
        check :attr:`Payment.state` rather than assuming success.

        Args:
            amount: Amount in major units (shillings), at most 2 decimal places.
            method: ``"mobile_money"``, ``"bank"`` or ``"qr"``.
            currency: ISO currency code. Settlo currently supports ``"TZS"`` only.
            phone: Payer's phone in E.164 (``+255...``). Required for mobile money.
            network: Override network detection (``vodacom``, ``tigo``, ``airtel``, ``halotel``).
            expires_at: QR only. Timezone-aware, 5 minutes to 30 days ahead.
            customer_id: Your customer id; omit for guests.
            merchant_reference: Your order id (max 120), echoed on webhooks.
            description: Internal description (not returned).
            statement_descriptor: Max 22 characters.
            return_url: Redirect target for hosted pages.
            cancel_url: Redirect target when the customer cancels.
            metadata: Arbitrary JSON object (not returned).
            idempotency_key: Max 120 chars. Generated if omitted; pass your own,
                derived from your order, so a crash-and-retry cannot charge twice.

        Example:
            >>> payment = client.payments.create(
            ...     amount=25_000,
            ...     method="mobile_money",
            ...     phone="+255712345678",
            ...     merchant_reference="ORD-8451",
            ...     idempotency_key="order-8451-pay-1",
            ... )
            >>> payment.state
            'PENDING_AUTH'
        """
        opts = _create(
            amount=amount,
            method=method,
            currency=currency,
            phone=phone,
            network=network,
            expires_at=expires_at,
            customer_id=customer_id,
            merchant_reference=merchant_reference,
            description=description,
            statement_descriptor=statement_descriptor,
            return_url=return_url,
            cancel_url=cancel_url,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return self._client._request(opts, _parse)

    def list(self, *, limit: int | None = None, cursor: str | None = None) -> Page[Payment]:
        """List payments, newest first (includes QR payments customers made).

        Example:
            >>> page = client.payments.list(limit=50)
            >>> next_page = client.payments.list(cursor=page.next_cursor)
        """
        return self._client._request(_list(limit, cursor), _parse_page)

    def list_all(self, *, page_size: int = 100) -> Iterator[Payment]:
        """Iterate over every payment, fetching pages lazily.

        Example:
            >>> for payment in client.payments.list_all():
            ...     print(payment.id, payment.state)
        """
        cursor: str | None = None
        while True:
            page = self.list(limit=page_size, cursor=cursor)
            yield from page.data
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    def retrieve(self, payment_id: str) -> Payment:
        """Retrieve a payment by ``pi_`` id. Use this to poll when webhooks aren't possible.

        Example:
            >>> payment = client.payments.retrieve("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
            >>> payment.succeeded
            True
        """
        return self._client._request(_retrieve(payment_id), _parse)

    def amend(self, payment_id: str, *, amount: v.AmountLike, currency: str = "TZS") -> Payment:
        """Change the total of a QR payment that is ``AWAITING_CUSTOMER``.

        Example:
            >>> client.payments.amend("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK", amount=30_000)
        """
        return self._client._request(_amend(payment_id, amount, currency), _parse)

    def cancel(self, payment_id: str) -> Payment:
        """Cancel a payment in ``PENDING_AUTH``, ``AWAITING_CUSTOMER`` or ``AUTHORIZED``.

        Caution: a mobile-money prompt stays live on the customer's phone. If they
        approve it anyway the payment stays ``CANCELLED`` and you are not credited.

        Example:
            >>> client.payments.cancel("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK").state
            'CANCELLED'
        """
        return self._client._request(_cancel(payment_id), _parse)

    def inquire(self, payment_id: str) -> Payment:
        """Force a status check with the payment network for a payment that looks stuck.

        Example:
            >>> client.payments.inquire("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
        """
        return self._client._request(_inquire(payment_id), _parse)


class AsyncPayments(AsyncResource):
    """Async variant of :class:`Payments`. Access as ``client.payments``."""

    async def create(
        self,
        *,
        amount: v.AmountLike,
        method: PaymentMethod | str,
        currency: str = "TZS",
        phone: str | None = None,
        network: MobileNetwork | str | None = None,
        expires_at: datetime | None = None,
        customer_id: str | None = None,
        merchant_reference: str | None = None,
        description: str | None = None,
        statement_descriptor: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Payment:
        """Create a payment. See :meth:`Payments.create` for every argument.

        Example:
            >>> payment = await client.payments.create(
            ...     amount=25_000, method="mobile_money", phone="+255712345678",
            ...     idempotency_key="order-8451-pay-1",
            ... )
        """
        opts = _create(
            amount=amount,
            method=method,
            currency=currency,
            phone=phone,
            network=network,
            expires_at=expires_at,
            customer_id=customer_id,
            merchant_reference=merchant_reference,
            description=description,
            statement_descriptor=statement_descriptor,
            return_url=return_url,
            cancel_url=cancel_url,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return await self._client._request(opts, _parse)

    async def list(self, *, limit: int | None = None, cursor: str | None = None) -> Page[Payment]:
        """List payments, newest first.

        Example:
            >>> page = await client.payments.list(limit=50)
        """
        return await self._client._request(_list(limit, cursor), _parse_page)

    async def list_all(self, *, page_size: int = 100) -> AsyncIterator[Payment]:
        """Iterate over every payment, fetching pages lazily.

        Example:
            >>> async for payment in client.payments.list_all():
            ...     print(payment.id)
        """
        cursor: str | None = None
        while True:
            page = await self.list(limit=page_size, cursor=cursor)
            for item in page.data:
                yield item
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    async def retrieve(self, payment_id: str) -> Payment:
        """Retrieve a payment by ``pi_`` id.

        Example:
            >>> payment = await client.payments.retrieve("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
        """
        return await self._client._request(_retrieve(payment_id), _parse)

    async def amend(
        self, payment_id: str, *, amount: v.AmountLike, currency: str = "TZS"
    ) -> Payment:
        """Change the total of a QR payment that is ``AWAITING_CUSTOMER``.

        Example:
            >>> await client.payments.amend("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK", amount=30_000)
        """
        return await self._client._request(_amend(payment_id, amount, currency), _parse)

    async def cancel(self, payment_id: str) -> Payment:
        """Cancel a pending payment. See the caution on :meth:`Payments.cancel`.

        Example:
            >>> await client.payments.cancel("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
        """
        return await self._client._request(_cancel(payment_id), _parse)

    async def inquire(self, payment_id: str) -> Payment:
        """Force a status check for a payment that looks stuck.

        Example:
            >>> await client.payments.inquire("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
        """
        return await self._client._request(_inquire(payment_id), _parse)
