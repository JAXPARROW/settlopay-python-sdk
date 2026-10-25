"""String constants for API enums.

Response models type these fields as plain ``str`` because Settlo may add values
without a version change; compare against these members (they are ``str``
subclasses, so ``payment.state == PaymentState.SUCCEEDED`` works). Every method
that takes one of these also accepts the plain string.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)


class PaymentMethod(_StrEnum):
    MOBILE_MONEY = "mobile_money"
    BANK = "bank"
    QR = "qr"


class MobileNetwork(_StrEnum):
    VODACOM = "vodacom"
    TIGO = "tigo"
    AIRTEL = "airtel"
    HALOTEL = "halotel"


class PaymentState(_StrEnum):
    CREATED = "CREATED"
    RISK_REVIEW = "RISK_REVIEW"
    ROUTED = "ROUTED"
    PENDING_AUTH = "PENDING_AUTH"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    AUTHORIZED = "AUTHORIZED"
    CAPTURING = "CAPTURING"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"
    CHARGEBACK_WON = "CHARGEBACK_WON"
    CHARGEBACK_LOST = "CHARGEBACK_LOST"


#: States a payment never leaves.
FINAL_PAYMENT_STATES: frozenset[str] = frozenset(
    {
        PaymentState.BLOCKED,
        PaymentState.FAILED,
        PaymentState.EXPIRED,
        PaymentState.CANCELLED,
        PaymentState.REFUNDED,
        PaymentState.CHARGEBACK_WON,
        PaymentState.CHARGEBACK_LOST,
    }
)


class RefundReason(_StrEnum):
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    OTHER = "other"


class RefundState(_StrEnum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PayoutState(_StrEnum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    SUCCEEDED = "SUCCEEDED"
    FAILED_REVERSED = "FAILED_REVERSED"
    REJECTED_FUNDS = "REJECTED_FUNDS"


class BeneficiaryKind(_StrEnum):
    MOMO = "MOMO"
    BANK = "BANK"


class BeneficiaryStatus(_StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    ACTIVE = "active"


class QrCodeState(_StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
