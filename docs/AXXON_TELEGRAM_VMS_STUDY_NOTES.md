# Axxon Telegram VMS Study Notes

Source studied:

```text
/Users/jerrygergov/Documents/GitHub/axxon-telegram-vms
```

## Purpose

`axxon-telegram-vms` is a Telegram-first control and notification layer for Axxon One.

Main production entrypoints:

- `scripts/axxon_tg_bot.py`
- `scripts/archive_stream_relay.py`
- `scripts/axxon_web_api.py`

The bot uses Axxon One mostly through the web HTTP API and the HTTP `/grpc` wrapper.

## API Lessons Useful For This Repo

The bot has useful production-oriented patterns we should reuse conceptually:

- HTTP `/grpc` response parsing must handle plain JSON, multipart-like payloads, and `text/event-stream`.
- Event searches need normalized operator-facing cards, not just raw Axxon event JSON.
- Camera and detector filters should prefer exact access points when available.
- If a requested scope cannot be resolved, do not silently fall back to a broad query.
- LPR results can store plates in several places, including `body.data.Hypotheses`, `details.auto_recognition_result[_ex].hypotheses`, `details.listed_item_detected_result.listed_plate_info`, and sometimes localization text.
- Subscription filters map to `DomainNotifier` include filters with `event_type` plus optional `subject`.

## Files Worth Re-reading

- `scripts/axxon_web_api.py`
- `axxon_telegram_vms/client/transport.py`
- `axxon_telegram_vms/models/event_normalization.py`
- `axxon_telegram_vms/models/query_filters.py`
- `axxon_telegram_vms/services/event_search.py`
- `axxon_telegram_vms/services/license_plate_search.py`
- `axxon_telegram_vms/services/subscriptions.py`
- `tests/test_event_search_service.py`
- `tests/test_event_search_execution.py`
- `support/references/live-data-model/README.md`
- `support/references/live-data-model/raw/events.recent.json`

## Comparison With Current Direct gRPC Lab

Telegram bot approach:

- Uses HTTP `/grpc` wrapper.
- Uses Basic auth in its current `AxxonClient`.
- Parses SSE and multipart-style `/grpc` responses.
- Optimized for Telegram UX, subscriptions, media links, and archive relay.

Current local API lab approach:

- Uses direct gRPC on `20109`.
- Uses TLS root CA and `grpc.ssl_target_name_override`.
- Authenticates with `AuthenticateEx2`, then sends token metadata.
- Optimized for exact proto behavior, API validation, and low-level learning.

Both are useful. Direct gRPC should remain the main expert/test path. The Telegram bot repo is a practical reference for UX shaping, normalization, and HTTP wrapper behavior.

## Event Search Features Ported Into This Repo

The new local CLI borrows these ideas from the Telegram bot repo:

- Operator-friendly normalized event cards.
- Camera name/access-point resolution.
- Category classification for detector, LPR, alert, integrity, status, and generic events.
- Plate extraction from multiple raw event shapes.
- Text/value/subject filtering.
- Safe behavior when a named camera cannot be resolved.

Tool:

```text
arm64-docker/tools/axxon_event_search.py
```

Latest saved output:

```text
arm64-docker/docs/api-test-runs/event-search-latest.json
```
