# Spec: phase-17-datastorage-settings

## Original task statement
Add DomainSettingsService data-storage tools: read the data-storage settings
(system-logs + VMDA/metadata retention and cleanup) and update them safely. The
update is approval-gated and confirmation-tokened, consistent with the existing
mutation idiom, and manages the etag/field-mask internally so the change is
scoped and concurrency-safe.

## Background (live-verified before freeze)
- `GetDataStorageSettings` returns `system_logs_settings {retention_period,
  cleanup_period}`, `vmda_storage_settings {network_location, retention_period}`,
  and an `etag` (optimistic-concurrency fingerprint).
- `UpdateDataStorageSettings(data_storage_settings, update_mask)` applies a
  field-masked change; the `DataStorageSettings.etag` carries the concurrency
  token. Response returns the updated settings + a new etag.
- Live-proven reversible: read cleanup_period=43200s -> update to 43260s (new
  etag) -> readback confirms -> restore to 43200s. Durations are seconds.
- GDPR (`privacy_mask_type`) and Bookmark settings exist too but are out of scope
  here to keep the diff tight; data-storage is the richest reversible target.

## Acceptance criteria

### AC1 — module + dataclass + gating
`tools/axxon_mcp_settings.py` adds `AxxonMcpSettings` (dataclass) mirroring
`AxxonMcpAudit`: `client_factory`/`config_factory`/`client`/`enabled`,
`settings_connect_axxon_profile`, `ensure_client`. The update tool is gated by
`AXXON_SETTINGS_APPROVE=1` + confirmation token `CONFIRM-settings-update`. Env
unset -> `disabled`; wrong token -> `gap`; neither touches the stand.

### AC2 — get_data_storage_settings (read)
`get_data_storage_settings()` calls `GetDataStorageSettings` and returns a flat,
readable shape: `system_logs {retention_period_s, cleanup_period_s}`,
`vmda {retention_period_s}`, and `etag`. Durations surfaced as integer seconds.
Read-only, not gated.

### AC3 — update_data_storage_settings (safe, field-masked, etag-managed)
`update_data_storage_settings(system_logs_retention_s, system_logs_cleanup_s,
vmda_retention_s, confirmation)` updates only the provided (non-None) fields. It
reads the current etag, builds the field mask from exactly the provided fields,
sends `UpdateDataStorageSettings`, and returns the updated values + new etag. If
no field is provided -> error (no wire call). The caller never handles etags or
field-mask paths.

### AC4 — server registration behind a flag
`register_settings_tools` registers the 2 tools +
`settings_connect_axxon_profile`, wired via `--enable-settings` (off by default)
and a `settings` param through `create_server` (6-edit pattern).

### AC5 — unit tests + full suite green
`tools/tests/test_axxon_mcp_settings.py` covers (fake client, no network):
get shape + seconds conversion, update gating (disabled / bad token), update
empty-payload error, update builds the correct field-mask paths for each provided
field and carries the read etag, and seconds->Duration conversion. Full suite
`python3.12 -m unittest discover -s tools/tests` stays green.

### AC6 — corpus restamp, live-justified
After a live run (raw/live-verify.txt, sanitized), restamp
`GetDataStorageSettings` and `UpdateDataStorageSettings` `pending -> tested-pass`
via `tools/axxon_corpus_restamp.py`. The other DomainSettings RPCs (Export/GDPR/
Bookmark get+update) stay pending. Update coverage doc counts.

## Constraints
- Smallest defensible diff; reuse `public_config_summary`, `message_to_dict`,
  `stub_from_proto`, `import_module`.
- The update must be field-masked (never blind-overwrite) and etag-managed.
- Any live mutation must be restored (read-then-restore), leaving no residue.
- Secrets env-only; sanitize evidence. No biometric data.

## Non-goals
- GDPR/Bookmark/Export settings updates (separate follow-up).
- VMDA network_location credential changes (would need real storage creds).

## Verification plan
- Unit: the fake-client suite; full discover run.
- Live: get -> update cleanup_period -> readback -> restore (already captured),
  leaving settings at their original values.
