# Axxon One MCP Corpus

This directory contains the sanitized structured API corpus used by the MCP server.
It is the machine-readable companion to the all-in-one roadmap in
[`docs/ALL_IN_ONE_VMS_API_ROADMAP.md`](../../ALL_IN_ONE_VMS_API_ROADMAP.md).

The corpus is derived from local proto/PDF/API audit material, but it does not
redistribute proto files, the Integration APIs PDF, CA files, credentials, bearer
tokens, or raw media.

## Files

- `api_methods.json`: 361 gRPC methods with package, service, request/response names,
  streaming mode, safety class, HTTP annotation, proto path, live status, and evidence
  links when known.
- `http_endpoints.json`: 221 annotated `/v1/...` HTTP endpoints parsed from the API
  endpoint catalog.
- `task_recipes.json`: task-oriented integration recipes and mutation playbook
  references.
- `fixtures.json`: fixture requirements and live coverage blockers.
- `safety_policies.json`: risk classes, default posture, stream caps, mutation gates,
  rollback expectations, and redaction rules.
- `known_behaviors.json`: demo-stand quirks and compatibility notes that tools should
  not rediscover repeatedly.

## Current Summary

As of 2026-06-11:

| Metric | Value |
| --- | ---: |
| gRPC services | 51 |
| gRPC RPCs | 361 |
| RPCs live-verified | 286 |
| RPCs fixture-blocked | 55 |
| RPCs pending | 20 |
| HTTP `/v1` endpoints | 221 |

Regenerate the core status counts with:

```bash
python3 - <<'PY'
import collections, json
methods = json.load(open("docs/api-audit/mcp-corpus/api_methods.json"))["methods"]
counts = collections.Counter(method["live_status"] for method in methods)
verified = sum(count for status, count in counts.items() if status.startswith("tested-pass"))
print(counts)
print({"verified": verified, "total": len(methods)})
PY
```

## MCP Layers That Consume This Corpus

The knowledge tools in `tools/axxon_mcp_server.py` and `tools/axxon_mcp_docs.py` expose:

- `search_api_docs(query)`
- `get_api_method(fqmn)`
- `get_http_endpoint(path_or_topic)`
- `get_verified_example(topic)`
- `explain_task_recipe(task)`
- `list_remaining_gaps()`
- `list_capabilities()`

The live/operator/generator layers use the same corpus for tool descriptions, safety
classification, verified examples, fixtures, and gap reporting:

- Live read-only inspection: inventory, events, archive intervals, metadata samples,
  layouts/maps/walls, statistics, and health.
- Controlled operator workflows: cameras, detectors, layouts, maps, macros, alarms,
  settings, security/admin operations, PTZ, videowall, shared KV, and other gated
  mutations.
- Partner authoring: Python/Node integration templates, plugin scaffold/lint/package,
  and natural-language recipe assembly/validation/execution.

Run the MCP server over stdio:

```bash
python3.12 tools/axxon_mcp_server.py --transport stdio
```

Use `--read-only` for a locked-down deployment. Running with no capability flags enables
all groups; mutating tools still require per-call confirmation tokens and their approval
environment variables.

## Maintenance Rules

- Keep this corpus sanitized. Do not add credentials, tokens, CA material, private keys,
  full user/security payloads, raw images, raw video, or copied proto/PDF source text.
- When live evidence changes an RPC status, update `api_methods.json`,
  `docs/COVERAGE.md`, and any roadmap/status counts together.
- Record fixture requirements as explicit gaps instead of making tools infer unsupported
  API shapes.
- Prefer adding task recipes and safety notes here before adding broad new MCP tools.
