# Task Spec: phase-5-client-web-api

## Metadata
- Task ID: phase-5-client-web-api
- Created: 2026-06-15T09:28:07+00:00
- Frozen: 2026-06-15
- Repo root: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp
- Working directory at init: /Users/jerrygergov/Documents/GitHub/axxon-one-mcp

## Guidance sources
- AGENTS.md, CLAUDE.md (root + global)
- docs/ALL_IN_ONE_VMS_API_ROADMAP.md (rows: "HTTP, WebSocket, embeddable video"; backlog item 3 first-class `client_api`/`web_api`)
- README.md, docs/COVERAGE.md
- docs/integration-apis-3.0/sections/03-embeddable-video-component-for-working-with-web-server.md (pages 525-529)
- tools/axxon_mcp_media.py, tools/axxon_mcp_videowall.py, tools/axxon_mcp_export.py (module/registration/test patterns)
- tools/axxon_external_client_preflight.py (existing Client HTTP + embeddable preflight smoke)
- tools/axxon_mcp_server.py (CAPABILITY_GROUPS, register_*_tools, create_server, main())
- Memory: [[stand-web-client-surface-reachable]], [[fixture-blocked-unreachable-on-stand]]

## Original task statement
Phase 5: Client/Web API Layer. Add separate `client_api` / `web_api` groups for the Client HTTP
API, WebSocket events, embeddable video component helpers, and web-client parity. This needs a
reachable client/Web fixture. Use TDD; create evidence; run `python3.12 -m unittest discover -s
tools/tests`; fresh verifier must PASS; commit and push to main.

## Live fixture finding (decisive, probed 2026-06-15 on stand 100.76.150.18)
- Only TCP 80 open. Ports 8888 (legacy Client HTTP API), 81, 8000, 8080, 443 refused.
- Port 80 serves the genuine embeddable Video component: `GET /embedded.html` -> 200 text/html,
  title "Video component", loads `./embedded.js` + `./conn.js`; `GET /embedded.js` -> 200
  application/javascript; `GET /` and `/index.html` -> web client.
- WebSocket events live on port 80: `GET /events`, `/ws`, `/ws/events` -> HTTP 101 Switching
  Protocols, `Upgrade: websocket`. `/socket`, `/api/ws` -> 404.
- The `/v1` HTTP corpus (docs/api-audit/mcp-corpus/http_endpoints.json, 221 endpoints) has ZERO
  websocket/client-control/immersion entries; Client HTTP API + WebSocket are a separate Web-server
  feature, not the gRPC `/v1` bridge.
- The embeddable component is a browser-side postMessage/iframe API (init/reInit/SwitchMode/
  play/stop/setTime/setCamera). The MCP can only ship URL + command-schema helpers for it.

## Chosen scope (user-confirmed 2026-06-15): "Both groups, honest split"
Two new first-class groups mirroring existing group conventions:

### `web_api` group (reachable, live-verified) — module `tools/axxon_mcp_web_api.py`, class `AxxonMcpWebApi`
Read-only / knowledge; no mutation, no write gate (parity with `media`). Tools:
- `web_api_connect_axxon_profile(profile="env")` — env-only, lazy, redacted profile summary,
  `mode="read"`. Same shape as `media_connect_axxon_profile`.
- `embeddable_component_url(camera_origin="", mode="live", time="", archive_pane=None)` — build the
  `/embedded.html` iframe `src` URL from the connected profile's `http_url` plus a ready-to-paste
  `<iframe>` snippet. No credentials embedded in the URL.
- `embeddable_component_commands()` — return the typed postMessage command catalog (init, reInit,
  SwitchMode, play/stop, setTime, setCamera) with field schemas and ISO-8601 note, sourced from the
  integration doc. Knowledge only.
- `web_events_probe(path="/events")` — perform a single bounded WebSocket handshake (raw socket,
  timeout-capped) and report handshake metadata only: HTTP status (expect 101), `upgrade` header
  presence, whether the path is one of the known event paths. No credentials/cookies/headers values
  leaked beyond presence booleans; only an allowlist of known WS paths (`/events`, `/ws`,
  `/ws/events`) is probed.
- `web_events_sample(path="/events", max_frames=4, max_seconds=...)` — open one bounded WS
  connection, read up to a capped number of frames within a capped wall-clock window, and report
  frame-count / opcode tallies / byte counts only. No raw frame payload bytes returned. Hard caps:
  frames <= small constant, seconds <= small constant, bytes per frame summarized not returned.
- `web_client_parity_report()` — knowledge: summarize what the Web client / embeddable component can
  do vs which MCP groups already cover it (live/view/export/videowall/alarms), highlighting the
  embeddable-component-only browser surface. Offline, corpus/doc-sourced.

### `client_api` group (preflight + fixture-needed) — module `tools/axxon_mcp_client_api.py`, class `AxxonMcpClientApi`
Read-only preflight + honest fixture-needed catalog (mirrors Phase 4 fixture-needed handling). Tools:
- `client_api_connect_axxon_profile(profile="env")` — env-only, lazy, redacted summary, `mode="read"`.
- `client_api_preflight(client_http_port=8888)` — socket probe of `127.0.0.1:<port>` and
  `<host>:<port>`, plus an HTTP reachability check; report reachable booleans + a `fixture_gap`
  string when nothing is reachable. Reuses the probe shape from `axxon_external_client_preflight.py`
  but returns a sanitized dict (no password). Must NOT execute any SwitchLayout/display mutation.
- `list_client_api_operations()` — catalog the Client HTTP API operations (SwitchLayout,
  AddCameraToDisplay, RemoveCameraFromDisplay, SetArchiveMode, SetSearchMode, SetImmersionMode,
  current-layout cameras, display selection) each marked `status="fixture-needed"` with the risk and
  the required fixture (reachable Client HTTP API target on the configured port). Knowledge only; no
  wire calls.

## Acceptance criteria
- AC1: New module `tools/axxon_mcp_web_api.py` defines `AxxonMcpWebApi` with the six `web_api` tools
  above. Connect is env-only + lazy + redacts secrets (no raw password in any output). Live calls go
  through an injectable client/socket factory so unit tests run offline.
- AC2: New module `tools/axxon_mcp_client_api.py` defines `AxxonMcpClientApi` with the three
  `client_api` tools above. `client_api_preflight` performs only read-only socket/HTTP probes and
  returns sanitized dicts; `list_client_api_operations` marks every Client HTTP API operation
  `fixture-needed` and performs no wire calls.
- AC3: `web_events_probe` and `web_events_sample` are byte- and time-bounded: the WS probe is a
  single handshake; the sample enforces a hard frames cap and a hard wall-clock seconds cap and
  returns frame-count/opcode/byte-size metadata only, never raw frame payload bytes. Only the
  allowlisted WS paths are probed.
- AC4: `embeddable_component_url` builds a valid `/embedded.html` iframe `src` from the connected
  profile's `http_url`, embeds no credentials, and returns a paste-ready `<iframe>` snippet;
  `embeddable_component_commands` returns the typed postMessage catalog matching the integration doc.
- AC5: Both groups are wired into `tools/axxon_mcp_server.py`: `CAPABILITY_GROUPS` entries
  (`web_api`, `client_api`) with `--enable-web-api` / `--enable-client-api` flags; `register_web_api_tools`
  / `register_client_api_tools`; `create_server` params; `main()` lazy instantiation. They are
  on-by-default like the other groups and disabled under `--read-only` only for any mutating tool
  (these groups are read-only/knowledge, so they may stay enabled in read-only mode parity with
  `media`/`docs`; match whatever the existing read-only-safe groups do).
- AC6: New offline unit tests `tools/tests/test_axxon_mcp_web_api.py` and
  `tools/tests/test_axxon_mcp_client_api.py` cover: env-only connect + secret redaction, URL/command
  builders, WS probe/sample caps + no-raw-bytes + path allowlist (via fake socket factory), preflight
  read-only + sanitized, and fixture-needed operation catalog. Plus a server-registration assertion
  (both groups present in `CAPABILITY_GROUPS`, tools registered) added to the existing server test or
  a new test.
- AC7: Full suite green: `python3.12 -m unittest discover -s tools/tests` exits 0 with no
  regressions; the previously-passing count increases by the new tests.
- AC8: Docs updated for consistency: README tool-layers table + group count, docs/COVERAGE.md (if it
  enumerates groups), and the roadmap backlog item 3 / "HTTP, WebSocket, embeddable video" row note
  reflecting that `web_api` is live-reachable and `client_api` is preflight/fixture-needed (port 8888
  closed on stand). Counts must be re-derived, not guessed.

## Constraints
- Follow existing module/registration/test conventions exactly (see `media`, `videowall`, `export`,
  `docs`). Dataclass with injected `client_factory`/`config_factory` (+ a `socket_factory` for WS).
- Secrets policy: never return passwords, tokens, cookies, raw media/frame bytes, or CA material.
  Reuse `public_config_summary` for profile summaries and `client.sanitize` where a client is present.
- WebSocket and preflight calls must be hard-capped (frames, seconds, bytes) and path-allowlisted.
- No new third-party dependencies; use stdlib `socket`/`base64`/`urllib` (raw WS handshake) like the
  existing preflight smoke. Python 3.12, uv/stdlib only.
- Do not weaken or duplicate `axxon_external_client_preflight.py`; the new `client_api_preflight` may
  reuse its probe helpers but must return a sanitized MCP dict, not write report files.
- Live evidence against the stand must be sanitized (host/user/password/CA redacted; `AXXON_TLS_CN=Server`
  and intrinsic UIDs may remain). Retry transient remote-stand timeouts up to three times.
- No symlink to docs/grpc-proto-files committed; these groups need no protos (HTTP/WS only). Reads
  work over HTTP/port 80 with no CA.

## Non-goals
- No execution of Client HTTP API mutations (SwitchLayout/AddCameraToDisplay/SetArchiveMode/etc.) —
  port 8888 is closed on this stand; they remain fixture-needed.
- No raw media/video frame retrieval; no browser rendering/screenshot of the embeddable component.
- No new gRPC RPC coverage; this phase is HTTP/WebSocket/embeddable only.
- No Phase C destructive/infra work; no C# generator; no signing.

## Verification plan
- Build: `python3.12 -c "import tools.axxon_mcp_web_api, tools.axxon_mcp_client_api"` equivalent via
  importing modules from tools dir; `python3.12 tools/axxon_mcp_server.py --help` lists the new flags.
- Unit tests: `python3.12 -m unittest discover -s tools/tests` (exit 0); plus the two new test
  modules individually.
- Integration tests: bounded live evidence against stand 100.76.150.18 port 80 for `web_events_probe`
  (101 handshake), `embeddable_component_url` reachability of `/embedded.html`, and
  `client_api_preflight` showing 8888 unreachable. Sanitized; stored under raw/.
- Lint: repo has no enforced linter; n/a beyond import/compile check.
- Manual checks: confirm no secrets/raw bytes in any tool output; confirm caps enforced; confirm
  read-only (no mutations fired).

## Assumptions (resolved narrowly from request + probes)
- "Reachable client/Web fixture" = port 80 Web server (confirmed). Client HTTP API command port 8888
  is not exposed here, so `client_api` is intentionally preflight/fixture-needed, not apply-ready.
- WS event subscription protocol details are not documented in the corpus; `web_events_sample`
  reports transport-level frame metadata only and does not attempt to decode application event
  payloads (which would require an undocumented subscribe handshake).
