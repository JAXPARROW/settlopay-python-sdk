# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately via GitHub's
[private vulnerability reporting](https://github.com/JAXPARROW/settlopay-python-sdk/security/advisories/new).
Include the affected version, a description, and reproduction steps if possible.
**Never include API keys, webhook secrets or customer data in a report.**

You can expect an acknowledgement within 3 business days and a fix or
mitigation plan within 14 days for confirmed issues. We will credit reporters
who want it.

Vulnerabilities in the Settlo Pay API or dashboard itself should go to Settlo
directly (https://settlopay.co.tz/contact).

## Supported versions

| Version | Supported |
|---|---|
| latest 0.x minor | yes |
| older | no |

## What the SDK guarantees

- **Transport:** `base_url` must be `https://`; plain HTTP, embedded credentials
  and query strings are refused. TLS verification uses httpx defaults (certifi).
  Redirects are never followed, so the `Authorization` header cannot be forwarded
  to another host.
- **API key handling:** the key is read from the constructor or `SETTLO_API_KEY`.
  It is held in an object whose `repr`/`str` is masked (`sk_live_****`). The
  client and key refuse `pickle`/`copy`. Invalid keys are rejected without
  echoing the value. Nothing in the SDK logs headers or request/response bodies.
- **Input validation:** amounts, currencies, phone numbers, ids, idempotency keys,
  URLs, lengths and enums are checked locally before any request is sent. Ids
  are matched strictly, so user input cannot change the request path.
- **Duplicate-payment safety:** creates always carry an `Idempotency-Key` that is
  reused on retry. Ambiguous failures on non-idempotent actions are never retried.
- **Webhooks:** HMAC-SHA256 over the raw body with a constant-time comparison and
  a 5-minute replay window.
- **Supply chain:** releases are published from GitHub Actions via PyPI Trusted
  Publishing (OIDC) with attestations; no long-lived PyPI token exists. CI runs
  `bandit` and `pip-audit`; actions are pinned to commit SHAs.

## Your responsibilities

- Keep secret keys server-side. Never ship them in mobile/web clients or commit them.
  Use environment variables or a secrets manager. Rotate a key immediately if exposed.
- Remember there is **no sandbox**: test keys move real money.
- If you pass your own `httpx.Client`, keep TLS verification enabled.
- Error-tracking tools (Sentry etc.) can capture local variables from stack frames.
  Enable their secret scrubbing for `Authorization` and `api_key`.
- Verify every webhook with `verify_webhook` against the raw request body, and
  deduplicate on `Settlo-Event-Id`.
- Use your own stable idempotency keys for payouts so a restart cannot pay twice.
