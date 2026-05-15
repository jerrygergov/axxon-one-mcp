# MCP Generation Static Smoke

_run at 2026-05-15T14:56:46Z_

| template | status | files | bytes | verifier | compiles |
| --- | --- | --- | --- | --- | --- |
| grpc_consumer | ok | 3 | 3084 | ok | yes |
| http_grpc_consumer | ok | 3 | 1886 | ok | yes |
| legacy_http_consumer | ok | 3 | 1798 | ok | yes |
| event_consumer | ok | 3 | 2878 | ok | yes |
| external_event_producer | ok | 3 | 2460 | ok | yes |
| export_job | ok | 3 | 4162 | ok | yes |

## Detail

### grpc_consumer
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 3084,
  "notes": [],
  "required_env": [
    "AXXON_HOST",
    "AXXON_TLS_CN",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [],
  "status": "ok",
  "template": "grpc_consumer",
  "verifier_errors": [],
  "verifier_ok": true
}
```

### http_grpc_consumer
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 1886,
  "notes": [],
  "required_env": [
    "AXXON_HTTP_URL",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [],
  "status": "ok",
  "template": "http_grpc_consumer",
  "verifier_errors": [],
  "verifier_ok": true
}
```

### legacy_http_consumer
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 1798,
  "notes": [],
  "required_env": [
    "AXXON_HTTP_URL",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [],
  "status": "ok",
  "template": "legacy_http_consumer",
  "verifier_errors": [],
  "verifier_ok": true
}
```

### event_consumer
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 2878,
  "notes": [],
  "required_env": [
    "AXXON_HOST",
    "AXXON_TLS_CN",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [
    "event-supplier-subject"
  ],
  "status": "ok",
  "template": "event_consumer",
  "verifier_errors": [],
  "verifier_ok": true
}
```

### external_event_producer
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 2460,
  "notes": [],
  "required_env": [
    "AXXON_HTTP_URL",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [
    "detector-ex"
  ],
  "status": "ok",
  "template": "external_event_producer",
  "verifier_errors": [],
  "verifier_ok": true
}
```

### export_job
```json
{
  "compiles": true,
  "file_count": 3,
  "main_bytes": 4162,
  "notes": [],
  "required_env": [
    "AXXON_HOST",
    "AXXON_TLS_CN",
    "AXXON_USERNAME",
    "AXXON_PASSWORD"
  ],
  "required_fixtures": [
    "mm-export-agent"
  ],
  "status": "ok",
  "template": "export_job",
  "verifier_errors": [],
  "verifier_ok": true
}
```

## Next step (runtime smoke)

Each bundle requires the standard `AXXON_*` env vars listed in `required_env`. Run `python main.py` inside the generated directory with the demo profile loaded to exercise live execution. Network execution is intentionally out of scope for this static smoke and is gated on user approval per Stop Conditions in `docs/plans/2026-05-15-mcp-phase-4-integration-generation.md`.