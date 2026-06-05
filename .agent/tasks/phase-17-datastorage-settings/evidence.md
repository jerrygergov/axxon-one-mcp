# Evidence Bundle: phase-17-datastorage-settings

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + gating — PASS
- `tools/axxon_mcp_settings.py` adds `AxxonMcpSettings` mirroring `AxxonMcpAudit`.
  Update gated by `AXXON_SETTINGS_APPROVE=1` + `CONFIRM-settings-update`; env unset
  -> disabled, wrong token -> gap, no wire call either way.
- Proof: `UpdateGatingTests`; live [gate] lines (raw/live-verify.txt).

## AC2 — get_data_storage_settings — PASS
- `GetDataStorageSettings` -> flat `system_logs {retention_period_s,
  cleanup_period_s}`, `vmda {retention_period_s}`, `etag`; durations as seconds.
- Proof: `GetTests.test_get_shape_seconds`; live get returned real values + etag.

## AC3 — update_data_storage_settings (field-masked, etag-managed) — PASS
- Reads current etag, builds the FieldMask from exactly the provided fields,
  updates only those, returns updated values + new etag. Empty payload -> error,
  no wire call. Caller never handles etags or mask paths.
- Proof: `UpdateTests` (mask paths per provided field, carries read etag,
  single-field mask); live update cleanup 43200->43320 then restore to 43200.

## AC4 — server registration behind a flag — PASS
- `register_settings_tools` registers the 2 tools + connect; wired via
  `--enable-settings` (off by default) + `settings` param (6-edit pattern).
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit tests + full suite green — PASS
- 6 tests in `tools/tests/test_axxon_mcp_settings.py`.
- Full suite: `Ran 737 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp, live-justified — PASS
- `UpdateDataStorageSettings` restamped `pending -> tested-pass`;
  `GetDataStorageSettings` already tested-pass (re-cited). Coverage 189 pass /
  135 pending / 37 warn; DomainSettingsService 6/8.

## Stand hygiene
- The single live mutation was restored to its original value (read-then-restore);
  data-storage settings end unchanged. Updates are always field-masked
  (never a blind overwrite) with the read etag. No biometric data.

## Sanitization
- raw/live-verify.txt: host/creds redacted; etag fingerprint redacted.
