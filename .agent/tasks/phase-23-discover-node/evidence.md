# Evidence Bundle: phase-23-discover-node

## Summary
- Overall status: PASS (all 5 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — discover_node_devices — PASS
- `discover_node_devices(node, max_devices, max_seconds)` added to
  `tools/axxon_mcp_discovery.py`: clamps caps, starts the scan via
  `DiscoverNode(DiscoveryRequest(node))`, drains
  `GetNodeDiscoveryProgress(DiscoveryRequest(node))`, returns the discover_devices
  shape plus the echoed `node` and `progress_timed_out`.
- Proof: `DiscoverNodeTests.test_node_aggregates_and_echoes_node`,
  `test_node_empty_defaults_current`; live node="Server" found 3 devices.

## AC2 — shared helper + graceful deadline — PASS
- `_drain_progress` aggregates devices for both methods (no duplicated loop). A
  progress-stream `grpc.RpcError` with `DEADLINE_EXCEEDED` stops draining and the
  caller reports `progress_timed_out=True` with partial devices; other RpcErrors
  propagate. `discover_devices` keeps its shape/behavior.
- Proof: `DiscoverNodeTests.test_node_deadline_is_graceful` (partial devices kept,
  no exception), existing `DiscoveryTests` still green; live `progress_timed_out=True`
  handled cleanly.

## AC3 — server registration — PASS
- `discover_node_devices` registered inside the existing `register_discovery_tools`
  (no new flag/param; module already wired behind `--enable-discovery`). Name added
  to `DISCOVERY_TOOL_NAMES`.
- Proof: raw/test-unit.txt (server import OK).

## AC4 — unit + full suite green — PASS
- 4 new tests (8 in the discovery suite). Full suite `Ran 790 tests ... OK`
  (raw/test-unit.txt).

## AC5 — corpus restamp + coverage doc — PASS
- DiscoverNode -> tested-pass. Coverage 199 pass-class / 124 pending / 38
  fixture-warn. All 4 non-fixture DiscoveryService methods now pass (only Probe
  stays fixture-warn). Restamp dry-run reports 0 after --write.

## Stand hygiene
- Read-only: a node-scoped network scan was started and progress read; nothing on
  the stand was created, changed, or deleted. No proto/CA/PDF committed; secrets
  env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`, device MAC/IP
  -> `<device>`. Node name `Server` may stay.
