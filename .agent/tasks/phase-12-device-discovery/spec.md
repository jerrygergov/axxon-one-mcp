# Task Spec: phase-12-device-discovery

## Metadata
- Task ID: phase-12-device-discovery
- Created: 2026-06-05
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- docs/api-audit/capability-vs-coverage-2026-06-05.md (DiscoveryService 2/5)
- Pattern: tools/axxon_mcp_recognizer.py (read-only streaming module + server reg).
- Live probe (this session): Discover() starts a scan; GetDiscoveryProgress streams
  real found cameras (Hikvision/Dahua with driver/vendor/model/mac/ip).

## Original task statement
Expose DiscoveryService as a READ-ONLY MCP tool so an integration can scan the
network for IP cameras to add (the desktop "search for devices" feature).
`discover_devices` calls `Discover` (start) then consumes the server-streaming
`GetDiscoveryProgress`, aggregating found devices until the scan finishes or caps hit.

DiscoverNode/GetNodeDiscoveryProgress (multi-node) and Probe (single-IP, already
fixture-warn) are OUT OF SCOPE.

## Acceptance criteria
- AC1: New module `tools/axxon_mcp_discovery.py` with an `AxxonMcpDiscovery` dataclass
  exposing `discovery_connect_axxon_profile` and `discover_devices`. Direct gRPC via
  `DiscoveryService` (`axxonsoft/bl/discovery/Discovery.proto`).
- AC2: `discover_devices(max_devices=200, max_seconds=20)` calls `Discover` (Empty),
  then iterates `GetDiscoveryProgress` (Empty, server-stream), de-duplicating devices
  by (mac_address or ip_address), stopping when state is a finished state, when
  max_devices is reached, or when max_seconds elapses. Returns status, device count,
  the final progress state, last promille, and a list of device summaries.
- AC3: Each device summary surfaces driver, vendor, model, mac_address, ip_address,
  ip_port, firmware_version, categories, support_mode (DeviceDescription fields).
- AC4: Caps are enforced and reported back in a `caps` block
  (`max_devices`, `max_seconds`); the stream is always cancelled on exit.
- AC5: Unit tests under `tools/tests/` cover the start+stream flow against a fake
  streaming client, de-duplication, the device cap, and the device-summary shape.
  Full suite stays green.
- AC6: `Discover` and `GetDiscoveryProgress` restamped `pending -> tested-pass` in the
  corpus via `tools/axxon_corpus_restamp.py` with a cited live-evidence string.
  DiscoverNode/GetNodeDiscoveryProgress/Probe stay as-is.
- AC7: Registered in `tools/axxon_mcp_server.py` behind `--enable-discovery`
  (read-only, off by default).

## Constraints
- Reuse `AxxonApiClient` direct gRPC; no new client.
- Read-only and BOUNDED: cap device count and wall-clock; cancel the stream on exit.
- Env-only secrets; sanitize evidence. Discovered camera MAC/IP/vendor are LAN scan
  results, not credentials; they may stay, but redact any WAN address to
  `<redacted-wan>` in committed evidence.
- Google-style docstrings, no banned words, no defensive programming beyond validation.

## Non-goals
- Adding a discovered device (that is the existing create_camera operator workflow).
- DiscoverNode / Probe.
- Continuous/background discovery.

## Verification plan
- Build: new tools/axxon_mcp_discovery.py + tests + server registration + restamp.
- Unit: `python3.12 -m unittest discover -s tools/tests` green incl. new tests.
- Integration: live discover_devices against the stand; record found-device count and
  a redacted sample in raw/. AXXON_TIMEOUT=30, retry 3x on transient DEADLINE_EXCEEDED.
- Lint: n/a.
- Manual: confirm caps block + stream cancels.
