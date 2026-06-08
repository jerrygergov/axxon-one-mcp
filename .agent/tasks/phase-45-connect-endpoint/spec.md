# Spec: phase-45-connect-endpoint

## Original task

Close MediaService.ConnectEndpoint, which phase-44 left fixture-warn ("needs a real speaker sink").
The operator provisioned the fixtures: camera 50 has a microphone with continuous environmental
sound, and camera 54 is a real camera with a speaker sink. Live probing then established that
ConnectEndpoint connects a producer (mic source) to a consumer (speaker sink) and returns
status=DONE end-to-end. Ship a `connect_endpoint` MCP tool and restamp the method tested-pass.

This is a small follow-up to phase-44, not a new cluster. The other phase-44 walls were re-probed
against the same fixtures and stay fixture-warn: the 10 Telemetry methods (FocusAuto/IrisAuto/
AreaZoom/PerformAuxiliaryOperation + 6 tour ops) are blocked by Axxon's generic Hikvision driver on
camera 54 (GoPreset works once a preset exists, but it was already tested-pass); BuildHeatmapTyped
still hangs server-side; AwaitConnection is the NGP sink-side transient-object interface and cannot
be driven from a plain client call.

## Acceptance criteria

- AC1: `tools/axxon_mcp_media.py` gains a `connect_endpoint(source_endpoint, sink_endpoint,
  priority)` method that validates both endpoints before any wire call, sends the ConnectEndpoint
  Context request, briefly holds the link with a keepalive, then releases it with keepalive=false
  (reversible — no persistent connection left), and returns the connection status name +
  `connected` boolean. Metadata only: no raw audio bytes relayed or stored. The tool is wired into
  the server (`connect_endpoint` in register_media_tools) and added to MEDIA_TOOL_NAMES.
- AC2: Live evidence (sanitized) in raw/live-verify.txt shows ConnectEndpoint returning status=DONE
  for camera-50 mic -> camera-54 speaker (and camera-54 mic -> camera-54 speaker), proving a real
  producer->consumer audio link is established end-to-end, with the wedged-sink retry caveat
  documented honestly.
- AC3: Corpus restamp is honest + idempotent: MediaService.ConnectEndpoint -> tested-pass with the
  live DONE citation. `tools/axxon_corpus_restamp.py --write` then a dry-run reports `0 method(s)
  restamped`. MediaService becomes 5/6; totals reflect +1 tested-pass (276 tested-pass). Coverage
  doc updated.
- AC4: Unit test for connect_endpoint (FakeClient, no network): asserts a DONE response maps to
  connected=True with the keepalive_ms, and that missing endpoints block the wire call
  (client.calls == []). Full suite green; production modules lint clean.

## Constraints

- Credentials only from env; .env never staged. Sanitize host/creds in artifacts; secret-scan the
  staged diff.
- Metadata only: connect_endpoint returns connection status, never raw audio samples.
- The tool must release the link (keepalive=false) so it does not leave a held connection.
- Only restamp ConnectEndpoint; do not touch the methods that remain genuinely walled.

## Non-goals

- No change to the 10 Telemetry driver-walled methods, BuildHeatmapTyped (server bug), or
  AwaitConnection (transient-object architecture).
- No raw audio relay / transcoding; connect_endpoint is a connect-and-report tool.
- No fix for the server-side wedged-sink resource state (a stand quirk, not an RPC defect).
