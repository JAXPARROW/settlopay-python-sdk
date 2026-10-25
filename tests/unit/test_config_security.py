"""Client configuration and secret-handling guarantees."""

from __future__ import annotations

import copy
import logging
import pickle

import httpx
import pytest
import respx

from settlopay import (
    API_VERSION,
    APIError,
    AsyncSettloPay,
    ConfigurationError,
    RetryPolicy,
    SettloPay,
    WebhookVerifier,
)

from ._helpers import BASE, FAKE_KEY, money


def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SETTLO_API_KEY", FAKE_KEY)
    with SettloPay() as client:
        assert client.mode == "test"


def test_missing_api_key_raises() -> None:
    with pytest.raises(ConfigurationError, match="SETTLO_API_KEY"):
        SettloPay()


@pytest.mark.parametrize(
    "bad", ["", "sk_live_", "pk_live_abcdefghijkl", "sk_live_abc def ghij", "sk_live_abc\r\nX: y"]
)
def test_malformed_key_rejected_without_echo(bad: str) -> None:
    with pytest.raises(ConfigurationError) as info:
        SettloPay(bad)
    if len(bad) > len("sk_live_"):  # the message names the prefixes themselves
        assert bad not in str(info.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.settlopay.co.tz",
        "ftp://api.settlopay.co.tz",
        "https://user:pw@api.settlopay.co.tz",
        "https://api.settlopay.co.tz?x=1",
        "https://",
        "api.settlopay.co.tz",
    ],
)
def test_non_https_base_url_refused(url: str) -> None:
    with pytest.raises(ConfigurationError):
        SettloPay(FAKE_KEY, base_url=url)


def test_repr_masks_key() -> None:
    with SettloPay(FAKE_KEY) as client:
        text = repr(client) + str(client) + repr(client._api_key) + repr(client._auth)
    assert FAKE_KEY not in text
    assert "fake-key" not in text
    assert "sk_test_****" in text


@pytest.mark.parametrize("op", [pickle.dumps, copy.copy, copy.deepcopy])
def test_client_and_key_cannot_be_serialised(op: object) -> None:
    with SettloPay(FAKE_KEY) as client:
        for obj in (client, client._api_key):
            with pytest.raises(TypeError):
                op(obj)  # type: ignore[operator]


def test_webhook_verifier_masks_secret() -> None:
    verifier = WebhookVerifier("whsec_super_secret_value")
    assert "super_secret" not in repr(verifier)
    with pytest.raises(TypeError):
        pickle.dumps(verifier)


def test_retry_and_max_retries_are_exclusive() -> None:
    with pytest.raises(ConfigurationError):
        SettloPay(FAKE_KEY, retry=RetryPolicy(), max_retries=1)


@pytest.mark.parametrize("value", [-1, 11, True])
def test_retry_policy_bounds(value: int) -> None:
    with pytest.raises(ConfigurationError):
        RetryPolicy(max_retries=value)


def test_invalid_api_version() -> None:
    with pytest.raises(ValueError, match="api_version"):
        SettloPay(FAKE_KEY, api_version="latest")


def test_standard_headers(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    route = respx_mock.get(f"{BASE}/v1/balance").mock(
        return_value=httpx.Response(
            200, json={"amount": money(10), "as_of": "2026-09-06T10:00:00Z"}
        )
    )
    client.balance.retrieve()
    headers = route.calls.last.request.headers
    assert headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert headers["Settlo-Version"] == API_VERSION
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"].startswith("settlopay-python/")
    assert "Idempotency-Key" not in headers
    assert "Content-Type" not in headers


def test_api_version_none_omits_header(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/balance").mock(
        return_value=httpx.Response(200, json={"amount": money(1)})
    )
    with SettloPay(FAKE_KEY, api_version=None) as client:
        client.balance.retrieve()
    assert "Settlo-Version" not in route.calls.last.request.headers


def test_redirects_are_never_followed(respx_mock: respx.MockRouter, client: SettloPay) -> None:
    respx_mock.get(f"{BASE}/v1/balance").mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/steal"})
    )
    evil = respx_mock.get("https://evil.example/steal")
    with pytest.raises(APIError, match="redirect"):
        client.balance.retrieve()
    assert not evil.called


def test_logs_never_contain_key(
    respx_mock: respx.MockRouter, client: SettloPay, caplog: pytest.LogCaptureFixture
) -> None:
    respx_mock.get(f"{BASE}/v1/balance").mock(
        side_effect=[httpx.Response(500, json={}), httpx.Response(200, json={"amount": money(1)})]
    )
    with caplog.at_level(logging.DEBUG, logger="settlopay"):
        client.balance.retrieve()
    assert caplog.records, "expected request/retry log lines"
    assert all(FAKE_KEY not in r.getMessage() for r in caplog.records)
    assert "Bearer" not in caplog.text


def test_user_supplied_http_client_is_not_closed(respx_mock: respx.MockRouter) -> None:
    http = httpx.Client()
    with SettloPay(FAKE_KEY, http_client=http):
        pass
    assert not http.is_closed
    http.close()


async def test_async_client_closes_own_pool() -> None:
    client = AsyncSettloPay(FAKE_KEY)
    await client.aclose()
    assert client._http.is_closed
