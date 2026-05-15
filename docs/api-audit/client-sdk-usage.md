# Axxon One Local API Client Usage

This document describes the reusable Python client helper for the local ARM64 Axxon One lab.

Source file:

- `arm64-docker/tools/axxon_api_client.py`

Use it when building plugins, vertical integrations, quick probes, or new API sweep tools. It centralizes the local-lab details that are easy to get wrong: gRPC TLS, certificate CN override, proto stub generation, HTTP `/grpc` authentication, `/v1` request handling, safe report shaping, and archive/inventory fixtures.

Current tools using this client path:

- `arm64-docker/tools/axxon_api_probe.py`
- `arm64-docker/tools/axxon_readonly_sweep.py`
- `arm64-docker/tools/axxon_event_search.py`
- `arm64-docker/tools/axxon_http_grpc_sweep.py`
- `arm64-docker/tools/axxon_http_v1_sweep.py`
- `arm64-docker/tools/examples/`

## Environment

Credentials are not stored in this repo. Export them before running examples:

```bash
export AXXON_USERNAME=root
export AXXON_PASSWORD='<password>'
export AXXON_HOST=127.0.0.1
export AXXON_GRPC_PORT=20109
export AXXON_HTTP_URL=http://127.0.0.1:8000
export AXXON_TLS_CN=F4E66972EC19
```

Recommended Python runtime:

```bash
python3 -m venv /tmp/axxon-grpc-venv
/tmp/axxon-grpc-venv/bin/python -m pip install -r arm64-docker/tools/requirements-api-probe.txt
```

## Direct gRPC Example

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_grpc()

domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
domain = client.common_stubs()["domain"]

response = domain.GetVersion(domain_pb2.GetVersionRequest(), timeout=client.config.timeout)
print(client.message_to_dict(response))
```

Direct gRPC rules handled by the client:

- Uses TLS on port `20109`.
- Loads `api.ngp.root-ca.crt`.
- Sets `grpc.ssl_target_name_override` to `F4E66972EC19` for localhost Docker testing.
- Authenticates with `AuthenticationService.AuthenticateEx2`.
- Reconnects with returned token metadata for follow-up calls.

## Dynamic Stub Example

Use `stub_from_proto()` when working from the catalog row values:

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
stub = client.stub_from_proto("axxonsoft/bl/domain/Domain.proto", "DomainService")
domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")

pages = stub.ListCameras(domain_pb2.ListCamerasRequest(page_size=100), timeout=10)
for page in pages:
    print(client.shape_protobuf(page))
```

Many Axxon APIs are server-streaming. Always iterate returned pages for methods marked as server streaming in `grpc-api-catalog.csv`.

## HTTP `/grpc` Example

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
response = client.http_grpc("axxonsoft.bl.domain.DomainService.GetVersion", {})
print(client.shape(response["body"]))
```

HTTP `/grpc` rules handled by the client:

- Authentication call uses HTTP Basic auth plus a JSON `/grpc` body.
- Follow-up calls use `Authorization: Bearer <token_value>`.
- JSON, multipart `ngpboundary`, and `text/event-stream` wrappers are parsed.
- Tokens and passwords are redacted by `sanitize()`.

## HTTP `/v1` Example

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_http_grpc()

response = client.http_request("GET", "/v1/domain/cameras", bearer=True)
print(client.shape(response["body"]))
```

For GET endpoints with request parameters:

```python
query = client.query_string({"page_size": 100})
response = client.http_request("GET", "/v1/domain/cameras", bearer=True, query=query)
```

## Inventory Helpers

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
inventory = client.load_inventory()

print(len(inventory["cameras"]))
print(client.node_name())
print(client.archive_access_point())
print(client.archive_source_access_point())
```

Current local-lab assumptions encoded in helpers:

- Prefer the AliceBlue archive access point for archive service calls.
- Prefer a real `/Sources/src.*` component access point for archive history, calendar, and size calls.
- Use the first domain node name, falling back to the TLS CN override.

## Archive Fixture Helpers

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_grpc()

archive_pb2 = client.import_module("axxonsoft.bl.archive.ArchiveSupport_pb2")
archive = client.common_stubs()["archive"]

begin, end = client.archive_time_range_1900_ms(hours=1)
request = archive_pb2.GetHistory2Request(
    access_point=client.archive_source_access_point(),
    begin_time=begin,
    end_time=end,
    max_count=8,
    min_gap_ms=1000,
    scan_mode=archive_pb2.GetHistory2Request.SM_APPROXIMATE,
)
response = archive.GetHistory2(request, timeout=10)
print(client.shape_protobuf(response))
```

Use `archive_time_range_legacy()` for APIs that expect `YYYYMMDDTHHMMSS.ffffff` time strings.

## Report Safety

Use these helpers before writing reports:

```python
safe_details = client.sanitize(raw_details)
shape_only = client.shape(raw_response_body)
protobuf_shape = client.shape_protobuf(raw_proto_message)
```

Do not persist:

- Passwords.
- Bearer tokens or gRPC token metadata.
- License keys.
- Serial numbers.
- Full security/user/role payloads unless explicitly needed and reviewed.

## Reuse In New Tools

New probe or integration scripts should usually:

1. Parse common args with `add_common_args(parser)`.
2. Build config with `config_from_args(args)`.
3. Create `AxxonApiClient(config)`.
4. Use direct gRPC for durable integrations.
5. Use HTTP `/grpc` or `/v1` for web-adjacent checks.
6. Save response shapes and counts, not full sensitive payloads.

## Practical Examples

Example scripts live in:

```text
arm64-docker/tools/examples/
```

Run examples with the same environment variables used by the probes:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/inventory_sync.py
```

Available examples:

- `inventory_sync.py`: direct-gRPC inventory bootstrap for cameras, archives, components, and version.
- `event_search_summary.py`: compact recent event search using `AxxonEventSearch`.
- `camera_archive_status.py`: camera inventory plus archive traits, volume state, and disk state.
- `metadata_tracker_stream.py`: live object-tracker metadata samples from a VMDA endpoint.
- `http_grpc_vs_grpc.py`: compare direct gRPC `GetVersion` with HTTP `/grpc` wrapper behavior.

Recommended smoke sequence:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/inventory_sync.py

AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/event_search_summary.py --hours 1 --limit 3

AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/http_grpc_vs_grpc.py
```
