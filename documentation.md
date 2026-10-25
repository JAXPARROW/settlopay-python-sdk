# Settlo Pay Python SDK — Documentation

Complete reference for `settlo-pay-python-sdk` **0.1.0**, targeting Settlo Pay API
version **2026-04-29**.

> **There is no sandbox.** `sk_test_` and `sk_live_` keys both hit the live API and
> move real money. Test with small amounts and your own phone.

---

## Contents

1. [Names: `settlo-pay-python-sdk` vs `settlopay`](#1-names-settlo-pay-python-sdk-vs-settlopay)
2. [Installation](#2-installation)
3. [Creating a client](#3-creating-a-client)
4. [Sync vs async at a glance](#4-sync-vs-async-at-a-glance)
5. [Payments](#5-payments--clientpayments)
6. [Refunds](#6-refunds--clientrefunds)
7. [Payouts](#7-payouts--clientpayouts)
8. [Beneficiaries](#8-beneficiaries--clientbeneficiaries)
9. [Balance](#9-balance--clientbalance)
10. [Checkout sessions](#10-checkout-sessions--clientcheckout_sessions)
11. [QR code](#11-qr-code--clientqr_code)
12. [Webhooks](#12-webhooks)
13. [Pagination](#13-pagination)
14. [Idempotency](#14-idempotency)
15. [Retries](#15-retries)
16. [Errors](#16-errors)
17. [Input validation rules](#17-input-validation-rules)
18. [Response models](#18-response-models)
19. [Enums and constants](#19-enums-and-constants)
20. [Logging and security](#20-logging-and-security)
21. [Testing your integration](#21-testing-your-integration)

---

## 1. Names: `settlo-pay-python-sdk` vs `settlopay`

| Where | Name |
|---|---|
| Company / product | **Settlo Pay** (website `settlopay.co.tz`) |
| PyPI distribution (what you `pip install`) | **`settlo-pay-python-sdk`** |
| Python import (what you `import`) | **`settlopay`** |
| Client classes | `SettloPay`, `AsyncSettloPay` |
| Environment variable | `SETTLO_API_KEY` |

The install name and the import name differ, as with `pip install beautifulsoup4`
and `import bs4`. Python identifiers can't contain hyphens, so the import is
`settlopay`.

```bash
pip install settlo-pay-python-sdk
```

```python
import settlopay
from settlopay import SettloPay
```

---

## 2. Installation

Requires Python **3.10+**. Runtime dependencies: `httpx` and `pydantic` v2.

```bash
pip install settlo-pay-python-sdk
```

The package ships `py.typed`, so mypy and pyright type-check your calls.

---

## 3. Creating a client

```python
from settlopay import SettloPay

client = SettloPay()  # reads SETTLO_API_KEY
client = SettloPay("sk_live_...")  # or pass the key explicitly (prefer env)
```

### Constructor arguments

`SettloPay(...)` and `AsyncSettloPay(...)` take the same arguments.

| Argument | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str \| None` | `None` | Secret key. If `None`, the `SETTLO_API_KEY` environment variable is used. Must start with `sk_live_` or `sk_test_`. |
| `base_url` | `str` | `"https://api.settlopay.co.tz"` | API root. Must be `https://`; HTTP, embedded credentials and query strings are refused. |
| `api_version` | `str \| None` | `"2026-04-29"` | Sent as the `Settlo-Version` header. `None` omits the header, so the account's current version is used. |
| `timeout` | `float \| httpx.Timeout` | 30 s (10 s connect) | Request timeout. |
| `max_retries` | `int \| None` | `None` (2) | Shortcut for `retry=RetryPolicy(max_retries=...)`. Range 0–10. |
| `retry` | `RetryPolicy \| None` | `None` | Full retry configuration ([§15](#15-retries)). Don't combine with `max_retries`. |
| `http_client` | `httpx.Client` / `httpx.AsyncClient` | `None` | Bring your own client (proxies, custom TLS). You must close it yourself and keep TLS verification on. |

### Properties

| Property | Description |
|---|---|
| `client.mode` | `"live"` or `"test"`, from the key prefix. Both move real money. |
| `client.base_url` | The validated API root. |
| `client.api_version` | The `Settlo-Version` value, or `None`. |
| `client.retry` | The active `RetryPolicy`. |

### Closing

**Sync**

```python
with SettloPay() as client:  # closes automatically
    ...

client = SettloPay()
client.close()  # or close manually
```

**Async**

```python
async with AsyncSettloPay() as client:
    ...

client = AsyncSettloPay()
await client.aclose()
```

`close()` / `aclose()` don't close an `http_client` you supplied yourself.

---

## 4. Sync vs async at a glance

Both clients expose the same resources and the same method names. With the async
client, `await` every call, and use `async for` with the `list_all` iterators.

| Resource | Method | Sync | Async |
|---|---|---|---|
| Payments | create | `client.payments.create(...)` | `await client.payments.create(...)` |
| | list | `client.payments.list(...)` | `await client.payments.list(...)` |
| | list_all | `for p in client.payments.list_all()` | `async for p in client.payments.list_all()` |
| | retrieve | `client.payments.retrieve(id)` | `await client.payments.retrieve(id)` |
| | amend | `client.payments.amend(id, amount=...)` | `await client.payments.amend(id, amount=...)` |
| | cancel | `client.payments.cancel(id)` | `await client.payments.cancel(id)` |
| | inquire | `client.payments.inquire(id)` | `await client.payments.inquire(id)` |
| Refunds | create | `client.refunds.create(...)` | `await client.refunds.create(...)` |
| | retrieve | `client.refunds.retrieve(id)` | `await client.refunds.retrieve(id)` |
| Payouts | create | `client.payouts.create(...)` | `await client.payouts.create(...)` |
| | quote | `client.payouts.quote(...)` | `await client.payouts.quote(...)` |
| | list | `client.payouts.list(...)` | `await client.payouts.list(...)` |
| | list_all | `for p in client.payouts.list_all()` | `async for p in client.payouts.list_all()` |
| | retrieve | `client.payouts.retrieve(id)` | `await client.payouts.retrieve(id)` |
| | limits | `client.payouts.limits()` | `await client.payouts.limits()` |
| Beneficiaries | list | `client.beneficiaries.list(...)` | `await client.beneficiaries.list(...)` |
| | list_all | `for b in client.beneficiaries.list_all()` | `async for b in client.beneficiaries.list_all()` |
| | create | `client.beneficiaries.create(...)` | `await client.beneficiaries.create(...)` |
| | retrieve | `client.beneficiaries.retrieve(id)` | `await client.beneficiaries.retrieve(id)` |
| | confirm | `client.beneficiaries.confirm(id, code=...)` | `await client.beneficiaries.confirm(id, code=...)` |
| | resend_code | `client.beneficiaries.resend_code(id)` | `await client.beneficiaries.resend_code(id)` |
| | delete | `client.beneficiaries.delete(id)` | `await client.beneficiaries.delete(id)` |
| Balance | retrieve | `client.balance.retrieve()` | `await client.balance.retrieve()` |
| Checkout | create | `client.checkout_sessions.create(...)` | `await client.checkout_sessions.create(...)` |
| | retrieve | `client.checkout_sessions.retrieve(id)` | `await client.checkout_sessions.retrieve(id)` |
| | cancel | `client.checkout_sessions.cancel(id)` | `await client.checkout_sessions.cancel(id)` |
| QR code | retrieve | `client.qr_code.retrieve()` | `await client.qr_code.retrieve()` |
| | request | `client.qr_code.request(...)` | `await client.qr_code.request(...)` |
| Client | close | `client.close()` | `await client.aclose()` |

Webhook verification ([§12](#12-webhooks)) is a plain function and works the
same in sync and async code.

All keyword arguments are **keyword-only** (after `*`) except the resource id,
which is positional.

---

## 5. Payments — `client.payments`

API: `/v1/payments`. Ids start with `pi_`.

### 5.1 `create`

Collect money by mobile money (a prompt on the payer's phone), bank reference or QR code.

```python
create(
    *,
    amount: int | Decimal | str | float,
    method: PaymentMethod | str,            # "mobile_money" | "bank" | "qr"
    currency: str = "TZS",
    phone: str | None = None,               # required for mobile_money
    network: MobileNetwork | str | None = None,
    expires_at: datetime | None = None,     # qr only
    customer_id: str | None = None,
    merchant_reference: str | None = None,
    description: str | None = None,
    statement_descriptor: str | None = None,
    return_url: str | None = None,
    cancel_url: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Payment
```

| Parameter | Rules |
|---|---|
| `amount` | > 0, at most 2 decimal places. **Whole shillings for `qr`.** |
| `method` | `mobile_money`, `bank` or `qr`. |
| `currency` | 3 upper-case letters. Settlo supports `TZS`. |
| `phone` | E.164 `+255` + 9 digits, e.g. `+255712345678`. **Required for `mobile_money`, not allowed otherwise.** |
| `network` | `vodacom`, `tigo`, `airtel`, `halotel`. Overrides detection from the number. Mobile money only. |
| `expires_at` | **QR only.** Timezone-aware `datetime`, 5 minutes to 30 days ahead. Default on Settlo's side: 15 min. |
| `customer_id` | Max 120 chars. Omit for guests. |
| `merchant_reference` | Max 120 chars. Echoed on the payment and on webhooks. |
| `description` | Max 1000 chars. Not returned. |
| `statement_descriptor` | Max 22 chars. |
| `return_url`, `cancel_url` | Absolute `http(s)` URLs, for hosted pages. |
| `metadata` | JSON-serialisable mapping with string keys. Not returned. |
| `idempotency_key` | 1–120 printable ASCII chars, no spaces, must not start with `refund:`. Generated if omitted. |

What comes back:

- `mobile_money`: `state == "PENDING_AUTH"`, `next_action.type == "await_mobile_prompt"`.
- `bank`: `state == "AWAITING_CUSTOMER"`, `next_action.type == "display_bank_reference"` (see `next_action.reference`, `payable_at`).
- `qr`: `next_action.type == "display_qr"` (see `next_action.image.svg`, `display`).
- A risk-rejected payment comes back as `state == "BLOCKED"` **with HTTP 201, not an exception**. Always check `payment.state`.

> **The customer pays more than `amount`.** For mobile money, Settlo adds its
> collection fee on top of `amount`, and you're credited the full `amount`.
> Settlo support confirmed (2026-10-25) that payments **below TZS 5,000** carry a
> flat **TZS 200 fee + 18% VAT = TZS 236**, and payments of **TZS 5,000 and above**
> carry **2.5% + VAT**. So TZS 5,000 costs the customer less in fees than TZS 4,999.
> Live tests matched this: TZS 100 → customer paid 336, TZS 500 → 736. Vodacom
> M-Pesa charged the payer a further TZS 60. Rates are negotiable by volume. The
> payment object has no fee fields, so tell customers the total before sending the push.

**Sync**

```python
from settlopay import SettloPay, PaymentMethod

with SettloPay() as client:
    payment = client.payments.create(
        amount=25_000,
        method=PaymentMethod.MOBILE_MONEY,
        phone="+255712345678",
        merchant_reference="ORD-8451",
        idempotency_key="order-8451-pay-1",
    )
    print(payment.id, payment.state)  # pi_..., PENDING_AUTH
```

**Async**

```python
from settlopay import AsyncSettloPay

async with AsyncSettloPay() as client:
    payment = await client.payments.create(
        amount=25_000,
        method="mobile_money",
        phone="+255712345678",
        merchant_reference="ORD-8451",
        idempotency_key="order-8451-pay-1",
    )
```

Bank and QR variants:

```python
bank = client.payments.create(amount=150_000, method="bank", merchant_reference="INV-77")
print(bank.next_action.reference)

from datetime import datetime, timedelta, timezone

qr = client.payments.create(
    amount=10_000,  # whole shillings
    method="qr",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
)
print(qr.next_action.image.svg)
```

### 5.2 `list`

```python
list(*, limit: int | None = None, cursor: str | None = None) -> Page[Payment]
```

Newest first. Includes payments customers made by scanning your QR code
(`origin == "payer_initiated"`). `limit` is 1–100 (Settlo's default is 20).

**Sync**

```python
page = client.payments.list(limit=50)
for p in page.data:
    print(p.id, p.state)
if page.next_cursor:
    page2 = client.payments.list(limit=50, cursor=page.next_cursor)
```

**Async**

```python
page = await client.payments.list(limit=50)
```

### 5.3 `list_all`

```python
list_all(*, page_size: int = 100) -> Iterator[Payment]          # sync
list_all(*, page_size: int = 100) -> AsyncIterator[Payment]     # async
```

Iterates over every payment, fetching pages lazily.

**Sync**

```python
for payment in client.payments.list_all():
    print(payment.id)
```

**Async**

```python
async for payment in client.payments.list_all():
    print(payment.id)
```

### 5.4 `retrieve`

```python
retrieve(payment_id: str) -> Payment
```

Fetch the current state. Use it to poll when you can't receive webhooks.

**Sync**

```python
payment = client.payments.retrieve("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
if payment.succeeded:
    fulfil_order()
```

**Async**

```python
payment = await client.payments.retrieve("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
```

### 5.5 `amend`

```python
amend(payment_id: str, *, amount: int | Decimal | str | float, currency: str = "TZS") -> Payment
```

Change the total of a **QR** payment that is still `AWAITING_CUSTOMER`. Whole
shillings only. Sending the same amount again changes nothing. If money already
received covers the new total, the payment succeeds.

**Sync**

```python
client.payments.amend("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK", amount=30_000)
```

**Async**

```python
await client.payments.amend("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK", amount=30_000)
```

### 5.6 `cancel`

```python
cancel(payment_id: str) -> Payment
```

Allowed from `PENDING_AUTH`, `AWAITING_CUSTOMER` or `AUTHORIZED`.

> **Caution:** cancelling a mobile-money payment leaves the prompt live on the
> customer's phone. If they approve it anyway, the payment stays `CANCELLED` and
> you are **not** credited; the customer has to go through Settlo support to get
> the money back.

**Sync**

```python
client.payments.cancel("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
```

**Async**

```python
await client.payments.cancel("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
```

### 5.7 `inquire`

```python
inquire(payment_id: str) -> Payment
```

Force a status check with the payment network for a payment that looks stuck.

**Sync**

```python
payment = client.payments.inquire("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
```

**Async**

```python
payment = await client.payments.inquire("pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK")
```

### Payment states

| Group | States |
|---|---|
| Pending | `CREATED`, `RISK_REVIEW`, `ROUTED`, `PENDING_AUTH`, `AWAITING_CUSTOMER`, `AUTHORIZED`, `CAPTURING` |
| Succeeded | `SUCCEEDED` |
| Final (failed) | `BLOCKED`, `FAILED`, `EXPIRED`, `CANCELLED`, `CHARGEBACK_LOST` |
| Final (other) | `REFUNDED`, `CHARGEBACK_WON` |
| After success | `PARTIALLY_REFUNDED`, `DISPUTED` |

Helpers on `Payment`:

- `payment.is_final` is `True` for states that never change.
- `payment.succeeded` is `True` for `SUCCEEDED`, `PARTIALLY_REFUNDED`, `DISPUTED` and `CHARGEBACK_WON`.

---

## 6. Refunds — `client.refunds`

API: `/v1/refunds`. Ids start with `ref_`.

### 6.1 `create`

```python
create(
    *,
    payment_intent: str,                   # pi_ id
    reason: RefundReason | str,            # requested_by_customer | duplicate | fraudulent | other
    amount: int | Decimal | str | float | None = None,   # None = everything refundable
    currency: str = "TZS",
    merchant_reference: str | None = None, # max 120
    description: str | None = None,        # max 1000, not returned
    metadata: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Refund
```

Rules (enforced by Settlo):

- Only for payments in `SUCCEEDED` or `PARTIALLY_REFUNDED`, within 30 days.
- The total of all refunds can't exceed the payment.
- QR and payer-initiated payments can't be refunded through the API (`422 refund_unsupported_method`).
- Fee: 2% (minimum TZS 500) + 18% VAT, debited from your balance on top of the refund. The customer receives the full refund amount. Example: refunding TZS 50,000 debits TZS 51,180.

**Sync**

```python
refund = client.refunds.create(
    payment_intent="pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK",
    reason="requested_by_customer",
    amount=10_000,  # omit for a full refund
    idempotency_key="refund-ORD-8451-1",  # not "refund:..." (reserved)
)
print(refund.id, refund.state)
```

**Async**

```python
refund = await client.refunds.create(
    payment_intent="pi_01J9X4M3K2J7Y2Q8R6T1V5W3ZK",
    reason="duplicate",
)
```

### 6.2 `retrieve`

```python
retrieve(refund_id: str) -> Refund
```

States: `CREATED`, `PENDING`, `PENDING_REVIEW`, `SUCCEEDED`, `FAILED`, `CANCELLED`.

**Sync**

```python
refund = client.refunds.retrieve("ref_01J9X4QZ8M2N3P")
```

**Async**

```python
refund = await client.refunds.retrieve("ref_01J9X4QZ8M2N3P")
```

---

## 7. Payouts — `client.payouts`

API: `/v1/payouts`. Ids start with `po_`. **TZS only.**

### 7.1 `create`

```python
create(
    *,
    amount: int | Decimal | str | float,   # what the destination receives (TZS)
    destination_id: str | None = None,     # dst_ id; omit = your settlement account
    description: str | None = None,        # max 200
    merchant_reference: str | None = None, # max 120
    idempotency_key: str | None = None,
) -> Payout
```

Your balance is debited `amount + fee + VAT`. Call `quote` first to see the total.

> **Pass your own `idempotency_key`**, derived from your withdrawal record (e.g.
> `"withdrawal-397"`). If your process crashes mid-request and retries, the same
> key returns the original payout instead of paying twice.
>
> If you get `ServiceUnavailableError` (`503 try_later`), nothing was sent. Retry
> with a **new** key. The SDK never retries a 503 automatically for this reason.

States: `REQUESTED` → `AUTHORIZED` (debited and sent) → `SUCCEEDED`. A returned
payout ends in `FAILED_REVERSED` (money credited back); a payout can also end in
`REJECTED_FUNDS`.

**Sync**

```python
payout = client.payouts.create(
    amount=50_000,
    destination_id="dst_01J9X5A1B2C3D4",
    merchant_reference="W-397",
    idempotency_key="withdrawal-397",
)
print(payout.state, payout.fee.value, payout.vat.value)
```

**Async**

```python
payout = await client.payouts.create(amount=50_000, idempotency_key="withdrawal-397")
```

### 7.2 `quote`

```python
quote(*, amount: int | Decimal | str | float | None = None, destination_id: str | None = None) -> PayoutQuote
```

Price a payout without creating it. Omit `amount` to get the maximum you can
send. A quote doesn't check your balance, reserve the price or count toward
limits, and it sends no idempotency key.

**Sync**

```python
quote = client.payouts.quote(amount=50_000, destination_id="dst_01J9X5A1B2C3D4")
print(quote.amount.value, quote.fee.value, quote.vat.value, quote.total_debit.value)
# Decimal('50000') Decimal('1000') Decimal('180') Decimal('51180')
```

**Async**

```python
quote = await client.payouts.quote(amount=50_000)
```

### 7.3 `list`

```python
list(*, state: PayoutState | str | None = None, limit: int | None = None, cursor: str | None = None) -> Page[Payout]
```

**Sync**

```python
page = client.payouts.list(state="SUCCEEDED", limit=20)
```

**Async**

```python
page = await client.payouts.list(state="SUCCEEDED", limit=20)
```

### 7.4 `list_all`

```python
list_all(*, state: PayoutState | str | None = None, page_size: int = 100) -> Iterator[Payout]       # sync
list_all(*, state: PayoutState | str | None = None, page_size: int = 100) -> AsyncIterator[Payout]  # async
```

**Sync**

```python
reversed_ = [p for p in client.payouts.list_all(state="FAILED_REVERSED")]
```

**Async**

```python
async for payout in client.payouts.list_all(state="FAILED_REVERSED"):
    print(payout.id)
```

### 7.5 `retrieve`

```python
retrieve(payout_id: str) -> Payout
```

**Sync**

```python
payout = client.payouts.retrieve("po_01J9X5C7D8E9F0")
```

**Async**

```python
payout = await client.payouts.retrieve("po_01J9X5C7D8E9F0")
```

### 7.6 `limits`

```python
limits() -> list[PayoutLimit]
```

One row per `purpose` (`SETTLEMENT`, `BENEFICIARY`) and `destination_kind`
(`BANK`, `MOMO`), each with `per_txn_cap`, `daily_cap`, `currency` and `source`.

**Sync**

```python
for row in client.payouts.limits():
    print(row.purpose, row.destination_kind, row.per_txn_cap, row.daily_cap)
```

**Async**

```python
rows = await client.payouts.limits()
```

---

## 8. Beneficiaries — `client.beneficiaries`

API: `/v1/beneficiaries`. Ids start with `dst_`. Saved payout destinations.
Needs the key scopes `beneficiaries:read` (for GET) and `beneficiaries:write`
(for create, confirm, resend and delete). Without them you get `PermissionDeniedError`.

**Flow:** `create` → show `verified_name` to your user → the Settlo account
holder receives a 6-digit code → `confirm` → pay with `payouts.create(destination_id=...)`.
A beneficiary in `pending_confirmation` can't receive payouts. To change an
account, delete the beneficiary and create a new one.

### 8.1 `create`

```python
create(
    *,
    kind: BeneficiaryKind | str,       # "MOMO" | "BANK"
    fsp_code: str,                     # e.g. "VODATZ", "CRDBTZ"
    account_number: str,
    account_name: str | None = None,   # max 140; only if the bank/network can't return it
    label: str | None = None,          # max 60
    idempotency_key: str | None = None,
) -> Beneficiary
```

| `kind` | `account_number` format |
|---|---|
| `MOMO` | `255` + 9 digits, **no `+`** (e.g. `255712345678`) |
| `BANK` | 6–32 letters or digits |

**Sync**

```python
dst = client.beneficiaries.create(
    kind="MOMO",
    fsp_code="VODATZ",
    account_number="255712345678",
    label="Supplier A",
)
print(dst.id, dst.status, dst.verified_name)  # dst_..., pending_confirmation, JOHN DOE
print(dst.confirmation.channel, dst.confirmation.sent_to)
```

**Async**

```python
dst = await client.beneficiaries.create(
    kind="BANK",
    fsp_code="CRDBTZ",
    account_number="0150123456789",
)
```

### 8.2 `confirm`

```python
confirm(beneficiary_id: str, *, code: str) -> Beneficiary
```

`code` is the 6-digit code **as a string** (keeps leading zeros). It's valid for
10 minutes and allows 5 wrong tries. The SDK never retries this call, so an
automatic retry can't burn your tries.

| Error | Meaning |
|---|---|
| `UnprocessableEntityError` `confirmation_code_invalid` | Wrong code (tries left in message) |
| `UnprocessableEntityError` `confirmation_code_expired` | Ask for a new code with `resend_code` |
| `ConflictError` `confirmation_not_pending` | Already confirmed or retired |

**Sync**

```python
dst = client.beneficiaries.confirm("dst_01J9X5A1B2C3D4", code="482913")
assert dst.status == "active"
```

**Async**

```python
dst = await client.beneficiaries.confirm("dst_01J9X5A1B2C3D4", code="482913")
```

### 8.3 `resend_code`

```python
resend_code(beneficiary_id: str, *, channel: str | None = None) -> Beneficiary
```

`channel="sms"` forces SMS. Limits: once a minute and 5 per hour per beneficiary,
and 20 per hour per account holder. Beyond that you get `RateLimitError`
(`confirmation_throttled`) with `retry_after` set.

**Sync**

```python
client.beneficiaries.resend_code("dst_01J9X5A1B2C3D4", channel="sms")
```

**Async**

```python
await client.beneficiaries.resend_code("dst_01J9X5A1B2C3D4")
```

### 8.4 `list`

```python
list(*, status: BeneficiaryStatus | str | None = None, limit: int | None = None, cursor: str | None = None) -> Page[Beneficiary]
```

`status`: `pending_confirmation` or `active`.

**Sync**

```python
page = client.beneficiaries.list(status="active")
```

**Async**

```python
page = await client.beneficiaries.list(status="active")
```

### 8.5 `list_all`

```python
list_all(*, status: BeneficiaryStatus | str | None = None, page_size: int = 100) -> Iterator[Beneficiary]       # sync
list_all(*, status: BeneficiaryStatus | str | None = None, page_size: int = 100) -> AsyncIterator[Beneficiary]  # async
```

**Sync**

```python
names = [b.verified_name for b in client.beneficiaries.list_all(status="active")]
```

**Async**

```python
async for b in client.beneficiaries.list_all():
    print(b.id, b.status)
```

### 8.6 `retrieve`

```python
retrieve(beneficiary_id: str) -> Beneficiary
```

**Sync**

```python
dst = client.beneficiaries.retrieve("dst_01J9X5A1B2C3D4")
```

**Async**

```python
dst = await client.beneficiaries.retrieve("dst_01J9X5A1B2C3D4")
```

### 8.7 `delete`

```python
delete(beneficiary_id: str) -> DeletedBeneficiary
```

Retires the beneficiary, including a pending one. Returns `retired=True`.

**Sync**

```python
assert client.beneficiaries.delete("dst_01J9X5A1B2C3D4").retired
```

**Async**

```python
result = await client.beneficiaries.delete("dst_01J9X5A1B2C3D4")
```

---

## 9. Balance — `client.balance`

### 9.1 `retrieve`

```python
retrieve() -> Balance
```

Available balance in TZS. If Settlo is temporarily unavailable (`503 try_later`),
the SDK retries automatically.

**Sync**

```python
balance = client.balance.retrieve()
print(balance.amount.value, balance.amount.currency, balance.as_of)
```

**Async**

```python
balance = await client.balance.retrieve()
```

---

## 10. Checkout sessions — `client.checkout_sessions`

API: `/v1/checkout/sessions`. Ids start with `cs_`. A Settlo-hosted payment page.

### 10.1 `create`

```python
create(
    *,
    amount: int | Decimal | str | float,
    currency: str = "TZS",
    merchant_reference: str | None = None,   # max 120
    description: str | None = None,          # max 1000
    customer_email: str | None = None,       # prefill
    customer_phone: str | None = None,       # prefill, E.164
    customer_name: str | None = None,        # prefill, max 140
    return_url: str | None = None,
    cancel_url: str | None = None,
    allowed_methods: Sequence[PaymentMethod | str] | None = None,  # e.g. ["mobile_money"]
    metadata: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> CheckoutSession
```

Redirect the customer to `session.url`. Sessions expire after 30 minutes. If an
attempt fails, the customer can retry on the same session; each attempt is a
payment carrying the session's `merchant_reference`.

**Sync**

```python
session = client.checkout_sessions.create(
    amount=25_000,
    merchant_reference="ORD-8451",
    customer_phone="+255712345678",
    allowed_methods=["mobile_money"],
    return_url="https://shop.example/orders/8451",
    cancel_url="https://shop.example/cart",
)
return redirect(session.url)
```

**Async**

```python
session = await client.checkout_sessions.create(amount=25_000, merchant_reference="ORD-8451")
```

### 10.2 `retrieve`

```python
retrieve(session_id: str) -> CheckoutSession
```

**Sync**

```python
session = client.checkout_sessions.retrieve("cs_01J9X6F0G1H2J3")
```

**Async**

```python
session = await client.checkout_sessions.retrieve("cs_01J9X6F0G1H2J3")
```

### 10.3 `cancel`

```python
cancel(session_id: str) -> CheckoutSession
```

**Sync**

```python
client.checkout_sessions.cancel("cs_01J9X6F0G1H2J3")
```

**Async**

```python
await client.checkout_sessions.cancel("cs_01J9X6F0G1H2J3")
```

---

## 11. QR code — `client.qr_code`

Each account has one printable (static) QR code. Customers who scan it create
`payer_initiated` payments, which show up in `payments.list()` already `SUCCEEDED`.
Needs the `qr_code:read` / `qr_code:write` scopes.

States: `PENDING`, `ACTIVE`, `FAILED` (request again to retry).

### 11.1 `retrieve`

```python
retrieve() -> QrCode
```

Raises `NotFoundError` if no QR code exists yet. `image.svg` and
`qr_merchant_id` (8 digits, for manual entry) are only present when `ACTIVE`.

**Sync**

```python
qr = client.qr_code.retrieve()
if qr.state == "ACTIVE":
    print(qr.image.svg, qr.qr_merchant_id)
```

**Async**

```python
qr = await client.qr_code.retrieve()
```

### 11.2 `request`

```python
request(*, label: str | None = None, idempotency_key: str | None = None) -> QrCode
```

`label` is max 60 chars and defaults to your trading name. Starts setup (or
retries a `FAILED` code). If a `PENDING` or `ACTIVE` code already exists, it is
returned instead.

**Sync**

```python
qr = client.qr_code.request(label="Main counter")
```

**Async**

```python
qr = await client.qr_code.request(label="Main counter")
```

---

## 12. Webhooks

Settlo signs every delivery with:

```
Settlo-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>." + raw_body)>
Settlo-Event-Id:  <unique per event; retries reuse it>
```

The secret is the full `whsec_...` string shown once in the Settlo dashboard.

### 12.1 `verify_webhook`

```python
from settlopay import verify_webhook

verify_webhook(
    payload: bytes | str,          # RAW request body, before any JSON parsing
    signature_header: str | None,  # value of Settlo-Signature
    secret: str,                   # "whsec_..."
    *,
    tolerance: int = 300,          # seconds; rejects older (and future) timestamps
    now: float | None = None,      # override clock (tests)
) -> WebhookEvent
```

Raises `WebhookVerificationError` if:

- the header is missing or malformed;
- the timestamp is outside the tolerance;
- the signature doesn't match (compared in constant time);
- the body isn't a valid event.

### 12.2 `WebhookVerifier`

The same check, with the secret held in an object whose `repr` is masked:

```python
from settlopay import WebhookVerifier

verifier = WebhookVerifier(os.environ["SETTLO_WEBHOOK_SECRET"], tolerance=300)
event = verifier.verify(raw_body, signature_header)
```

### 12.3 `compute_signature` (for tests)

```python
from settlopay.webhooks import compute_signature

sig = compute_signature(body_bytes, 1767000000, "whsec_test_secret")
header = f"t=1767000000,v1={sig}"
```

### Framework examples

Verification is CPU-only, so the same function works in sync and async code.

**Flask (sync)**

```python
from flask import Flask, request
from settlopay import SIGNATURE_HEADER, EVENT_ID_HEADER, WebhookVerificationError, verify_webhook

app = Flask(__name__)


@app.post("/settlo/webhook")
def settlo_webhook():
    try:
        event = verify_webhook(
            request.get_data(),  # raw bytes
            request.headers.get(SIGNATURE_HEADER),
            os.environ["SETTLO_WEBHOOK_SECRET"],
        )
    except WebhookVerificationError:
        return "", 400
    if already_processed(request.headers.get(EVENT_ID_HEADER)):
        return "", 200
    enqueue(event)  # respond fast (Settlo read timeout is 10 s)
    return "", 200
```

**FastAPI (async)**

```python
from fastapi import FastAPI, Request, Response
from settlopay import WebhookVerificationError, verify_webhook

app = FastAPI()


@app.post("/settlo/webhook")
async def settlo_webhook(request: Request) -> Response:
    raw = await request.body()
    try:
        event = verify_webhook(
            raw, request.headers.get("settlo-signature"), os.environ["SETTLO_WEBHOOK_SECRET"]
        )
    except WebhookVerificationError:
        return Response(status_code=400)
    await enqueue(event)
    return Response(status_code=200)
```

### Handling events correctly

- `event.type` is e.g. `payment_intent.succeeded`; `event.data` is the raw object snapshot (`dict`).
- Events can arrive **out of order**. Act on the object's current state; when in doubt, `payments.retrieve(event.data["id"])`.
- Deduplicate on `Settlo-Event-Id`.
- Missed events aren't resent; catch up with `payments.list_all()`.
- Settlo doesn't follow redirects, and auto-disables an endpoint after 50 consecutive failures.

Event types:

| Prefix | Events |
|---|---|
| `payment_intent.` | `created`, `requires_action`, `authorized`, `partially_paid`, `amended`, `claimed`, `unclaimed`, `succeeded`, `failed`, `cancelled`, `expired` |
| `refund.` | `succeeded`, `failed`, `created` (only for `"*"` subscriptions) |
| `payout.` | `authorized`, `succeeded`, `failed`, `rejected` (only for `"*"` subscriptions) |
| `checkout_session.` | `created`, `confirmed`, `paid`, `cancelled`, `expired` |
| `bill.` | `paid`, `voided`, `payment_received`, `expired` |
| `qr_code.` | `activated`, `failed` |

---

## 13. Pagination

List endpoints return `Page[T]`:

| Field | Type | Meaning |
|---|---|---|
| `data` | `list[T]` | Items on this page, newest first |
| `next_cursor` | `str \| None` | Pass back as `cursor=` for the next page |
| `has_more` | `bool` | More pages exist |

You can page manually with `list(limit=..., cursor=...)`, or use `list_all()`,
which stops when a page is empty or has no `next_cursor`.

```python
# sync, manual
cursor = None
while True:
    page = client.payouts.list(limit=100, cursor=cursor)
    handle(page.data)
    if not page.data or not page.next_cursor:
        break
    cursor = page.next_cursor

# async, automatic
async for payout in aclient.payouts.list_all(page_size=100):
    handle(payout)
```

---

## 14. Idempotency

Every **create** call (`payments.create`, `refunds.create`, `payouts.create`,
`beneficiaries.create`, `checkout_sessions.create`, `qr_code.request`) sends an
`Idempotency-Key` header.

- If you don't pass one, the SDK generates `"<scope>-<uuid4>"` (e.g. `payout-3f2c...`) and **reuses it on every automatic retry** of that call.
- If you pass one, it must be 1–120 printable ASCII characters without spaces, and must not start with `refund:` (reserved by Settlo).
- Same key + same body within 24 h: Settlo returns the original response.
- Same key + different body, or while the first request is still running: `IdempotencyConflictError`.

**Use your own key for anything that moves money.** A generated key only protects
against retries inside a single call. A key derived from your own record (order
id, withdrawal id) also covers your process crashing and restarting.

```python
client.payouts.create(amount=50_000, idempotency_key=f"withdrawal-{withdrawal.id}")
```

`payouts.quote` sends no key. `amend`, `cancel`, `inquire`, `confirm`,
`resend_code` and `delete` don't create anything and send no key.

---

## 15. Retries

```python
from settlopay import RetryPolicy, SettloPay

client = SettloPay(
    retry=RetryPolicy(
        max_retries=2,  # 0-10 extra attempts
        backoff_factor=0.5,  # delay ceiling = backoff_factor * 2**attempt
        max_backoff=8.0,  # cap per delay, seconds
        max_retry_after=60.0,  # honour Retry-After up to this; longer waits raise immediately
    )
)
client = SettloPay(max_retries=0)  # disable retries
```

Delays use exponential backoff with full jitter. What gets retried:

| Failure | Reads, `quote`, `amend`, `inquire` | Creates (carry a key) | `cancel`, `confirm`, `resend_code`, `delete` |
|---|---|---|---|
| Connection failed before sending | ✅ | ✅ | ✅ |
| Timeout after sending, 500, 502, 504 | ✅ | ✅ same key | ❌ |
| 503 | ✅ | ❌ (Settlo wants a new key) | ❌ |
| 429 | ✅ waits `Retry-After` | ✅ | ✅ |
| 400, 401, 402, 403, 404, 409, 422 | ❌ | ❌ | ❌ |

Sync and async clients behave the same; the async client sleeps with `asyncio.sleep`.

---

## 16. Errors

Every exception derives from `SettloError`.

```
SettloError
├── ConfigurationError          bad setup: missing/invalid key, non-HTTPS base_url
├── ValidationError             input rejected locally, before any request
├── WebhookVerificationError    bad/missing/stale webhook signature
├── UnexpectedResponseError     2xx response that couldn't be parsed
├── APIConnectionError          no HTTP response (DNS, TLS, reset)
│   └── APITimeoutError
└── APIError                    Settlo returned an error status
    ├── InvalidRequestError         400   (also a ValidationError)
    ├── AuthenticationError         401
    ├── PaymentFailedError          402
    ├── PermissionDeniedError       403
    ├── NotFoundError               404
    ├── ConflictError               409
    │   └── IdempotencyConflictError
    ├── UnprocessableEntityError    422   business declines
    ├── RateLimitError              429
    └── ServerError                 5xx
        ├── ProviderError           502 / 504
        └── ServiceUnavailableError 503
```

`APIError` attributes:

| Attribute | Example |
|---|---|
| `status_code` | `422` |
| `code` | `"insufficient_funds"`: branch on this |
| `type` | `"business_decline"` |
| `message` | `"Insufficient funds to complete this payout"` |
| `param` | `"amount.value"` |
| `request_id` | quote it to Settlo support |
| `retry_after` | seconds (`RateLimitError`, some 503s) |
| `body` | decoded JSON error body |

`str(err)` looks like `[422 insufficient_funds] Insufficient funds ... (request_id=0d9f...)`.

**Sync**

```python
from settlopay import (
    SettloError,
    ValidationError,
    AuthenticationError,
    PermissionDeniedError,
    UnprocessableEntityError,
    RateLimitError,
    ServiceUnavailableError,
    APIConnectionError,
)

try:
    payout = client.payouts.create(amount=50_000, idempotency_key="withdrawal-397")
except ValidationError as e:  # local check or API 400
    print("bad input:", e.param, e.message)
except AuthenticationError:
    print("check SETTLO_API_KEY")
except PermissionDeniedError as e:  # missing scope / merchant_not_transactable
    print(e.code)
except UnprocessableEntityError as e:  # insufficient_funds, payout_limit_exceeded, ...
    print("declined:", e.code)
except ServiceUnavailableError:
    print("nothing sent; retry later with a NEW idempotency key")
except RateLimitError as e:
    print("slow down; retry in", e.retry_after)
except APIConnectionError:
    print("network problem; safe to retry with the SAME key")
except SettloError as e:
    print("unexpected:", e)
```

**Async**: identical, around `await`:

```python
try:
    await aclient.payouts.create(amount=50_000, idempotency_key="withdrawal-397")
except UnprocessableEntityError as e:
    ...
```

Common `code` values:

| Status | Codes |
|---|---|
| 400 | `invalid_request`, `parameter_invalid`, `unsupported_currency`, `unsupported_method`, `unsupported_phone_network` |
| 401 | `authentication_required` |
| 402 | `payment_failed` |
| 403 | `permission_denied`, `merchant_not_transactable` |
| 404 | `resource_missing` |
| 409 | `idempotency_conflict`, `state_invalid`, `confirmation_not_pending` |
| 422 | `insufficient_funds`, `insufficient_balance`, `no_payout_destination`, `payout_limit_exceeded`, `payout_unpriceable`, `refund_unsupported_method`, `payer_account_unknown`, `payer_name_unknown`, `payment_disputed`, `payment_not_refundable`, `risk_blocked`, `merchant_not_activated`, `merchant_suspended`, `beneficiary_account_not_found`, `beneficiary_limit_reached`, `beneficiary_not_confirmed`, `beneficiary_rejected`, `confirmation_code_expired`, `confirmation_code_invalid`, `no_confirmation_channel` |
| 429 | `rate_limit_exceeded`, `confirmation_throttled` |
| 500 | `api_error` |
| 502 / 504 | `provider_error` / `provider_timeout` |
| 503 | `service_unavailable`, `try_later` |

---

## 17. Input validation rules

Checked locally; on failure the SDK raises `ValidationError` and sends nothing.

| Input | Rule |
|---|---|
| Amounts | `int`, `Decimal`, numeric `str` or finite `float`; > 0; ≤ 2 decimal places; `bool` rejected. QR create/amend: whole shillings |
| Currency | `^[A-Z]{3}$`; payouts are always TZS |
| Payment phone | `+255` + 9 digits |
| Checkout phone | Any E.164 (`+` and 8–15 digits) |
| Email | `local@domain.tld`, ≤ 254 chars |
| URLs | Absolute `http`/`https`, no whitespace or control chars, ≤ 2048 chars |
| Ids | Exact prefix (`pi_`, `ref_`, `po_`, `dst_`, `cs_`) + 1–100 letters/digits; no `/`, `?` or `..` |
| Text fields | Non-blank, no control characters, max length per field |
| Idempotency key | 1–120 printable ASCII, no spaces, not `refund:...` |
| `metadata` | Mapping with `str` keys, JSON-serialisable |
| `limit` | Integer 1–100 |
| `expires_at` | Timezone-aware datetime, 5 min – 30 days ahead |
| `fsp_code` | 2–16 upper-case letters/digits |
| Beneficiary account | MOMO `255` + 9 digits; BANK 6–32 letters/digits |
| Confirmation code | Exactly 6 digits, as a string |
| `allowed_methods` | Non-empty list of lower-case identifiers |

---

## 18. Response models

All models are immutable Pydantic v2 objects. Unknown fields Settlo adds later
are kept in `model.model_extra`. Amounts are `Decimal` and timestamps are
timezone-aware `datetime`. Enum-like fields are plain `str` (compare them with
[§19](#19-enums-and-constants)).

Serialise with `payment.model_dump()` / `payment.model_dump_json()`.

| Model | Fields |
|---|---|
| `Money` | `value: Decimal`, `currency: str` |
| `Payment` | `id`, `state`, `object`, `ref`, `message`, `receipt_no`, `amount: Money`, `method`, `origin`, `merchant_reference`, `linked_payment_id`, `claim: PaymentClaim`, `payer_receipt`, `created_at`, `expires_at`, `amount_received`, `overpaid`, `payments`, `next_action: NextAction`, `failure_code`; properties `is_final`, `succeeded` |
| `NextAction` | `type`, `reference`, `payable_at`, `expires_at`, `image: QrImage`, `display` |
| `QrImage` | `svg` |
| `PaymentClaim` | `claim_partner`, `claim_ref`, `claim_label`, `amount_applied`, `claimed_at` |
| `Refund` | `id`, `state`, `object`, `ref`, `message`, `receipt_no`, `amount`, `payment_intent`, `reason`, `merchant_reference`, `created_at` |
| `Payout` | `id`, `state`, `object`, `ref`, `message`, `amount`, `fee`, `vat`, `destination: PayoutDestination`, `description`, `merchant_reference`, `failure_code`, `created_at`, `updated_at` |
| `PayoutDestination` | `destination_id`, `purpose`, `kind`, `fsp_code`, `account_masked`, `account_name`, `label` |
| `PayoutQuote` | `amount`, `fee`, `vat`, `total_debit` (all `Money`) |
| `PayoutLimit` | `purpose`, `destination_kind`, `per_txn_cap`, `daily_cap`, `currency`, `source` |
| `Beneficiary` | `id`, `status`, `object`, `kind`, `fsp_code`, `account_masked`, `account_name`, `verified_name`, `label`, `created_via`, `confirmation: BeneficiaryConfirmation`, `confirmed_at`, `created_at` |
| `BeneficiaryConfirmation` | `channel`, `sent_to`, `expires_at` |
| `DeletedBeneficiary` | `id`, `object`, `retired: bool` |
| `Balance` | `amount: Money`, `as_of` |
| `CheckoutSession` | `id`, `state`, `object`, `url`, `amount`, `merchant_reference`, `return_url`, `cancel_url`, `expires_at`, `created_at` |
| `QrCode` | `id`, `state`, `label`, `image: QrImage`, `qr_merchant_id`, `qr_kind`, `failure_message`, `created_at`, `updated_at` |
| `WebhookEvent` | `id`, `type`, `api_version`, `created`, `data: dict`, `delivery: WebhookDelivery` |
| `WebhookDelivery` | `id`, `attempt` |
| `Page[T]` | `data: list[T]`, `next_cursor`, `has_more` |

---

## 19. Enums and constants

Enums are `str` subclasses, so `payment.state == PaymentState.SUCCEEDED` works and
every method also accepts the plain string.

| Enum | Values |
|---|---|
| `PaymentMethod` | `MOBILE_MONEY`, `BANK`, `QR` |
| `MobileNetwork` | `VODACOM`, `TIGO`, `AIRTEL`, `HALOTEL` |
| `PaymentState` | see [§5 Payment states](#payment-states) |
| `RefundReason` | `REQUESTED_BY_CUSTOMER`, `DUPLICATE`, `FRAUDULENT`, `OTHER` |
| `RefundState` | `CREATED`, `PENDING`, `PENDING_REVIEW`, `SUCCEEDED`, `FAILED`, `CANCELLED` |
| `PayoutState` | `REQUESTED`, `AUTHORIZED`, `SUCCEEDED`, `FAILED_REVERSED`, `REJECTED_FUNDS` |
| `BeneficiaryKind` | `MOMO`, `BANK` |
| `BeneficiaryStatus` | `PENDING_CONFIRMATION`, `ACTIVE` |
| `QrCodeState` | `PENDING`, `ACTIVE`, `FAILED` |

| Constant | Value |
|---|---|
| `DEFAULT_BASE_URL` | `"https://api.settlopay.co.tz"` |
| `API_VERSION` | `"2026-04-29"` |
| `API_KEY_ENV_VAR` | `"SETTLO_API_KEY"` |
| `SIGNATURE_HEADER` | `"Settlo-Signature"` |
| `EVENT_ID_HEADER` | `"Settlo-Event-Id"` |
| `FINAL_PAYMENT_STATES` | `frozenset` of final payment states |
| `__version__` | SDK version |

---

## 20. Logging and security

```python
import logging

logging.getLogger("settlopay").setLevel(logging.DEBUG)
```

- `DEBUG`: one line per response: `POST /v1/payouts -> 201 (attempt 1, request_id=...)`.
- `INFO`: retries, e.g. `Retrying GET /v1/balance in 0.31s after HTTP 503 (retry 1)`.
- The SDK never logs headers or request/response bodies, so your key and customer data stay out of logs.

Built-in protections:

- HTTPS-only `base_url`; redirects are never followed, so the key can't leak to another host.
- The API key is masked in `repr` (`sk_live_****`). Clients and keys refuse `pickle`/`copy`, and invalid keys are rejected without echoing them.
- Strict id validation, so user input can't change the request path.

Your side:

- Keep keys server-side, in env vars or a secrets manager. Never commit them or ship them to apps.
- Enable secret scrubbing in error trackers (Sentry etc.) for `Authorization`/`api_key`.
- See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## 21. Testing your integration

### Unit tests with respx

```python
import httpx, respx
from settlopay import SettloPay


def test_my_checkout(respx_mock):
    respx_mock.post("https://api.settlopay.co.tz/v1/payments").mock(
        return_value=httpx.Response(201, json={"id": "pi_TEST1", "state": "PENDING_AUTH"})
    )
    client = SettloPay("sk_test_" + "dummy-for-tests", max_retries=0)
    assert client.payments.create(amount=1000, method="bank").id == "pi_TEST1"
```

### Live smoke test (this repository)

Read-only by default (balance, lists, limits, payout quote):

```bash
export SETTLO_API_KEY=sk_...      # never commit it
SETTLO_RUN_LIVE=1 pytest -m live tests/live -v
```

The optional collection test sends one prompt to your own phone. Money only
moves if you approve it:

```bash
SETTLO_RUN_LIVE=1 SETTLO_LIVE_PHONE=+2557XXXXXXXX SETTLO_ALLOW_MONEY_MOVEMENT=1 \
  pytest -m live tests/live -v
```
