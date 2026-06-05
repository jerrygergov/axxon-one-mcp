# Spec: phase-18-gdpr-bookmark-settings

## Original task statement
Extend the DomainSettings tools (phase 17) with bookmark and GDPR settings
updates, following the same etag/field-mask, approval-gated idiom. These are the
last two pending DomainSettingsService update RPCs (UpdateBookmarkSettings,
UpdateGDPRSettings).

## Background (live-verified before freeze)
- Both GDPR/Bookmark updates carry the etag at the REQUEST level (field 3), unlike
  DataStorage where the etag is inside the settings message. The tools manage this
  difference internally.
- `BookmarkSettings`: `bookmark_max_duration` (Duration), `mandatory_protection`
  (bool), `retention_period` (Duration), plus display mode + categories (out of
  scope). Live-proven reversible: toggled `mandatory_protection` False->True->False
  with the request etag and field mask.
- `GDPRSettings`: single `privacy_mask_type` enum (UNSPECIFIED/MOSAIC/BLACK). The
  update is reachable and accepted (returns an etag, no error) but is a NO-OP on
  this stand: privacy_mask_type stays UNSPECIFIED after update. GDPR privacy
  masking needs a module/license not provisioned here (dead-fixture class like
  HeatMap), so UpdateGDPRSettings is built + unit-tested but stays fixture-warn.

## Acceptance criteria

### AC1 — update_bookmark_settings (safe, field-masked, etag-managed)
Add `update_bookmark_settings(mandatory_protection, bookmark_max_duration_s,
retention_period_s, confirmation)` to `tools/axxon_mcp_settings.py`. Updates only
the provided (non-None) fields; reads the current request etag from
`GetBookmarkSettings`; builds the field mask from exactly the provided fields;
sends `UpdateBookmarkSettings(settings, mask, etag)`. Empty payload -> error, no
wire call. Gated by the existing `AXXON_SETTINGS_APPROVE=1` +
`CONFIRM-settings-update`. Returns the updated values + new etag.

### AC2 — get_bookmark_settings + get_gdpr_settings (reads)
Add `get_bookmark_settings()` and `get_gdpr_settings()` returning flat shapes
(bookmark: mandatory_protection, bookmark_max_duration_s, retention_period_s,
etag; gdpr: privacy_mask_type as the enum name + etag). Read-only, not gated.

### AC3 — update_gdpr_settings (built, gated, fixture-warn live)
Add `update_gdpr_settings(privacy_mask_type, confirmation)` mapping a friendly
mask name (`unspecified`/`mosaic`/`black`) to the enum, with the request-level
etag + field mask. Same gating. Unknown mask name -> error, no wire call. (Live
it is a no-op on this stand; corpus stays fixture-warn.)

### AC4 — server registration
Register the 4 new tools (`get_bookmark_settings`, `update_bookmark_settings`,
`get_gdpr_settings`, `update_gdpr_settings`) in the existing
`register_settings_tools` block. No new flag needed (reuse `--enable-settings`).

### AC5 — unit tests + full suite green
Extend `tools/tests/test_axxon_mcp_settings.py`: bookmark update gating, empty
error, field-mask paths + request-etag carry, seconds<->Duration; gdpr mask-name
mapping + unknown-name error. Full suite stays green.

### AC6 — corpus restamp, live-justified
Restamp `UpdateBookmarkSettings` `pending -> tested-pass` (reversible round-trip).
Restamp `UpdateGDPRSettings` `pending -> tested-warn-fixture-needed` (reachable,
no-op without the GDPR module). Update coverage doc.

## Constraints
- Smallest defensible diff; extend the phase-17 module, do not duplicate.
- Field-masked, etag-managed, never blind-overwrite.
- Any live bookmark mutation restored (read-then-restore); no residue.
- Secrets env-only; sanitize evidence. No biometric data.

## Non-goals
- Bookmark categories / retention_period_display_mode editing.
- Export settings (already tested-pass-safe-record).
- Making GDPR masking actually apply (needs the GDPR module/license).

## Verification plan
- Unit: extended settings suite; full discover run.
- Live: bookmark mandatory_protection toggle + restore (captured); gdpr update
  reachable but no-op (captured, documented as fixture-warn).
