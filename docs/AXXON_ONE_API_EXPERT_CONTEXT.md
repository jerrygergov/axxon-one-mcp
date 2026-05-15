# Axxon One API Expert Context

This is the first file to read in future sessions about Axxon One gRPC or HTTP API work in this repository.

## Mission

The user is building a local Axxon One API test lab and wants Codex to become an Axxon One gRPC and HTTP API expert/guru.

The working style should be:

- Test against the local server whenever possible.
- Prefer generated gRPC clients and proto definitions for exact behavior.
- Use HTTP `/grpc` and REST-style endpoints for quick checks and troubleshooting.
- Document every verified behavior and every gotcha in repo docs.
- Do not rely on chat history as the only source of truth.

## Current Local Server

- Product: Axxon One
- Version: `3.0.0.46`
- Container: `axxon-one-arm64`
- Image: `axxon-one:3.0.0.46-arm64-local`
- Web UI: `http://127.0.0.1:8000`
- HTTP API base: `http://127.0.0.1:8000`
- Direct gRPC: `127.0.0.1:20109`
- TLS CN override: `F4E66972EC19`
- Root CA: `arm64-docker/docs/grpc-proto-files/api.ngp.root-ca.crt`
- Docker compose: `arm64-docker/docker-compose.arm64-local.yml`

Credentials are intentionally not stored in documentation. Use `AXXON_USERNAME` and `AXXON_PASSWORD` environment variables for scripts.

## External Demo Stand

The user provided a richer demo stand for broader API-book examples. Use it when the local Docker lab is too small for analytics, event, archive, layout, map, realtime recognizer, or security read examples.

- Product: Axxon One
- Version: `3.0.0.46`
- HTTP API base: `http://<demo-host>:80`
- Direct gRPC: `<demo-host>:20109`
- TLS CN override: `Server`
- Temporary certificate path used during testing: `/tmp/axxon-demo-server.crt`

Do not store the demo password, bearer tokens, license keys, serial numbers, or full plate values in repo docs. Sanitized results are recorded in:

```text
arm64-docker/docs/api-audit/demo-stand-2026-05-01.md
```

Demo-stand findings from 2026-05-02:

- Parent `AVDetector.*` objects usually provide tracker metadata and VMDA endpoints.
- Child `AppDataDetector.*` objects are the semantic event producers for rules such as motion in area, line crossing, loitering, multiple objects, and track masking.
- `ConfigurationService.ChangeConfig` was verified with rollback for temporary archive, virtual camera, `AVDetector`, and `AppDataDetector` objects.
- For this demo, temporary virtual camera creation needs `vendor=Virtual`; the PDF `vendor=axxonsoft` example failed on this stand.

## Current Configuration Snapshot

Validated on 2026-04-26 by the comprehensive API probe.

- PASS: `24`
- WARN: `0`
- FAIL: `0`
- Nodes: `1`
- Cameras: `2`
- Archives: `3`
- Components: `22`
- Health service: `SERVING`

Cameras:

- `hosts/F4E66972EC19/DeviceIpint.1/SourceEndpoint.video:0:0`, display name `Camera`, enabled.
- `hosts/F4E66972EC19/DeviceIpint.2/SourceEndpoint.video:0:0`, display name `Camera 2`, enabled.

Main archive:

- `hosts/F4E66972EC19/MultimediaStorage.AliceBlue/MultimediaStorage`

Tracker metadata endpoint:

- `hosts/F4E66972EC19/AVDetector.2/SourceEndpoint.vmda`

Sample video in the container:

- `/data/video/LPR/video.mkv`

## Read Order

Use this order when resuming API work:

1. `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
2. `arm64-docker/docs/AXXON_ONE_API_TESTING_RUNBOOK.md`
3. `arm64-docker/docs/api-test-runs/latest.md`
4. `arm64-docker/docs/api-audit/README.md`
5. `arm64-docker/docs/api-audit/demo-stand-2026-05-01.md`
6. `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.md`
7. `arm64-docker/docs/api-audit/pdf-gap-coverage-summary.md`
8. `arm64-docker/docs/api-audit/fixture-discovery-latest.md`
9. `arm64-docker/docs/api-audit/appdata-detectors-demo-2026-05-02.md`
10. `arm64-docker/docs/api-audit/config-model-study-latest.md`
11. `arm64-docker/docs/api-audit/config-mutation-smoke-latest.md`
12. `arm64-docker/docs/api-audit/mutating-api-fixtures.md`
13. `arm64-docker/docs/api-audit/grpc-api-catalog.md`
14. `arm64-docker/docs/api-audit/http-endpoints-catalog.md`
15. `arm64-docker/docs/api-audit/live-readonly-sweep-latest.md`
16. `arm64-docker/docs/api-audit/http-grpc-sweep-latest.md`
17. `arm64-docker/docs/api-audit/http-v1-sweep-latest.md`
18. `arm64-docker/docs/api-audit/mutating-fixture-sweep-latest.md`
19. `arm64-docker/docs/api-audit/client-sdk-usage.md`
20. `arm64-docker/docs/api-audit/integration-playbooks.md`
21. `arm64-docker/tools/axxon_api_client.py`
22. `arm64-docker/tools/axxon_config_model_study.py`
23. `arm64-docker/tools/axxon_config_mutation_smoke.py`
24. `arm64-docker/tools/examples/`
25. `arm64-docker/tools/axxon_api_probe.py`
26. `arm64-docker/tools/axxon_readonly_sweep.py`
27. `arm64-docker/tools/axxon_http_grpc_sweep.py`
28. `arm64-docker/tools/axxon_http_v1_sweep.py`
29. `arm64-docker/tools/axxon_mutating_fixture_sweep.py`
30. `arm64-docker/docs/GRPC_API_STUDY_NOTES.md`
31. `arm64-docker/docs/grpc-proto-files/SERVICE_INDEX.md`
32. `arm64-docker/docs/AXXON_TELEGRAM_VMS_STUDY_NOTES.md`
33. Relevant `.proto` files under `arm64-docker/docs/grpc-proto-files/axxonsoft`
34. Converted PDF sections under `arm64-docker/docs/integration-apis-3.0/sections`

## Comprehensive Probe

Reusable client module:

```text
arm64-docker/tools/axxon_api_client.py
```

Use it for new integrations and probes instead of copying TLS/auth/HTTP helper code. Examples are in:

```text
arm64-docker/docs/api-audit/client-sdk-usage.md
```

Current core tools using this client path are `axxon_api_probe.py`, `axxon_readonly_sweep.py`, `axxon_event_search.py`, `axxon_http_grpc_sweep.py`, `axxon_http_v1_sweep.py`, `axxon_config_model_study.py`, `axxon_config_mutation_smoke.py`, and the scripts in `arm64-docker/tools/examples/`.

Runnable plugin/integration examples are in:

```text
arm64-docker/tools/examples/
```

Create or refresh the Python venv:

```bash
python3 -m venv /tmp/axxon-grpc-venv
/tmp/axxon-grpc-venv/bin/python -m pip install -r arm64-docker/tools/requirements-api-probe.txt
```

Run the full probe:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_api_probe.py --verbose
```

Generated reports:

- `arm64-docker/docs/api-test-runs/latest.md`
- `arm64-docker/docs/api-test-runs/latest.json`
- `arm64-docker/docs/api-test-runs/axxon-api-probe-<timestamp>.md`
- `arm64-docker/docs/api-test-runs/axxon-api-probe-<timestamp>.json`

## Verified API Surfaces

The current probe validates:

- TCP reachability for web and gRPC ports.
- `AuthenticationService.AuthenticateEx2`.
- `grpc.health.v1.Health.Check`.
- `DomainService.GetVersion`.
- `DomainService.GetHostPlatformInfo`.
- `DomainService.ListNodes`.
- `DomainService.ListCameras`.
- `DomainService.ListArchives`.
- `DomainService.ListComponents`.
- `DomainService.BatchGetCameras`.
- `DomainService.GetHostTimeZone`.
- `ConfigurationService.ListUnits`.
- `ConfigurationService.ListUnitsByAccessPoints`.
- `ConfigurationService.ListTemplates`.
- `ArchiveService.GetArchiveTraits`.
- `ArchiveService.GetVolumesState`.
- `ArchiveService.GetDiskSpace`.
- `ArchiveService.GetHistory2`.
- `MetadataService.PullMetadata`.
- `ExportService.ListSessions`.
- `LicenseService.LicenseKeyInfo`.
- `LicenseService.GetGlobalRestrictions`.
- `LicenseService.GetNodeRestrictions`.
- `LicenseService.IsPossibleToLaunch`.
- `StatisticService.GetStatistics`.
- `EventHistoryService.ReadCount`.
- `SharedKVStorageService.Commit`.
- `SharedKVStorageService.BatchGetRecords`.
- `SharedKVStorageService.GetRecordsStream`.
- HTTP `/grpc` auth and service calls.
- REST-style `/v1/domain/nodes`, `/v1/domain/cameras`, `/v1/license:info`.

## Full API Audit Catalog

Generated one-by-one catalogs for the whole local proto API are kept in:

- `arm64-docker/docs/api-audit/README.md`
- `arm64-docker/docs/api-audit/grpc-api-catalog.md`
- `arm64-docker/docs/api-audit/grpc-api-catalog.csv`
- `arm64-docker/docs/api-audit/http-endpoints-catalog.md`
- `arm64-docker/docs/api-audit/live-readonly-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-grpc-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-v1-sweep-latest.md`
- `arm64-docker/docs/api-audit/mutating-fixture-sweep-latest.md`
- `arm64-docker/docs/api-audit/read-fixture-notes.md`
- `arm64-docker/docs/api-audit/client-sdk-usage.md`
- `arm64-docker/docs/api-audit/integration-playbooks.md`
- `arm64-docker/docs/api-audit/mutating-api-fixtures.md`

Regenerate them after proto or probe-status changes:

```bash
./arm64-docker/tools/generate_api_catalog.py
```

Run the conservative direct-gRPC read sweep:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_readonly_sweep.py
```

Run HTTP and controlled mutating sweeps:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_grpc_sweep.py

AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_v1_sweep.py

AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_mutating_fixture_sweep.py
```

## Event Search Tool

Reusable direct-gRPC event search CLI:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py --hours 1 --limit 5
```

Useful examples:

```bash
# Latest detector events containing operator text
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --category detector --text 'Line crossing' --limit 5

# Camera-specific history
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'Camera 2' --limit 10

# Integrity history
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 168 --category integrity --limit 10

# LPR-specific search
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 168 --lpr --predicate '*82*' --limit 10
```

Latest saved event-search report:

```text
arm64-docker/docs/api-test-runs/event-search-latest.json
```

## Critical Gotchas

Direct gRPC:

- Use TLS on `20109`.
- Use the root CA from `docs/grpc-proto-files`.
- Override target name to `F4E66972EC19` when connecting to `127.0.0.1`.
- Authenticate first without metadata, then attach the returned token metadata to later calls.

HTTP:

- `/grpc` auth requires Basic auth plus JSON body data.
- Later `/grpc` calls use Bearer auth.
- Streaming method responses may be `text/event-stream`.

Configuration:

- Virtual camera creation worked with `vendor=Virtual`, `model=Virtual`.
- `vendor=axxonsoft`, `model=Virtual` failed on this local image.
- In ARM Docker, object tracker decoder should be CPU.

Metadata:

- Do not treat tracker existence as sufficient.
- Real proof is `MetadataService.PullMetadata` returning samples and tracklets from the VMDA endpoint.

Archive:

- Prefer the AliceBlue archive AP for ArchiveService calls.
- Embedded storage APs can appear in inventory but may not work for all archive API methods.

SharedKV:

- Empty prefix works for safe write/read/remove testing.
- Non-empty prefixes returned `EConflict` during local tests.
- Read by key only after write; key plus returned revision returned no data.
- Delete can leave a key-only tombstone in `BatchGetRecords`; verify delete by `ListRecords` absence and no value.

## Security Rules

- Do not write plaintext passwords into docs, scripts, reports, or commits.
- Do not write bearer tokens into docs, scripts, reports, or commits.
- Do not write license keys or serial numbers into docs, scripts, reports, or commits.
- Keep generated reports sanitized.

## If The Server Is Down

Start Docker container:

```bash
docker compose -f arm64-docker/docker-compose.arm64-local.yml up -d
```

Check status:

```bash
docker ps --filter name=axxon-one-arm64
docker inspect -f '{{.State.Status}} {{.State.Health.Status}}' axxon-one-arm64
nc -zv 127.0.0.1 8000
nc -zv 127.0.0.1 20109
```

## Next API Areas To Deepen

- Archive search and VMDA query APIs.
- Event subscription and notification APIs.
- Media streaming APIs.
- Configuration mutations for cameras, archives, layouts, users, macros, and detector masks.
- Export workflow with an export agent configured.
- Error handling patterns and canonical status-code mapping.
- HTTP `/grpc` parity for the direct-gRPC event-search tool.
