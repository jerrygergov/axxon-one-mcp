# Evidence Bundle: phase-18-gdpr-bookmark-settings

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — update_bookmark_settings (field-masked, etag-managed) — PASS
- Extends `tools/axxon_mcp_settings.py`. Reads the request-level etag from
  `GetBookmarkSettings`, builds the mask from exactly the provided fields, sends
  `UpdateBookmarkSettings(settings, mask, etag)`. Empty payload -> error, no wire
  call. Gated by `AXXON_SETTINGS_APPROVE=1` + `CONFIRM-settings-update`.
- Proof: `BookmarkTests` (gating, empty error, mask paths + request-etag carry);
  live mandatory_protection False->True->False round-trip (raw/live-verify.txt).

## AC2 — get_bookmark_settings + get_gdpr_settings — PASS
- Flat read shapes; gdpr surfaces the friendly mask-type name + etag.
- Proof: `BookmarkTests.test_get_shape`, `GDPRTests.test_get_shape`; live gets.

## AC3 — update_gdpr_settings (built, gated, fixture-warn live) — PASS
- Maps friendly mask name (unspecified/mosaic/black) to the enum, request-level
  etag + field mask. Unknown name -> error, no wire call. Live: accepted but a
  no-op on this stand (value stays unspecified), documented fixture-warn.
- Proof: `GDPRTests` (name mapping, unknown error, gating); live no-op recorded.

## AC4 — server registration — PASS
- 4 new tools registered in `register_settings_tools` (reusing `--enable-settings`).
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit tests + full suite green — PASS
- 9 new tests (15 total in the settings suite).
- Full suite: `Ran 746 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp, live-justified — PASS
- `UpdateBookmarkSettings` -> tested-pass; `UpdateGDPRSettings` ->
  tested-warn-fixture-needed. Coverage 190 pass / 133 pending / 38 warn;
  DomainSettingsService 7/8.

## Stand hygiene
- The bookmark mutation was restored (read-then-restore); the GDPR update was a
  no-op. Stand ends unchanged. Updates always field-masked + etag-carried. No
  biometric data.

## Sanitization
- raw/live-verify.txt: host/creds + etag fingerprints redacted.
