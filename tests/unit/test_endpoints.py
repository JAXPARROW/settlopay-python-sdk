"""Request shape and response parsing for every endpoint (sync client)."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from settlopay import Page, Payment, PaymentState, SettloPay, UnexpectedResponseError

from ._helpers import (
    BASE,
    CS,
    DST,
    PI,
    PO,
    REF,
    beneficiary_json,
    body_of,
    money,
    payment_json,
    payout_json,
)

# ---------------------------------------------------------------- payments


def test_create_mobile_money_payment(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(201, json=payment_json(unknown_future_field=1))
    )
    payment = client.payments.create(
        amount=25000,
        method="mobile_money",
        phone="+255712345678",
        network="vodacom",
        merchant_reference="ORD-8451",
        metadata={"order": 8451},
        idempotency_key="order-8451-pay-1",
    )
    request = route.calls.last.request
    assert request.headers["Idempotency-Key"] == "order-8451-pay-1"
    assert request.headers["Content-Type"] == "application/json"
    assert body_of(request) == {
        "amount": {"value": 25000, "currency": "TZS"},
        "method": "mobile_money",
        "method_data": {"phone": "+255712345678", "network": "vodacom"},
        "merchant_reference": "ORD-8451",
        "metadata": {"order": 8451},
    }
    assert isinstance(payment, Payment)
    assert payment.state == PaymentState.PENDING_AUTH
    assert payment.amount is not None
    assert payment.amount.value == Decimal("25000.0")
    assert payment.next_action is not None
    assert payment.next_action.type == "await_mobile_prompt"
    assert payment.model_extra == {"unknown_future_field": 1}
    assert not payment.is_final
    assert not payment.succeeded


def test_create_generates_idempotency_key(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(
            201, json=payment_json(method="bank", state="AWAITING_CUSTOMER")
        )
    )
    client.payments.create(amount=1000, method="bank")
    assert route.calls.last.request.headers["Idempotency-Key"].startswith("payment-")


def test_blocked_payment_is_returned_not_raised(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    respx_mock.post(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(201, json=payment_json(state="BLOCKED"))
    )
    payment = client.payments.create(amount=1000, method="mobile_money", phone="+255712345678")
    assert payment.is_final
    assert not payment.succeeded


def test_list_and_paginate_payments(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/payments").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": [payment_json(id="pi_A1")], "next_cursor": "c1", "has_more": True},
            ),
            httpx.Response(
                200,
                json={"data": [payment_json(id="pi_B2")], "next_cursor": None, "has_more": False},
            ),
        ]
    )
    ids = [p.id for p in client.payments.list_all(page_size=1)]
    assert ids == ["pi_A1", "pi_B2"]
    assert route.calls[0].request.url.params["limit"] == "1"
    assert "cursor" not in route.calls[0].request.url.params
    assert route.calls[1].request.url.params["cursor"] == "c1"


def test_list_returns_page(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(200, json={"data": [], "next_cursor": None, "has_more": False})
    )
    page = client.payments.list(limit=5)
    assert isinstance(page, Page)
    assert page.data == []


@pytest.mark.parametrize(
    ("call", "method", "url"),
    [
        (lambda c: c.payments.retrieve(PI), "GET", f"/v1/payments/{PI}"),
        (lambda c: c.payments.cancel(PI), "POST", f"/v1/payments/{PI}/cancel"),
        (lambda c: c.payments.inquire(PI), "POST", f"/v1/payments/{PI}/inquire"),
    ],
)
def test_payment_actions(
    respx_mock: respx.MockRouter, client: SettloPay, call: object, method: str, url: str
) -> None:
    route = respx_mock.route(method=method, url=BASE + url).mock(
        return_value=httpx.Response(200, json=payment_json())
    )
    call(client)  # type: ignore[operator]
    assert route.called


def test_amend_qr_payment(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.patch(f"{BASE}/v1/payments/{PI}").mock(
        return_value=httpx.Response(200, json=payment_json(method="qr", state="AWAITING_CUSTOMER"))
    )
    client.payments.amend(PI, amount=30000)
    assert body_of(route.calls.last.request) == {"amount": {"value": 30000, "currency": "TZS"}}


# ---------------------------------------------------------------- refunds


def test_create_refund(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/refunds").mock(
        return_value=httpx.Response(
            201,
            json={"id": REF, "object": "refund", "state": "PENDING", "payment_intent": PI},
        )
    )
    refund = client.refunds.create(
        payment_intent=PI, reason="duplicate", amount="5000.50", idempotency_key="refund-ORD-1"
    )
    assert body_of(route.calls.last.request) == {
        "payment_intent": PI,
        "reason": "duplicate",
        "amount": {"value": 5000.5, "currency": "TZS"},
    }
    assert refund.state == "PENDING"


def test_retrieve_refund(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/refunds/{REF}").mock(
        return_value=httpx.Response(200, json={"id": REF, "state": "SUCCEEDED"})
    )
    assert client.refunds.retrieve(REF).state == "SUCCEEDED"


# ---------------------------------------------------------------- payouts


def test_create_payout(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/payouts").mock(
        return_value=httpx.Response(201, json=payout_json())
    )
    payout = client.payouts.create(
        amount=50000, destination_id=DST, merchant_reference="W-397", idempotency_key="w-397"
    )
    assert body_of(route.calls.last.request) == {
        "amount": {"value": 50000, "currency": "TZS"},
        "destination_id": DST,
        "merchant_reference": "W-397",
    }
    assert payout.fee is not None
    assert payout.fee.value == Decimal("1000")
    assert payout.destination is not None
    assert payout.destination.kind == "MOMO"


def test_payout_quote_has_no_idempotency_key(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payouts/quote").mock(
        return_value=httpx.Response(
            200,
            json={
                "amount": money(50000.00),
                "fee": money(1000.00),
                "vat": money(180.00),
                "total_debit": money(51180.00),
            },
        )
    )
    quote = client.payouts.quote(amount=50000)
    request = route.calls.last.request
    assert "Idempotency-Key" not in request.headers
    assert body_of(request) == {"currency": "TZS", "amount": 50000}
    assert quote.total_debit.value == Decimal("51180")


def test_list_payouts_with_state(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/payouts").mock(
        return_value=httpx.Response(200, json={"data": [payout_json()], "has_more": False})
    )
    page = client.payouts.list(state="SUCCEEDED", limit=10)
    assert route.calls.last.request.url.params["state"] == "SUCCEEDED"
    assert page.data[0].id == PO


def test_retrieve_payout(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/payouts/{PO}").mock(
        return_value=httpx.Response(200, json=payout_json(state="SUCCEEDED"))
    )
    assert client.payouts.retrieve(PO).state == "SUCCEEDED"


@pytest.mark.parametrize(
    "payload",
    [
        [{"purpose": "SETTLEMENT", "destination_kind": "BANK", "per_txn_cap": 5000000}],
        {"data": [{"purpose": "SETTLEMENT", "destination_kind": "BANK", "per_txn_cap": 5000000}]},
        {"limits": [{"purpose": "SETTLEMENT", "destination_kind": "BANK", "per_txn_cap": 5000000}]},
    ],
)
def test_payout_limits_accepts_bare_or_wrapped_list(
    respx_mock: respx.MockRouter, client: SettloPay, payload: object
) -> None:
    respx_mock.get(f"{BASE}/v1/payout-limits").mock(return_value=httpx.Response(200, json=payload))
    rows = client.payouts.limits()
    assert rows[0].purpose == "SETTLEMENT"


# ---------------------------------------------------------------- beneficiaries


def test_beneficiary_flow(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    create = respx_mock.post(f"{BASE}/v1/beneficiaries").mock(
        return_value=httpx.Response(201, json=beneficiary_json())
    )
    confirm = respx_mock.post(f"{BASE}/v1/beneficiaries/{DST}/confirm").mock(
        return_value=httpx.Response(200, json=beneficiary_json(status="active", confirmation=None))
    )
    resend = respx_mock.post(f"{BASE}/v1/beneficiaries/{DST}/resend_code").mock(
        return_value=httpx.Response(200, json=beneficiary_json())
    )
    delete = respx_mock.delete(f"{BASE}/v1/beneficiaries/{DST}").mock(
        return_value=httpx.Response(200, json={"id": DST, "object": "beneficiary", "retired": True})
    )

    dst = client.beneficiaries.create(
        kind="MOMO", fsp_code="VODATZ", account_number="255712345678", label="Supplier"
    )
    assert body_of(create.calls.last.request) == {
        "kind": "MOMO",
        "fsp_code": "VODATZ",
        "account_number": "255712345678",
        "label": "Supplier",
    }
    assert create.calls.last.request.headers["Idempotency-Key"].startswith("beneficiary-")
    assert dst.confirmation is not None
    assert dst.confirmation.channel == "sms"

    assert client.beneficiaries.confirm(DST, code="482913").status == "active"
    assert body_of(confirm.calls.last.request) == {"code": "482913"}

    client.beneficiaries.resend_code(DST, channel="sms")
    assert body_of(resend.calls.last.request) == {"channel": "sms"}

    assert client.beneficiaries.delete(DST).retired is True
    assert delete.called


def test_list_and_retrieve_beneficiaries(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/beneficiaries").mock(
        return_value=httpx.Response(200, json={"data": [beneficiary_json()], "has_more": False})
    )
    respx_mock.get(f"{BASE}/v1/beneficiaries/{DST}").mock(
        return_value=httpx.Response(200, json=beneficiary_json(status="active"))
    )
    assert [b.id for b in client.beneficiaries.list_all(status="active")] == [DST]
    assert route.calls.last.request.url.params["status"] == "active"
    assert client.beneficiaries.retrieve(DST).status == "active"


# ---------------------------------------------------------------- balance / checkout / qr


def test_balance(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/balance").mock(
        return_value=httpx.Response(
            200, json={"amount": money(1250000.00), "as_of": "2026-09-06T10:00:00Z"}
        )
    )
    balance = client.balance.retrieve()
    assert balance.amount.value == Decimal("1250000")
    assert balance.amount.currency == "TZS"


def test_checkout_session(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    session_json = {
        "id": CS,
        "object": "checkout_session",
        "state": "CREATED",
        "url": "https://pay.settlopay.co.tz/c/cs_01J9X6F0G1H2J3",
        "amount": money(25000),
    }
    create = respx_mock.post(f"{BASE}/v1/checkout/sessions").mock(
        return_value=httpx.Response(201, json=session_json)
    )
    respx_mock.get(f"{BASE}/v1/checkout/sessions/{CS}").mock(
        return_value=httpx.Response(200, json=session_json)
    )
    cancel = respx_mock.post(f"{BASE}/v1/checkout/sessions/{CS}/cancel").mock(
        return_value=httpx.Response(200, json={**session_json, "state": "CANCELLED"})
    )
    session = client.checkout_sessions.create(
        amount=25000,
        customer_phone="+255712345678",
        allowed_methods=["mobile_money"],
        return_url="https://shop.example/done",
    )
    assert body_of(create.calls.last.request)["allowed_methods"] == ["mobile_money"]
    assert session.url is not None
    assert client.checkout_sessions.retrieve(CS).state == "CREATED"
    assert client.checkout_sessions.cancel(CS).state == "CANCELLED"
    assert cancel.called


def test_qr_code(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    qr = {
        "id": "qr_01J9X7",
        "state": "ACTIVE",
        "image": {"svg": "https://cdn.settlopay.co.tz/qr.svg"},
        "qr_merchant_id": "12345678",
        "qr_kind": "static",
    }
    respx_mock.get(f"{BASE}/v1/qr_code").mock(return_value=httpx.Response(200, json=qr))
    post = respx_mock.post(f"{BASE}/v1/qr_code").mock(return_value=httpx.Response(200, json=qr))
    retrieved = client.qr_code.retrieve()
    assert retrieved.image is not None
    assert retrieved.image.svg
    client.qr_code.request(label="Counter 1")
    assert body_of(post.calls.last.request) == {"label": "Counter 1"}
    assert post.calls.last.request.headers["Idempotency-Key"].startswith("qr-")


# ---------------------------------------------------------------- malformed responses


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>gateway</html>"),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_unparseable_success_response(
    respx_mock: respx.MockRouter, client: SettloPay, response: httpx.Response
) -> None:
    respx_mock.get(f"{BASE}/v1/payments/{PI}").mock(return_value=response)
    with pytest.raises(UnexpectedResponseError):
        client.payments.retrieve(PI)
