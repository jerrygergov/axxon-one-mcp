# axxon-one-mcp

Axxon One MCP is a source-checkout Model Context Protocol server for Axxon One VMS. It ships a sanitized API corpus, optional live read tools, guarded mutation workflows, and integration templates.

The safe default is knowledge-only: with no capability flags the server starts a seven-tool knowledge-only profile and needs no Axxon host, ports, credentials, private proto files, CA material, or live VMS.

## Quick start

Use Python 3.12:

```bash
python3.12 -m pip install -r tools/requirements-mcp.txt
python3.12 -m pip check
python3.12 tools/axxon_mcp_server.py --transport stdio
```

Common verification commands:

```bash
python3.12 -m unittest discover -s tools/tests -v
python3.12 tools/verify_mcp_startup.py
python3.12 tools/axxon_corpus_restamp.py --check
python3.12 tools/generate_coverage.py --check
python3.12 -m unittest discover -s customer-templates/python-reference -p "test*.py" -v
```

Node reference checks:

```bash
cd customer-templates/node-reference
npm ci
npm run build
npm test
```

## API corpus status

The bundled sanitized corpus currently covers:

- 363 gRPC RPCs across 52 services, with 288 live-verified, 55 fixture-blocked, and 20 pending in [docs/COVERAGE.md](docs/COVERAGE.md).
- 221 annotated `/v1/...` HTTP endpoints in `docs/api-audit/mcp-corpus/http_endpoints.json`.
- 81 documented legacy, `/grpc`, and local Client HTTP API routes in `docs/api-audit/mcp-corpus/legacy_http_endpoints.json`.

The standard gRPC health service is included in the corpus and tool surface:
`grpc.health.v1.Health.Check` and `grpc.health.v1.Health.Watch`.

## Runtime profiles

| Profile | Command shape | Registered tools | Mutation posture |
| --- | --- | --- | --- |
| Knowledge default | `python3.12 tools/axxon_mcp_server.py --transport stdio` | exactly `search_api_docs`, `get_api_method`, `get_http_endpoint`, `get_verified_example`, `explain_task_recipe`, `list_remaining_gaps`, `list_capabilities` | no mutation groups are registered |
| Live observation | add `--enable-live` and any specific `--enable-*` groups | only requested groups | write groups stay absent unless explicitly enabled |
| Broad read-only | add `--read-only` | broad discovery surface | authoritatively disables mutation execution even if approval variables are inherited |
| Full registration | add `--enable-all` | all capability groups | registration only; it does not authorize mutations |

`--enable-all` does not authorize mutations. A mutating call still requires the relevant group to be registered, the exact value of that group approval variable to be `AXXON_*_APPROVE=1`, and the tool's per-call plan, confirmation, or workflow gate to accept the request. Values such as `true` or `yes` are ignored.

Operator workflows are deliberately two-step: call `plan_operator_workflow`, get caller review and caller approval, then call `apply_operator_plan` with the returned plan identifier and confirmation token. Use `verify_operator_plan` after apply and `rollback_operator_plan` when a reversible workflow needs cleanup. `execute_operator_workflow` is only a compatibility planner.

## Claude Desktop setup

Do not put the Axxon host/IP, gRPC port, HTTP port, username, password, or TLS common name into Claude Desktop config or environment variables. Register only the server command and non-secret local paths/timeouts:

```json
{
  "mcpServers": {
    "axxon-one": {
      "command": "python3.12",
      "args": [
        "/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py",
        "--transport",
        "stdio",
        "--enable-all"
      ],
      "env": {
        "AXXON_CA": "/full/path/to/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt",
        "AXXON_PROTO_DIR": "/full/path/to/axxon-one-mcp/docs/grpc-proto-files",
        "AXXON_GRPC_STUBS": "/tmp/axxon-grpc-py",
        "AXXON_TIMEOUT": "10.0"
      }
    }
  }
}
```

Before any live Axxon call, Claude should:

1. Call `get_axxon_connection_status` or `request_axxon_connection`.
2. Ask the user for `host`, `grpc_port`, `http_port`, `username`, and `password`.
3. Call `configure_axxon_connection` with those values. Optional fields are `tls_cn`, `http_scheme`, `http_url`, and `timeout`.
4. Use live/admin/operator/export tools normally. Public summaries show `password_present: true`; they never return the password.
5. Call `clear_axxon_connection` to forget the in-memory profile.

The runtime profile is kept only in this MCP server process memory. Restarting Claude Desktop or calling `clear_axxon_connection` removes it. Customer deployments should use HTTPS, a least-privilege account, and the expected TLS common name; if the certificate common name differs from the host/IP, provide it as `tls_cn` when calling `configure_axxon_connection`.

Axxon proto files, CA files, and customer credentials are not redistributed in this repository.

## Architecture

The entrypoint is `tools/axxon_mcp_server.py`. It registers knowledge tools by default and adds capability modules from `tools/axxon_mcp_*.py` when matching flags are selected.

Server-backed groups expose connection helper tools for validating the active runtime profile. Offline authoring exceptions are `generator`, `partner`, and `translator`, which create or validate artifacts without contacting Axxon. Operator planning is also transport-free, but it requires the runtime connection profile so generated plans target the user-supplied host UID instead of a hardcoded host.

Knowledge tools work entirely from `docs/api-audit/mcp-corpus/`:

- `search_api_docs`
- `get_api_method`
- `get_http_endpoint`
- `get_verified_example`
- `explain_task_recipe`
- `list_remaining_gaps`
- `list_capabilities`

Use `list_capabilities` to see which groups are registered in the current process and which flags enable disabled groups.

Notable live capability flags include:

| Capability | Flag | Notes |
| --- | --- | --- |
| Standard gRPC health | `--enable-health` | Exposes bounded `grpc_health_check` and `grpc_health_watch`. |
| Installer packages | `--enable-package-availability` | Checks package metadata and probes installer downloads without returning bytes. |
| Backup source | `--enable-backup-source` | `BundleBackup` status sampling plus gated `MakeBackup` and `CancelBackup`. |
| Config revisions | `--enable-config-revisions` | Revision reads, capped backup probe, plus gated `SetRevision` and `RestoreBackup`. |
| Notifier actions | `--enable-notifier-actions` | Gated diagnostic event pushes and email sends; responses are metadata-only. |
| Documented HTTP API | `--enable-http-api` | Lists `/v1`, legacy web, `/grpc`, and Client HTTP API routes; executes allowlisted server HTTP routes with response caps. |

Client HTTP API routes are cataloged and searchable, but execution remains fixture-needed by default because those routes target a local Axxon Client process rather than the server.

## Mutation safety

Mutation-capable groups have separate approval variables and per-call guards. Examples include operator workflows, PTZ control, macros, admin changes, settings updates, bookmark mutation, export lifecycle operations, and other write paths. Tool registration is never sufficient by itself.

For customer operations:

1. Start with the smallest explicit `--enable-*` set.
2. Use `--read-only` when a client needs broad discovery but must not mutate.
3. Enable mutation only by setting the exact documented approval variable to `1` outside the server process.
4. Require caller review of every returned plan and confirmation token before apply.
5. Run verification and rollback/cleanup where the workflow provides it.

Additional approval variables for the newly exposed gated surfaces:

| Surface | Approval variable | Confirmation token |
| --- | --- | --- |
| BackupSourceService `MakeBackup` / `CancelBackup` | `AXXON_BACKUP_SOURCE_APPROVE=1` | `CONFIRM-backup-source` |
| ConfigurationManager `SetRevision` | `AXXON_CONFIG_REVISIONS_APPROVE=1` | `CONFIRM-config-set-revision` |
| ConfigurationManager `RestoreBackup` | `AXXON_CONFIG_REVISIONS_APPROVE=1` | `CONFIRM-config-restore-backup` |
| Domain/Node diagnostic push and email send | `AXXON_NOTIFIER_ACTIONS_APPROVE=1` | `CONFIRM-notifier-actions` |
| Mutating documented HTTP routes | `AXXON_HTTP_API_APPROVE=1` | `CONFIRM-http-api` |

Backup, restore, installer download, and email tools return status and metadata only. They do not return raw backup bytes, installer package bytes, bearer tokens, passwords, or email message bodies.

## Repository layout

```text
tools/
  axxon_mcp_server.py        MCP server entrypoint
  axxon_mcp_*.py             capability modules
  axxon_api_client.py        shared client implementation class
  verify_mcp_startup.py      real MCP stdio startup verifier
  generate_coverage.py       deterministic coverage renderer
  tests/                     offline test suite
docs/api-audit/mcp-corpus/   sanitized API corpus
docs/COVERAGE.md             generated coverage summary
customer-templates/          Python and Node reference projects
```

## License

See [LICENSE](LICENSE). Axxon One, the Integration API, and proto/CA material belong to AxxonSoft and are not redistributed here.
