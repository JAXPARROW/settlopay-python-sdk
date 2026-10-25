"""``/v1/refunds``: return money for a succeeded payment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import _validation as v
from .._base import RequestOptions, model_parser, path
from ..enums import RefundReason
from ..models import Refund
from ._base import AsyncResource, SyncResource

_REASONS = frozenset(r.value for r in RefundReason)


def _create(
    *,
    payment_intent: str,
    reason: str,
    amount: v.AmountLike | None,
    currency: str,
    merchant_reference: str | None,
    description: str | None,
    metadata: Mapping[str, Any] | None,
    idempotency_key: str | None,
) -> RequestOptions:
    body = v.compact(
        payment_intent=v.resource_id(payment_intent, "pi_", param="payment_intent"),
        reason=v.choice(reason, _REASONS, param="reason"),
        amount=None if amount is None else v.money(v.amount(amount), v.currency(currency)),
        merchant_reference=v.optional_text(
            merchant_reference, param="merchant_reference", max_len=120
        ),
        description=v.optional_text(description, param="description", max_len=1000),
        metadata=v.metadata(metadata),
    )
    return RequestOptions(
        "POST",
        "/v1/refunds",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="refund"),
        retry_safe=True,
    )


def _retrieve(refund_id: str) -> RequestOptions:
    rid = v.resource_id(refund_id, "ref_", param="refund_id")
    return RequestOptions("GET", path("/v1/refunds/{}", rid), retry_safe=True)


_parse = model_parser(Refund)


class Refunds(SyncResource):
    """Refund payments. Access as ``client.refunds``."""

    def create(
        self,
        *,
        payment_intent: str,
        reason: RefundReason | str,
        amount: v.AmountLike | None = None,
        currency: str = "TZS",
        merchant_reference: str | None = None,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Refund:
        """Refund a ``SUCCEEDED`` / ``PARTIALLY_REFUNDED`` payment (within 30 days).

        Omit ``amount`` to refund everything still refundable. Settlo charges a fee
        (2%, minimum TZS 500, plus 18% VAT) to your balance on top of the refund.
        QR and payer-initiated payments cannot be refunded through the API.

        Args:
            payment_intent: The ``pi_`` id of the payment.
            reason: ``requested_by_customer``, ``duplicate``, ``fraudulent`` or ``other``.
            amount: Partial refund amount; defaults to the full refundable amount.
            currency: Currency of ``amount``.
            merchant_reference: Your reference (max 120).
            description: Internal description (not returned).
            metadata: Arbitrary JSON object (not returned).
            idempotency_key: Generated if omitted. Must not start with ``refund:``.

        Example:
            >>> refund = client.refunds.create(
            ...     payment_intent="pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK",
            ...     reason="requested_by_customer",
            ...     idempotency_key="refund-ORD-8451-1",
            ... )
        """
        opts = _create(
            payment_intent=payment_intent,
            reason=reason,
            amount=amount,
            currency=currency,
            merchant_reference=merchant_reference,
            description=description,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return self._client._request(opts, _parse)

    def retrieve(self, refund_id: str) -> Refund:
        """Retrieve a refund by ``ref_`` id.

        Example:
            >>> client.refunds.retrieve("ref_01J9X4QZ8M2N").state
            'SUCCEEDED'
        """
        return self._client._request(_retrieve(refund_id), _parse)


class AsyncRefunds(AsyncResource):
    """Async variant of :class:`Refunds`. Access as ``client.refunds``."""

    async def create(
        self,
        *,
        payment_intent: str,
        reason: RefundReason | str,
        amount: v.AmountLike | None = None,
        currency: str = "TZS",
        merchant_reference: str | None = None,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Refund:
        """Refund a payment. See :meth:`Refunds.create`.

        Example:
            >>> refund = await client.refunds.create(
            ...     payment_intent="pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK", reason="duplicate",
            ... )
        """
        opts = _create(
            payment_intent=payment_intent,
            reason=reason,
            amount=amount,
            currency=currency,
            merchant_reference=merchant_reference,
            description=description,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        return await self._client._request(opts, _parse)

    async def retrieve(self, refund_id: str) -> Refund:
        """Retrieve a refund by ``ref_`` id.

        Example:
            >>> refund = await client.refunds.retrieve("ref_01J9X4QZ8M2N")
        """
        return await self._client._request(_retrieve(refund_id), _parse)
