# Evidence Bundle: phase-20-server-loglevel

## Summary
- Overall status: PASS (all 6 acceptance criteria PASS)
- Last updated: 2026-06-06

## AC1 — module + gating idiom — PASS
- `tools/axxon_mcp_server_settings.py` (`AxxonMcpServerSettings`) exposes read
  `get_log_level` and gated writes `set_log_level`, `drop_logs`. `_write_gate`
  returns `disabled` (env unset) / `gap` (bad token) before any wire call. Env
  `AXXON_SERVER_APPROVE=1` + confirmation `CONFIRM-server-set`.
- Proof: `GatingTests` (disabled/gap, no calls recorded); live `[gating]` block in
  raw/live-verify.txt.

## AC2 — get_log_level + set_log_level — PASS
- `get_log_level` returns `{node: level_name}` + `failed_nodes`. `set_log_level`
  is gated, requires a non-empty level, resolves the LogLevel enum by name, sends
  SetLogLevel, reads back the resulting levels.
- Proof: `ReadTests`, `SetLogLevelTests` (set then GetLogLevel order, nodes passed
  through), `InputTests.test_set_log_level_requires_level`; live INFO -> DEBUG ->
  restore.

## AC3 — drop_logs + invalid level — PASS
- `drop_logs` gated; sends DropLogs for the given nodes (empty = current node) and
  returns `applied` + `failed_nodes`. Invalid level name -> `error` with
  `valid_levels`, no wire call.
- Proof: `DropLogsTests` (request shape, nodes), `InputTests.test_set_log_level_invalid_name`;
  live authorized drop, server healthy after.

## AC4 — server registration — PASS
- 6-edit pattern in `tools/axxon_mcp_server.py`: `server_settings` param,
  `register_server_settings_tools` call, the function (4 tools), `--enable-server`
  flag, flag-gated instantiation, passed to `create_server`.
- Proof: raw/test-unit.txt (server import OK).

## AC5 — unit + full suite green — PASS
- 11 new tests. Full suite `Ran 771 tests ... OK` (raw/test-unit.txt).

## AC6 — corpus restamp + coverage doc — PASS
- SetLogLevel, DropLogs -> tested-pass. Coverage 195 pass-class / 128 pending /
  38 fixture-warn; ServerSettings 3/3. Restamp dry-run reports 0 after --write.

## Stand hygiene
- Log level set to LOG_LEVEL_DEBUG then restored to LOG_LEVEL_INFO (original).
  DropLogs is irreversible and was explicitly user-authorized for this phase; the
  stand's accumulated log history was deleted by design (same class as the
  previously-authorized Clear). Stand ends at its original log level. No
  proto/CA/PDF committed; secrets env-only; no biometric data.

## Sanitization
- raw/live-verify.txt: host -> `<demo-host>`, creds -> `<redacted>`.
