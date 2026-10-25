"""``/v1/balance``."""

from __future__ import annotations

from .._base import RequestOptions, model_parser
from ..models import Balance
from ._base import AsyncResource, SyncResource

_RETRIEVE = RequestOptions("GET", "/v1/balance", retry_safe=True)
_parse = model_parser(Balance)


class BalanceResource(SyncResource):
    """Access as ``client.balance``."""

    def retrieve(self) -> Balance:
        """Retrieve your available balance (TZS).

        Example:
            >>> client.balance.retrieve().amount.value
            Decimal('1250000.00')
        """
        return self._client._request(_RETRIEVE, _parse)


class AsyncBalanceResource(AsyncResource):
    """Access as ``client.balance``."""

    async def retrieve(self) -> Balance:
        """Retrieve your available balance (TZS).

        Example:
            >>> balance = await client.balance.retrieve()
        """
        return await self._client._request(_RETRIEVE, _parse)
