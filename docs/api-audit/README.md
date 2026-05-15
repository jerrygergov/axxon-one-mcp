# Axxon One API Audit

This folder tracks the one-by-one gRPC and HTTP API audit for plugin and vertical integration work.

## Generated Artifacts

- `grpc-api-catalog.md`: service-by-service RPC catalog.
- `grpc-api-catalog.csv`: machine-readable RPC catalog.
- `http-endpoints-catalog.md`: HTTP endpoint catalog from proto annotations.
- `live-readonly-sweep-latest.md`: latest conservative live gRPC read sweep.
- `live-readonly-sweep-latest.json`: machine-readable latest conservative live gRPC read sweep.
- `http-grpc-sweep-latest.md`: latest HTTP `/grpc` parity sweep.
- `http-grpc-sweep-latest.json`: machine-readable latest HTTP `/grpc` parity sweep.
- `http-v1-sweep-latest.md`: latest safe `/v1` GET and read-like POST endpoint sweep.
- `http-v1-sweep-latest.json`: machine-readable latest safe `/v1` endpoint sweep.
- `mutating-fixture-sweep-latest.md`: latest controlled low-risk mutating fixture sweep.
- `mutating-fixture-sweep-latest.json`: machine-readable latest controlled mutating fixture sweep.
- `export-preflight-latest.md`: latest read-only export sessions/settings/fixture preflight.
- `export-smoke-latest.md`: latest controlled gRPC export lifecycle smoke.
- `http-export-smoke-latest.md`: latest controlled legacy HTTP export lifecycle smoke.
- `archive-management-noop-smoke-latest.md`: latest no-op archive-management dispatch smoke.
- `delete-video-noop-probe-latest.md`: latest no-op dispatch probe for the PDF legacy HTTP delete-video endpoint.
- `mcp-live-smoke-latest.md`: latest read-only MCP live-inspection smoke against the demo stand.
- `mcp-corpus/`: Phase 0 structured corpus and Phase 1 docs-query notes for the planned public Axxon One MCP server.
- `pdf-gap-coverage-matrix.md`: machine-trackable PDF gap status, risk, tooling, report, and next step matrix.
- `pdf-gap-coverage-summary.md`: summary counts and final gap disposition.
- `client-sdk-usage.md`: reusable Python client examples for direct gRPC, HTTP `/grpc`, `/v1`, inventory, and archive fixtures.
- `read-fixture-notes.md`: read-only fixture fixes and remaining subsystem-required warning groups.
- `integration-playbooks.md`: API choices for common plugin and vertical-integration patterns.
- `mutating-api-fixtures.md`: fixture and rollback strategy for write/destructive APIs.

## Current Coverage

- Services: 51
- RPC methods: 361
- HTTP annotations: 221
- Read or stream-read heuristic: 160
- Mutating heuristic: 147
- Needs manual safety review: 54
- Live-tested method entries already recorded: 176

## Latest Sweep Results

- Direct gRPC read sweep: PASS=117, WARN=32, FAIL=0
- HTTP `/grpc` parity sweep: PASS=66, WARN=9, FAIL=0
- HTTP `/v1` safe endpoint sweep: PASS=70, WARN=8, FAIL=0
- Controlled mutating fixture sweep: PASS=1, WARN=0, FAIL=0
- Demo-stand export preflight on 2026-05-11: PASS=3, WARN=1, FAIL=0; export sessions/settings, current archive interval discovery, and `hosts/Server/MMExportAgent.0` fixture discovery pass.
- Demo-stand gRPC export lifecycle on 2026-05-11: PASS=2, WARN=0, FAIL=0; temporary `codex-*` archive snapshot export completed and downloaded a bounded JPEG result, then destroyed the session; temporary live export reached `S_RUNNING`, then stop/destroy cleanup passed.
- Demo-stand legacy HTTP export lifecycle on 2026-05-11: PASS=1, WARN=0, FAIL=0; `POST /export/archive/...` returned HTTP 202, `GET /export/{id}/status` reached state 2, bounded `GET /export/{id}/file` returned JPEG bytes, and `DELETE /export/{id}` returned HTTP 204.
- Demo-stand security mutation lifecycle on 2026-05-11: PASS=1, WARN=0, FAIL=0; temporary UUID-indexed `codex-*` role/user lifecycle, generated in-memory password set, temp-role global/object/group/macro permission updates, no-op password-policy/IP-filter/trusted-IP writes, temporary LDAP directory add/edit/remove, and rollback to baseline counts passed.
- Demo-stand archive management no-op smoke on 2026-05-12: PASS=5, WARN=0, FAIL=0; no-op `FormatVolumes`, `Reindex`, and `CancelReindex` dispatch against a `codex-nonexistent-*` volume id returned `NOT_FOUND` or empty responses, and the fake volume remained absent before and after.
- Demo-stand delete-video no-op probe on 2026-05-12: PASS=1, WARN=0, FAIL=0; the PDF `DELETE /archive/contents/bookmarks/` shape reached the server and returned HTTP 404 for a `codex-nonexistent-*` endpoint/storage pair without targeting real archive data.
- Demo-stand fixture disposition on 2026-05-12: FOUND=5, MISSING=5, WARN=0; export agent, maps, detectors, RTSP playback, and the embeddable component at `/embedded.html` are present, while PTZ telemetry, control panels, water-level devices, and Client HTTP API remain missing. WebSocket `/events` still upgrades then closes during receive.
- MCP Phase 0 corpus on 2026-05-12: generated `api_methods.json` with 361 gRPC methods, `http_endpoints.json` with 221 annotated endpoints, `task_recipes.json`, `fixtures.json`, `safety_policies.json`, and `known_behaviors.json`.
- MCP Phase 1 docs-only server foundation on 2026-05-12: `arm64-docker/tools/axxon_mcp_docs.py` serves the corpus without credentials, `arm64-docker/tools/axxon_mcp_server.py` wraps it in FastMCP tools/resources, and unknown APIs return explicit `gap` results.
- MCP Phase 2 read-only live inspection foundation on 2026-05-12: `arm64-docker/tools/axxon_mcp_live.py` reuses `AxxonApiClient` for redacted inventory summaries and fixture preflight; `axxon_mcp_server.py --enable-live` exposes live tools only when explicitly enabled.
- MCP live-inspection demo smoke on 2026-05-12: read-only inventory summary returned 33 cameras, 14 archives, 35 detector entries, 18 AppDataDetector entries, 51 event suppliers, and 15 metadata endpoints; `subscribe detector events` preflight is `ready`.

## Audit Rules

- Use local proto definitions as the source of truth for method signatures.
- Prefer live direct-gRPC tests for exact behavior.
- Use HTTP `/grpc` and annotated `/v1/...` endpoints for HTTP parity checks.
- Never run destructive/mutating APIs without an explicit fixture and rollback plan.
- Record every live test result in generated or handwritten docs.
- Keep credentials, tokens, serial numbers, and license keys out of docs.

## Status Buckets

- `tested-pass`: live tested successfully.
- `tested-pass-empty`: API call works but returned no rows on this server.
- `tested-pass-safe-record`: live tested with an isolated temporary record.
- `tested-warn-fixture-needed`: live call reached the server but needs a better fixture, active subsystem, or non-empty parameter.
- `tested-fail`: live test failed due to a tool or unexpected server error and needs investigation.
- `pending`: not yet live tested.

## Commands

Use the reusable local API client in new tools:

```text
arm64-docker/tools/axxon_api_client.py
```

See:

```text
arm64-docker/docs/api-audit/client-sdk-usage.md
```

Runnable integration examples:

```text
arm64-docker/tools/examples/
```

Current core tools using the reusable client path: `axxon_api_probe.py`, `axxon_readonly_sweep.py`, `axxon_event_search.py`, `axxon_http_grpc_sweep.py`, `axxon_http_v1_sweep.py`, and `arm64-docker/tools/examples/`.

Regenerate the proto-derived catalogs:

```bash
./arm64-docker/tools/generate_api_catalog.py
```

Run the conservative direct-gRPC read sweep:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_readonly_sweep.py
```

Run HTTP `/grpc` parity for direct-gRPC-passing unary read methods:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_grpc_sweep.py
```

Run the safe `/v1` GET plus read-like POST endpoint sweep:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_v1_sweep.py
```

Run the controlled SharedKV mutating fixture with rollback:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_mutating_fixture_sweep.py
```
