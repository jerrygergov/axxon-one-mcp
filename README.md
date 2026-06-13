# axxon-one-mcp

A Model Context Protocol (MCP) server for [Axxon One VMS](https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314535799/Documentation).
It exposes the Axxon One gRPC / HTTP Integration API to an LLM as a large set of
safe, typed tools so you can inspect, operate, and configure a VMS — and generate
integrations against it — in plain language.

The goal is full coverage of what the desktop client can do: view live and archive,
pull events, read and change configuration, add cameras / detectors / layouts,
drive PTZ, manage alarms and macros, and more. The service-by-service target map
is in [`docs/ALL_IN_ONE_VMS_API_ROADMAP.md`](docs/ALL_IN_ONE_VMS_API_ROADMAP.md).

## What it covers

- **51 services, 361 gRPC RPCs** mapped from the Integration API.
- **286 RPCs are live-verified** (`tested-pass`) against a real stand. The rest are
  either blocked by a stand fixture (`fixture-warn`) or not yet exercised (`pending`).
  Per-service coverage is summarized in [`docs/COVERAGE.md`](docs/COVERAGE.md); the
  authoritative per-RPC status (machine-readable) lives in
  [`docs/api-audit/mcp-corpus/api_methods.json`](docs/api-audit/mcp-corpus/api_methods.json).
- **309 MCP tools** across 50 capability groups in seven layers (see below). This is the
  all-enabled runtime count: 304 tools registered in `tools/axxon_mcp_server.py` plus
  5 delegated translator tools from `tools/axxon_mcp_translator.py`. Existing live-audited
  groups are covered by the latest real-stand audit
  ([`docs/api-audit/preexisting-tools-audit-latest.md`](docs/api-audit/preexisting-tools-audit-latest.md));
  the Phase 1 `site_graph` group is read-only and unit-verified offline, and the Phase 2
  `export` group and Phase 3 `bulk_onboarding` group are approval-gated and unit-verified
  offline.

### Tool layers

All layers are **on by default** (use `--read-only` to restrict to reads).

| Layer | What it gives you |
| --- | --- |
| **Knowledge** | `search_api_docs`, `get_api_method`, `get_verified_example`, `explain_task_recipe`, `list_capabilities` — search the API corpus, verified examples, fixtures, and safety notes without a server connection. |
| **Live read-only** | `connect_axxon_profile`, `list_cameras`, `list_archives`, `list_detectors`, `search_events`, `subscribe_events_bounded`, and more. Inspect a connected server. |
| **Site graph** | `site_graph_connect_axxon_profile`, `build_site_graph` — join cameras, archives, detectors, layouts, maps, permissions, health, access points, and event suppliers into one read-only graph. |
| **Operator / config** | Mutating tools (cameras, detectors, layouts, macros, alarms, PTZ, videowall, settings). Every mutation requires a per-call confirmation token, with plan / apply / verify / rollback where it applies. |
| **Export** | `export_plan_snapshot`, `export_start_snapshot`, `export_status`, `export_download`, `export_cleanup_owned` — plan/start/status/download/cleanup for owned snapshot exports with approval, byte, chunk, timeout, and path caps. |
| **Bulk onboarding** | `bulk_onboarding_schema`, `bulk_onboarding_validate_manifest`, `bulk_onboarding_plan`, `bulk_onboarding_apply_plan`, `bulk_onboarding_verify_plan`, `bulk_onboarding_rollback_plan` — validate inline CSV/JSON camera manifests, plan catalog/discovery/site-graph-aware onboarding, and apply/rollback with approval. |
| **Generator** | Generate Python / Node integration skeletons (14 templates, each in both languages) and versioned partner plugin scaffolds. |

## Requirements

- Python 3.12
- `pip install -r tools/requirements-mcp.txt`
- An Axxon One server, and its credentials, for the live tools.

## 1. Install

```bash
git clone https://github.com/jerrygergov/axxon-one-mcp.git
cd axxon-one-mcp
pip install -r tools/requirements-mcp.txt
```

That's enough to run the **knowledge layer** (API search, verified examples) with no
server connection:

```bash
python tools/axxon_mcp_server.py --transport stdio
```

## 2. Connect it to your LLM

The server speaks MCP over stdio, so any MCP-capable client can use it. You give the
client the command to run and your Axxon One connection details as environment variables.

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config) and add:

```json
{
  "mcpServers": {
    "axxon-one": {
      "command": "python",
      "args": ["/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py"],
      "env": {
        "AXXON_HOST": "192.168.1.50",
        "AXXON_HTTP_URL": "http://192.168.1.50",
        "AXXON_USERNAME": "root",
        "AXXON_PASSWORD": "your-password"
      }
    }
  }
}
```

That's the whole setup — **host and credentials, no flags.** Running with no flags enables
**every** capability (reads, operator/config, PTZ, alarms, …). Mutating tools still require a
per-call confirmation token before anything changes (the assistant supplies it; see Safety), so
nothing destructive happens by accident.

Want a locked-down, reads-only deployment? Add `"--read-only"` to `args` — then mutating tools
are disabled entirely. Want only specific groups? Use individual `--enable-*` flags (see step 4).

Restart Claude Desktop, then ask it things like *"list my cameras"*, *"what events fired in
the last hour?"*, or *"add a virtual camera named Lobby-Cam"*.

> **Tip:** the assistant can call the always-on `list_capabilities` tool to see exactly what
> this server can do — so you never get a wrong "I can't".

### Cursor, VS Code, and other MCP clients

Any client that supports MCP servers uses the same shape — a `command`, `args`, and `env`.
Point it at `tools/axxon_mcp_server.py` with the same environment variables above.

### ChatGPT / other LLMs

ChatGPT supports MCP via custom connectors / the Agents SDK; any framework that can launch
an MCP stdio server (LangChain, the OpenAI Agents SDK, etc.) connects the same way: run the
command above and pass the `AXXON_*` environment variables.

## 3. Connection settings

Set these as environment variables (in the MCP client `env` block, or exported in your shell).
Only host, URL, username, and password are required.

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `AXXON_HOST` | yes | — | Server IP or hostname |
| `AXXON_HTTP_URL` | yes | `http://127.0.0.1:8000` | `http://<host>` (or `https://`) |
| `AXXON_USERNAME` | yes | — | Axxon One user |
| `AXXON_PASSWORD` | yes | — | password (kept in memory, never logged) |
| `AXXON_HTTP_PORT` | no | `8000` | set to `80` for a standard install |
| `AXXON_GRPC_PORT` | no | `20109` | direct gRPC port |
| `AXXON_TLS_CN` | for gRPC | `Server` | gRPC certificate common name |
| `AXXON_CA` | for gRPC | — | path to the gRPC root CA |
| `AXXON_PROTO_DIR` | for gRPC | — | folder with the `.proto` files |

**Basic reads** (cameras, archives, events) work over the HTTP `/grpc` bridge with just
host + credentials — no certificate or proto files needed.

**Full gRPC tools** (configuration, PTZ, media, etc.) additionally need the Axxon One
`.proto` files and the gRPC root CA. These are AxxonSoft material and are **not** included
in this repo. **Request them from AxxonSoft technical support**, place them in a local
folder, and point the server at them:

```bash
export AXXON_PROTO_DIR=/path/to/axxon-proto-files
export AXXON_CA=/path/to/api.ngp.root-ca.crt
```

The server compiles the protos automatically on first use.

## 4. Restricting what's on (optional)

Running with no flags enables everything (step 2). To restrict:

```bash
# Reads only — all mutating tools disabled
python tools/axxon_mcp_server.py --read-only --transport stdio

# Only specific groups (each has its own --enable-* flag)
python tools/axxon_mcp_server.py --enable-live --enable-ptz --transport stdio
```

Run `python tools/axxon_mcp_server.py --help` for the full flag list, or ask the assistant to
call `list_capabilities`. When you select groups explicitly, mutating groups also need their
`AXXON_*_APPROVE` env var (e.g. `AXXON_OPERATOR_APPROVE=1`) — the no-flag default sets these for you.

## Safety model

- **Everything is on by default**; use `--read-only` to disable all mutating tools.
- Every mutation requires a **per-call confirmation token** (`CONFIRM-…`) — the assistant must pass
  the exact token, so nothing destructive fires by accident.
- For locked-down deployments, `--read-only` disables mutating tools entirely, and the per-group
  `--enable-*` flags + `AXXON_*_APPROVE` env vars give fine-grained control.
- Operator workflows expose `plan` → `apply` → `verify` → `rollback`.
- Export start/download/stop/destroy/cleanup require `AXXON_EXPORT_APPROVE=1` plus
  `CONFIRM-export`; downloads are metadata-only in responses and save only under the
  module-owned export artifact root.
- Bulk onboarding apply/rollback requires `AXXON_BULK_ONBOARDING_APPROVE=1` plus
  `CONFIRM-bulk-onboarding` or `CONFIRM-bulk-onboarding-rollback`; manifests are inline
  `rows`, `csv_text`, or `json_text` only and path/URL imports are rejected.
- Streaming and export tools are byte- and time-capped.
- Secrets (passwords, tokens, cookies, raw media bytes) are never returned by tools.

## Examples

Runnable standalone scripts that use the same client (`tools/examples/`):

- `camera_archive_status.py` — list cameras and their archive intervals
- `event_search_summary.py` — search and summarize events
- `metadata_tracker_stream.py` — bounded live object-track sampling
- `inventory_sync.py` — dump the full device inventory
- `http_grpc_vs_grpc.py` — compare the HTTP `/grpc` bridge vs direct gRPC

## Tests

```bash
python3.12 -m unittest discover -s tools/tests     # 1147 unit tests, offline (no server needed)
```

## Layout

```
tools/
  axxon_mcp_server.py        MCP server entrypoint (--enable-* flags, --transport)
  axxon_mcp_*.py             feature modules (live reads, operator, ptz, alarms, videowall, …)
  axxon_api_client.py        gRPC/HTTP client (TLS-CN override, HTTP /grpc fallback, auth)
  examples/                  runnable standalone scripts
  templates/                 integration generator templates
  tests/                     offline unit tests
docs/api-audit/mcp-corpus/   the API corpus the server loads (methods, recipes, fixtures, safety)
customer-templates/          reference partner plugins (Python + Node)
```

## License

See [LICENSE](LICENSE). Axxon One, the Integration API, the proto files, and the
Integration APIs PDF are property of AxxonSoft and are not redistributed here.
