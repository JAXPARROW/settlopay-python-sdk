"""Live smoke test against the real Settlo Pay API.

Settlo has NO sandbox: sk_test_ keys move real money too. Everything here is
read-only by default: balance, lists, limits, and a payout *quote*, which creates
nothing. Run with:

    SETTLO_API_KEY=sk_... SETTLO_RUN_LIVE=1 pytest -m live tests/live -v

The optional collection test asks the phone in SETTLO_LIVE_PHONE to pay (a prompt
appears on the phone). Money only moves if that prompt is approved. It needs a
second opt-in:

    SETTLO_LIVE_PHONE=+2557XXXXXXXX SETTLO_ALLOW_MONEY_MOVEMENT=1 ...

Nothing in this file creates payouts, refunds or beneficiaries.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

from settlopay import NotFoundError, PermissionDeniedError, SettloPay

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (os.environ.get("SETTLO_API_KEY") and os.environ.get("SETTLO_RUN_LIVE") == "1"),
        reason="live tests need SETTLO_API_KEY and SETTLO_RUN_LIVE=1",
    ),
]


@pytest.fixture(scope="module")
def live() -> Iterator[SettloPay]:
    with SettloPay() as client:  # key comes from SETTLO_API_KEY only
        yield client


def test_auth_and_balance(live: SettloPay) -> None:
    balance = live.balance.retrieve()
    assert balance.amount.currency == "TZS"


def test_list_payments(live: SettloPay) -> None:
    page = live.payments.list(limit=1)
    assert isinstance(page.data, list)
    if page.data:
        assert live.payments.retrieve(page.data[0].id).id == page.data[0].id


def test_list_payouts_and_limits(live: SettloPay) -> None:
    live.payouts.list(limit=1)
    for row in live.payouts.limits():
        assert row.purpose


def test_payout_quote_creates_nothing(live: SettloPay) -> None:
    quote = live.payouts.quote(amount=1000)
    assert quote.total_debit.value >= quote.amount.value


def test_beneficiaries_read(live: SettloPay) -> None:
    try:
        live.beneficiaries.list(limit=1)
    except PermissionDeniedError:
        pytest.skip("key lacks beneficiaries:read scope")


def test_qr_code_read(live: SettloPay) -> None:
    try:
        live.qr_code.retrieve()
    except (NotFoundError, PermissionDeniedError) as exc:
        pytest.skip(f"no QR code / scope: {exc.code}")


@pytest.mark.skipif(
    not (
        os.environ.get("SETTLO_LIVE_PHONE") and os.environ.get("SETTLO_ALLOW_MONEY_MOVEMENT") == "1"
    ),
    reason="collection test needs SETTLO_LIVE_PHONE and SETTLO_ALLOW_MONEY_MOVEMENT=1",
)
def test_mobile_money_collection_prompt(live: SettloPay) -> None:
    """Sends a payment prompt to your own phone. Ignore or decline it and it expires."""
    amount = int(os.environ.get("SETTLO_LIVE_AMOUNT", "500"))
    key = f"sdk-smoke-{uuid.uuid4()}"
    payment = live.payments.create(
        amount=amount,
        method="mobile_money",
        phone=os.environ["SETTLO_LIVE_PHONE"],
        merchant_reference="sdk-smoke-test",
        idempotency_key=key,
    )
    assert payment.id.startswith("pi_")
    # Replaying the same key must return the same payment, not create a second one.
    again = live.payments.create(
        amount=amount,
        method="mobile_money",
        phone=os.environ["SETTLO_LIVE_PHONE"],
        merchant_reference="sdk-smoke-test",
        idempotency_key=key,
    )
    assert again.id == payment.id
    assert live.payments.retrieve(payment.id).id == payment.id
