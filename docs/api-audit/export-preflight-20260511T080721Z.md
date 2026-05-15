# Axxon One Export Preflight

- Started: `2026-05-11T08:07:21.852897+00:00`
- Finished: `2026-05-11T08:07:26.134139+00:00`
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
| PASS | `list_sessions` | 192 | pages=1 sessions=1 states={'S_COMPLETED': 1} |
| PASS | `get_export_settings` | 210 | etag_len=40 options_keys={'video_file_format': {'type': 'str', 'present': True}, 'image_file_format': {'type': 'str', 'present': True}, 'video_quality': {'type': 'str', 'present': True}, 'audio_quality': {'type': 'str',  |
| WARN | `fixture_preflight` | 868 | export_agents=0 archive_interval=True gap=no export-agent component found |
| WARN | `approval_only_mutations` | 0 | ExportService.StartSession, ExportService.DownloadFile, ExportService.StopSession, ExportService.DestroySession, DomainSettingsService.UpdateExportSettings |
