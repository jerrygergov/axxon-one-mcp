# Task Spec: phase-41-layout-manager

## Guidance sources
- AGENTS.md, CLAUDE.md
- docs/api-audit/mcp-corpus/api_methods.json (LayoutManager rows)
- tools/axxon_mcp_config_change.py (gated module idiom to mirror)

## Original task statement
Continue the API-coverage proof loop. Close the three remaining LayoutManager methods
(BatchGetLayouts, LayoutsOnView, Update) via a new module mirroring the config_change idiom.
Live-verify reversibly. This brings LayoutManager to 5/5.

## Live probe findings (2026-06-07, demo stand)
- BatchGetLayouts: etag-conditional read. ListLayouts(view=FULL) exposes per-layout
  meta.layout_id + meta.etag. BatchGetLayouts with an empty/stale etag returns the full
  LayoutFull body; with a matching etag returns nothing (conditional-GET optimization); with
  a bogus id returns not_found. SERVICEABLE (read).
- LayoutsOnView: pushes a layout set to the view; returns empty response, OK. SERVICEABLE.
- Update: create/modify/remove layouts. Verified reversibly: modify a writable layout's
  body.display_name via its etag -> re-read (etag rotates) -> restore to the original name.
  SERVICEABLE (reversible).

## Message shapes (confirmed live)
- ListLayoutsResponse{current, items[LayoutFull{meta{layout_id, etag, has_write_access, owned_by_user}, body{id, display_name, cells, ...}}]}.
- BatchGetLayoutsRequest{items[Locator{layout_id, etag}]}; BatchGetLayoutsResponse{items[LayoutFull], not_found_items}.
- UpdateRequest{created[Layout], modified[TaggedLayout{body, etag}], removed, ...}; UpdateResponse{created_layouts}.
- LayoutsOnViewRequest{layouts[LayoutOnView{layout_id, layout_display_name}]}; LayoutsOnViewResponse{}.

## Acceptance criteria
- AC1: New module tools/axxon_mcp_layout_manager.py exposes batch_get_layouts (read),
  layouts_on_view (read/push), update_layout_name (gated write), with connect helper +
  ensure_client + _stub_and_pb2 + _write_gate matching config_change. Approval env
  AXXON_LAYOUT_MANAGER_APPROVE=1, confirmation token CONFIRM-layout-update. update_layout_name
  reads the layout's current etag/body, changes only display_name, and uses the live etag.
- AC2: update_layout_name enforces the gate before any wire call: env-off -> {"status":"disabled"};
  bad token -> {"status":"gap"}; empty layout_id -> {"status":"error"}. batch_get_layouts and
  layouts_on_view require a layout_id else error. Unit tests assert client.calls==[] in each
  gated/empty case.
- AC3: Server wiring complete via the 6-edit pattern (param, conditional register,
  register_layout_manager_tools with @server.tool entries, --enable-layout-manager flag,
  flag-gated instantiation, pass to create_server). Module importable, server builds.
- AC4: Live evidence: batch_get_layouts returns a layout body for an empty etag and
  not_found for a bogus id; layouts_on_view returns ok; update_layout_name changes
  display_name and is restored to the original. Raw transcript raw/live-verify.txt sanitized.
- AC5: Corpus restamp marks BatchGetLayouts, LayoutsOnView, Update tested-pass. Dry-run after
  --write reports 0 restamped. Coverage doc updated; LayoutManager 5/5.
- AC6: Full test suite passes (no regressions). New unit-test file for the module.

## Constraints
- update verification changes only display_name and restores it; no residual layout change,
  no create/remove of real layouts.
- Never fake live evidence; only restamp what the device services.
- .env gitignored and unstaged; sanitize demo host -> <demo-host>, creds -> <redacted>.
- Smallest defensible diff; reuse public_config_summary.

## Non-goals
- Layout create/remove, sharing, ordering, slideshow editing (beyond a display_name change).
- UserDataCleanup (already covered in phase-30).

## Verification plan
- Build: import module + server create_server smoke.
- Unit tests: tools/tests/test_axxon_mcp_layout_manager.py (read, gate, no-leak).
- Integration: full suite.
- Lint: ruff on production module + server.
- Manual: live transcript + restamp dry-run clean.
