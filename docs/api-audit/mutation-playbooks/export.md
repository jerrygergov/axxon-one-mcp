# Mutation Playbook: Export

- PDF pages: 176-180, 218-222.
- APIs involved: export start/status/download/stop/destroy.
- Fixture requirements: export agent, short archived camera interval, byte limit for downloads, temp output path.
- Preflight read snapshot: list export sessions and available archive interval.
- Mutation request: start one short `codex-` export job.
- Verification command: poll status until done/error with timeout.
- Rollback request: stop/destroy the export session and remove generated output.
- Post-rollback verification: list sessions and verify the `codex-` session is absent or terminal.
- Read-only preflight result: `export-preflight-latest.md` verifies `ExportService.ListSessions` and `DomainSettingsService.GetExportSettings`; it also verifies a current archive interval is available for the selected camera. The demo stand has zero export sessions and zero export-agent components.
- Approval-only operations: `ExportService.StartSession`, `DownloadFile`, `StopSession`, `DestroySession`, and `DomainSettingsService.UpdateExportSettings` are intentionally not executed by preflight.
- Risk level: medium.
- Approval requirement: explicit approval for disk usage and export-agent target.
