"""API error responses map onto the exception hierarchy."""

from __future__ import annotations

import httpx
import pytest
import respx

from settlopay import (
    APIError,
    AuthenticationError,
    ConflictError,
    IdempotencyConflictError,
    InvalidRequestError,
    NotFoundError,
    PaymentFailedError,
    PermissionDeniedError,
    ProviderError,
    RateLimitError,
    RetryPolicy,
    ServerError,
    ServiceUnavailableError,
    SettloError,
    SettloPay,
    UnprocessableEntityError,
    ValidationError,
)

from ._helpers import BASE, FAKE_KEY, PI, error_json


@pytest.fixture
def no_retry_client() -> SettloPay:
    return SettloPay(FAKE_KEY, retry=RetryPolicy(max_retries=0))


@pytest.mark.parametrize(
    ("status", "code", "exc"),
    [
        (400, "parameter_invalid", InvalidRequestError),
        (401, "authentication_required", AuthenticationError),
        (402, "payment_failed", PaymentFailedError),
        (403, "permission_denied", PermissionDeniedError),
        (403, "merchant_not_transactable", PermissionDeniedError),
        (404, "resource_missing", NotFoundError),
        (409, "state_invalid", ConflictError),
        (409, "idempotency_conflict", IdempotencyConflictError),
        (422, "insufficient_funds", UnprocessableEntityError),
        (429, "rate_limit_exceeded", RateLimitError),
        (500, "api_error", ServerError),
        (502, "provider_error", ProviderError),
        (503, "try_later", ServiceUnavailableError),
        (504, "provider_timeout", ProviderError),
        (418, "teapot", APIError),
        (599, None, ServerError),
    ],
)
def test_status_mapping(
    respx_mock: respx.MockRouter,
    no_retry_client: SettloPay,
    status: int,
    code: str | None,
    exc: type[APIError],
) -> None:
    body = error_json(code, "boom", param="amount.value", request_id="req-123") if code else {}
    respx_mock.get(f"{BASE}/v1/payments/{PI}").mock(return_value=httpx.Response(status, json=body))
    with pytest.raises(exc) as info:
        no_retry_client.payments.retrieve(PI)
    err = info.value
    assert type(err) is exc
    assert isinstance(err, SettloError)
    assert err.status_code == status
    assert err.code == code
    if code:
        assert err.param == "amount.value"
        assert err.request_id == "req-123"
        assert "req-123" in str(err)


def test_invalid_request_is_also_validation_error(
    respx_mock: respx.MockRouter, no_retry_client: SettloPay
) -> None:
    respx_mock.get(f"{BASE}/v1/payments/{PI}").mock(
        return_value=httpx.Response(400, json=error_json("parameter_invalid"))
    )
    with pytest.raises(ValidationError):
        no_retry_client.payments.retrieve(PI)


def test_business_decline_fields(respx_mock: respx.MockRouter, no_retry_client: SettloPay) -> None:
    respx_mock.post(f"{BASE}/v1/payouts").mock(
        return_value=httpx.Response(
            422,
            json={
                "type": "business_decline",
                "code": "insufficient_funds",
                "message": "Insufficient funds to complete this payout",
                "param": "amount.value",
                "request_id": "0d9f7c3a",
            },
        )
    )
    with pytest.raises(UnprocessableEntityError) as info:
        no_retry_client.payouts.create(amount=50000, idempotency_key="w-1")
    assert info.value.type == "business_decline"
    assert info.value.message == "Insufficient funds to complete this payout"


def test_error_envelope_and_non_json(
    respx_mock: respx.MockRouter, no_retry_client: SettloPay
) -> None:
    route = respx_mock.get(f"{BASE}/v1/payments/{PI}")
    route.mock(return_value=httpx.Response(404, json={"error": error_json("resource_missing")}))
    with pytest.raises(NotFoundError) as info:
        no_retry_client.payments.retrieve(PI)
    assert info.value.code == "resource_missing"

    route.mock(return_value=httpx.Response(500, text="Internal Server Error"))
    with pytest.raises(ServerError, match="HTTP 500"):
        no_retry_client.payments.retrieve(PI)


@pytest.mark.parametrize(
    ("header", "expected"),
    [("17", 17.0), ("0", 0.0), ("garbage", None), ("Wed, 21 Oct 2015 07:28:00 GMT", 0.0)],
)
def test_retry_after_parsing(
    respx_mock: respx.MockRouter, no_retry_client: SettloPay, header: str, expected: float | None
) -> None:
    respx_mock.get(f"{BASE}/v1/balance").mock(
        return_value=httpx.Response(
            429, json=error_json("rate_limit_exceeded"), headers={"Retry-After": header}
        )
    )
    with pytest.raises(RateLimitError) as info:
        no_retry_client.balance.retrieve()
    assert info.value.retry_after == expected
