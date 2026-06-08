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
  Per-service coverage is summarized in [`docs/COVERAGE.md`](docs/COVERAGE.md); the
  authoritative per-RPC status (machine-readable) lives in
  [`docs/api-audit/mcp-corpus/api_methods.json`](docs/api-audit/mcp-corpus/api_methods.json).
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
      "args": ["/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py", "--enable-live"],
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

Restart Claude Desktop, then ask it things like *"list my cameras"* or *"what events
fired in the last hour?"*. Claude calls `connect_axxon_profile` and the read tools for you.

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

## 4. Enabling operator and config tools

By default only read tools are active. Each group of mutating tools is turned on with its
own `--enable-*` flag (added to `args` in your LLM config), and mutating groups also require
an approval env var plus a per-call confirmation token. Examples:

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
