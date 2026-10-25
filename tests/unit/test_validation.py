"""Inputs are rejected locally, before any request is sent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
import respx

from settlopay import SettloPay, ValidationError
from settlopay import _validation as v

from ._helpers import PI


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (25000, Decimal("25000.00")),
        ("25000.5", Decimal("25000.50")),
        (Decimal("0.01"), Decimal("0.01")),
        (100.1, Decimal("100.10")),
    ],
)
def test_amount_accepts(value: v.AmountLike, expected: Decimal) -> None:
    assert v.amount(value) == expected


@pytest.mark.parametrize(
    "value",
    [0, -5, "abc", "1.001", float("nan"), float("inf"), True, None, [1], "1e13", Decimal("NaN")],
)
def test_amount_rejects(value: Any) -> None:
    with pytest.raises(ValidationError):
        v.amount(value)


def test_amount_whole_shillings() -> None:
    assert v.amount(100, whole=True) == Decimal("100.00")
    with pytest.raises(ValidationError, match="whole shillings"):
        v.amount("100.50", whole=True)


def test_money_serialises_whole_numbers_as_int() -> None:
    assert v.money(Decimal("25000.00"), "TZS") == {"value": 25000, "currency": "TZS"}
    assert v.money(Decimal("10.50"), "TZS") == {"value": 10.5, "currency": "TZS"}


@pytest.mark.parametrize("phone", ["0712345678", "255712345678", "+25571234567", "+2557123456789"])
def test_tz_phone_rejects(phone: str) -> None:
    with pytest.raises(ValidationError):
        v.tz_phone(phone)


@pytest.mark.parametrize(
    ("value", "prefix"),
    [
        ("pi_../../v1/payouts", "pi_"),
        ("po_123", "pi_"),
        ("pi_", "pi_"),
        ("pi_abc?x=1", "pi_"),
        ("pi_abc/def", "pi_"),
        (123, "pi_"),
    ],
)
def test_resource_id_rejects_path_tricks(value: Any, prefix: str) -> None:
    with pytest.raises(ValidationError):
        v.resource_id(value, prefix)


def test_idempotency_key_rules() -> None:
    assert v.idempotency_key(None, scope="payout").startswith("payout-")
    assert v.idempotency_key("order-1", scope="x") == "order-1"
    for bad in ["", "a" * 121, "has space", "refund:abc", "line\nbreak"]:
        with pytest.raises(ValidationError):
            v.idempotency_key(bad, scope="x")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"method": "card"}, "method"),
        ({"method": "mobile_money"}, "phone"),
        ({"method": "bank", "phone": "+255712345678"}, "phone"),
        ({"method": "mobile_money", "phone": "+255712345678", "network": "mpesa"}, "network"),
        ({"method": "bank", "expires_at": datetime.now(timezone.utc)}, "expires_at"),
        ({"method": "qr", "amount": "10.50"}, "whole"),
        ({"method": "bank", "currency": "tzs"}, "currency"),
        ({"method": "bank", "statement_descriptor": "x" * 23}, "statement_descriptor"),
        ({"method": "bank", "merchant_reference": "x" * 121}, "merchant_reference"),
        ({"method": "bank", "merchant_reference": "   "}, "merchant_reference"),
        ({"method": "bank", "return_url": "javascript:alert(1)"}, "return_url"),
        ({"method": "bank", "metadata": {"k": object()}}, "metadata"),
        ({"method": "bank", "metadata": {1: "x"}}, "metadata"),
    ],
)
def test_payment_create_validation(
    respx_mock: respx.MockRouter, client: SettloPay, kwargs: dict[str, Any], match: str
) -> None:
    kwargs.setdefault("amount", 1000)
    with pytest.raises(ValidationError, match=match):
        client.payments.create(**kwargs)
    assert not respx_mock.calls, "nothing may be sent when validation fails"


def test_qr_expiry_window(client: SettloPay) -> None:
    now = datetime.now(timezone.utc)
    for when in (now + timedelta(minutes=1), now + timedelta(days=31)):
        with pytest.raises(ValidationError, match="expires_at"):
            client.payments.create(amount=1000, method="qr", expires_at=when)
    with pytest.raises(ValidationError, match="timezone-aware"):
        client.payments.create(
            amount=1000, method="qr", expires_at=datetime.now() + timedelta(hours=1)
        )


def test_payout_rejects_non_tzs_and_bad_destination(client: SettloPay) -> None:
    with pytest.raises(ValidationError, match="destination_id"):
        client.payouts.create(amount=1000, destination_id=PI)
    with pytest.raises(ValidationError, match="description"):
        client.payouts.create(amount=1000, description="x" * 201)


@pytest.mark.parametrize(
    ("kind", "account"),
    [("MOMO", "+255712345678"), ("MOMO", "0712345678"), ("BANK", "12345"), ("BANK", "12 3456")],
)
def test_beneficiary_account_formats(client: SettloPay, kind: str, account: str) -> None:
    with pytest.raises(ValidationError, match="account_number"):
        client.beneficiaries.create(kind=kind, fsp_code="VODATZ", account_number=account)


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", 482913])
def test_confirmation_code_format(client: SettloPay, code: Any) -> None:
    with pytest.raises(ValidationError, match="code"):
        client.beneficiaries.confirm("dst_01J9X5A1B2C3D4", code=code)


@pytest.mark.parametrize("limit", [0, 101, True, "10"])
def test_page_limit(client: SettloPay, limit: Any) -> None:
    with pytest.raises(ValidationError, match="limit"):
        client.payments.list(limit=limit)


def test_checkout_inputs(client: SettloPay) -> None:
    with pytest.raises(ValidationError, match="customer_email"):
        client.checkout_sessions.create(amount=1000, customer_email="not-an-email")
    with pytest.raises(ValidationError, match="customer_phone"):
        client.checkout_sessions.create(amount=1000, customer_phone="0712345678")
    with pytest.raises(ValidationError, match="allowed_methods"):
        client.checkout_sessions.create(amount=1000, allowed_methods="mobile_money")
