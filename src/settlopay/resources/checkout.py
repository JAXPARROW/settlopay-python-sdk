"""``/v1/checkout/sessions``: Settlo-hosted payment pages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .. import _validation as v
from .._base import RequestOptions, model_parser, path
from ..enums import PaymentMethod
from ..models import CheckoutSession
from ._base import AsyncResource, SyncResource

_PREFIX = "cs_"


def _create(
    *,
    amount: v.AmountLike,
    currency: str,
    merchant_reference: str | None,
    description: str | None,
    customer_email: str | None,
    customer_phone: str | None,
    customer_name: str | None,
    return_url: str | None,
    cancel_url: str | None,
    allowed_methods: Sequence[PaymentMethod | str] | None,
    metadata: Mapping[str, Any] | None,
    idempotency_key: str | None,
) -> RequestOptions:
    body = v.compact(
        amount=v.money(v.amount(amount), v.currency(currency)),
        merchant_reference=v.optional_text(
            merchant_reference, param="merchant_reference", max_len=120
        ),
        description=v.optional_text(description, param="description", max_len=1000),
        customer_email=None
        if customer_email is None
        else v.email(customer_email, param="customer_email"),
        customer_phone=None
        if customer_phone is None
        else v.e164_phone(customer_phone, param="customer_phone"),
        customer_name=v.optional_text(customer_name, param="customer_name", max_len=140),
        return_url=v.optional_url(return_url, param="return_url"),
        cancel_url=v.optional_url(cancel_url, param="cancel_url"),
        allowed_methods=v.token_list(allowed_methods, param="allowed_methods"),
        metadata=v.metadata(metadata),
    )
    return RequestOptions(
        "POST",
        "/v1/checkout/sessions",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="checkout"),
        retry_safe=True,
    )


def _retrieve(session_id: str) -> RequestOptions:
    sid = v.resource_id(session_id, _PREFIX, param="session_id")
    return RequestOptions("GET", path("/v1/checkout/sessions/{}", sid), retry_safe=True)


def _cancel(session_id: str) -> RequestOptions:
    sid = v.resource_id(session_id, _PREFIX, param="session_id")
    return RequestOptions("POST", path("/v1/checkout/sessions/{}/cancel", sid))


_parse = model_parser(CheckoutSession)


class CheckoutSessions(SyncResource):
    """Hosted checkout. Access as ``client.checkout_sessions``."""

    def create(
        self,
        *,
        amount: v.AmountLike,
        currency: str = "TZS",
        merchant_reference: str | None = None,
        description: str | None = None,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        customer_name: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        allowed_methods: Sequence[PaymentMethod | str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        """Create a hosted checkout page and redirect the customer to ``session.url``.

        Sessions expire after 30 minutes. Each attempt on the page is a payment
        carrying the session's ``merchant_reference``.

        Args:
            amount: Amount to collect.
            currency: Currency code, ``"TZS"``.
            merchant_reference: Your order id (max 120).
            description: Shown on the hosted page.
            customer_email: Prefill.
            customer_phone: Prefill, E.164.
            customer_name: Prefill.
            return_url: Where to send the customer after paying.
            cancel_url: Where to send the customer if they cancel.
            allowed_methods: Limit the offered methods, e.g. ``["mobile_money"]``.
            metadata: Arbitrary JSON object.
            idempotency_key: Generated if omitted.

        Example:
            >>> session = client.checkout_sessions.create(
            ...     amount=25_000,
            ...     merchant_reference="ORD-8451",
            ...     return_url="https://shop.example/orders/8451",
            ... )
            >>> redirect(session.url)
        """
        opts = _create(
            amount=amount,
            currency=currency,
            merchant_reference=merchant_reference,
            description=description,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            return_url=return_url,
            cancel_url=cancel_url,
            allowed_methods=allowed_methods,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return self._client._request(opts, _parse)

    def retrieve(self, session_id: str) -> CheckoutSession:
        """Retrieve a checkout session by ``cs_`` id.

        Example:
            >>> client.checkout_sessions.retrieve("cs_01J9X6F0G1H2").state
            'CREATED'
        """
        return self._client._request(_retrieve(session_id), _parse)

    def cancel(self, session_id: str) -> CheckoutSession:
        """Cancel a checkout session.

        Example:
            >>> client.checkout_sessions.cancel("cs_01J9X6F0G1H2")
        """
        return self._client._request(_cancel(session_id), _parse)


class AsyncCheckoutSessions(AsyncResource):
    """Async variant of :class:`CheckoutSessions`."""

    async def create(
        self,
        *,
        amount: v.AmountLike,
        currency: str = "TZS",
        merchant_reference: str | None = None,
        description: str | None = None,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        customer_name: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        allowed_methods: Sequence[PaymentMethod | str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> CheckoutSession:
        """Create a hosted checkout page. See :meth:`CheckoutSessions.create`.

        Example:
            >>> session = await client.checkout_sessions.create(amount=25_000)
        """
        opts = _create(
            amount=amount,
            currency=currency,
            merchant_reference=merchant_reference,
            description=description,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_name=customer_name,
            return_url=return_url,
            cancel_url=cancel_url,
            allowed_methods=allowed_methods,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return await self._client._request(opts, _parse)

    async def retrieve(self, session_id: str) -> CheckoutSession:
        """Retrieve a checkout session by ``cs_`` id.

        Example:
            >>> session = await client.checkout_sessions.retrieve("cs_01J9X6F0G1H2")
        """
        return await self._client._request(_retrieve(session_id), _parse)

    async def cancel(self, session_id: str) -> CheckoutSession:
        """Cancel a checkout session.

        Example:
            >>> await client.checkout_sessions.cancel("cs_01J9X6F0G1H2")
        """
        return await self._client._request(_cancel(session_id), _parse)
