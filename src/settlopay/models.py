"""Typed response models (Pydantic v2).

Models are immutable and keep unknown fields (``model.model_extra``), because
Settlo adds fields without bumping the API version. Enum-like fields are plain
``str``; compare them against :mod:`settlopay.enums`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from .enums import FINAL_PAYMENT_STATES, PaymentState

__all__ = [
    "Balance",
    "Beneficiary",
    "BeneficiaryConfirmation",
    "CheckoutSession",
    "DeletedBeneficiary",
    "Money",
    "NextAction",
    "Page",
    "Payment",
    "PaymentClaim",
    "Payout",
    "PayoutDestination",
    "PayoutLimit",
    "PayoutQuote",
    "QrCode",
    "QrImage",
    "Refund",
    "SettloModel",
    "WebhookDelivery",
    "WebhookEvent",
]


class SettloModel(BaseModel):
    """Base for all response models."""

    model_config = ConfigDict(extra="allow", frozen=True)


class Money(SettloModel):
    """An amount, e.g. ``Money(value=Decimal("25000.00"), currency="TZS")``."""

    value: Decimal
    currency: str


class QrImage(SettloModel):
    svg: str | None = None


class NextAction(SettloModel):
    """What the customer has to do next (``await_mobile_prompt``, ``display_bank_reference``,
    ``display_qr``)."""

    type: str
    reference: str | None = None
    payable_at: list[Any] | None = None
    expires_at: datetime | None = None
    image: QrImage | None = None
    display: dict[str, Any] | None = None


class PaymentClaim(SettloModel):
    claim_partner: str | None = None
    claim_ref: str | None = None
    claim_label: str | None = None
    amount_applied: Any = None
    claimed_at: datetime | None = None


class Payment(SettloModel):
    """A payment intent (``pi_`` id)."""

    id: str
    state: str
    object: str = "payment_intent"
    ref: str | None = None
    message: str | None = None
    receipt_no: str | None = None
    amount: Money | None = None
    method: str | None = None
    origin: str | None = None
    merchant_reference: str | None = None
    linked_payment_id: str | None = None
    claim: PaymentClaim | None = None
    payer_receipt: Any = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    amount_received: Money | Decimal | None = None
    overpaid: Any = None
    payments: list[dict[str, Any]] | None = None
    next_action: NextAction | None = None
    failure_code: str | None = None

    @property
    def is_final(self) -> bool:
        """``True`` once the payment can no longer change state on its own."""
        return self.state in FINAL_PAYMENT_STATES

    @property
    def succeeded(self) -> bool:
        """``True`` when money was collected (including later partial refunds/disputes)."""
        return self.state in {
            PaymentState.SUCCEEDED,
            PaymentState.PARTIALLY_REFUNDED,
            PaymentState.DISPUTED,
            PaymentState.CHARGEBACK_WON,
        }


class Refund(SettloModel):
    """A refund (``ref_`` id)."""

    id: str
    state: str
    object: str = "refund"
    ref: str | None = None
    message: str | None = None
    receipt_no: str | None = None
    amount: Money | None = None
    payment_intent: str | None = None
    reason: str | None = None
    merchant_reference: str | None = None
    created_at: datetime | None = None


class PayoutDestination(SettloModel):
    destination_id: str | None = None
    purpose: str | None = None
    kind: str | None = None
    fsp_code: str | None = None
    account_masked: str | None = None
    account_name: str | None = None
    label: str | None = None


class Payout(SettloModel):
    """A payout (``po_`` id)."""

    id: str
    state: str
    object: str = "payout"
    ref: str | None = None
    message: str | None = None
    amount: Money | None = None
    fee: Money | None = None
    vat: Money | None = None
    destination: PayoutDestination | None = None
    description: str | None = None
    merchant_reference: str | None = None
    failure_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PayoutQuote(SettloModel):
    """Price of a payout. Creates nothing and reserves nothing."""

    amount: Money
    fee: Money
    vat: Money
    total_debit: Money


class PayoutLimit(SettloModel):
    purpose: str | None = None
    destination_kind: str | None = None
    per_txn_cap: Money | Decimal | None = None
    daily_cap: Money | Decimal | None = None
    currency: str | None = None
    source: str | None = None


class BeneficiaryConfirmation(SettloModel):
    channel: str | None = None
    sent_to: str | None = None
    expires_at: datetime | None = None


class Beneficiary(SettloModel):
    """A payout destination (``dst_`` id)."""

    id: str
    status: str
    object: str = "beneficiary"
    kind: str | None = None
    fsp_code: str | None = None
    account_masked: str | None = None
    account_name: str | None = None
    verified_name: str | None = None
    label: str | None = None
    created_via: str | None = None
    confirmation: BeneficiaryConfirmation | None = None
    confirmed_at: datetime | None = None
    created_at: datetime | None = None


class DeletedBeneficiary(SettloModel):
    id: str
    object: str = "beneficiary"
    retired: bool


class Balance(SettloModel):
    amount: Money
    as_of: datetime | None = None


class CheckoutSession(SettloModel):
    """A hosted checkout page (``cs_`` id). Redirect the customer to :attr:`url`."""

    id: str
    state: str
    object: str = "checkout_session"
    url: str | None = None
    amount: Money | None = None
    merchant_reference: str | None = None
    return_url: str | None = None
    cancel_url: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


class QrCode(SettloModel):
    """The account's printable QR code (``qr_`` id)."""

    id: str
    state: str
    label: str | None = None
    image: QrImage | None = None
    qr_merchant_id: str | None = None
    qr_kind: str | None = None
    failure_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WebhookDelivery(SettloModel):
    id: str | None = None
    attempt: int | None = None


class WebhookEvent(SettloModel):
    """A verified webhook event. ``data`` is the raw object snapshot."""

    id: str
    type: str
    api_version: str | None = None
    created: datetime | None = None
    data: dict[str, Any]
    delivery: WebhookDelivery | None = None


T = TypeVar("T", bound=SettloModel)


class Page(SettloModel, Generic[T]):
    """One page of a list endpoint. Pass :attr:`next_cursor` back as ``cursor``."""

    data: list[T]
    next_cursor: str | None = None
    has_more: bool = False
