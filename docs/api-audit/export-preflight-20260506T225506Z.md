# Axxon One Export Preflight

- Started: `2026-05-06T22:55:06.725169+00:00`
- Finished: `2026-05-06T22:55:09.896156+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`

Read-only preflight for export workflows. It does not start export sessions, download files, stop sessions, destroy sessions, or update export settings.

## Summary

- PASS: 2
- WARN: 2
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `list_sessions` | 134 | pages=0 sessions=0 states={} |
| PASS | `get_export_settings` | 131 | etag_len=40 options_keys={'video_file_format': {'type': 'str', 'present': True}, 'image_file_format': {'type': 'str', 'present': True}, 'video_quality': {'type': 'str', 'present': True}, 'audio_quality': {'type': 'str',  |
| WARN | `fixture_preflight` | 533 | export_agents=0 archive_interval=True gap=no export-agent component found |
| WARN | `approval_only_mutations` | 0 | ExportService.StartSession, ExportService.DownloadFile, ExportService.StopSession, ExportService.DestroySession, DomainSettingsService.UpdateExportSettings |
