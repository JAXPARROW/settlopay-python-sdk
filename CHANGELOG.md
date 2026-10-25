# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-25

### Changed
- Releases are now published by pushing a `vX.Y.Z` tag, via PyPI Trusted Publishing.
- The PyPI publish action is pinned to its release commit rather than the tag object.
- README: updated release instructions.

## [0.1.0] - 2026-10-25

### Added
- Sync (`SettloPay`) and async (`AsyncSettloPay`) clients for Settlo Pay API `2026-04-29`.
- Payments, refunds, payouts (incl. quote and limits), beneficiaries, balance,
  checkout sessions and QR code endpoints.
- Webhook signature verification (`verify_webhook`, `WebhookVerifier`).
- Automatic idempotency keys, a safe retry policy with exponential backoff, and
  a typed exception hierarchy.
