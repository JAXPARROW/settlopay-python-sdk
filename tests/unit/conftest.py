from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest

from settlopay import AsyncSettloPay, SettloPay

from ._helpers import FAKE_KEY, FAST_RETRY


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must never pick up a real key from the developer's shell."""
    monkeypatch.delenv("SETTLO_API_KEY", raising=False)


@pytest.fixture
def client() -> Iterator[SettloPay]:
    with SettloPay(FAKE_KEY, retry=FAST_RETRY) as c:
        c._sleep = lambda _seconds: None
        yield c


@pytest.fixture
async def aclient() -> AsyncIterator[AsyncSettloPay]:
    async def _no_sleep(_seconds: float) -> None:
        return None

    async with AsyncSettloPay(FAKE_KEY, retry=FAST_RETRY) as c:
        c._sleep = _no_sleep
        yield c
