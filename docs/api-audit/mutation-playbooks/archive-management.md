# Mutation Playbook: Archive Management

- PDF pages: 420-439.
- APIs involved: archive create, volume changes, cloud archive examples, reindex, remove/link operations.
- Fixture requirements: isolated archive storage, non-production node, known disk budget.
- Preflight read snapshot: archive list, volumes state, disk space, and bindings shape.
- Mutation request: create/change/link only a `codex-` archive fixture.
- Verification command: list archives and read volumes/bindings for the fixture.
- Rollback request: unlink/remove the fixture archive and restore volume settings.
- Post-rollback verification: archive list and disk state return to baseline.
- Read-only preflight result: `archive-management-preflight-latest.md` verifies AliceBlue `GetArchiveTraits`, `GetVolumesState`, and `GetDiskSpace`. The demo stand has one mounted volume and disk-space status `OK`.
- No-op dispatch smoke: `archive-management-noop-smoke-latest.md` verifies `ArchiveService.FormatVolumes`, `ArchiveService.Reindex`, and `ArchiveService.CancelReindex` against a `codex-nonexistent-*` volume id without touching real storage.
- Approval-only operations: `ArchiveService.FormatVolumes`, `ArchiveService.Reindex`, and `ArchiveService.CancelReindex` remain approval-only for real archive volume state changes.
- Risk level: high.
- Approval requirement: explicit approval for target node/storage and disk impact.
