from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._client import AsyncSettloPay, SettloPay


class SyncResource:
    def __init__(self, client: SettloPay) -> None:
        self._client = client


class AsyncResource:
    def __init__(self, client: AsyncSettloPay) -> None:
        self._client = client
