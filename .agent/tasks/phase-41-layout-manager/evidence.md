# Evidence: phase-41-layout-manager

Overall: PASS (all acceptance criteria PASS)

## AC1 — New module with reads + gated rename — PASS
`tools/axxon_mcp_layout_manager.py` defines `AxxonMcpLayoutManager` with `batch_get_layouts`
(read), `layouts_on_view` (read/push), `update_layout_name` (gated), plus connect helper /
ensure_client / _stub_and_pb2 / _write_gate. Approval env `AXXON_LAYOUT_MANAGER_APPROVE`,
token `CONFIRM-layout-update`. update_layout_name reads the live layout via ListLayouts,
changes only display_name, and uses the live etag.

## AC2 — Gate + input validation before any wire call — PASS
`tools/tests/test_axxon_mcp_layout_manager.py` GateTests: update env-off -> disabled, bad
token -> gap, empty id -> error; batch_get/layouts_on_view empty id -> error; all assert
`client.calls == []`. Live: gate env-off=disabled, bad-token=gap (raw/live-verify.txt).

## AC3 — Server wiring via 6-edit pattern — PASS
`tools/axxon_mcp_server.py`: param `layout_manager`, conditional `register_layout_manager_tools`,
the register function with 4 `@server.tool` entries, `--enable-layout-manager` flag,
flag-gated instantiation, pass to create_server. Server smoke registered all 4 tools. Imports
OK (raw/build.txt).

## AC4 — Live reversible evidence — PASS
raw/live-verify.txt (sanitized): batch_get_layouts[empty etag] returns the layout body,
[bogus] returns not_found; layouts_on_view -> ok; update_layout_name probe -> "Fire [probe]"
-> restore -> "Fire" (UPDATE REVERSIBLE OK, read back via batch_get_layouts). No residual
layout change.

## AC5 — Corpus restamp honest + idempotent — PASS
`tools/axxon_corpus_restamp.py` restamps BatchGetLayouts, LayoutsOnView, Update ->
tested-pass. Dry-run after --write reports `0 method(s) restamped`. Coverage doc updated to
254 tested-pass / 69 pending / 38 fixture-warn; LayoutManager 5/5.

## AC6 — Full suite green — PASS
raw/test-integration.txt: `912 passed` (902 prior + 10 new). Production module + server lint
clean (raw/lint.txt). Test-file E402 is the repo-wide sys.path baseline.
