# Evidence: phase-36-config-change

Overall: PASS (all acceptance criteria PASS)

## AC1 — New module with read + gated write tools — PASS
`tools/axxon_mcp_config_change.py` defines `AxxonMcpConfigChange` with:
- reads: `list_similar_units`, `batch_get_factories`
- gated writes: `change_unit_property` (ChangeConfig), `change_unit_property_stream` (ChangeConfigStream)
- `config_change_connect_axxon_profile` / `connect_axxon_profile` / `ensure_client` / `_stub_and_pb2` / `_write_gate`
Approval env `AXXON_CONFIG_CHANGE_APPROVE`, token `CONFIRM-config-change`. Idiom matches
`tools/axxon_mcp_logic_alerts.py`.

## AC2 — Gate enforced before any wire call — PASS
Unit tests `tools/tests/test_axxon_mcp_config_change.py`:
- env off -> `{"status":"disabled"}`, `client.calls == []`
- bad token -> `{"status":"gap"}`, `client.calls == []`
- missing uid/type/property -> `{"status":"error"}`, `client.calls == []`
Live: gate (env off) -> disabled, gate (bad token) -> gap (raw/live-verify.txt).

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: create_server param `config_change`, conditional
`register_config_change_tools`, the register function with 5 `@server.tool` entries,
`--enable-config-change` flag, flag-gated instantiation, pass to create_server. Server
wiring smoke registered all 5 tools. Imports OK (raw/build.txt).

## AC4 — Live reversible evidence — PASS
raw/live-verify.txt (sanitized): ChangeConfig round-trip Tracker -> "Tracker [probe]" ->
Tracker (applied, failed=[]); ChangeConfigStream round-trip Tracker -> "Tracker [stream]"
-> Tracker (applied, failed=[]); list_similar_units status=ok with next_page_token;
final read equals original both times (REVERSIBLE OK). No residual config change.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps ChangeConfig, ChangeConfigStream,
ListSimilarUnits -> tested-pass; BatchGetFactories -> tested-warn-fixture-needed.
Dry-run after --write reports `0 method(s) restamped`. Coverage doc updated to
238 tested-pass / 96 pending / 27 fixture-warn; ConfigurationService 11/12.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `863 passed` (852 prior + 11 new). No regressions.
Production module + server lint clean (raw/lint.txt); test-file E402 is the repo-wide
sys.path baseline shared by every test file.
