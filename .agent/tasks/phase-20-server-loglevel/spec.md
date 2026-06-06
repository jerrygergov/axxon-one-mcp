# Spec: phase-20-server-loglevel

## Original task statement
Close the two pending ServerSettings mutations (`SetLogLevel`, `DropLogs`) so the
service reaches 3/3 tested-pass. Ship them as approval-gated MCP tools behind a
new `--enable-server` flag, live-verify both against the demo stand, and restamp
the corpus. `SetLogLevel` is reversible (read level, set, restore). `DropLogs`
permanently deletes server log history; the user explicitly authorized the live
drop for this phase (same class as the previously-authorized Clear).

## Acceptance criteria
- **AC1**: New module `tools/axxon_mcp_server_settings.py` (`AxxonMcpServerSettings`)
  mirrors the audit-injector gating idiom. `_write_gate(confirmation)` returns
  `{"status":"disabled"}` when `AXXON_SERVER_APPROVE` != "1", `{"status":"gap"}`
  on a wrong confirmation token, and `None` (proceed) only when both pass. No wire
  call happens before the gate passes.
- **AC2**: `get_log_level(nodes=None)` reads via `GetLogLevel`, returning a
  `{node: level_name}` map plus `failed_nodes`. `set_log_level(level="", nodes=None,
  confirmation="")` is gated, requires a non-empty `level` (else `{"status":"error"}`,
  no wire call), resolves the `LogLevel` enum by name, sends `SetLogLevel`, and
  reads back the resulting levels.
- **AC3**: `drop_logs(nodes=None, confirmation="")` is gated and, once past the
  gate, sends `DropLogs` for the given nodes (empty = current node) and returns
  `{"status":"applied","failed_nodes":[...]}`. Invalid `level` name in
  `set_log_level` returns `{"status":"error"}` with the list of valid names, no
  wire call.
- **AC4**: `tools/axxon_mcp_server.py` registers the tools behind a new
  `--enable-server` flag using the established 6-edit pattern: `server_settings`
  param on `create_server`, registration call, `register_server_settings_tools`
  (4 tools: `server_connect_axxon_profile`, `get_log_level`, `set_log_level`,
  `drop_logs`), `--enable-server` CLI flag, flag-gated instantiation in `main`,
  and the value passed to `create_server`.
- **AC5**: Unit tests in `tools/tests/test_axxon_mcp_server_settings.py` (fake pb2
  stand-ins) cover: reads, gating (disabled/gap with no wire call recorded),
  empty/invalid level error (no wire call), set-then-readback order, and drop_logs
  request shape. Full suite stays green (`python3.12 -m unittest discover -s
  tools/tests`).
- **AC6**: `tools/axxon_corpus_restamp.py` restamps `SetLogLevel` and `DropLogs`
  to `tested-pass`; `docs/api-audit/mcp-corpus/api_methods.json` reflects it
  (ServerSettings 3/3); coverage doc count moves to 195 pass-class / 128 pending /
  38 fixture-warn and notes ServerSettings 3/3. Restamp dry-run reports 0 after
  `--write`.

## Constraints
- Probe-first already done: both RPCs live-verified through direct gRPC against
  the stand before any code (see raw/live-verify.txt). SetLogLevel reversed back
  to its original level; DropLogs authorized irreversible.
- ServerSettings carries no etag; writes are plain field builds.
- Reuse the timezone module idiom exactly (dataclass, factories,
  `connect_axxon_profile`/`ensure_client`, `_stub_and_pb2`, `_write_gate`).
- Secrets env-only; never hardcode creds in the repo.
- Committed evidence sanitized: host -> `<demo-host>`, creds -> `<redacted>`.
  `AXXON_TLS_CN=Server` and node name `Server` may stay. No proto/CA/PDF committed.
- TDD: write the unit tests first, watch them fail, then implement.

## Non-goals
- No log streaming/download tools; only level get/set and drop.
- No multi-node fan-out beyond what `nodes` already supports (stand is single-node
  `Server`).
- DropLogs recovery/backup is out of scope (logs are gone by design).

## Gating idiom
- Env `AXXON_SERVER_APPROVE=1`, confirmation token `CONFIRM-server-set`.

## Verification plan
- `python3.12 -c "import sys; sys.path.insert(0,'tools'); import axxon_mcp_server; import axxon_mcp_server_settings"`
- `python3.12 -m unittest discover -s tools/tests`
- `python3.12 -m unittest discover -s tools/tests -p test_axxon_mcp_server_settings.py -v`
- `python3.12 tools/axxon_corpus_restamp.py`  (dry-run = 0 after write)
- Live evidence in raw/live-verify.txt (sanitized).
