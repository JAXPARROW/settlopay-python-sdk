"""``/v1/qr_code``: the account's printable (static) QR code."""

from __future__ import annotations

from .. import _validation as v
from .._base import RequestOptions, model_parser
from ..models import QrCode
from ._base import AsyncResource, SyncResource

_RETRIEVE = RequestOptions("GET", "/v1/qr_code", retry_safe=True)


def _request(label: str | None, idempotency_key: str | None) -> RequestOptions:
    body = v.compact(label=v.optional_text(label, param="label", max_len=60))
    return RequestOptions(
        "POST",
        "/v1/qr_code",
        body=body,
        idempotency_key=v.idempotency_key(idempotency_key, scope="qr"),
        retry_safe=True,
    )


_parse = model_parser(QrCode)


class QrCodeResource(SyncResource):
    """Access as ``client.qr_code``. Needs the ``qr_code:read`` / ``qr_code:write`` scopes."""

    def retrieve(self) -> QrCode:
        """Retrieve your QR code. Raises :class:`~settlopay.NotFoundError` if none exists.

        Example:
            >>> qr = client.qr_code.retrieve()
            >>> qr.image.svg if qr.state == "ACTIVE" else qr.state
        """
        return self._client._request(_RETRIEVE, _parse)

    def request(self, *, label: str | None = None, idempotency_key: str | None = None) -> QrCode:
        """Request a QR code (or retry a ``FAILED`` one). Returns the existing code if
        one is already ``PENDING`` or ``ACTIVE``.

        Example:
            >>> qr = client.qr_code.request(label="Main counter")
            >>> qr.state
            'PENDING'
        """
        return self._client._request(_request(label, idempotency_key), _parse)


class AsyncQrCodeResource(AsyncResource):
    """Async variant of :class:`QrCodeResource`."""

    async def retrieve(self) -> QrCode:
        """Retrieve your QR code.

        Example:
            >>> qr = await client.qr_code.retrieve()
        """
        return await self._client._request(_RETRIEVE, _parse)

    async def request(
        self, *, label: str | None = None, idempotency_key: str | None = None
    ) -> QrCode:
        """Request a QR code.

        Example:
            >>> qr = await client.qr_code.request(label="Main counter")
        """
        return await self._client._request(_request(label, idempotency_key), _parse)
