# settlo-pay-python-sdk

Typed Python SDK (sync and async) for the [Settlo Pay API](https://settlopay.co.tz/docs):
payments (mobile money, bank, QR), refunds, payouts, beneficiaries, balance,
hosted checkout, QR codes and webhook verification.

- Built on `httpx`; Pydantic v2 response models; `py.typed`, checked with `mypy --strict`
- Inputs are validated before any request is sent
- Idempotency keys are generated automatically and reused across retries
- Retries use exponential backoff, only where they cannot duplicate a charge or payout
- HTTPS only, redirects never followed, the API key is never logged, printed or pickled

📖 **Full reference: [documentation.md](documentation.md)**, covering every method in sync and async form.

> **There is no sandbox.** `sk_test_` and `sk_live_` keys both move real money.

## Install

```bash
pip install settlo-pay-python-sdk
```

Python 3.10+. Import name: `settlopay`.

## Quick start

```python
from settlopay import SettloPay

client = SettloPay()  # reads SETTLO_API_KEY from the environment

payment = client.payments.create(
    amount=25_000,  # TZS, major units
    method="mobile_money",
    phone="+255712345678",  # E.164
    merchant_reference="ORD-8451",
    idempotency_key="order-8451-pay-1",  # derive from your own record
)
print(payment.id, payment.state)  # pi_..., PENDING_AUTH
```

Async:

```python
from settlopay import AsyncSettloPay

async with AsyncSettloPay() as client:
    balance = await client.balance.retrieve()
    async for p in client.payments.list_all():
        ...
```

## Resources

| Attribute | Methods |
|---|---|
| `client.payments` | `create`, `list`, `list_all`, `retrieve`, `amend`, `cancel`, `inquire` |
| `client.refunds` | `create`, `retrieve` |
| `client.payouts` | `create`, `quote`, `list`, `list_all`, `retrieve`, `limits` |
| `client.beneficiaries` | `create`, `list`, `list_all`, `retrieve`, `confirm`, `resend_code`, `delete` |
| `client.balance` | `retrieve` |
| `client.checkout_sessions` | `create`, `retrieve`, `cancel` |
| `client.qr_code` | `retrieve`, `request` |

Amounts accept `int`, `Decimal` or numeric `str` (floats are accepted but discouraged).
Response amounts are `Decimal`.

## Errors

```python
from settlopay import SettloError, UnprocessableEntityError, RateLimitError

try:
    client.payouts.create(amount=50_000, idempotency_key="withdrawal-397")
except UnprocessableEntityError as e:  # business decline
    if e.code == "insufficient_funds":
        ...
except RateLimitError as e:
    print("retry in", e.retry_after)
except SettloError as e:
    print(e, e.request_id)  # quote request_id to Settlo support
```

The full hierarchy is documented in [`settlopay/exceptions.py`](src/settlopay/exceptions.py).
`ValidationError` covers both local input checks and the API's `400` responses.

## Idempotency and retries

Every create call sends an `Idempotency-Key`. If you don't pass one, the SDK
generates a random key and reuses it on every retry of that call. **For payouts
and payments, pass your own key derived from your database record.** Then a
crash-and-restart re-sends the same key, and Settlo returns the original result
instead of paying twice.

Default policy (`RetryPolicy(max_retries=2)`):

| Failure | GET / quote / amend / inquire | Create (has key) | cancel / confirm / resend / delete |
|---|---|---|---|
| Connection refused (never sent) | retry | retry | retry |
| Timeout, 500, 502, 504 | retry | retry, same key | **no** |
| 503 | retry | **no** (Settlo wants a new key) | **no** |
| 429 | retry after `Retry-After` (≤ 60 s) | same | same |

## Webhooks

```python
from settlopay import verify_webhook, WebhookVerificationError


@app.post("/settlo/webhook")
def webhook():
    try:
        event = verify_webhook(
            request.get_data(),  # RAW bytes
            request.headers.get("Settlo-Signature"),
            os.environ["SETTLO_WEBHOOK_SECRET"],  # full whsec_... string
        )
    except WebhookVerificationError:
        return "", 400
    # Deduplicate on request.headers["Settlo-Event-Id"]; events may arrive out of order.
    enqueue(event)  # respond fast, work later
    return "", 200
```

## Logging

The SDK logs to the `settlopay` logger: method, path, status, request id and
retries. It never logs headers or bodies.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install --upgrade "pip>=25.1"
pip install -e . --group dev
pre-commit install
pytest                  # unit tests (live tests are deselected)
ruff check . && ruff format --check . && mypy
```

### Live smoke test

Read-only by default (balance, lists, limits, a payout quote):

```bash
export SETTLO_API_KEY=sk_...           # from your password manager; never commit it
SETTLO_RUN_LIVE=1 pytest -m live tests/live -v
```

Add `SETTLO_LIVE_PHONE=+2557... SETTLO_ALLOW_MONEY_MOVEMENT=1` to also send one
collection prompt to your own phone. Money only moves if you approve it.

### Releasing

Pushing commits only runs CI. A version is published when you push a tag:

1. Bump `src/settlopay/_version.py` and update `CHANGELOG.md`, then commit and push.
2. Optional dry run: Actions → **Publish** → *Run workflow* uploads to TestPyPI.
3. Run `git tag vX.Y.Z && git push origin vX.Y.Z`. The **Publish** workflow
   tests, checks that the tag matches the version, builds, and uploads to PyPI via
   Trusted Publishing (OIDC). No token is stored anywhere.

## License

MIT
