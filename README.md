# axxon-one-mcp

Axxon One MCP is a source-checkout Model Context Protocol server for Axxon One VMS. It combines a sanitized API corpus, live read tools, guarded mutation workflows, and customer integration templates in one repository.

The default is intentionally safe: with no capability flags the server starts a seven-tool knowledge-only profile and needs no Axxon credentials, private proto files, CA material, or live VMS.

## Runtime profiles

| Profile | Command shape | What is registered | Mutation posture |
| --- | --- | --- | --- |
| Knowledge default | `python3.12 tools/axxon_mcp_server.py --transport stdio` | exactly `search_api_docs`, `get_api_method`, `get_http_endpoint`, `get_verified_example`, `explain_task_recipe`, `list_remaining_gaps`, `list_capabilities` | no mutation groups are registered |
| Live observation | add `--enable-live` and other specific `--enable-*` flags | only the requested groups | mutation groups remain absent unless explicitly enabled |
| Broad read-only | add `--read-only` | broad compatibility surface for clients that expect the full tool list | authoritatively disables mutation execution even if approval environment variables are inherited |
| Broad registration | add `--enable-all` | all capability groups | registration only; it does not authorize mutations |

`--enable-all` does not authorize mutations. A mutating call requires all of the following: the relevant group is registered, the exact value of that group approval variable is `AXXON_*_APPROVE=1`, and the per-call plan, confirmation, or workflow gate accepts the request. Values such as `true`, `yes`, or inherited approvals under `--read-only` do not enable execution.

Operator workflows are deliberately two-step. Use `plan_operator_workflow`, obtain caller review and caller approval, then call `apply_operator_plan` with the returned plan identifier and confirmation token. After apply, use `verify_operator_plan`; when a reversible workflow needs cleanup, use `rollback_operator_plan`. `execute_operator_workflow` is only a compatibility planner and does not apply a plan or supply automatic confirmation.

## Install and local release checks

Use Python 3.12 for both installation and execution:

```bash
python3.12 -m pip install -r tools/requirements-mcp.txt
python3.12 -m pip check
python3.12 tools/axxon_mcp_server.py --transport stdio
```

Offline checks used by CI:

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

## Claude Desktop / MCP client example

This primary example uses HTTPS and a least-privilege service account. Replace the placeholders with deployment-specific values and keep credentials in the MCP client environment block or secret store.

```json
{
  "mcpServers": {
    "axxon-one": {
      "command": "python3.12",
      "args": [
        "/full/path/to/axxon-one-mcp/tools/axxon_mcp_server.py",
        "--transport",
        "stdio",
        "--enable-live"
      ],
      "env": {
        "AXXON_HOST": "vms.example.internal",
        "AXXON_HTTP_URL": "https://vms.example.internal",
        "AXXON_USERNAME": "axxon_mcp_reader",
        "AXXON_PASSWORD": "<from-client-secret-store>",
        "AXXON_TLS_CN": "vms.example.internal"
      }
    }
  }
}
```

HTTP endpoints may exist in local or isolated deployments, but use HTTP only in an explicitly accepted trusted lab. Customer deployments should use HTTPS, a least-privilege account, and the expected TLS common name for the target server.

## Connection settings

The table below documents the development-oriented runtime defaults implemented by `AxxonClientConfig.from_env`. Customer deployments must override AXXON_HOST, AXXON_USERNAME, AXXON_PASSWORD, AXXON_TLS_CN, and usually AXXON_HTTP_URL with least-privilege HTTPS/TLS values appropriate for the target VMS.

| Variable | Runtime default | Customer guidance |
| --- | --- | --- |
| `AXXON_HOST` | `127.0.0.1` | override with the VMS DNS name or address |
| `AXXON_HTTP_URL` | `http://127.0.0.1:8000` | override with the HTTPS base URL in customer deployments |
| `AXXON_USERNAME` | `root` | override with a least-privilege service account |
| `AXXON_PASSWORD` | empty string | supply through the MCP client secret environment, never in source |
| `AXXON_HTTP_PORT` | `8000` | match the deployment only when HTTP bridge use is intentionally accepted |
| `AXXON_GRPC_PORT` | `20109` | direct gRPC port |
| `AXXON_TLS_CN` | `F4E66972EC19` | override with the certificate common name expected by the deployment |
| `AXXON_CA` | `docs/grpc-proto-files/api.ngp.root-ca.crt` | set to the Axxon gRPC root CA supplied for the deployment |
| `AXXON_PROTO_DIR` | `docs/grpc-proto-files` | set to the directory containing Axxon `.proto` files |
| `AXXON_GRPC_STUBS` | `/tmp/axxon-grpc-py` | generated Python stubs cache |
| `AXXON_TIMEOUT` | `10.0` | request timeout in seconds |

Axxon proto files, CA files, and customer credentials are not redistributed in this repository.

## Architecture

The entrypoint is `tools/axxon_mcp_server.py`. It registers knowledge tools by default and registers additional capability modules from `tools/axxon_mcp_*.py` when matching flags are selected.

Capability groups reuse the same client implementation class from `tools/axxon_api_client.py`, but they currently instantiate separate capability objects and separate client objects rather than one shared global client. The server-backed groups expose connection helper tools for validating the active Axxon profile. There are offline authoring and planning exceptions: generator, partner, and translator tools create or validate integration artifacts without contacting Axxon, and operator planning can create plans before an explicit apply step connects to perform a mutation.

Knowledge tools work entirely from `docs/api-audit/mcp-corpus/`:

- `search_api_docs`
- `get_api_method`
- `get_http_endpoint`
- `get_verified_example`
- `explain_task_recipe`
- `list_remaining_gaps`
- `list_capabilities`

Use `list_capabilities` to see which groups are registered in the current process and which flags enable the disabled groups.

## Mutation safety

Mutation-capable groups have separate approval variables and per-call guards. Examples include operator workflows, PTZ control, macros, admin changes, settings updates, bookmark mutation, export lifecycle operations, and other write paths. Tool registration is never sufficient by itself.

For customer operations:

1. Start with the smallest explicit `--enable-*` set.
2. Use `--read-only` when a client needs broad discovery but must not mutate.
3. Enable mutation only by setting the exact documented approval variable to `1` outside the server process.
4. Require caller review of every returned plan and confirmation token before apply.
5. Run verification and rollback/cleanup where the workflow provides it.

## Repository layout

```
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
