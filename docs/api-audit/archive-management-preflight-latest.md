# Axxon One Archive Management Preflight

- Started: `2026-05-06T22:40:16.440417+00:00`
- Finished: `2026-05-06T22:40:19.232619+00:00`
- gRPC target: `<demo-host>:20109`
- HTTP target: `http://<demo-host>:80`
- Archive AP: `hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage`

Read-only preflight for archive-management mutations. It does not format, reindex, cancel reindex, resize, clear, delete, or link archive volumes.

## Summary

- PASS: 3
- WARN: 1
- FAIL: 0

## Results

| Status | Group | ms | Evidence |
| --- | --- | ---: | --- |
| PASS | `get_archive_traits` | 135 | keys=2 |
| PASS | `get_volumes_state` | 122 | volume_count=1 states={'MOUNTED': 1} readonly_count=0 |
| PASS | `get_disk_space` | 120 | volume_id_len=36 status_code=OK capacity_present=True |
| WARN | `approval_only_mutations` | 0 | ArchiveService.FormatVolumes, ArchiveService.Reindex, ArchiveService.CancelReindex |
