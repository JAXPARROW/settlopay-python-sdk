"""The async client shares builders with the sync one; check the async plumbing."""

from __future__ import annotations

import httpx
import pytest
import respx

from settlopay import AsyncSettloPay, NotFoundError, ServiceUnavailableError

from ._helpers import (
    BASE,
    CS,
    DST,
    PI,
    PO,
    REF,
    beneficiary_json,
    body_of,
    error_json,
    money,
    payment_json,
    payout_json,
)


async def test_create_payment(respx_mock: respx.MockRouter, aclient: AsyncSettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(201, json=payment_json())
    )
    payment = await aclient.payments.create(
        amount=25000, method="mobile_money", phone="+255712345678", idempotency_key="k1"
    )
    assert payment.id == PI
    assert body_of(route.calls.last.request)["method_data"] == {"phone": "+255712345678"}


async def test_async_pagination(respx_mock: respx.MockRouter, aclient: AsyncSettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/payouts").mock(
        side_effect=[
            httpx.Response(200, json={"data": [payout_json(id="po_A")], "next_cursor": "n"}),
            httpx.Response(200, json={"data": [], "next_cursor": None}),
        ]
    )
    ids = [p.id async for p in aclient.payouts.list_all()]
    assert ids == ["po_A"]


async def test_async_retry_then_success(
    respx_mock: respx.MockRouter, aclient: AsyncSettloPay
) -> None:
    route = respx_mock.get(f"{BASE}/v1/balance").mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(200, json={"amount": money(5)})]
    )
    balance = await aclient.balance.retrieve()
    assert balance.amount.currency == "TZS"
    assert route.call_count == 2


async def test_async_errors(respx_mock: respx.MockRouter, aclient: AsyncSettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/payouts/{PO}").mock(
        return_value=httpx.Response(404, json=error_json("resource_missing"))
    )
    respx_mock.post(f"{BASE}/v1/payouts").mock(
        return_value=httpx.Response(503, json=error_json("try_later"))
    )
    with pytest.raises(NotFoundError):
        await aclient.payouts.retrieve(PO)
    with pytest.raises(ServiceUnavailableError):
        await aclient.payouts.create(amount=100, idempotency_key="w")


async def test_async_surface(respx_mock: respx.MockRouter, aclient: AsyncSettloPay) -> None:
    """Smoke every async method once so none drifts from its sync twin."""
    respx_mock.get(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(200, json={"data": [payment_json()]})
    )
    respx_mock.get(f"{BASE}/v1/payments/{PI}").mock(
        return_value=httpx.Response(200, json=payment_json())
    )
    respx_mock.patch(f"{BASE}/v1/payments/{PI}").mock(
        return_value=httpx.Response(200, json=payment_json())
    )
    for action in ("cancel", "inquire"):
        respx_mock.post(f"{BASE}/v1/payments/{PI}/{action}").mock(
            return_value=httpx.Response(200, json=payment_json())
        )
    respx_mock.post(f"{BASE}/v1/refunds").mock(
        return_value=httpx.Response(201, json={"id": REF, "state": "PENDING"})
    )
    respx_mock.get(f"{BASE}/v1/refunds/{REF}").mock(
        return_value=httpx.Response(200, json={"id": REF, "state": "SUCCEEDED"})
    )
    respx_mock.post(f"{BASE}/v1/payouts/quote").mock(
        return_value=httpx.Response(
            200,
            json={k: money(1) for k in ("amount", "fee", "vat", "total_debit")},
        )
    )
    respx_mock.get(f"{BASE}/v1/payouts").mock(return_value=httpx.Response(200, json={"data": []}))
    respx_mock.get(f"{BASE}/v1/payout-limits").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"{BASE}/v1/beneficiaries").mock(
        return_value=httpx.Response(200, json={"data": [beneficiary_json()]})
    )
    respx_mock.post(f"{BASE}/v1/beneficiaries").mock(
        return_value=httpx.Response(201, json=beneficiary_json())
    )
    respx_mock.get(f"{BASE}/v1/beneficiaries/{DST}").mock(
        return_value=httpx.Response(200, json=beneficiary_json())
    )
    for action in ("confirm", "resend_code"):
        respx_mock.post(f"{BASE}/v1/beneficiaries/{DST}/{action}").mock(
            return_value=httpx.Response(200, json=beneficiary_json())
        )
    respx_mock.delete(f"{BASE}/v1/beneficiaries/{DST}").mock(
        return_value=httpx.Response(200, json={"id": DST, "retired": True})
    )
    session = {"id": CS, "state": "CREATED"}
    respx_mock.post(f"{BASE}/v1/checkout/sessions").mock(
        return_value=httpx.Response(201, json=session)
    )
    respx_mock.get(f"{BASE}/v1/checkout/sessions/{CS}").mock(
        return_value=httpx.Response(200, json=session)
    )
    respx_mock.post(f"{BASE}/v1/checkout/sessions/{CS}/cancel").mock(
        return_value=httpx.Response(200, json=session)
    )
    qr = {"id": "qr_1", "state": "PENDING"}
    respx_mock.get(f"{BASE}/v1/qr_code").mock(return_value=httpx.Response(200, json=qr))
    respx_mock.post(f"{BASE}/v1/qr_code").mock(return_value=httpx.Response(201, json=qr))

    assert (await aclient.payments.list()).data
    assert [p.id async for p in aclient.payments.list_all()] == [PI]
    await aclient.payments.retrieve(PI)
    await aclient.payments.amend(PI, amount=100)
    await aclient.payments.cancel(PI)
    await aclient.payments.inquire(PI)
    await aclient.refunds.create(payment_intent=PI, reason="other")
    await aclient.refunds.retrieve(REF)
    await aclient.payouts.quote()
    await aclient.payouts.list()
    assert await aclient.payouts.limits() == []
    assert [b.id async for b in aclient.beneficiaries.list_all()] == [DST]
    await aclient.beneficiaries.list()
    await aclient.beneficiaries.create(kind="BANK", fsp_code="CRDBTZ", account_number="0150123456")
    await aclient.beneficiaries.retrieve(DST)
    await aclient.beneficiaries.confirm(DST, code="000111")
    await aclient.beneficiaries.resend_code(DST)
    assert (await aclient.beneficiaries.delete(DST)).retired
    await aclient.checkout_sessions.create(amount=100)
    await aclient.checkout_sessions.retrieve(CS)
    await aclient.checkout_sessions.cancel(CS)
    await aclient.qr_code.retrieve()
    await aclient.qr_code.request()
