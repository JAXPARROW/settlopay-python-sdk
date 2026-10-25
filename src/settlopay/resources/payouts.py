"""``/v1/payouts``: send money to your settlement account or a beneficiary."""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any

from pydantic import TypeAdapter

from .. import _validation as v
from .._base import RequestOptions, model_parser, path
from ..enums import PayoutState
from ..models import Page, Payout, PayoutLimit, PayoutQuote
from ._base import AsyncResource, SyncResource

_STATES = frozenset(s.value for s in PayoutState)
_PAYOUT_CURRENCIES = frozenset({"TZS"})


def _destination(destination_id: str | None) -> str | None:
    if destination_id is None:
        return None
    return v.resource_id(destination_id, "dst_", param="destination_id")


def _create(
    *,
    amount: v.AmountLike,
    destination_id: str | None,
    description: str | None,
    merchant_reference: str | None,
    idempotency_key: str | None,
) -> RequestOptions:
    body = v.compact(
        amount=v.money(v.amount(amount), "TZS"),
        destination_id=_destination(destination_id),
        description=v.optional_text(description, param="description", max_len=200),
        merchant_reference=v.optional_text(
            merchant_reference, param="merchant_reference", max_len=120
        ),
    )
    # Retrying with the same key after a timeout is documented as safe; a 503 is
    # never retried (Settlo wants a fresh key), see RetryPolicy.
    return RequestOptions(
        "POST",
        "/v1/payouts",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="payout"),
        retry_safe=True,
    )


def _quote(amount: v.AmountLike | None, destination_id: str | None) -> RequestOptions:
    body = v.compact(
        currency="TZS",
        amount=None if amount is None else v.number(v.amount(amount)),
        destination_id=_destination(destination_id),
    )
    return RequestOptions("POST", "/v1/payouts/quote", body=body, retry_safe=True)


def _list(state: str | None, limit: int | None, cursor: str | None) -> RequestOptions:
    params = {
        "state": v.optional_choice(state, _STATES, param="state"),
        "limit": v.page_limit(limit),
        "cursor": v.cursor(cursor),
    }
    return RequestOptions("GET", "/v1/payouts", params=params, retry_safe=True)


def _retrieve(payout_id: str) -> RequestOptions:
    pid = v.resource_id(payout_id, "po_", param="payout_id")
    return RequestOptions("GET", path("/v1/payouts/{}", pid), retry_safe=True)


_LIMITS = RequestOptions("GET", "/v1/payout-limits", retry_safe=True)
_limits_adapter = TypeAdapter(builtins.list[PayoutLimit])


def _parse_limits(data: Any) -> builtins.list[PayoutLimit]:
    # The live API wraps rows as {"limits": [...]}; tolerate {"data": [...]} and a bare list.
    rows = data
    if isinstance(data, dict):
        rows = data.get("limits", data.get("data", data))
    return _limits_adapter.validate_python(rows)


_parse = model_parser(Payout)
_parse_quote = model_parser(PayoutQuote)
_parse_page = model_parser(Page[Payout])


class Payouts(SyncResource):
    """Send and track payouts. Access as ``client.payouts``."""

    def create(
        self,
        *,
        amount: v.AmountLike,
        destination_id: str | None = None,
        description: str | None = None,
        merchant_reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> Payout:
        """Send a payout in TZS. Your balance is debited ``amount`` plus fee and VAT.

        Omit ``destination_id`` to pay your settlement account. Call :meth:`quote`
        first to see the total debit.

        Pass your own ``idempotency_key`` derived from your withdrawal record: if the
        process dies mid-request, re-sending with the same key cannot pay twice. On
        :class:`~settlopay.ServiceUnavailableError` (``503 try_later``) nothing was
        sent; retry with a **new** key.

        Args:
            amount: Amount the destination receives, in TZS.
            destination_id: An active beneficiary's ``dst_`` id.
            description: Max 200 characters.
            merchant_reference: Your reference (max 120).
            idempotency_key: Max 120 chars. Generated if omitted.

        Example:
            >>> payout = client.payouts.create(
            ...     amount=50_000,
            ...     destination_id="dst_01J9X5A1B2C3",
            ...     idempotency_key="withdrawal-397",
            ... )
            >>> payout.state
            'REQUESTED'
        """
        opts = _create(
            amount=amount,
            destination_id=destination_id,
            description=description,
            merchant_reference=merchant_reference,
            idempotency_key=idempotency_key,
        )
        return self._client._request(opts, _parse)

    def quote(
        self, *, amount: v.AmountLike | None = None, destination_id: str | None = None
    ) -> PayoutQuote:
        """Price a payout without creating it. Omit ``amount`` for the maximum sendable.

        A quote does not check your balance, reserve the price or count toward limits.

        Example:
            >>> quote = client.payouts.quote(amount=50_000)
            >>> quote.total_debit.value
            Decimal('51180.00')
        """
        return self._client._request(_quote(amount, destination_id), _parse_quote)

    def list(
        self,
        *,
        state: PayoutState | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Payout]:
        """List payouts, newest first, optionally filtered by ``state``.

        Example:
            >>> page = client.payouts.list(state="SUCCEEDED", limit=20)
        """
        return self._client._request(_list(state, limit, cursor), _parse_page)

    def list_all(
        self, *, state: PayoutState | str | None = None, page_size: int = 100
    ) -> Iterator[Payout]:
        """Iterate over every payout, fetching pages lazily.

        Example:
            >>> failed = [p for p in client.payouts.list_all(state="FAILED_REVERSED")]
        """
        cursor: str | None = None
        while True:
            page = self.list(state=state, limit=page_size, cursor=cursor)
            yield from page.data
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    def retrieve(self, payout_id: str) -> Payout:
        """Retrieve a payout by ``po_`` id.

        Example:
            >>> client.payouts.retrieve("po_01J9X5C7D8E9").state
            'SUCCEEDED'
        """
        return self._client._request(_retrieve(payout_id), _parse)

    def limits(self) -> builtins.list[PayoutLimit]:
        """Retrieve your payout limits, one row per purpose and destination kind.

        Example:
            >>> for row in client.payouts.limits():
            ...     print(row.purpose, row.destination_kind, row.daily_cap)
        """
        return self._client._request(_LIMITS, _parse_limits)


class AsyncPayouts(AsyncResource):
    """Async variant of :class:`Payouts`. Access as ``client.payouts``."""

    async def create(
        self,
        *,
        amount: v.AmountLike,
        destination_id: str | None = None,
        description: str | None = None,
        merchant_reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> Payout:
        """Send a payout in TZS. See :meth:`Payouts.create` for idempotency guidance.

        Example:
            >>> payout = await client.payouts.create(
            ...     amount=50_000, idempotency_key="withdrawal-397",
            ... )
        """
        opts = _create(
            amount=amount,
            destination_id=destination_id,
            description=description,
            merchant_reference=merchant_reference,
            idempotency_key=idempotency_key,
        )
        return await self._client._request(opts, _parse)

    async def quote(
        self, *, amount: v.AmountLike | None = None, destination_id: str | None = None
    ) -> PayoutQuote:
        """Price a payout without creating it.

        Example:
            >>> quote = await client.payouts.quote(amount=50_000)
        """
        return await self._client._request(_quote(amount, destination_id), _parse_quote)

    async def list(
        self,
        *,
        state: PayoutState | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Payout]:
        """List payouts, newest first.

        Example:
            >>> page = await client.payouts.list(state="SUCCEEDED")
        """
        return await self._client._request(_list(state, limit, cursor), _parse_page)

    async def list_all(
        self, *, state: PayoutState | str | None = None, page_size: int = 100
    ) -> AsyncIterator[Payout]:
        """Iterate over every payout, fetching pages lazily.

        Example:
            >>> async for payout in client.payouts.list_all():
            ...     print(payout.id)
        """
        cursor: str | None = None
        while True:
            page = await self.list(state=state, limit=page_size, cursor=cursor)
            for item in page.data:
                yield item
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    async def retrieve(self, payout_id: str) -> Payout:
        """Retrieve a payout by ``po_`` id.

        Example:
            >>> payout = await client.payouts.retrieve("po_01J9X5C7D8E9")
        """
        return await self._client._request(_retrieve(payout_id), _parse)

    async def limits(self) -> builtins.list[PayoutLimit]:
        """Retrieve your payout limits.

        Example:
            >>> rows = await client.payouts.limits()
        """
        return await self._client._request(_LIMITS, _parse_limits)
