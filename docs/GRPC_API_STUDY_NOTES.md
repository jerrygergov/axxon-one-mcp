# Axxon One gRPC API Study Notes

These notes summarize the local Axxon One 3.0 Integration APIs documentation and the local gRPC proto bundle.

## Local Expert Context

The working objective for this repository is to make Codex an Axxon One gRPC and HTTP API expert/guru by combining official docs, proto inspection, and repeatable live tests against the local server.

For future sessions, read these first:

- `arm64-docker/docs/AXXON_ONE_API_EXPERT_CONTEXT.md`
- `arm64-docker/docs/AXXON_ONE_API_TESTING_RUNBOOK.md`
- `arm64-docker/docs/api-test-runs/latest.md`

The current comprehensive probe is `arm64-docker/tools/axxon_api_probe.py`.

The current reusable event-history search tool is `arm64-docker/tools/axxon_event_search.py`.

Latest clean live result on 2026-04-26:

- PASS: 24
- WARN: 0
- FAIL: 0

Latest event-search notes:

- `EventHistoryService.ReadEvents` works for broad history, camera-scoped history, event-type filters, text filters, and value filters.
- `EventHistoryService.ReadCount` works for general event counts.
- `EventHistoryService.ReadLprEvents` works as an API call but currently returns no LPR rows on the local test server.
- The Telegram bot repo at `<external-reference-repo>/axxon-telegram-vms` is a useful reference for event normalization, LPR plate extraction, HTTP `/grpc` response parsing, and subscription filter shaping.

## Sources

- Converted API document: `arm64-docker/docs/integration-apis-3.0/integration-apis-3.0.md`
- gRPC section: `arm64-docker/docs/integration-apis-3.0/sections/02-grpc-api.md`
- Proto bundle: `arm64-docker/docs/grpc-proto-files`
- Generated proto index: `arm64-docker/docs/grpc-proto-files/SERVICE_INDEX.md`
- Root CA in proto bundle: `arm64-docker/docs/grpc-proto-files/api.ngp.root-ca.crt`

## Main Takeaways

- Axxon One exposes two gRPC access patterns: true gRPC over TLS and a web-server JSON wrapper.
- Direct gRPC uses TLS and the gRPC API port, documented as `20109`.
- In our local Docker setup, the useful host endpoints are `127.0.0.1:8000` for web and `127.0.0.1:20109` for direct gRPC when the container is running with the current compose file.
- The web-server JSON wrapper uses `POST /grpc` on the web port. In our local setup this is `http://127.0.0.1:8000/grpc`.
- Direct gRPC is the better path for real integrations, streaming APIs, media, metadata, export downloads, notifications, and anything that needs generated client types.
- The `/grpc` wrapper is practical for simple calls and troubleshooting because the request body is JSON with a fully qualified method name.
- Most non-trivial APIs require authentication metadata. Authenticate first, then send the returned token metadata on later calls.

## Proto Bundle Inventory

The local proto bundle contains the Axxon protos plus bundled Google/grpc dependencies.

- Axxon `.proto` files: 98
- Services generated from Axxon protos: 51
- RPC methods generated from Axxon protos: 361
- Unary RPCs: 276
- Server-streaming RPCs: 76
- Client-streaming RPCs: 2
- Bidirectional-streaming RPCs: 7

Use `arm64-docker/docs/grpc-proto-files/SERVICE_INDEX.md` as the quick reference for service names, packages, proto files, and RPC signatures.

## TLS And Certificates

Direct gRPC requires TLS.

The local proto bundle includes:

```text
arm64-docker/docs/grpc-proto-files/api.ngp.root-ca.crt
```

Certificate details observed locally:

```text
subject=CN = api.ngp Root CA
issuer=CN = api.ngp Root CA
notBefore=Jun 11 16:19:16 2021 GMT
notAfter=Dec 31 16:19:16 2099 GMT
sha256=5F:C9:AC:B5:50:CE:45:83:1C:3B:12:C8:4F:52:30:E9:53:DA:53:94:11:08:D8:0C:7C:35:32:B9:36:FC:20:A8
```

The PDF example uses `C:\ProgramData\AxxonSoft\Axxon One\Tickets\Node.crt` and extracts the certificate common name for `grpc.ssl_target_name_override`. For local Docker testing, start with the bundled `api.ngp.root-ca.crt`. If direct TLS validation fails, copy `Node.crt` from the running server/container and use its CN as the override.

## Authentication Flow

Preferred auth methods from `Authentication.proto`:

- `axxonsoft.bl.auth.AuthenticationService.Authenticate2`
- `axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2`
- `axxonsoft.bl.auth.AuthenticationService.RenewSession2`
- `axxonsoft.bl.auth.AuthenticationService.CloseSession`

Deprecated or less preferred methods still exist:

- `Authenticate`
- `AuthenticateEx`
- `RenewSession`

Recommended flow for direct gRPC:

1. Create a TLS channel to `host:20109`.
2. Call `AuthenticationService.AuthenticateEx2` or `Authenticate2` with `user_name` and `password`.
3. Read `token_name` and `token_value` from the response.
4. Add metadata to later calls as `(token_name, token_value)`. Usually this is `("auth_token", "<jwt>")`.
5. Renew before expiration using `RenewSession2`.
6. Close the session with `CloseSession` when finished.

The PDF direct Python example uses the older `Authenticate` method, but the proto comments explicitly prefer `Authenticate2` / `AuthenticateEx2`.

## Web `/grpc` Wrapper

The web wrapper accepts JSON:

```json
{
  "method": "axxonsoft.bl.domain.DomainService.ListCameras",
  "data": {
    "view": "VIEW_MODE_FULL"
  }
}
```

Local URL when the Docker container is running:

```text
http://127.0.0.1:8000/grpc
```

Important auth behavior from the PDF:

- Direct gRPC authentication can be anonymous for the first auth request.
- HTTP requests to the web server cannot be anonymous, so token acquisition through `/grpc` requires Basic auth.
- After token acquisition, HTTP calls should use Bearer authorization with the returned token.

Use the wrapper for quick checks such as `DomainService.ListCameras`, `ConfigurationService.ListUnits`, or auth calls. Use direct gRPC for streaming APIs and production-like clients.

## Python Client Generation

Install dependencies:

```bash
python3 -m venv /tmp/axxon-grpc-venv
source /tmp/axxon-grpc-venv/bin/activate
pip install grpcio grpcio-tools pyOpenSSL googleapis-common-protos
```

Generate Python stubs from the local proto bundle:

```bash
mkdir -p /tmp/axxon-grpc-py
python -m grpc_tools.protoc \
  -I arm64-docker/docs/grpc-proto-files \
  --python_out=/tmp/axxon-grpc-py \
  --grpc_python_out=/tmp/axxon-grpc-py \
  $(find arm64-docker/docs/grpc-proto-files/axxonsoft -name '*.proto')
```

The bundled `google` and `grpc` proto dependencies are already under `arm64-docker/docs/grpc-proto-files`, so the single include path is enough for the local bundle.

## High-Value Services

### Authentication

Package: `axxonsoft.bl.auth`

Proto: `axxonsoft/bl/auth/Authentication.proto`

Use this first for any client. `AuthenticateEx2` is the safest default because it returns structured auth error codes instead of relying only on exceptions.

Key methods:

- `Authenticate2`
- `AuthenticateEx2`
- `RenewSession2`
- `CloseSession`
- `GetSessionInfo`

### Domain Inventory

Package: `axxonsoft.bl.domain`

Proto: `axxonsoft/bl/domain/Domain.proto`

This is the main discovery/inventory service for cameras, archives, nodes, microphones, speakers, relays, maps, and domain objects.

Key methods:

- `ListCameras`
- `BatchGetCameras`
- `ListArchives`
- `BatchGetArchives`
- `ListNodes`

Most inventory list methods are server-streaming. Client code must iterate the response stream, not expect a single response object.

### Configuration

Package: `axxonsoft.bl.config`

Proto: `axxonsoft/bl/config/ConfigurationService.proto`

Use this to inspect and modify server/device configuration units.

Key methods:

- `ListUnits`
- `ListUnitsStream`
- `ListUnitsByAccessPoints`
- `ChangeConfig`
- `ChangeConfigStream`
- `ListTemplates`

The PDF examples for camera/device management mostly use `ConfigurationService` with unit UIDs and access points returned from domain inventory calls.

### Export

Package: `axxonsoft.bl.mmexport`

Proto: `axxonsoft/bl/mmexport/ExportService.proto`

Export has a specific operational constraint: tasks are performed by an export agent, not by the gRPC channel itself. The PDF says an export agent cannot be created via gRPC and must be created manually in the Client.

Key methods:

- `ListSessions`
- `StartSession`
- `GetSessionState`
- `StopSession`
- `DestroySession`
- `DownloadFile`

Important details:

- If several export agents exist and `StartSession` does not specify one, agent index `1` is used.
- Export starts on the node where the first camera is located; tasks are forwarded automatically.
- `S_COMPLETED` does not guarantee success. Check `Result.succeeded` and result files.
- Completed export files are available for 1 hour. `GetSessionState` and `DownloadFile` reset the timeout.
- `DownloadFile` is server-streaming and returns `FileChunk`.
- `DownloadFileRequest.chunk_size_kb` is recommended at 16-64 KiB; default gRPC incoming message limit is 4 MB.

### Events And Notifications

Packages:

- `axxonsoft.bl.events.EventHistoryService`
- `axxonsoft.bl.events.DomainNotifier`
- `axxonsoft.bl.events.NodeNotifier`

Protos:

- `axxonsoft/bl/events/EventHistory.proto`
- `axxonsoft/bl/events/Notification.proto`

Use `EventHistoryService` for historical/search queries. Use notifier services for live event subscriptions.

Important methods:

- `EventHistoryService.ListEvents`
- `EventHistoryService.ListTextEvents`
- `EventHistoryService.FindByPrompt`
- `EventHistoryService.FindContacts`
- `EventHistoryService.FindSimilarObjects`
- `DomainNotifier.PullEvents`
- `DomainNotifier.PullDetailedEvents`
- `NodeNotifier.PullEvents`
- `NodeNotifier.PullDetailedEvents`
- `NodeNotifier.Ping`

These are mostly streaming APIs.

### Media

Package: `axxonsoft.bl.media`

Proto: `axxonsoft/bl/media/MediaService.proto`

This service handles NGP media connections and bidirectional media streaming.

Key methods:

- `Stream`
- `RequestConnection`
- `RequestQoS`
- `AwaitConnection`
- `ConnectEndpoint`
- `RequestTunnel`

`Stream`, `AwaitConnection`, and `ConnectEndpoint` are bidirectional-streaming RPCs. The proto comments describe heartbeat/config-update behavior for idle channels.

### Metadata

Package: `axxonsoft.bl.metadata`

Proto: `axxonsoft/bl/metadata/MetadataService.proto`

Key method:

- `PullMetadata`

`PullMetadata` is bidirectional streaming. The client sends request messages and the server returns metadata samples, heartbeat messages, or config updates.

### PTZ / Telemetry

Package: `axxonsoft.bl.ptz`

Proto: `axxonsoft/bl/ptz/Telemetry.proto`

PTZ control is session-based.

Basic flow:

1. `AcquireSessionId`
2. `KeepAlive` periodically while controlling
3. Send control commands such as `Move`, `Zoom`, `Focus`, `Iris`, `AbsoluteMove`, presets, or tours
4. `ReleaseSessionId`

### Archive And Search

Relevant packages:

- `axxonsoft.bl.archive`
- `axxonsoft.bl.vmda`

Relevant protos:

- `axxonsoft/bl/archive/ArchiveSupport.proto`
- `axxonsoft/bl/archive/ArchiveVolumeService.proto`
- `axxonsoft/bl/vmda/VMDA.proto`

Archive support covers archive traits, recording history, calendar, size, seeking, disk space, formatting, and reindexing.

VMDA search methods:

- `ExecuteQuery`
- `ExecuteQueryTyped`

`ExecuteQuery` is deprecated; prefer `ExecuteQueryTyped`.

## Practical Local Testing Order

When the local Docker container is running:

1. Confirm web: `curl http://127.0.0.1:8000/`
2. Confirm gRPC TCP port: `nc -zv 127.0.0.1 20109`
3. Generate Python stubs into `/tmp/axxon-grpc-py`.
4. Build a TLS gRPC channel with `api.ngp.root-ca.crt` or a server `Node.crt`.
5. Authenticate with `AuthenticationService.AuthenticateEx2`.
6. Call `DomainService.ListCameras` to verify real API access.
7. Call `ConfigurationService.ListUnits` for `root` to verify configuration access.

## Gotchas

- Many list/search methods are server-streaming. If the generated method returns an iterator, consume it fully.
- The PDF examples sometimes use deprecated auth methods; prefer the newer methods from the proto comments.
- `/grpc` and true gRPC are different transports. A request that works through `/grpc` does not prove a native gRPC client has TLS/certificate setup correct.
- Export requires a manually configured export agent.
- Media and metadata APIs are stream-oriented and should be treated as long-lived channels with heartbeat handling.
- Token renewal should be implemented for any long-running integration.
