# Task Spec: phase-37-archive-volume

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (ArchiveService rows)
- tools/axxon_mcp_config_change.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close the serviceable pending ArchiveService method
(Resize) via a new gated module mirroring the config_change idiom. Live-verify reversibly.
Document the non-serviceable pending methods honestly (deprecated / environment-walled).

## Live probe findings (2026-06-07, demo stand)
- Resize: SERVICEABLE. GetVolumesState on standalone storage
  hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage returns one MOUNTED volume
  (id 4b025154-..., capacity 107374182400). Resize to the SAME capacity returns
  EStatusCode DONE (0): reversible no-op, no data change.
- ChangeBookmarks: server returns UNIMPLEMENTED "ChangeBookmarks deprecated." -> fixture-warn.
  Replacement is BookmarkService.CreateBookmark (already pass).
- CreateReaderEndpoint: CORBA INTERNAL system exception on every source AP -> fixture-warn.
- Seek: depends on a reader endpoint that cannot be created -> fixture-warn.
- ClearInterval: CORBA INTERNAL on every resolvable source/storage AP form; the recorded
  source under AliceBlue is not resolvable on this stand -> fixture-warn.

## Message shapes (confirmed live)
- GetVolumesStateRequest{access_point}; GetVolumesStateResponse{volumes_state: map<id, {state, used_bytes, capacity_bytes, progress}>}.
- ResizeRequest{access_point, volume_id, new_size(uint64)}; ResizeResponse{status_code: EStatusCode(DONE/OPERATION_IN_PROGRESS/NO_SPACE/NOT_SUPPORTED/TRY_LATER)}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_archive_volume.py exposes list_volume_states (read) and
  resize_volume (gated write), with connect helper + ensure_client + _stub_and_pb2 +
  _write_gate matching the config_change idiom. Approval env AXXON_ARCHIVE_VOLUME_APPROVE=1,
  confirmation token CONFIRM-archive-resize.
- AC2: resize_volume enforces the gate before any wire call: env-off -> {"status":"disabled"};
  bad token -> {"status":"gap"}; missing access_point/volume_id -> {"status":"error"}.
  Unit tests assert client.calls==[] in each case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_archive_volume_tools with @server.tool entries, --enable-archive-volume flag,
  flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: list_volume_states returns the mounted volume; resize_volume to the
  volume's current capacity returns status DONE (reversible no-op, capacity unchanged).
  Raw transcript raw/live-verify.txt with host/creds sanitized.
- AC5: Corpus restamp marks ArchiveService.Resize tested-pass; ChangeBookmarks,
  CreateReaderEndpoint, Seek, ClearInterval left tested-warn-fixture-needed with honest
  citations. Dry-run after --write reports 0 restamped. Coverage doc updated.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- Resize only to the volume's current capacity in verification (reversible no-op).
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>.
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- Shrinking/growing volumes to a different size in verification.
- Making the deprecated/environment-walled methods pass.
- Reader-endpoint / ClearInterval tooling (subsystem unavailable on this stand).

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_archive_volume.py (read, gate, no-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript + restamp dry-run clean.
