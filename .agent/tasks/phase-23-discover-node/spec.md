# Spec: phase-23-discover-node

## Original task statement
Close the pending DiscoveryService method `DiscoverNode` (node-scoped network
device discovery) by adding a read-only `discover_node_devices` tool to the
existing `tools/axxon_mcp_discovery.py` module, live-verify it, and restamp the
corpus. `DiscoverNode` is the node-scoped twin of the already-shipped `Discover`:
it starts a scan on one node via `DiscoverNode(DiscoveryRequest{node})` and the
results stream from `GetNodeDiscoveryProgress(DiscoveryRequest{node})` (already
tested-pass). It is read-only (a network scan, no VMS mutation), like the shipped
`discover_devices`, so no approval gate is needed.

## Acceptance criteria
- **AC1**: `tools/axxon_mcp_discovery.py` gains
  `discover_node_devices(node="", max_devices=200, max_seconds=20.0)` that clamps
  the caps the same way as `discover_devices`, starts the scan via
  `DiscoverNode(DiscoveryRequest(node=node))`, then drains
  `GetNodeDiscoveryProgress(DiscoveryRequest(node=node))`, aggregating devices
  until the device/time cap or a finished state. It returns the same shape as
  `discover_devices` plus the echoed `node` and a `progress_timed_out` bool.
- **AC2**: The progress-drain loop is shared between `discover_devices` and
  `discover_node_devices` via a private helper (no duplicated loop body). The
  helper tolerates a progress-stream `grpc.RpcError` with
  `StatusCode.DEADLINE_EXCEEDED` gracefully: it stops draining and the caller
  reports `progress_timed_out=True` with whatever devices were gathered, instead
  of raising. Other RpcErrors still propagate. `discover_devices` keeps its
  existing return shape and behavior.
- **AC3**: The new tool `discover_node_devices` is registered in
  `tools/axxon_mcp_server.py` inside the existing `register_discovery_tools`
  (the discovery module is already wired behind `--enable-discovery`; no new flag
  or create_server param). `DISCOVERY_TOOL_NAMES` includes the new name.
- **AC4**: Unit tests in `tools/tests/test_axxon_mcp_discovery.py` (fake stub +
  pb2) cover: `discover_node_devices` aggregates devices from node-progress pages
  and echoes the node; cap clamping; a DEADLINE_EXCEEDED mid-drain yields
  `progress_timed_out=True` (not an exception) with partial devices; and that
  `discover_devices` still works unchanged. Full suite stays green.
- **AC5**: `tools/axxon_corpus_restamp.py` restamps `DiscoverNode` to
  `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json` reflects it
  (DiscoveryService Discover/DiscoverNode/GetDiscoveryProgress/GetNodeDiscoveryProgress
  all pass; Probe stays fixture-warn). Coverage doc count moves to 199 pass-class
  / 124 pending / 38 fixture-warn and notes DiscoverNode. Restamp dry-run reports
  0 after `--write`.

## Constraints
- Probe-first already done: `DiscoverNode` live-verified read-only (3/3 standalone
  OK, returns Empty; node-progress yielded state=PROGRESS_STATE_RUNNING promille=42
  devices=3). Node identifier is the bare node name (TLS CN "Server"); `hosts/Server`
  fails "Can't get connection channel"; empty node = current node. See
  raw/live-verify.txt.
- `GetNodeDiscoveryProgress` is intermittently slow on this single-node stand and
  can hit the per-call timeout before yielding; the graceful DEADLINE_EXCEEDED
  handling is the motivation (a real observability concession for a read-only
  network scan that the server may not populate immediately).
- Read-only: no VMS mutation, no rollback, no approval gate (mirrors
  `discover_devices`).
- Reuse the existing module's caps (DEVICE_CAP/SECONDS_CAP), `_summarize_device`,
  and connect/ensure_client. Do not duplicate the progress loop.
- Secrets env-only. Committed evidence sanitized: host -> `<demo-host>`, creds ->
  `<redacted>`, device MAC/IP -> `<device>`. Node name `Server` may stay. No
  proto/CA/PDF committed.
- TDD: add the failing tests first, then implement.

## Non-goals
- No device-add workflow (that stays in the create_camera operator path).
- No change to `Probe` (stays fixture-warn) or to the global `discover_devices`
  return shape.
- No new server flag or create_server param.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_discovery"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_discovery.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
