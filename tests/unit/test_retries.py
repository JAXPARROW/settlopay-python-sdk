"""Retries happen only where they cannot duplicate a side effect."""

from __future__ import annotations

import httpx
import pytest
import respx

from settlopay import (
    APIConnectionError,
    APITimeoutError,
    ConflictError,
    RateLimitError,
    RetryPolicy,
    ServerError,
    ServiceUnavailableError,
    SettloPay,
)

from ._helpers import BASE, DST, FAKE_KEY, PI, error_json, money, payment_json, payout_json

OK_BALANCE = httpx.Response(200, json={"amount": money(1)})


def test_get_retried_on_5xx(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/balance").mock(
        side_effect=[httpx.Response(502), httpx.Response(503), OK_BALANCE]
    )
    client.balance.retrieve()
    assert route.call_count == 3


def test_gives_up_after_max_retries(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/balance").mock(return_value=httpx.Response(500))
    with pytest.raises(ServerError):
        client.balance.retrieve()
    assert route.call_count == 3  # 1 + max_retries(2)


def test_create_retry_reuses_idempotency_key(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments").mock(
        side_effect=[
            httpx.ReadTimeout("slow"),
            httpx.Response(504, json=error_json("provider_timeout")),
            httpx.Response(201, json=payment_json()),
        ]
    )
    client.payments.create(amount=1000, method="mobile_money", phone="+255712345678")
    keys = {call.request.headers["Idempotency-Key"] for call in route.calls}
    assert route.call_count == 3
    assert len(keys) == 1, "every retry must carry the same idempotency key"


def test_payout_503_try_later_is_not_retried(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payouts").mock(
        return_value=httpx.Response(503, json=error_json("try_later"))
    )
    with pytest.raises(ServiceUnavailableError):
        client.payouts.create(amount=1000, destination_id=DST, idempotency_key="w-1")
    assert route.call_count == 1


def test_payout_timeout_retried_with_same_key(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payouts").mock(
        side_effect=[httpx.ReadTimeout("slow"), httpx.Response(201, json=payout_json())]
    )
    client.payouts.create(amount=1000, idempotency_key="w-2")
    assert [c.request.headers["Idempotency-Key"] for c in route.calls] == ["w-2", "w-2"]


@pytest.mark.parametrize(
    "side_effect", [httpx.ReadTimeout("slow"), httpx.Response(500), httpx.Response(502)]
)
def test_unsafe_actions_not_retried_on_ambiguous_failure(
    respx_mock: respx.MockRouter, client: SettloPay, side_effect: httpx.Response | Exception
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments/{PI}/cancel").mock(side_effect=[side_effect])
    with pytest.raises((APIConnectionError, ServerError)):
        client.payments.cancel(PI)
    assert route.call_count == 1


def test_beneficiary_confirm_never_retried_on_5xx(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/beneficiaries/{DST}/confirm").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(ServerError):
        client.beneficiaries.confirm(DST, code="123456")
    assert route.call_count == 1


def test_connect_error_retried_even_for_unsafe(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments/{PI}/cancel").mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json=payment_json())]
    )
    client.payments.cancel(PI)
    assert route.call_count == 2


def test_rate_limit_honours_retry_after(respx_mock: respx.MockRouter) -> None:
    slept: list[float] = []
    with SettloPay(FAKE_KEY, retry=RetryPolicy(max_retries=2)) as client:
        client._sleep = slept.append
        respx_mock.get(f"{BASE}/v1/balance").mock(
            side_effect=[
                httpx.Response(
                    429, json=error_json("rate_limit_exceeded"), headers={"Retry-After": "3"}
                ),
                OK_BALANCE,
            ]
        )
        client.balance.retrieve()
    assert slept == [3.0]


def test_long_retry_after_raises_immediately(
    respx_mock: respx.MockRouter, client: SettloPay
) -> None:
    route = respx_mock.post(f"{BASE}/v1/beneficiaries/{DST}/resend_code").mock(
        return_value=httpx.Response(
            429, json=error_json("confirmation_throttled"), headers={"Retry-After": "3600"}
        )
    )
    with pytest.raises(RateLimitError) as info:
        client.beneficiaries.resend_code(DST)
    assert info.value.retry_after == 3600
    assert route.call_count == 1


def test_conflict_not_retried(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.post(f"{BASE}/v1/payments").mock(
        return_value=httpx.Response(409, json=error_json("idempotency_conflict"))
    )
    with pytest.raises(ConflictError):
        client.payments.create(amount=1000, method="bank", idempotency_key="k")
    assert route.call_count == 1


def test_timeout_surfaces_as_api_timeout(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/balance").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(APITimeoutError) as info:
        client.balance.retrieve()
    assert isinstance(info.value.__cause__, httpx.ReadTimeout)


def test_backoff_is_bounded() -> None:
    policy = RetryPolicy(backoff_factor=1.0, max_backoff=4.0)
    for attempt in range(10):
        assert 0 <= policy.backoff(attempt) <= 4.0
