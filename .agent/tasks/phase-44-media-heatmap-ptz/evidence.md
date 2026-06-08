# Evidence: phase-44-media-heatmap-ptz

Overall: PASS (all acceptance criteria PASS)

## AC1 — TelemetryService PointMove added to axxon_mcp_ptz.py — PASS
`tools/axxon_mcp_ptz.py` adds `point_move(access_point, session_id, x, y)`: validates the access
point is a TelemetryControl endpoint before any wire call (refused/bad-access-point otherwise),
authenticates, builds `PointMoveRequest(point=primitive.Point(x, y))`, and calls
TelemetryService.PointMove. Server tool `ptz_point_move` wired. Focus/Iris already had wrappers.

## AC2 — New read-only HeatMapService module — PASS
`tools/axxon_mcp_heatmap.py` (`AxxonMcpHeatmap`) exposes build_heatmap, build_events_heatmap,
build_floor_heatmap (image metadata only: result flag, heatmap cell count, image byte count — raw
bytes never returned) and execute_heatmap_query / execute_heatmap_query_typed (streaming, capped at
MAX_STREAM_RESPONSES=8, returns response count + last progress only). Module idiom
(client_factory/config_factory/client/profile_name, connect helper, ensure_client,
public_config_summary). No write gate — builds are read-only computations over VMDA metadata.

## AC3 — New read-only MediaService module — PASS
`tools/axxon_mcp_media.py` (`AxxonMcpMedia`) exposes request_connection, request_qos, request_tunnel
and stream_probe (one MediaRequest, reads up to MAX_STREAM_SAMPLES=4, returns sample-type tallies
only). Metadata only: cookie_present boolean (never the raw cookie/token), transport name,
proto/endpoint presence, sample counts. Module idiom; no write gate (transport probes do not change
config).

## AC4 — Server wiring via the established pattern — PASS
`tools/axxon_mcp_server.py`: create_server params `heatmap`/`media`; conditional
register_heatmap_tools / register_media_tools; the two register functions with @server.tool entries
(6 heatmap + 5 media); `--enable-heatmap` / `--enable-media` CLI flags; flag-gated instantiation;
passed to create_server. `ptz_point_move` registered in register_ptz_tools. Server smoke registered
all 11 new tools (raw/build.txt: all imports OK).

## AC5 — Live evidence — PASS
raw/live-verify.txt (sanitized, host -> <demo-host>):
- Telemetry tested-pass: Focus + Iris -> status ok (Empty) on TelemetryControl.0; PointMove ->
  status ok on TelemetryControl.2.
- Telemetry fixture-warn: FocusAuto/IrisAuto UNIMPLEMENTED ("Device does not support"); AreaZoom
  INTERNAL "operation returned error: 2"; PerformAuxiliaryOperation -> GetAuxiliaryOperations
  returns []; StartFillTour/PlayTour (and StopTour/SetTourPoint/StopFillTour/RemoveTour) ->
  GeneralError, no tour created.
- HeatMap tested-pass: BuildHeatmap result=True image_bytes>0; BuildEventsHeatmap result=True
  ~22KB; BuildFloorHeatmap result=True; ExecuteHeatmapQuery + ExecuteHeatmapQueryTyped -> 2 streamed
  responses each with progress on AVDetector.1.
- HeatMap fixture-warn: BuildHeatmapTyped DEADLINE_EXCEEDED >120s (server-side typed-query hang).
- Media tested-pass: RequestConnection cookie_present True; RequestQoS ok with frameRate;
  RequestTunnel proto=tcp cookie_present True; stream_probe (Stream) yields a config_update sample.
- Media fixture-warn: AwaitConnection (needs peer), ConnectEndpoint (NOT_FOUND, needs speaker sink).

## AC6 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps 25 methods: 12 -> tested-pass (Telemetry Focus/Iris/
PointMove; HeatMap Build*/ExecuteHeatmapQuery/Typed; Media RequestConnection/RequestQoS/
RequestTunnel/Stream) and 13 -> tested-warn-fixture-needed (Telemetry FocusAuto/IrisAuto/AreaZoom/
PerformAuxiliaryOperation + 6 tour ops; HeatMap BuildHeatmapTyped; Media AwaitConnection/
ConnectEndpoint). `--write` applied; dry-run after = `0 method(s) restamped`. Coverage doc updated to
275 tested-pass / 36 pending / 50 fixture-warn; TelemetryService 22/32, HeatMapService 5/6,
MediaService 4/6. Also corrected the stale B.9 "HeatMapService is a dead fixture" claim (a
wrong-argument artifact, not a provisioning wall).

## AC7 — Unit tests + full suite green + lint — PASS
New tests: tools/tests/test_axxon_mcp_heatmap.py (7), tools/tests/test_axxon_mcp_media.py (7),
plus 2 PointMove cases added to tools/tests/test_axxon_mcp_ptz.py. They assert input validation
blocks wire calls (client.calls == []), metadata-only returns (no raw bytes/cookies in output), and
streaming caps. raw/test-integration.txt: `946 passed` (930 prior + 16 new). Production modules
(heatmap, media, ptz, server) lint clean (raw/lint.txt: "All checks passed!").
