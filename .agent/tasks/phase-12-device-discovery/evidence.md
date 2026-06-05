# Evidence Bundle: phase-12-device-discovery

## Summary
- Overall status: PASS (all 7 acceptance criteria PASS)
- Last updated: 2026-06-05

## AC1 — module + dataclass + direct gRPC — PASS
- `tools/axxon_mcp_discovery.py` adds `AxxonMcpDiscovery` with
  `discovery_connect_axxon_profile`, `discover_devices`. Direct gRPC via
  `stub_from_proto(DISCOVERY_PROTO, "DiscoveryService")`.

## AC2 — start + stream + dedup + stop conditions — PASS
- `discover_devices` calls `Discover` (Empty), then iterates the server-streaming
  `GetDiscoveryProgress`, de-duplicating by mac/ip, stopping on a finished state,
  max_devices, or max_seconds. Returns status/state/promille/count/devices.
- Proof: `test_discover_aggregates_and_dedupes`.

## AC3 — device summary shape — PASS
- Surfaces driver/vendor/model/mac/ip/port/firmware/categories/support_mode.
- Proof: `test_device_summary_shape`; live sample shows Hikvision + Dahua cameras.

## AC4 — caps enforced + stream cancelled — PASS
- `caps` block returned; cap stops aggregation; stream `cancel()` called on exit.
- Proof: `test_device_cap_enforced_and_stream_cancelled`, `test_caps_reported`.

## AC5 — unit tests + full suite green — PASS
- 4 tests in `tools/tests/test_axxon_mcp_discovery.py`.
- Full suite `Ran 705 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp, live-justified — PASS
- Live (raw/live-verify.txt): scan started; 3 real network cameras streamed
  (Hikvision/Dahua, driver/vendor/model/mac/ip). WAN addresses redacted.
- `Discover` restamped `pending -> tested-pass`; `GetDiscoveryProgress` already
  tested-pass (unchanged). DiscoveryService now 4/5.

## AC7 — server registration behind --enable-discovery — PASS
- `register_discovery_tools` registers `discovery_connect_axxon_profile` +
  `discover_devices`; wired via `--enable-discovery` (read-only, off by default);
  `discovery` param threaded through `create_server`.

## Sanitization
- raw/live-verify.txt: WAN addresses redacted; LAN MAC/IP of discovered cameras are
  scan results (not credentials). No host IP / creds.
