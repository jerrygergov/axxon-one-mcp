# Spec: phase-44-media-heatmap-ptz

## Original task

Close serviceable pending API methods across the three "physical/hardware" clusters the user
named: TelemetryService (PTZ commands, no dedicated PTZ camera assumed — study proto + probe the
live stand), HeatMapService (heatmaps build from tracker/neurotracker VMDA metadata, so they are
testable against cameras that have a VMDA detector), and MediaService (live streaming / tunneling).

Live probing established the actual serviceable surface on the demo stand (3 telemetry sources on
DeviceIpint.53; many AVDetector/SourceEndpoint.vmda detectors; HeatMapBuilder synthesized AP;
DeviceIpint.1 video source). Only methods that the device actually services are restamped
tested-pass; device/firmware-walled methods are restamped tested-warn-fixture-needed with the live
citation.

## Serviceable scope (12 methods -> tested-pass)

- TelemetryService (3): Focus, Iris, PointMove
- HeatMapService (5): BuildHeatmap, BuildEventsHeatmap, BuildFloorHeatmap, ExecuteHeatmapQuery,
  ExecuteHeatmapQueryTyped
- MediaService (4): Stream, RequestConnection, RequestQoS, RequestTunnel

## Walled scope (9 methods -> tested-warn-fixture-needed, honest live citation)

- TelemetryService: FocusAuto (UNIMPLEMENTED "Device does not support FocusAuto"), IrisAuto
  (UNIMPLEMENTED), AreaZoom (INTERNAL "operation returned error: 2"), PerformAuxiliaryOperation
  (GetAuxiliaryOperations returns no operations on any source), PlayTour/StopTour/StartFillTour/
  SetTourPoint/StopFillTour/RemoveTour (all return GeneralError; no tour is created — firmware does
  not support on-device tours)
- HeatMapService: BuildHeatmapTyped (DEADLINE_EXCEEDED even at 120s with a 30-min window / 8x8 mask
  / DATA result; the typed-query compile path hangs server-side, unlike the string-query path)
- MediaService: AwaitConnection (bidi sink-side, needs a peer offering a connection), ConnectEndpoint
  (NOT_FOUND — needs a real speaker sink endpoint; DeviceIpint.1 has none)

## Acceptance criteria

- AC1: TelemetryService PointMove is added to the existing `tools/axxon_mcp_ptz.py` module
  (Focus/Iris already have wrappers there). PointMove builds a `PointMoveRequest` with a
  `primitive.Point`, requires an acquired session id, and validates inputs before any wire call.
- AC2: A new read-only module `tools/axxon_mcp_heatmap.py` (`AxxonMcpHeatmap`) exposes
  build_heatmap, build_events_heatmap, build_floor_heatmap, execute_heatmap_query (streaming, bounded
  response cap), execute_heatmap_query_typed (streaming, bounded). It follows the module idiom
  (client_factory/config_factory/client/profile_name, connect helper, ensure_client, public_config_summary)
  and returns image metadata only (byte counts, result flag, heatmap length) — never raw image bytes.
  Heatmap builds are read-only computations, so there is no write gate.
- AC3: A new read-only module `tools/axxon_mcp_media.py` (`AxxonMcpMedia`) exposes
  request_connection, request_qos, request_tunnel, and stream_probe (one MediaRequest, reads up to N
  samples, returns sample-type counts only — never raw media bytes). Module idiom; no write gate
  (these establish/probe transport, they do not change config).
- AC4: Server wiring via the established pattern: `axxon_mcp_ptz.py` PointMove tool registered;
  `heatmap` and `media` modules wired with create_server params, conditional register_*_tools
  functions with @server.tool entries, `--enable-heatmap` / `--enable-media` CLI flags, flag-gated
  instantiation, and passed to create_server. Server smoke registers the new tools.
- AC5: Live evidence (sanitized) in raw/live-verify.txt proves each tested-pass method against the
  stand: Focus/Iris return Empty (OK), PointMove OK on TelemetryControl.2; BuildHeatmap/
  BuildEventsHeatmap/BuildFloorHeatmap result=True with image byte counts; ExecuteHeatmapQuery and
  ExecuteHeatmapQueryTyped yield >=1 streamed response with progress; RequestConnection returns a
  cookie; RequestQoS OK with frameRate; RequestTunnel returns tcp config + cookie; Stream yields a
  sample. The 9 walled methods are cited with their live error.
- AC6: Corpus restamp is honest and idempotent: the 12 serviceable methods -> tested-pass, the 9
  walled methods -> tested-warn-fixture-needed. `tools/axxon_corpus_restamp.py --write` then a
  dry-run reports `0 method(s) restamped`. Coverage doc updated. New totals reflect +12 tested-pass.
- AC7: Unit tests for the three modules (FakeClient/FakeConfig, no network) assert input validation
  blocks wire calls, metadata-only returns, and no config secret leak. Full suite green; production
  modules lint clean.

## Constraints

- Credentials only from env; .env never staged. Sanitize host/creds in artifacts (`<demo-host>`,
  `<redacted>`); secret-scan the staged diff.
- Metadata only: never return or store raw image bytes, raw media sample bytes, or session tokens.
- Telemetry motion commands (Focus/Iris/PointMove) are transient nudges with value 0.0 / center
  point; they self-recover and need no rollback. Tours probe used a throwaway tour name and created
  nothing (GeneralError), so nothing to clean up.
- Heatmap and media reads create no persistent state. RequestConnection/RequestTunnel allocate a
  transient cookie that the server reaps on idle; the probe does not stream payload.
- Only restamp what the device actually services. Verifiers judge current code + current results.

## Non-goals

- No new PTZ hardware-dependent features (auto-focus/iris, area zoom, tours, aux operations).
- No bidi sink/producer connection brokering (AwaitConnection, ConnectEndpoint) — needs a peer/speaker.
- No fix for the server-side BuildHeatmapTyped hang.
- No raw media relay or transcoding; stream_probe is a liveness probe only.
