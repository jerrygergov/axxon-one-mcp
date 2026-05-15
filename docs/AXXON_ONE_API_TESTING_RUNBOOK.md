# Axxon One API Testing Runbook

This runbook captures the local ARM64 Docker test server API workflow and the API behavior verified on 2026-04-26.

## Read This First

This repository is being used as an Axxon One gRPC and HTTP API learning and test lab. The goal is to make future Codex sessions able to act as an Axxon One API expert without relying on chat history.

Start with:

- `arm64-docker/docs/AXXON_ONE_API_EXPERT_CONTEXT.md`
- `arm64-docker/docs/api-audit/README.md`
- `arm64-docker/docs/api-audit/live-readonly-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-grpc-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-v1-sweep-latest.md`
- `arm64-docker/docs/api-audit/mutating-fixture-sweep-latest.md`
- `arm64-docker/docs/api-audit/read-fixture-notes.md`
- `arm64-docker/docs/api-audit/client-sdk-usage.md`
- `arm64-docker/docs/api-audit/integration-playbooks.md`
- `arm64-docker/docs/api-test-runs/latest.md`
- `arm64-docker/tools/axxon_api_client.py`
- `arm64-docker/tools/examples/`
- `arm64-docker/tools/axxon_api_probe.py`

## Target

- Container: `axxon-one-arm64`
- Image: `axxon-one:3.0.0.46-arm64-local`
- Web UI and HTTP API: `http://127.0.0.1:8000`
- Direct gRPC API: `127.0.0.1:20109`
- TLS CN override: `F4E66972EC19`
- Root CA: `docs/grpc-proto-files/api.ngp.root-ca.crt`
- Server version tested: `3.0.0.46`

## Setup

Reusable API client:

```text
arm64-docker/tools/axxon_api_client.py
```

Use it for new Axxon One gRPC/HTTP scripts. It handles local Docker TLS, gRPC auth metadata, HTTP `/grpc` Basic-to-Bearer auth, `/v1` request handling, safe parsing, sanitizing, and inventory/archive helpers. See:

```text
arm64-docker/docs/api-audit/client-sdk-usage.md
```

Current core tools using this client path are `axxon_api_probe.py`, `axxon_readonly_sweep.py`, `axxon_event_search.py`, `axxon_http_grpc_sweep.py`, `axxon_http_v1_sweep.py`, and the scripts in `arm64-docker/tools/examples/`.

Runnable integration examples:

```text
arm64-docker/tools/examples/
```

Use these before writing new plugin code:

- `inventory_sync.py`
- `event_search_summary.py`
- `camera_archive_status.py`
- `metadata_tracker_stream.py`
- `http_grpc_vs_grpc.py`

Create or refresh the probe venv:

```bash
python3 -m venv /tmp/axxon-grpc-venv
/tmp/axxon-grpc-venv/bin/python -m pip install -r arm64-docker/tools/requirements-api-probe.txt
```

Run the complete probe:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_api_probe.py --verbose
```

Reports are written to:

- `docs/api-test-runs/latest.md`
- `docs/api-test-runs/latest.json`
- `docs/api-test-runs/axxon-api-probe-<timestamp>.md`
- `docs/api-test-runs/axxon-api-probe-<timestamp>.json`

The report writer redacts tokens, passwords, license keys, serial numbers, and session tokens.

## Full API Catalog

Generate the service-by-service gRPC catalog and HTTP endpoint catalog from local protos:

```bash
./arm64-docker/tools/generate_api_catalog.py
```

Generated files:

- `arm64-docker/docs/api-audit/README.md`
- `arm64-docker/docs/api-audit/grpc-api-catalog.md`
- `arm64-docker/docs/api-audit/grpc-api-catalog.csv`
- `arm64-docker/docs/api-audit/http-endpoints-catalog.md`
- `arm64-docker/docs/api-audit/live-readonly-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-grpc-sweep-latest.md`
- `arm64-docker/docs/api-audit/http-v1-sweep-latest.md`
- `arm64-docker/docs/api-audit/mutating-fixture-sweep-latest.md`
- `arm64-docker/docs/api-audit/client-sdk-usage.md`
- `arm64-docker/docs/api-audit/integration-playbooks.md`
- `arm64-docker/docs/api-audit/mutating-api-fixtures.md`

Run the conservative read-oriented live sweep:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_readonly_sweep.py
```

Run HTTP `/grpc` parity:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_grpc_sweep.py
```

Run safe `/v1` GET plus read-like POST endpoints:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_v1_sweep.py
```

Run the low-risk SharedKV mutating fixture:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_mutating_fixture_sweep.py
```

## Current Clean Result

Latest verified result on 2026-04-26:

- PASS: 24
- WARN: 0
- FAIL: 0

Validated surfaces:

- TCP reachability for ports `8000` and `20109`.
- Direct gRPC authentication with `AuthenticationService.AuthenticateEx2`.
- gRPC health check, returning `SERVING`.
- Domain inventory through version, platform, nodes, cameras, archives, and components.
- Domain batch camera lookup.
- Configuration unit and access-point lookup.
- Archive traits, volume state, disk state, and short history query.
- Live tracker metadata through `MetadataService.PullMetadata`.
- Export session listing.
- License state, restrictions, and launch feasibility.
- Statistics service.
- Event history count query.
- SharedKV write, read, streaming read, and remove.
- HTTP `/grpc` authentication and authenticated service calls.
- REST-style HTTP endpoints for nodes, cameras, and license info.

## Event Search CLI

Reusable event-history search tool:

```text
arm64-docker/tools/axxon_event_search.py
```

It uses direct gRPC on `20109` with the same TLS/auth rules as the comprehensive probe.

Basic search:

```bash
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py --hours 1 --limit 5
```

Focused examples:

```bash
# Detector events with matching text
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --category detector --text 'Line crossing' --limit 5

# Events scoped to Camera 2
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'Camera 2' --limit 5

# Integrity events
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 168 --category integrity --limit 5

# LPR-specific search
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 168 --lpr --predicate '*82*' --limit 5
```

Save JSON output:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --limit 10 --json \
  --save arm64-docker/docs/api-test-runs/event-search-latest.json
```

Current live findings from event search:

- The local server has thousands of recent events.
- Recent history is dominated by `ET_DetectorEvent` line-crossing events on `1.Camera`.
- Camera 2 has a small setup/audit/state-change history.
- Integrity history includes both previous compromised states and later trusted states.
- `ReadLprEvents` currently returns no LPR events on this test server.

## Inventory Snapshot

The local test server currently has:

- Node count: `1`
- Camera count: `2`
- Archive count: `3`
- Component count: `22`

Cameras:

- `hosts/F4E66972EC19/DeviceIpint.1/SourceEndpoint.video:0:0`, display name `Camera`, enabled.
- `hosts/F4E66972EC19/DeviceIpint.2/SourceEndpoint.video:0:0`, display name `Camera 2`, enabled.

Main archive:

- `hosts/F4E66972EC19/MultimediaStorage.AliceBlue/MultimediaStorage`

Object tracker metadata endpoint:

- `hosts/F4E66972EC19/AVDetector.2/SourceEndpoint.vmda`

## Direct gRPC Rules

Direct gRPC uses TLS on port `20109`.

The local Docker certificate does not match `127.0.0.1`, so client code must use:

```python
grpc.secure_channel(
    "127.0.0.1:20109",
    grpc.ssl_channel_credentials(root_certificates=root_ca_bytes),
    options=(("grpc.ssl_target_name_override", "F4E66972EC19"),),
)
```

The first authentication call is made without auth metadata:

```text
axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2
```

Authenticated follow-up calls must pass the returned token as gRPC metadata:

```python
metadata = ((auth_response.token_name, auth_response.token_value),)
```

Many Axxon gRPC methods are server-streaming. Client code must iterate response pages, even when only one page is expected.

## HTTP API Rules

HTTP `/grpc` is available through the web port on `8000`.

Authentication:

- Call `/grpc` with method `axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2`.
- Use HTTP Basic auth for this authentication call.
- Send username and password in the JSON `data` object.

Follow-up HTTP `/grpc` calls:

- Use `Authorization: Bearer <token_value>`.
- Use fully qualified method names, for example `axxonsoft.bl.domain.DomainService.GetVersion`.
- Server-streaming methods can come back as `text/event-stream`, not simple JSON.

REST-style endpoints verified:

- `GET /v1/domain/nodes`
- `GET /v1/domain/cameras`
- `GET /v1/license:info`

## Configuration Gotchas

For this local ARM64 Docker image, virtual device creation worked with:

- `vendor=Virtual`
- `model=Virtual`

The PDF/example pair `vendor=axxonsoft`, `model=Virtual` failed on this image with a native-layer error saying the model could not be found in the device info index.

Object tracker mode:

- Use CPU decoder mode in this Docker/ARM setup.
- GPU decoder mode logs CUDA initialization failures.

## Metadata Gotcha

The most reliable end-to-end tracker validation is not just checking that the `AVDetector` unit exists.

Use:

```text
axxonsoft.bl.metadata.MetadataService.PullMetadata
```

Target the tracker VMDA endpoint:

```text
hosts/F4E66972EC19/AVDetector.2/SourceEndpoint.vmda
```

The clean probe run received:

- Metadata samples: `5`
- Tracklets seen: `25`

This proves the camera, video source, tracker, and metadata pipeline are all working.

## Archive Gotcha

Prefer the real archive access point for archive service calls:

```text
hosts/F4E66972EC19/MultimediaStorage.AliceBlue/MultimediaStorage
```

Embedded storage access points are listed for virtual cameras, but can be unsuitable for some ArchiveService calls.

The clean probe confirmed the AliceBlue archive has:

- Trait: `AT_RANDOM_RECORDING`
- Volume count: `1`
- Disk capacity around `75.9 GB`
- Free space around `50.0 GB`

## SharedKV Gotchas

SharedKV is useful as a safe write/read/remove API test because it does not modify video server configuration.

Observed on this build:

- Writes with an empty prefix succeed.
- Writes with non-empty prefixes returned `EConflict`.
- After writing, `BatchGetRecords` and `GetRecordsStream` should request by key without the returned revision.
- Requesting by key plus returned revision produced no data in testing.
- After removal, `BatchGetRecords` may still return a key-only tombstone.
- Use `ListRecords` absence and absence of a value in `BatchGetRecords` as the deletion check.

The probe namespaces its records as `codex-api-probe-*` and removes probe records before/after the test.

## Probe Source Files

- `tools/axxon_api_probe.py`
- `tools/requirements-api-probe.txt`
- `docs/plans/2026-04-26-axxon-api-comprehensive-test.md`

## Quick Health Checks

Container state:

```bash
docker ps --filter name=axxon-one-arm64
```

Port state:

```bash
nc -zv 127.0.0.1 8000
nc -zv 127.0.0.1 20109
```

Latest report summary:

```bash
/tmp/axxon-grpc-venv/bin/python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("arm64-docker/docs/api-test-runs/latest.json").read_text())
print(data["summary"])
PY
```
