# Task Spec: phase-5h-metadata-search

## Metadata
- Task ID: phase-5h-metadata-search
- Created: 2026-06-04
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp/.claude/worktrees/focused-benz-eee61e

## Original task statement

Add a metadata / VMDA object-track search capability to the MCP server, matching the
desktop client's "Metadata search" (MOTION IN AREA / object tracks). Investigation proved:
- `MetadataService.PullMetadata` returns live VMDA tracklets from a tracker's `.vmda`
  SourceEndpoint (confirmed live: moving objects with bbox/color/behavior on camera 1's
  `AVDetector.112/SourceEndpoint.vmda`).
- `VMDAService.ExecuteQueryTyped` is the archived forensic search (MotionInArea, LineCrossing,
  Loitering, MoveFromAreaToArea, MultipleObjects + object-type/behaviour constraints). The
  correct binding is `access_point` = the `.vmda` endpoint and `camera_ID` = that same
  access-point string (empty/placeholder ids return server INTERNAL). On THIS stand it returns
  0 intervals because VMDA tracks are not persisted to the archive DB, but the call is correct
  and returns data on any stand that records metadata.

Deliver a read-only `AxxonMcpMetadata` module + MCP tools behind `--enable-metadata`.

## Acceptance criteria

- AC1: New module `tools/axxon_mcp_metadata.py` exposes `AxxonMcpMetadata` with
  `connect_axxon_profile`, `list_vmda_sources`, `live_track_sample`, and `vmda_query`.
- AC2: `list_vmda_sources()` returns the stand's VMDA-capable endpoints (the
  `*/SourceEndpoint.vmda` access points), reusing the existing analytics/inventory discovery;
  result is a dict with `status` and a bounded `sources` list.
- AC3: `live_track_sample(access_point, seconds, limit)` wraps
  `MetadataService.PullMetadata`, is bounded by both a duration cap and a frame/object limit,
  and returns `{status, access_point, applied:{seconds,limit}, count, tracklets:[...]}` where
  each tracklet summary carries id, state, behavior, and bbox. Caps clamp to module maxima.
- AC4: `vmda_query(access_point, query_type, ...)` wraps `VMDAService.ExecuteQueryTyped` using
  the proven binding (`camera_ID = access_point`), supports at least `motion_in_area` (default
  full-frame polygon) with optional `object_types` (face/human/group/vehicle) and
  `behaviours` (moving/abandoned) constraints and a bounded time range, and returns
  `{status, access_point, query_type, interval_count, object_count, intervals:[...]}` (bounded).
- AC5: All inputs are clamped against module caps (max seconds, max frames/objects, max
  intervals); credentials come only from env via `AxxonClientConfig.from_env`; no host/token
  literals in code.
- AC6: The three capabilities are registered as MCP tools in `register_metadata_tools` in
  `tools/axxon_mcp_server.py`, gated behind a new `--enable-metadata` flag (mirroring
  `--enable-detector-archive`); a server test asserts they register only when enabled.
- AC7: Unit tests cover the module (caps clamping, response shapes, query construction,
  graceful handling of an empty/zero-result query) using a stub client; all pre-existing tests
  still pass (count grows from 621).
- AC8: Live verification against the demo stand: `list_vmda_sources` returns >0 sources;
  `live_track_sample` on a real `.vmda` endpoint returns status ok (tracklets when traffic is
  present); `vmda_query` executes without error (intervals may be 0 on this stand — documented).

## Constraints

- Read-only: no mutation of stand config. PullMetadata channel is bounded and closed cleanly.
- Reuse `AxxonApiClient` (`stub_from_proto`, `import_module`, `message_to_dict`) and the
  existing detector-archive discovery for VMDA endpoints; do not duplicate transport logic.
- No new third-party deps. No defensive try/except beyond bounding the stream and surfacing
  a clean error dict (a user-facing guarantee: the tool must never hang or leak a raw stack).
- Match existing module/tool naming and registration patterns (see `AxxonMcpDetectorArchive`
  and `register_detector_archive_tools` / `register_admin_tools`).
- Timestamps for VMDA use `%Y%m%dT%H%M%S.%f`; `camera_ID` must equal the access_point string.

## Non-goals

- Enabling metadata archiving on the stand (server-side config; out of scope).
- Heatmap build, LineCrossing/Loitering/MoveFromAreaToArea/MultipleObjects beyond minimal
  plumbing (motion_in_area is the required query type; others may be added later).
- C#/Node; this is a server-side Python MCP capability.
- PTZ Tag&Track (separate deferred phase).

## Verification plan

- Unit: `python3.12 -m unittest discover -s tools/tests` green, count grows; new test module
  `tools/tests/test_axxon_mcp_metadata.py` + a `register_metadata_tools` assertion in
  `test_axxon_mcp_server.py`.
- Live: run module methods against the stand (AXXON_HOST=<host>, GRPC 20109, CN=Server) for
  AC8; capture sanitized evidence under `.agent/tasks/phase-5h-metadata-search/raw/`.
