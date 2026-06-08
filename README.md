# axxon-one-mcp

A Model Context Protocol (MCP) server for [Axxon One VMS](https://docs.axxonsoft.com/confluence/spaces/ONE2025/pages/314535799/Documentation).
It exposes the Axxon One gRPC / HTTP Integration API to an LLM as a large set of
safe, typed tools so you can inspect, operate, and configure a VMS — and generate
integrations against it — in plain language.

The goal is full coverage of what the desktop client can do: view live and archive,
pull events, read and change configuration, add cameras / detectors / layouts,
drive PTZ, manage alarms and macros, and more.

## What it covers

- **51 services, 361 gRPC RPCs** mapped from the Integration API.
- **283 RPCs are live-verified** (`tested-pass`) against a real stand. The rest are
  either blocked by a stand fixture (`fixture-warn`) or not yet exercised (`pending`).
  The authoritative per-RPC status lives in
  [`docs/api-audit/mcp-corpus/api_methods.json`](docs/api-audit/mcp-corpus/api_methods.json)
  and the human-readable matrix in
  [`docs/api-audit/capability-vs-coverage-2026-06-05.md`](docs/api-audit/capability-vs-coverage-2026-06-05.md).
- **251 MCP tools** across four layers (see below).

### Tool layers

| Layer | Default | What it gives you |
| --- | --- | --- |
| **Knowledge** (always on) | on | `search_api_docs`, `get_api_method`, `get_verified_example`, `explain_task_recipe` — search the API corpus, verified examples, fixtures, and safety notes without a server connection. |
| **Live read-only** | `--enable-live` | `connect_axxon_profile`, `list_cameras`, `list_archives`, `list_detectors`, `search_events`, `subscribe_events_bounded`, and more. Inspect a connected server. |
| **Operator / config** | per-feature `--enable-*` | Mutating tools (cameras, detectors, layouts, macros, alarms, PTZ, videowall, settings). Every mutation is gated behind an approval env var **and** a per-call confirmation token, with plan / apply / verify / rollback where it applies. |
| **Generator** | `--enable-generator`, `--enable-partner` | Generate Python / Node integration skeletons and partner plugin scaffolds. |

## Requirements

- Python 3.12
- `pip install -r tools/requirements-mcp.txt` (the `mcp` package)
- For **live** tools: network access to an Axxon One server and the gRPC root CA + proto
  files (not shipped — copyrighted; see "Live connection" below).

## Quick start (knowledge layer, no server)

```bash
pip install -r tools/requirements-mcp.txt
python tools/axxon_mcp_server.py --transport stdio
```

This starts the server with the always-on documentation tools. Point your MCP client
(Claude Desktop, an IDE extension, or the Agent SDK) at it and try `search_api_docs`
with a task like "export video" or "subscribe to detector events".

## Live connection

Live tools authenticate from environment variables (credentials stay in memory, never
logged). The gRPC certificate CN on a stand is typically `Server`.

```bash
export AXXON_HOST=<host>
export AXXON_HTTP_URL=http://<host>
export AXXON_USERNAME=<user>
export AXXON_PASSWORD=<password>
export AXXON_TLS_CN=Server          # gRPC cert common name
export AXXON_CA=<path-to-root-ca>   # only needed for direct gRPC; reads work over HTTP /grpc without it

python tools/axxon_mcp_server.py --enable-live --transport stdio
```

Then call `connect_axxon_profile` and the read tools (`list_cameras`, `search_events`, …).

> The proto files, gRPC root CA, and the Integration APIs PDF are AxxonSoft material and
> are **not** committed. Keep them locally (the client reads protos from `AXXON_PROTO_DIR`
> and the CA from `AXXON_CA`). Reads also work over the HTTP `/grpc` bridge with no CA.

## Enabling operator and config tools

Each feature group is a separate flag, and mutating groups require an approval env var
plus a per-call confirmation token. Examples:

```bash
# Live + operator workflows (cameras, detectors, macros, exports — plan/apply/verify/rollback)
python tools/axxon_mcp_server.py --enable-live --enable-operator --transport stdio

# Alarm lifecycle mutations
AXXON_ALARMS_APPROVE=1 python tools/axxon_mcp_server.py --enable-alarms --enable-alarms-mutation --transport stdio

# LogicService control (macros, arm-state, config, counters)
AXXON_LOGIC_CONTROL_APPROVE=1 python tools/axxon_mcp_server.py --enable-logic-control --transport stdio

# Videowall control (register/change/set-control/unregister, reversible)
AXXON_VIDEOWALL_APPROVE=1 python tools/axxon_mcp_server.py --enable-videowall --transport stdio

# PTZ / telemetry, HeatMap + Media probes, metadata/VMDA search
python tools/axxon_mcp_server.py --enable-ptz --enable-heatmap --enable-media --enable-metadata --transport stdio
```

Run `python tools/axxon_mcp_server.py --help` for the full list of `--enable-*` flags.

## Safety model

- Read-only by default; mutating tools are off until explicitly enabled.
- Every mutation is gated by an approval env var **and** a per-call confirmation token.
- Operator workflows expose `plan` → `apply` → `verify` → `rollback`.
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
python3.12 -m pytest tools/tests/ -q     # 967 unit tests, offline (no server needed)
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
