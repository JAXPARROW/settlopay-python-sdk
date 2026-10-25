"""``/v1/beneficiaries``: saved payout destinations, confirmed by a one-time code."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from .. import _validation as v
from .._base import RequestOptions, model_parser, path
from ..enums import BeneficiaryKind, BeneficiaryStatus
from ..models import Beneficiary, DeletedBeneficiary, Page
from ._base import AsyncResource, SyncResource

_KINDS = frozenset(k.value for k in BeneficiaryKind)
_STATUSES = frozenset(s.value for s in BeneficiaryStatus)
_PREFIX = "dst_"


def _id(beneficiary_id: str) -> str:
    return v.resource_id(beneficiary_id, _PREFIX, param="beneficiary_id")


def _list(status: str | None, limit: int | None, cursor: str | None) -> RequestOptions:
    params = {
        "status": v.optional_choice(status, _STATUSES, param="status"),
        "limit": v.page_limit(limit),
        "cursor": v.cursor(cursor),
    }
    return RequestOptions("GET", "/v1/beneficiaries", params=params, retry_safe=True)


def _create(
    *,
    kind: str,
    fsp_code: str,
    account_number: str,
    account_name: str | None,
    label: str | None,
    idempotency_key: str | None,
) -> RequestOptions:
    kind = v.choice(kind, _KINDS, param="kind")
    body = v.compact(
        kind=kind,
        fsp_code=v.fsp_code(fsp_code),
        account_number=v.account_number(account_number, kind=kind),
        account_name=v.optional_text(account_name, param="account_name", max_len=140),
        label=v.optional_text(label, param="label", max_len=60),
    )
    return RequestOptions(
        "POST",
        "/v1/beneficiaries",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="beneficiary"),
        retry_safe=True,
    )


def _retrieve(beneficiary_id: str) -> RequestOptions:
    return RequestOptions("GET", path("/v1/beneficiaries/{}", _id(beneficiary_id)), retry_safe=True)


def _confirm(beneficiary_id: str, code: str) -> RequestOptions:
    # Not retried: each wrong attempt burns one of five tries.
    body = {"code": v.confirmation_code(code)}
    return RequestOptions(
        "POST", path("/v1/beneficiaries/{}/confirm", _id(beneficiary_id)), body=body
    )


def _resend(beneficiary_id: str, channel: str | None) -> RequestOptions:
    body = v.compact(channel=v.optional_choice(channel, {"sms"}, param="channel"))
    return RequestOptions(
        "POST", path("/v1/beneficiaries/{}/resend_code", _id(beneficiary_id)), body=body
    )


def _delete(beneficiary_id: str) -> RequestOptions:
    return RequestOptions("DELETE", path("/v1/beneficiaries/{}", _id(beneficiary_id)))


_parse = model_parser(Beneficiary)
_parse_page = model_parser(Page[Beneficiary])
_parse_deleted = model_parser(DeletedBeneficiary)


class Beneficiaries(SyncResource):
    """Manage payout beneficiaries. Access as ``client.beneficiaries``.

    Needs the ``beneficiaries:read`` / ``beneficiaries:write`` key scopes.
    """

    def list(
        self,
        *,
        status: BeneficiaryStatus | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Beneficiary]:
        """List beneficiaries, optionally filtered by ``status``.

        Example:
            >>> page = client.beneficiaries.list(status="active")
        """
        return self._client._request(_list(status, limit, cursor), _parse_page)

    def list_all(
        self, *, status: BeneficiaryStatus | str | None = None, page_size: int = 100
    ) -> Iterator[Beneficiary]:
        """Iterate over every beneficiary.

        Example:
            >>> names = [b.verified_name for b in client.beneficiaries.list_all()]
        """
        cursor: str | None = None
        while True:
            page = self.list(status=status, limit=page_size, cursor=cursor)
            yield from page.data
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    def create(
        self,
        *,
        kind: BeneficiaryKind | str,
        fsp_code: str,
        account_number: str,
        account_name: str | None = None,
        label: str | None = None,
        idempotency_key: str | None = None,
    ) -> Beneficiary:
        """Create a beneficiary. Settlo sends a 6-digit code to the account holder.

        Show :attr:`Beneficiary.verified_name` to the user, collect the code, then
        call :meth:`confirm`. A pending beneficiary cannot receive payouts.

        Args:
            kind: ``"MOMO"`` or ``"BANK"``.
            fsp_code: Network or bank code, e.g. ``"VODATZ"``, ``"CRDBTZ"``.
            account_number: MOMO: ``255`` + nine digits (no ``+``). BANK: 6-32 letters/digits.
            account_name: Only if the bank/network cannot return the holder's name (max 140).
            label: Your label (max 60).
            idempotency_key: Generated if omitted.

        Example:
            >>> dst = client.beneficiaries.create(
            ...     kind="MOMO", fsp_code="VODATZ", account_number="255712345678",
            ...     label="Supplier A",
            ... )
            >>> dst.status
            'pending_confirmation'
        """
        opts = _create(
            kind=kind,
            fsp_code=fsp_code,
            account_number=account_number,
            account_name=account_name,
            label=label,
            idempotency_key=idempotency_key,
        )
        return self._client._request(opts, _parse)

    def retrieve(self, beneficiary_id: str) -> Beneficiary:
        """Retrieve a beneficiary by ``dst_`` id.

        Example:
            >>> client.beneficiaries.retrieve("dst_01J9X5A1B2C3").status
            'active'
        """
        return self._client._request(_retrieve(beneficiary_id), _parse)

    def confirm(self, beneficiary_id: str, *, code: str) -> Beneficiary:
        """Confirm a pending beneficiary with the 6-digit code (valid 10 minutes, 5 tries).

        Example:
            >>> client.beneficiaries.confirm("dst_01J9X5A1B2C3", code="482913").status
            'active'
        """
        return self._client._request(_confirm(beneficiary_id, code), _parse)

    def resend_code(self, beneficiary_id: str, *, channel: str | None = None) -> Beneficiary:
        """Resend the confirmation code. ``channel="sms"`` forces SMS.

        Limited to once per minute and five per hour per beneficiary; beyond that a
        :class:`~settlopay.RateLimitError` (``confirmation_throttled``) is raised.

        Example:
            >>> client.beneficiaries.resend_code("dst_01J9X5A1B2C3", channel="sms")
        """
        return self._client._request(_resend(beneficiary_id, channel), _parse)

    def delete(self, beneficiary_id: str) -> DeletedBeneficiary:
        """Delete (retire) a beneficiary, including a pending one.

        Example:
            >>> client.beneficiaries.delete("dst_01J9X5A1B2C3").retired
            True
        """
        return self._client._request(_delete(beneficiary_id), _parse_deleted)


class AsyncBeneficiaries(AsyncResource):
    """Async variant of :class:`Beneficiaries`. Access as ``client.beneficiaries``."""

    async def list(
        self,
        *,
        status: BeneficiaryStatus | str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Beneficiary]:
        """List beneficiaries.

        Example:
            >>> page = await client.beneficiaries.list(status="active")
        """
        return await self._client._request(_list(status, limit, cursor), _parse_page)

    async def list_all(
        self, *, status: BeneficiaryStatus | str | None = None, page_size: int = 100
    ) -> AsyncIterator[Beneficiary]:
        """Iterate over every beneficiary.

        Example:
            >>> async for b in client.beneficiaries.list_all():
            ...     print(b.id)
        """
        cursor: str | None = None
        while True:
            page = await self.list(status=status, limit=page_size, cursor=cursor)
            for item in page.data:
                yield item
            if not page.data or not page.next_cursor:
                return
            cursor = page.next_cursor

    async def create(
        self,
        *,
        kind: BeneficiaryKind | str,
        fsp_code: str,
        account_number: str,
        account_name: str | None = None,
        label: str | None = None,
        idempotency_key: str | None = None,
    ) -> Beneficiary:
        """Create a beneficiary. See :meth:`Beneficiaries.create`.

        Example:
            >>> dst = await client.beneficiaries.create(
            ...     kind="BANK", fsp_code="CRDBTZ", account_number="0150123456789",
            ... )
        """
        opts = _create(
            kind=kind,
            fsp_code=fsp_code,
            account_number=account_number,
            account_name=account_name,
            label=label,
            idempotency_key=idempotency_key,
        )
        return await self._client._request(opts, _parse)

    async def retrieve(self, beneficiary_id: str) -> Beneficiary:
        """Retrieve a beneficiary by ``dst_`` id.

        Example:
            >>> dst = await client.beneficiaries.retrieve("dst_01J9X5A1B2C3")
        """
        return await self._client._request(_retrieve(beneficiary_id), _parse)

    async def confirm(self, beneficiary_id: str, *, code: str) -> Beneficiary:
        """Confirm a pending beneficiary with the 6-digit code.

        Example:
            >>> await client.beneficiaries.confirm("dst_01J9X5A1B2C3", code="482913")
        """
        return await self._client._request(_confirm(beneficiary_id, code), _parse)

    async def resend_code(self, beneficiary_id: str, *, channel: str | None = None) -> Beneficiary:
        """Resend the confirmation code.

        Example:
            >>> await client.beneficiaries.resend_code("dst_01J9X5A1B2C3")
        """
        return await self._client._request(_resend(beneficiary_id, channel), _parse)

    async def delete(self, beneficiary_id: str) -> DeletedBeneficiary:
        """Delete (retire) a beneficiary.

        Example:
            >>> await client.beneficiaries.delete("dst_01J9X5A1B2C3")
        """
        return await self._client._request(_delete(beneficiary_id), _parse_deleted)
