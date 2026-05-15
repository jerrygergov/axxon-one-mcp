# Axxon One Export Settings Update Proof

- Date: `2026-05-11`
- Target: `<demo-host>:20109`
- API: `DomainSettingsService.GetExportSettings` and `DomainSettingsService.UpdateExportSettings`

This was a no-op, ETag-guarded settings mutation. The probe read the current export settings, sent the same `ExportSettings` back with `mask.paths=["options.max_file_size_bytes"]`, and then read settings again.

## Result

- `GetExportSettings` before update returned an ETag with length 40.
- Current `options.max_file_size_bytes` was `0`.
- `UpdateExportSettings` returned an ETag with length 40.
- Follow-up `GetExportSettings` still returned `options.max_file_size_bytes=0`.
- No credentials, token values, file payloads, or generated export artifacts were stored.

Use a full change/restore workflow for any real export default change. This proof only verifies that the API accepts an ETag-guarded no-op update with a field mask.
