# axxon-one-mcp

Model Context Protocol (MCP) server, audit tooling, and Integration APIs 3.0
coverage matrix for Axxon One VMS.

## Status

- **174 / 174** unit tests passing.
- **33** PDF gap-coverage matrix rows. 27 verified, 6 fixture-blocked
  (hardware / process gates on the demo stand, documented under
  `docs/api-audit/`).
- **11** MCP operator workflows (7 ephemeral, 4 persistent) with
  plan / apply / verify / rollback safety.
- **15** MCP live tools covering inventory, events, metadata, archive,
  detector discovery, and bounded subscriptions.
- **8** integration generator templates (grpc_consumer, http_grpc_consumer,
  legacy_http_consumer, event_consumer, external_event_producer, export_job,
  webhook_bridge, inventory_sync) with a static verifier that rejects embedded
  secrets, disallowed imports, and missing safety caps. All 8 verified
  end-to-end against the demo stand
  (`docs/api-audit/mcp-generation-runtime-smoke-latest.md`).

See `docs/api-audit/pdf-gap-coverage-matrix.md` for the canonical coverage matrix.

## Layout

```
tools/                       — runnable smokes, MCP server, operator workflows, fixtures
  axxon_mcp_server.py        — entrypoint; docs / live / operator transports
  axxon_mcp_docs.py          — phase-1 docs-only query layer
  axxon_mcp_live.py          — phase-2 read-only live inspection
  axxon_mcp_operator.py      — phase-3 controlled mutation workflows
  axxon_mcp_operator_smoke.py — live smoke harness for all operator workflows
  axxon_mcp_generator.py     — phase-4 integration code generator
  axxon_mcp_generator_smoke.py — static smoke that generates+verifies all templates
  templates/                 — phase-4 string templates for generated bundles
  axxon_aux_topics_smoke.py  — aux topic coverage smoke (statistics, groups, alerts, ...)
  axxon_api_client.py        — gRPC + HTTP /grpc + legacy HTTP transport
  axxon_*_smoke.py           — per-area runnable verification scripts
  tests/                     — unit tests

docs/
  AXXON_ONE_API_BOOK.md      — primary API book (verified examples only)
  AXXON_ONE_API_EXPERT_CONTEXT.md
  AXXON_ONE_API_TESTING_RUNBOOK.md
  api-audit/                 — per-area evidence reports + run logs
    pdf-gap-coverage-matrix.{md,json}
    mcp-corpus/              — structured JSON corpus for MCP consumers
    mutation-playbooks/      — approval-gated mutation procedures
  plans/                     — planning docs
  api-test-runs/             — archived legacy probe runs
```

## MCP server

The MCP server has three optional transports:

```bash
# docs-only (no live connection)
python tools/axxon_mcp_server.py --transport stdio

# + read-only live inventory tools
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-live --transport stdio

# + controlled operator (plan/apply/verify/rollback) workflows
AXXON_OPERATOR_APPROVE=1 \
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-live --enable-operator --transport stdio

# + integration code generator (list/plan/generate/verify_integration)
python tools/axxon_mcp_server.py --enable-generator --transport stdio
```

### Live tools (read-only)

`connect_axxon_profile`, `list_cameras`, `list_archives`, `list_config_units`,
`list_detectors`, `list_appdata_detectors`, `find_event_suppliers`,
`find_metadata_endpoints`, `preflight_task`, `get_archive_intervals`,
`subscribe_events_bounded`, `list_event_types`, `list_detector_kinds`,
`search_events`, `pull_metadata_bounded`.

### Operator workflows

Ephemeral (auto-rollback): `temp_camera`, `temp_archive`, `temp_av_detector`,
`temp_appdata_detector`, `temp_device_template`, `external_event_inject`,
`temp_macro`.

Persistent (caller owns lifecycle): `create_camera`, `create_macro`,
`create_layout`, `set_unit_properties`.

All workflows expose: `list_operator_workflows`, `plan_operator_workflow`,
`apply_operator_plan`, `verify_operator_plan`, `rollback_operator_plan`. Plans
require a confirmation token before apply; rollback uses a separate token.

### Integration generator (Phase 4)

`list_integration_templates`, `plan_integration`, `generate_integration`,
`verify_integration`. Templates: `grpc_consumer`, `http_grpc_consumer`,
`legacy_http_consumer`, `event_consumer`, `external_event_producer`,
`export_job`, `webhook_bridge`, `inventory_sync`. Generated bundles read credentials only from environment, apply
duration/byte/count caps, and refuse `output_dir` paths inside this repo
unless `AXXON_GENERATOR_ALLOW_IN_REPO=1`. See
`docs/plans/2026-05-15-mcp-phase-4-integration-generation.md` and the static
smoke evidence at `docs/api-audit/mcp-generation-smoke-latest.md`.

## Verification

```bash
# Unit tests
ls tools/tests/test_*.py | sed 's|/|.|g; s|.py$||' | xargs python -m unittest

# Operator live smoke (plan-only by default)
python tools/axxon_mcp_operator_smoke.py

# Operator live smoke (full apply/verify/rollback cycle)
python tools/axxon_mcp_operator_smoke.py --enable-live
```

## Demo stand notes

The audit evidence under `docs/api-audit/` was generated against a private
Axxon One demo stand. Host IP and TLS CN are sanitized in published evidence
(replaced with `<demo-host>` / `<your-tls-cn>` / `<demo-tls-cn>`). The
`hosts/Server/...` access-point UIDs in evidence are intrinsic to that stand
and are meaningless without it.

## License

See `LICENSE`.

This project is unaffiliated with AxxonSoft. The Integration APIs 3.0 PDF and
its derived proto / Markdown content (under `docs/integration-apis-3.0/` in
the source repo) are AxxonSoft copyrighted material and are intentionally
excluded from this repository. Only audit tooling and evidence authored for
this project is published here.
