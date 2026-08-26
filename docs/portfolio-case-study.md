# Portfolio Case Study

## Problem

Creators who sell 3D-printable files often need to respond quickly when someone comments a keyword on Instagram. Manual replies are slow, and browser automation can be fragile or violate platform expectations.

## Solution

This project implements an official API-based automation: receive Meta webhook events, validate signatures, filter comments by media and keyword, and send a private reply with the configured STL link.

## Technical Highlights

- FastAPI webhook backend.
- Meta `X-Hub-Signature-256` validation.
- SQLite idempotency to avoid duplicate replies.
- Polling fallback when webhooks are delayed by review/access constraints.
- Raspberry Pi deployment scripts with systemd services.
- Separate status monitor for service health, logs and tunnel URL visibility.
- Tests with fake payloads and mocked API calls.

## Why It Matters

The project shows a complete product-minded automation: API integration, reliability, deployment, local monitoring and safe handling of credentials.

## Next Improvements

- Add a small admin UI for managing automations.
- Add GitHub Actions coverage reporting.
- Add Docker support for VPS deployment.
- Add structured logs and alerting.

