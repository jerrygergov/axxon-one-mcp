# Evidence: phase-5-client-web-api

Date: 2026-06-15
Overall: PASS (every acceptance criterion PASS)

## What shipped
- `tools/axxon_mcp_web_api.py` — `AxxonMcpWebApi`, read-only `web_api` group (6 tools).
- `tools/axxon_mcp_client_api.py` — `AxxonMcpClientApi`, read-only `client_api` group (3 tools).
- `tools/axxon_mcp_server.py` — `CAPABILITY_GROUPS` entries, `--enable-web-api` / `--enable-client-api`
  flags, `register_web_api_tools` / `register_client_api_tools`, `create_server` params,
  `enabled_groups`, and `main()` lazy construction.
- Tests: `tools/tests/test_axxon_mcp_web_api.py` (11), `tools/tests/test_axxon_mcp_client_api.py` (6),
  plus 3 server-registration tests in `tools/tests/test_axxon_mcp_server.py`.
- Docs: README tool-layers table + counts (326 tools / 53 groups / nine layers); roadmap "Current
  Numbers", "HTTP, WebSocket, embeddable video" row, "Layouts...client UI" row, and backlog item 3.

## Live fixture finding driving scope
Stand 100.76.150.18 probed 2026-06-15: Web server, embeddable component (`/embedded.html`,
`/embedded.js`), and WebSocket events (`/events`, `/ws`, `/ws/events` -> 101) are reachable on port
80; Client HTTP API port 8888 is closed. So `web_api` is live-verified and `client_api` is
preflight + fixture-needed. (See memory: stand-web-client-surface-reachable.)

## Acceptance criteria

### AC1 — web_api module: env-only lazy connect, secret redaction, injectable factories — PASS
- `tools/axxon_mcp_web_api.py` defines `AxxonMcpWebApi` with `client_factory`/`config_factory`/
  `socket_factory`. Connect rejects non-env, builds config lazily, returns `mode="read"` and a
  `public_config_summary` (no raw password).
- Unit: `test_axxon_mcp_web_api.py::ConnectTests::test_connect_env_only_lazy_and_redacts_secrets`
  (no client created for "prod"; `password_present` true; raw password absent).
- Live: raw/live-evidence.json `web_connect_profile_keys` has `password_present` and no `password`;
  `web_connect_password_value_absent=true`.

### AC2 — client_api module: read-only preflight + all-fixture-needed catalog, no wire — PASS
- `tools/axxon_mcp_client_api.py` defines `AxxonMcpClientApi`. `client_api_preflight` only
  socket-probes; `list_client_api_operations` performs no wire and marks every op `fixture-needed`.
- Unit: `test_axxon_mcp_client_api.py::PreflightTests` (probes 127.0.0.1 + host, no secret),
  `::OperationCatalogTests::test_operations_all_fixture_needed_no_wire` (no probe calls, 8 ops all
  fixture-needed).
- Live: raw/live-evidence.json `client_api_operations_count=8`, `client_api_all_fixture_needed=true`,
  `client_api_preflight.reachable_count=0` with a `fixture_gap`.

### AC3 — WebSocket probe/sample bounded, no raw bytes, path-allowlisted — PASS
- `tools/axxon_mcp_web_api.py`: probe is a single handshake; sample caps frames to
  `MAX_EVENT_FRAMES=8` and time to `MAX_EVENT_SECONDS=5.0`, returns opcode/size tallies only, never
  raw payload. Both reject any path not in `KNOWN_EVENT_PATHS`.
- Unit: `WebEventsTests` — `test_sample_caps_frames_and_returns_no_raw_bytes`,
  `test_sample_hard_cap_overrides_large_request` (50 frames requested -> <= 8),
  `test_probe_rejects_unknown_path` / `test_sample_rejects_unknown_path` (no socket created).
- Live: raw/live-evidence.json `web_events_sample` -> `frames=1`, `opcode_tallies={"close":1}`,
  `payload_bytes_seen=2` (count only), `frame_cap=4`, `seconds_cap=5.0`; probe `/events` and
  `/ws/events` both `http_status=101, upgraded=true`; no Sec-WebSocket-Accept value in output.

### AC4 — embeddable URL builder (no credentials) + postMessage command catalog — PASS
- `tools/axxon_mcp_web_api.py`: `embeddable_component_url` builds `/embedded.html?...`, rejects bad
  modes, embeds no credentials, returns a paste-ready iframe; `embeddable_component_commands` returns
  the typed catalog (init/reInit/SwitchMode/play|stop/setTime/setCamera) with the ISO-8601 note.
- Unit: `EmbeddableTests` — URL/iframe/no-credential, bad-mode rejection, command-type coverage,
  offline (no socket).
- Live: raw/live-evidence.json `embeddable_url.url` is `http://<stand-host>/embedded.html?origin=...&mode=live`
  (no `root:` credentials); `embeddable_commands_types` lists all six command types.

### AC5 — both groups wired into the server — PASS
- `tools/axxon_mcp_server.py`: `CAPABILITY_GROUPS["web_api"]`/`["client_api"]` with flags;
  `register_web_api_tools` / `register_client_api_tools`; `create_server` params + `enabled_groups`;
  `main()` lazy build + `create_server(...)` kwargs.
- raw/build.txt: `--help` lists both flags; group count 53; 321 server-local tool decorators.
- Unit: `test_axxon_mcp_server.py::test_create_server_registers_web_api_tools_only_when_enabled`,
  `..._client_api_tools_only_when_enabled`, `..._reports_web_and_client_api_disabled_and_enabled`.

### AC6 — offline unit tests cover the surface incl. server registration — PASS
- 11 web_api + 6 client_api module tests + 3 server tests. All offline (fake socket / fake probe /
  StubDocs+FakeFastMCP). raw/test-new-modules.txt: `Ran 17 tests ... OK`.

### AC7 — full suite green, +20 over prior 1156 — PASS
- raw/test-unit.txt: `Ran 1176 tests ... OK` (1156 -> 1176, +20: 17 module + 3 server). No regressions.

### AC8 — docs updated, counts re-derived — PASS
- README.md: 326 tools / 53 groups / nine layers; new "Client / Web API" layer row.
- ALL_IN_ONE_VMS_API_ROADMAP.md: Current Numbers (326/53), "HTTP, WebSocket, embeddable video" row,
  "Layouts...client UI" row, backlog item 3 — all reflect web_api live + client_api preflight/
  fixture-needed (8888 closed). COVERAGE.md unchanged (it enumerates gRPC RPCs, not MCP groups; this
  phase adds no new RPCs).

## Safety checks
- Secret scan of both modules: only docstring mentions of "password/cookie/token/CA"; no raw secret is
  returned (profiles use `public_config_summary` -> `password_present`).
- No mutations: client_api executes no display ops; web_api makes only read handshakes; preflight only
  socket-probes.
- No proto symlink needed or committed (HTTP/WS only). Live evidence sanitized (host -> <stand-host>).
