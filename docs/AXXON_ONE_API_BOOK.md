# Axxon One API Book

This is the task-first API book for building integrations against Axxon One 3.0 from this repository.

It combines three sources of truth:

- The vendor PDF converted under `integration-apis-3.0/`.
- Local proto definitions under `grpc-proto-files/`.
- Live behavior verified with the local Docker lab and the external demo stand.

Use this book first when building examples, bots, plugins, or vertical integrations. Use the generated catalogs when you need the full method list, exact request type names, or the HTTP annotation map.

## Evidence Levels

Use these labels in new notes and examples:

- `verified-local`: tested against the local ARM Docker stand.
- `verified-demo`: tested against the richer demo stand.
- `documented`: found in `Integration APIs 3.0.pdf` or proto comments, but not live-verified in the current fixture.
- `fixture-needed`: the call reaches the server, but a better object id, subsystem, or configured fixture is needed.
- `unsafe-without-plan`: write, delete, movement, export, user/security, or destructive operation needing an explicit fixture and rollback plan.

The current best demo evidence is in `api-audit/demo-stand-2026-05-01.md`.

## Safety Rules

Do not write these values into docs, reports, commits, or screenshots:

- Plaintext passwords.
- Bearer tokens or direct-gRPC token metadata.
- License keys.
- Hardware serial numbers.
- Full user, role, or permission payloads unless a specific review requires them.
- Full license plate values from event examples.

Prefer counts, response shapes, detector names, access points, and redacted examples.

## Target Profiles

### Local Docker Lab

Use this when you need a repeatable local fixture:

```bash
export AXXON_HOST=127.0.0.1
export AXXON_GRPC_PORT=20109
export AXXON_HTTP_URL=http://127.0.0.1:8000
export AXXON_TLS_CN=F4E66972EC19
export AXXON_USERNAME=root
export AXXON_PASSWORD='<password>'
```

Local direct gRPC uses the repository root CA:

```bash
export AXXON_CA=arm64-docker/docs/grpc-proto-files/api.ngp.root-ca.crt
```

### Demo Stand

Use this when you need broad analytics, event, archive, layout, map, and security coverage:

```bash
export AXXON_HOST=<demo-host>
export AXXON_GRPC_PORT=20109
export AXXON_HTTP_PORT=80
export AXXON_HTTP_URL=http://<demo-host>:80
export AXXON_TLS_CN=<your-tls-cn>
export AXXON_CA=/tmp/axxon-demo-server.crt
export AXXON_USERNAME=root
export AXXON_PASSWORD='<password>'
```

The demo stand presents a different certificate chain than the local Docker lab. Capture the server certificate into `/tmp` or use the proper root CA from the stand operator. Do not commit temporary certificates unless there is an explicit reason.

## Runtime Setup

Use Python 3.12 or newer. The system `python3` may be too old on some machines, so prefer the existing probe venv when available:

```bash
/tmp/axxon-grpc-venv/bin/python --version
/tmp/axxon-grpc-venv/bin/python -m pip install -r arm64-docker/tools/requirements-api-probe.txt
```

Reusable client module:

```text
arm64-docker/tools/axxon_api_client.py
```

It handles:

- TLS and `grpc.ssl_target_name_override`.
- `AuthenticationService.AuthenticateEx2`.
- Reconnecting with token metadata for direct gRPC.
- HTTP `/grpc` Basic-to-Bearer auth.
- `/v1` requests.
- Streaming wrapper parsing for multipart and `text/event-stream`.
- Sanitizing reports.

## Transport Choices

### Direct gRPC

Use direct gRPC for durable integrations, streaming, media, metadata, export, event search, and anything that benefits from generated protobuf types.

Baseline pattern:

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_grpc()

domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
domain = client.common_stubs()["domain"]

response = domain.GetVersion(domain_pb2.GetVersionRequest(), timeout=client.config.timeout)
print(client.message_to_dict(response))
```

Rules:

- Port `20109` uses TLS.
- The first auth call is made without token metadata.
- Follow-up calls must include the returned auth metadata. `AxxonApiClient` handles this.
- Many list and search APIs are server-streaming. Always iterate the returned pages.
- Prefer the proto request types over ad hoc JSON when building long-lived integrations.

### HTTP `/grpc`

Use HTTP `/grpc` for web-adjacent integrations, quick checks, and environments where native gRPC is inconvenient.

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
response = client.http_grpc("axxonsoft.bl.domain.DomainService.GetVersion", {})
print(client.shape(response["body"]))
```

Rules:

- Authentication uses Basic auth only for the `AuthenticateEx2` call.
- Follow-up calls use `Authorization: Bearer <token_value>`.
- Server-streaming responses can arrive as JSON, multipart, or `text/event-stream`.
- A method passing through HTTP `/grpc` does not prove native gRPC TLS is configured correctly.

### HTTP `/v1`

Use `/v1` for lightweight inventory and health checks:

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_http_grpc()

response = client.http_request("GET", "/v1/domain/cameras", bearer=True)
print(client.shape(response["body"]))
```

Rules:

- `/v1` endpoints are annotated wrappers over gRPC services.
- Some streaming endpoints return `text/event-stream`.
- Some direct gRPC calls pass while the `/v1` endpoint returns a wrapper-specific error. Record those as transport parity findings.

### Legacy HTTP

Use legacy HTTP for PDF-era integrations that call camera, archive, statistics, event, macro, and media paths directly.

Current demo evidence is in `api-audit/legacy-http-sweep-latest.md`.

Verified read examples on the demo stand:

```bash
GET /hosts/
GET /statistics/webserver
GET /statistics/hardware
GET /camera/list
GET /camera/list?filter=Server/DeviceIpint.1/SourceEndpoint.video:0:0
GET /statistics/Server/DeviceIpint.1/SourceEndpoint.video:0:0
```

Important findings:

- Many legacy paths use the three-part source id without the `hosts/` prefix, for example `Server/DeviceIpint.1/SourceEndpoint.video:0:0`.
- On the demo stand, Bearer auth from `AuthenticationService.AuthenticateEx2` is required for some legacy paths where Basic auth returns HTTP 401. With Bearer, `/product/version`, `/detectors/{device}`, `/archive/list/{camera}`, `/archive/contents/intervals/...`, `/archive/statistics/...`, `/archive/calendar/...`, `/audit/{host}/...`, `/archive/events/detectors/...`, `/archive/events/alerts/...`, `/macro/list/`, and `/macro/list/?exclude_auto` passed. See `api-audit/legacy-auth-probe-demo-2026-05-03.md` and `api-audit/legacy-http-sweep-demo-bearer-2026-05-03.md`.
- `/v1/logic_service/macros` is also verified through the HTTP `/v1` sweep. Prefer these documented macro list paths; the sweep no longer includes the non-PDF `/macros` path.
- Bounded media checks are recorded in `api-audit/media-stream-smoke-latest.md`. On the demo stand, Bearer auth from `/grpc` is required. With Bearer and 1 MiB byte caps, `/stream-info/{camera}`, live snapshot, live MJPEG, live HLS, live MP4, live RTSP descriptor, `/rtsp/stat`, direct RTSP playback with `ffprobe`, composite RTSP playback with `ffprobe`, ONVIF RTP frame timestamp extraction, archive JPEG frame by timestamp, and archive MJPEG passed. The direct RTSP playback probe verifies an H.264 video stream at 1280x720; the composite RTSP probe verifies a two-camera H.264 stream at 640x360 using the PDF-style `/composite/{source}+{source}` URL with `softacceleration=1`. The ONVIF probe opens RTSP interleaved TCP, parses RTP extension profile `0xABAC`, and decodes the NTP frame timestamp without privileged packet capture. No probe stores video. Archive media timestamps should be chosen from `/archive/contents/intervals/...`; using the start of an interval can time out on this stand.
- Bounded subscription checks are recorded in `api-audit/subscription-smoke-latest.md`. A filtered gRPC `DomainNotifier.PullEvents` run against active `ET_DetectorEvent` traffic on `34.Visitors` received 5 events in a bounded 20-second window. A current child-detector run against `hosts/Server/AppDataDetector.27/EventSupplier` plus camera 1 received 20 events on 2026-05-08. The PDF WebSocket variants `/events` with `include` and `track` commands reach HTTP 101 upgrade, but the socket closes immediately across URL Basic auth, explicit Basic header, schema/no-schema, origin variants, camera include, detector include, and device track. Keep this as fixture-needed until Web server WebSocket behavior is resolved.
- External detector event injection is recorded in `api-audit/external-event-smoke-latest.md`, `api-audit/external-event-detectorex-20260508.md`, and `api-audit/external-event-fixture-search-20260508.md`. With the real `hosts/Server/DetectorEx.1` fixture on camera 1, `/v1/detectors/external:raiseOccasionalEvent` accepts `Event1` and event history finds the injected event. `/v1/detectors/external:raisePeriodicalEvent` and direct gRPC accept `TargetList` tracklets, and `MetadataService.PullMetadata` on `hosts/Server/DetectorEx.1/SourceEndpoint.vmda` returns the injected tracklet. DetectorEx fixture setup remains a prerequisite: temporary AppDataDetector and RealtimeRecognizerExternal are not valid substitutes, direct public `ChangeConfig` creation attempts did not create DetectorEx, and `Plugin.LocalMonitoring` does not expose DetectorEx.
- A 2026-05-02 demo-stand subscription wait opened `DomainNotifier.PullEvents` while a controlled SharedKV mutation ran; rollback passed, but no subscription events arrived before the 25-second deadline. See `api-audit/demo-mutating-fixture-2026-05-02.md` and `api-audit/demo-subscription-during-mutation-2026-05-02.md`.
- Keep media, WebSocket, PTZ, archive deletion, bookmarks, macro execution, export, and virtual-device switching out of generic legacy sweeps.
- Legacy HTTP bookmark mutation is recorded in `api-audit/bookmark-smoke-latest.md`. On the demo stand, Bearer auth can read `/archive/contents/bookmarks/{host}/{end}/{begin}`, but both documented create variants `/archive/contents/bookmarks/create` and `/archive/contents/bookmarks/create/` return HTTP 501. Basic auth returns HTTP 403 for bookmark reads and create. The smoke verifies that no temporary `codex-` bookmark remains when create is not implemented.
- gRPC bookmark lifecycle mutation is recorded in `api-audit/grpc-bookmark-smoke-latest.md`. `BookmarkService.CreateBookmark`, filtered `ListBookmarks`, `UpdateBookmark`, another filtered `ListBookmarks`, `DeleteBookmark`, and post-delete filtered `ListBookmarks` passed on the demo stand with a temporary `codex-grpc-bookmark-smoke-*` public, unprotected bookmark bound to the AliceBlue archive. Use this as the current runnable lifecycle example when legacy HTTP create remains HTTP 501.
- The PDF delete-video shape is recorded in `api-audit/delete-video-noop-probe-latest.md`. `DELETE /archive/contents/bookmarks/` with `begins_at`, `ends_at`, `storage_id`, and `endpoint` query parameters reached the demo server and returned HTTP 404 for a `codex-nonexistent-*` endpoint/storage pair. Treat this as dispatch evidence only; real archive deletion remains maintenance-window work against an exact, approved interval.

## Authentication

Primary API:

- `axxonsoft.bl.auth.AuthenticationService.AuthenticateEx2`

PDF source:

- `integration-apis-3.0/pages/page-355.md`

Direct gRPC flow:

1. Create a TLS channel with the right CA and target-name override.
2. Call `AuthenticateEx2` without token metadata.
3. Save only the token field names in code memory, not docs.
4. Attach returned token metadata to follow-up calls.
5. Renew tokens for long-running integrations.

HTTP `/grpc` flow:

1. `POST /grpc` with Basic auth and method `AuthenticationService.AuthenticateEx2`.
2. Extract `token_value` in memory only.
3. Call later methods with Bearer auth.

Smoke checks:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_api_probe.py --verbose
```

## Inventory And Component Mapping

Primary APIs:

- `DomainService.GetVersion`
- `DomainService.ListNodes`
- `DomainService.ListCameras`
- `DomainService.BatchGetCameras`
- `DomainService.ListArchives`
- `DomainService.ListComponents`
- `DomainService.GetCamerasByComponents`
- `ConfigurationService.ListUnits`
- `ConfigurationService.ListUnitsByAccessPoints`
- `ConfigurationService.ListTemplates`

PDF source:

- `integration-apis-3.0/pages/page-357.md`

Use this for:

- Integration bootstrap.
- Camera selection.
- Mapping detector access points back to cameras.
- Archive binding lookup.
- UI inventory pages.

Direct gRPC example:

```python
from axxon_api_client import AxxonApiClient, AxxonClientConfig

client = AxxonApiClient(AxxonClientConfig.from_env())
client.authenticate_grpc()

domain_pb2 = client.import_module("axxonsoft.bl.domain.Domain_pb2")
domain = client.common_stubs()["domain"]

for page in domain.ListCameras(
    domain_pb2.ListCamerasRequest(
        view=domain_pb2.VIEW_MODE_FULL,
        page_size=100,
    ),
    timeout=10,
):
    for camera in page.items:
        print(camera.display_id, camera.display_name, camera.access_point)
```

CLI example:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/inventory_sync.py
```

Important findings:

- The local lab has a small inventory: 2 cameras, 3 archives, 22 components.
- The demo stand has a broad inventory: 33 cameras, 14 archives, 200 components.
- `ListComponents` is the fastest way to find detector, video-streaming, telemetry, and text-source access points.
- `GetCamerasByComponents` is the useful reverse lookup from detector or VMDA access point to camera.

## Archive And Recording Availability

Primary APIs:

- `ArchiveService.GetArchiveTraits`
- `ArchiveService.GetRecordingInfo`
- `ArchiveService.GetHistory`
- `ArchiveService.GetHistory2`
- `ArchiveService.GetHistoryStream`
- `ArchiveService.GetCalendar`
- `ArchiveService.GetSize`
- `ArchiveService.GetVolumesState`
- `ArchiveService.GetDiskSpace`

PDF sources:

- `integration-apis-3.0/pages/page-414.md`
- `integration-apis-3.0/pages/page-417.md`

Use this for:

- Timeline availability.
- Retention and calendar UI.
- Archive health checks.
- Storage utilization.

Direct gRPC history example:

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

HTTP `/v1` examples:

```bash
# After HTTP auth in the client helper
GET /v1/archive/history2
GET /v1/archive/calendar
GET /v1/archive/volumes/state
GET /v1/archive/volumes/diskSpace
```

Important findings:

- Prefer the AliceBlue archive access point when testing archive service calls.
- Embedded storage appears in inventory, but not every archive call can use every embedded AP.
- The demo stand returned real history intervals and calendar days.
- On both local and demo stands, direct gRPC `GetSize` can pass while `/v1/archive/size` may return HTTP 500.
- `api-audit/archive-management-preflight-latest.md` verifies AliceBlue `GetArchiveTraits`, `GetVolumesState`, and `GetDiskSpace` without changing archive state. On the demo stand, AliceBlue reported one mounted volume and disk-space status `OK`. `api-audit/archive-management-noop-smoke-latest.md` verifies no-op `FormatVolumes`, `Reindex`, and `CancelReindex` dispatch against a `codex-nonexistent-*` volume id; real archive-volume mutations remain approval-only until isolated storage fixtures are available.

## Events And Detector History

Primary APIs:

- `EventHistoryService.ReadEvents`
- `EventHistoryService.ReadCount`
- `EventHistoryService.ReadTextEvents`
- `EventHistoryService.ReadTextCount`
- `EventHistoryService.ReadAlerts`
- `EventHistoryService.ReadLprEvents`
- `EventHistoryService.ReadBookmarks`
- `EventHistoryService.FindByPrompt`
- `EventHistoryService.FindSimilarObjects`
- `EventHistoryService.FindSimilarObjects2`
- `EventHistoryService.FindContacts`
- `EventHistoryService.FindStrangers`
- `EventHistoryService.FindStrangersByObjects`

PDF sources:

- `integration-apis-3.0/pages/page-158.md`
- `integration-apis-3.0/pages/page-159.md`
- `integration-apis-3.0/pages/page-442.md`

Use this for:

- Incident bots.
- LPR lookups.
- Detector event dashboards.
- Alarm dashboards.
- Operator audit views.
- Search workflows.

CLI examples:

```bash
# Broad recent detector/event sample
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --limit 10

# Camera-specific face detector and recognizer events
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera Face --limit 5

# Camera-specific LPR and MMR events
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'LPR + MMR' --limit 5

# Traffic analyzer events
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera 'Traffic Analyzer RR 1' --limit 5

# Object tracker line and zone events
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 24 --camera Tracker --limit 5

# Specific child AppDataDetector event producer
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py \
  --hours 2 --event-type detector \
  --subject hosts/Server/AppDataDetector.22/EventSupplier \
  --limit 8
```

Demo-verified detector examples:

| Camera | Detector/event patterns | Use in docs |
| --- | --- | --- |
| `Tracker` | `moveInZone`, `oneLine`, person and vehicle categories | Object tracker and situation detector examples |
| `Face` | `faceAppeared`, `listed_face_detected`, alert close events | Face detection and realtime recognizer examples |
| `LPR + MMR` | `plateRecognized`, `plateUnrecognized`, `listed_lpr_detected` | LPR, vehicle class/color/brand examples; redact plates |
| `Traffic Analyzer RR 1` | `WrongDirectionDetected`, `OverspeedDetected`, `StatisticsInfo` | Road-rule analytics examples |

Demo-verified `AppDataDetector` examples:

| Camera | Child detector | Subject | Parent tracker | Recent pattern |
| --- | --- | --- | --- | --- |
| `1.Tracker` | `22.Vehicle` | `hosts/Server/AppDataDetector.22/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `moveInZone` `BEGAN` / `ENDED` |
| `1.Tracker` | `11.Person` | `hosts/Server/AppDataDetector.11/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `moveInZone` |
| `1.Tracker` | `6.Line crossing Right Side Road` | `hosts/Server/AppDataDetector.6/EventSupplier` | `hosts/Server/AVDetector.1/EventSupplier` | `oneLine` |
| `10.LPR + MMR` | `14.Vehicle_OUT` | `hosts/Server/AppDataDetector.14/EventSupplier` | `hosts/Server/AVDetector.74/EventSupplier` | `oneLine` |

Important findings:

- `ReadEvents` with a camera subject is more useful than `ReadLprEvents` alone on the demo stand, because recognizer-list and detector events are visible through the general event stream.
- `ReadLprEvents` can return no rows even when general detector history contains LPR-related `DetectorEvent` rows.
- Parent `AVDetector.*` objects are not the right default event-subscription subjects for semantic tracker rules. They mainly expose tracker metadata, scene descriptions, and parent detector events.
- Child `AppDataDetector.*` objects are the configured semantic event producers for motion in area, line crossing, loitering, multiple objects, pose rules, and masking. For precise event subscriptions, scan child `AppDataDetector.*` counts first and subscribe to the active child `EventSupplier`.
- Demo study: `api-audit/appdata-detectors-demo-2026-05-02.md`. Subscription proof with `hosts/Server/AppDataDetector.22/EventSupplier` returned 8 events in 1130 ms; see `api-audit/demo-appdata-subscription-2026-05-02.md`.
- The event body may contain a typed protobuf Any body, detector group labels, origin access points, detector access points, and localized text.
- Persist event shapes and redacted field examples, not raw personal data.

## Bookmarks

Primary APIs:

- `BookmarkService.ListBookmarks`
- `BookmarkService.CreateBookmark`
- `BookmarkService.UpdateBookmark`
- `BookmarkService.DeleteBookmark`

Use this for:

- Incident annotation.
- Operator review markers.
- Export-preparation workflows.
- Short archive-range labels bound to one or more cameras.

Opt-in lifecycle smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_grpc_bookmark_smoke.py \
  --host <demo-host> --grpc-port 20109 \
  --http-url http://<demo-host>:80 --http-port 80 --tls-cn Server \
  --i-understand-this-mutates --confirm CONFIRM-grpc-bookmark-smoke \
  --report-dir arm64-docker/docs/api-audit
```

Minimal direct-gRPC object shape:

```python
from google.protobuf.timestamp_pb2 import Timestamp

service_pb2 = client.import_module("axxonsoft.bl.bookmarks.BookmarkService_pb2")
bookmark_pb2 = client.import_module("axxonsoft.bl.bookmarks.Bookmark_pb2")
primitive_pb2 = client.import_module("axxonsoft.bl.primitive.Primitives_pb2")
stub = client.stub_from_proto("axxonsoft/bl/bookmarks/BookmarkService.proto", "BookmarkService")

begin = Timestamp()
begin.FromDatetime(range_begin)
end = Timestamp()
end.FromDatetime(range_end)

bookmark = bookmark_pb2.Bookmark(
    message="codex-grpc-bookmark-smoke-example",
    range=primitive_pb2.TimeRangeTS(begin_time=begin, end_time=end),
    protection=bookmark_pb2.NOT_PROTECTED,
    access=bookmark_pb2.PUBLIC,
    categories=["codex-smoke"],
)
camera = bookmark.camera_descriptions.descriptions.add()
camera.camera_access_point = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"
camera.bindings.add(access_point="hosts/Server/MultimediaStorage.AliceBlue/MultimediaStorage")

created = stub.CreateBookmark(service_pb2.CreateBookmarkRequest(bookmark=bookmark), timeout=10)
```

Important findings:

- The demo stand passed the full gRPC lifecycle with a temporary public, unprotected `codex-grpc-bookmark-smoke-*` bookmark. See `api-audit/grpc-bookmark-smoke-latest.md`.
- Legacy HTTP bookmark reads work with Bearer auth, but the documented legacy HTTP create endpoints return HTTP 501 on the demo stand. Keep that as a PDF-era compatibility limitation; use gRPC `BookmarkService` for runnable lifecycle examples.
- Always keep bookmark mutation probes scoped by a unique `codex-*` message/category and delete by returned bookmark id in `finally` cleanup.

## Metadata And Live Analytics Streams

Primary API:

- `MetadataService.PullMetadata`

Related APIs:

- `DomainService.ListComponents`
- `DomainService.GetCamerasByComponents`
- `NgpNodeService.ListSceneDescription`
- `VMDAService.EnumerateSchemes`

Use this for:

- Proving analytics are producing live object tracklets.
- Validating tracker configuration.
- Building object stream integrations.
- Mapping VMDA endpoints to archive bindings.

CLI example:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py \
  --endpoint hosts/Server/AVDetector.1/SourceEndpoint.vmda \
  --samples 1 --idle-ms 5000
```

Active endpoint selection:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py \
  --try-candidates --samples 1 --candidate-timeout 5
```

Demo-verified result shape:

```json
{
  "endpoint": "hosts/Server/AVDetector.1/SourceEndpoint.vmda",
  "samples": 1,
  "config_updates": 1,
  "heartbeats": 0,
  "items": [
    {
      "timestamp": "20260501T175457.605000",
      "tracklet_count": 20,
      "shape": {
        "timestamp": {"type": "str", "present": true},
        "tracklets": {"type": "object", "keys": 1}
      }
    }
  ]
}
```

Important findings:

- A configured VMDA endpoint is not always active at the moment you test it.
- The original generic probe selected a VMDA endpoint that returned no samples on the demo stand.
- Active candidate selection found live samples on `AVDetector.1`, mapped to camera `Tracker`.
- Treat `PullMetadata` as a bidirectional stream: send the initial endpoint request, continue sending keepalive/count requests, and handle samples, config updates, and heartbeats.

## Search In Archive

Primary APIs:

- `EventHistoryService.FindSimilarObjects`
- `EventHistoryService.FindSimilarObjects2`
- `EventHistoryService.FindContacts`
- `EventHistoryService.FindStrangers`
- `EventHistoryService.FindStrangersByObjects`
- `EventHistoryService.ReadLprEvents`
- `VMDAService.ExecuteQueryTyped`

PDF sources:

- `integration-apis-3.0/pages/page-439.md`
- `integration-apis-3.0/pages/page-440.md`
- `integration-apis-3.0/pages/page-442.md`
- `integration-apis-3.0/pages/page-446.md`

Use this for:

- Face similarity search.
- LPR history search.
- VMDA object search.
- Stranger/familiar-face workflows.
- Prompt-like archive search where enabled.

Current evidence:

- Demo read-only sweep passed the archive-search-style event methods listed above.
- Many calls returned empty shapes because no specific image, object, or target fixture was supplied.
- `api-audit/archive-search-smoke-latest.md` verifies `ReadLprEvents`, VMDA scheme enumeration, `HeatMapService.ExecuteHeatmapQuery`, and bounded `HeatMapService.BuildHeatmap` image generation with a PDF-style VMDA zone query. It also verifies legacy HTTP async `/search/auto/...`, `/search/face/...`, `/search/vmda/...`, `/search/stranger/...`, and `/search/heatmap/...` start/result/delete lifecycles with Bearer auth, plus image-body face matching and `faceAppearanceRate` using camera `9.Face` / `hosts/Server/AVDetector.93/EventSupplier`. No plate values, raw images, or raw heatmap payloads are stored; image checks record only byte counts and hashes.

## Layouts, Maps, Groups, And Macros

Primary APIs:

- `GroupManager.ListGroups`
- `LayoutManager.ListLayouts`
- `MapService.ListMaps`
- `MapService.BatchGetMaps`
- `MapService.GetMapsByComponent`
- `MapService.ListMapProviders`
- `LogicService.ListMacros`
- `LogicService.ListMacrosV2`
- `LogicService.GetConfig`

Use this for:

- Operator workspace export.
- Dashboard navigation.
- Map-aware integrations.
- Macro launch and automation UIs.

Demo findings:

- `GroupManager.ListGroups` returned 5 groups.
- `LayoutManager.ListLayouts` returned 20 layouts and one slideshow.
- `MapService.ListMaps` returned 5 maps.
- `MapService.ListMapProviders` returned 2 providers.
- `LogicService.ListMacros` returned 16 macros.
- `api-audit/config-detail-sweep-latest.md` verifies read-only macro config, templates, map list/batch/image shape, detector inventory shapes, and user/role counts.

Verified macro mutation smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_macro_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-macro-smoke
```

The smoke creates a disabled common `codex-temp-*` macro with no conditions or rules, changes its name, optionally launches only that disabled empty macro with `LaunchMacro`, reads it with `BatchGetMacros`, removes it, and verifies `not_found_macros`. Latest demo-stand proof is stored in `api-audit/macro-smoke-latest.md`. Do not generalize this to real macros with rules or side effects.

Verified temporary virtual-camera arm-state smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_armstate_smoke.py \
  --host <demo-host> --grpc-port 20109 \
  --http-url http://<demo-host>:80 --http-port 80 --tls-cn Server \
  --report-dir arm64-docker/docs/api-audit \
  --arm-timeout-seconds 2 \
  --i-understand-this-mutates \
  --confirm CONFIRM-armstate-smoke
```

The smoke creates a temporary virtual `DeviceIpint` camera through `ConfigurationService.ChangeConfig`, calls `LogicService.ChangeArmState` for that temporary camera with proto enum value `CS_Arm` and a short timeout, then removes the camera. Latest demo-stand proof is stored in `api-audit/armstate-smoke-latest.md`. Do not run this against real cameras from generic sweeps.

Verified map mutation smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_map_marker_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-map-marker-smoke
```

The smoke creates a temporary `codex-*` raster map with a tiny PNG and marker, changes the map, reads image and marker data, updates and removes the marker, then removes the map. Demo-stand proof from 2026-05-03 is stored in `api-audit/map-marker-smoke-demo-2026-05-03.md`.

Verified read-only layout and map-arrangement smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_layout_read_smoke.py
```

The read smoke reads `LayoutManager.ListLayouts`, `LayoutManager.BatchGetLayouts`, and `LayoutImagesManager.ListLayoutImages` without mutation. Demo-stand proof from 2026-05-06 is stored in `api-audit/layout-read-smoke-latest.md`: 20 layouts, 1 slideshow, 11 layouts with map-arrangement data, and 3 `MAP_VIEW_MODE_MAP_AND_LAYOUT` layouts.

Verified layout mutation smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_layout_mutation_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-layout-mutation-smoke
```

The mutation smoke creates a temporary `codex-layout-*` layout, updates its map arrangement through `LayoutManager.Update`, calls `LayoutsOnView` for that temporary layout, removes it, verifies the removed layout is not found, and checks that the current layout id did not change. Demo-stand proof is stored in `api-audit/layout-mutation-smoke-latest.md`.

Keep macro execution out of generic sweeps unless a fixture and rollback plan exists.

## Export

Primary APIs:

- `ExportService.ListSessions`
- `ExportService.StartSession`
- `ExportService.GetSessionState`
- `ExportService.DownloadFile`
- `ExportService.StopSession`
- `ExportService.DestroySession`
- `DomainSettingsService.GetExportSettings`
- `DomainSettingsService.UpdateExportSettings`

Use this for:

- Operator-driven archive export.
- Evidence package generation.
- Installer readiness checks for export capability.

Read-only preflight:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_export_preflight.py \
  --host <demo-host> --grpc-port 20109 \
  --http-url http://<demo-host>:80 --http-port 80 --tls-cn Server \
  --report-dir arm64-docker/docs/api-audit
```

Controlled gRPC export lifecycle:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_export_smoke.py \
  --host <demo-host> --grpc-port 20109 \
  --http-url http://<demo-host>:80 --http-port 80 --tls-cn Server \
  --max-download-bytes 262144 --max-file-size 1048576 \
  --i-understand-this-mutates --confirm CONFIRM-export-smoke
```

Controlled legacy HTTP export lifecycle:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_export_smoke.py \
  --host <demo-host> --grpc-port 20109 \
  --http-url http://<demo-host>:80 --http-port 80 --tls-cn Server \
  --max-download-bytes 262144 --max-file-size 1048576 \
  --i-understand-this-mutates --confirm CONFIRM-http-export-smoke
```

Demo findings:

- `api-audit/export-preflight-latest.md` verifies `ExportService.ListSessions` and `DomainSettingsService.GetExportSettings`.
- The demo stand returned zero pre-existing export sessions, a readable export settings ETag, a valid current archive interval, and `hosts/Server/MMExportAgent.0` in the configuration tree.
- `api-audit/export-smoke-latest.md` verifies `ExportService.StartSession`, `GetSessionState`, bounded `DownloadFile`, `StopSession`, and `DestroySession` with temporary `codex-*` sessions. The snapshot export completed, downloaded a bounded JPEG result, and was destroyed; the live export reached `S_RUNNING`, then stop/destroy cleanup passed.
- `api-audit/http-export-smoke-latest.md` verifies the legacy HTTP export flow from PDF pages 176-180: `POST /export/archive/...` returned HTTP 202, `GET /export/{id}/status` reached state `2`, bounded `GET /export/{id}/file` returned JPEG bytes, and `DELETE /export/{id}` returned HTTP 204.
- `api-audit/export-settings-update-20260511.md` verifies an ETag-guarded no-op `DomainSettingsService.UpdateExportSettings` call with `mask.paths=["options.max_file_size_bytes"]`. Real export default changes still need captured original settings and a restore step.

## Security, Permissions, And User Context

Primary APIs:

- `SecurityService.ListRoles`
- `SecurityService.ListUsers`
- `SecurityService.ListConfig`
- `SecurityService.GetRestrictedConfig`
- `SecurityService.ListGlobalPermissions`
- `SecurityService.ListObjectPermissions`
- `SecurityService.ListUserGlobalPermissions`
- `SecurityService.GetPolicies`
- `SecurityService.ListGroupsPermissions`
- `SecurityService.ListObjectsPermissionsInfo`
- `SecurityService.ListMacrosPermissionsPaged`
- `AuthenticationService.GetSessionInfo`

Use this for:

- Permission-aware integrations.
- Installer readiness checks.
- Current-user capability checks.

Rules:

- Store counts and response shapes, not full security payloads.
- Do not store password policy details unless needed for a specific review.
- Treat password, login, user, role, and permission mutations as unsafe without a rollback plan.

Demo findings:

- Security read APIs are broadly available.
- Demo stand has 4 roles and 35 users in sanitized read-sweep counts.
- `api-audit/security-admin-preflight-latest.md` verifies users/roles, policies, global/group/object/macro permissions, and restricted current-user config without storing full security payloads. The demo stand reports 4 roles, 35 users, 0 LDAP servers, 1 password policy, 0 IP filters, 0 trusted IPs, 36 object-permission info rows, 1 group-permission info row, and 16 macro-permission rows.
- `GetLDAPSynchronizationState` returns `UNAVAILABLE: Can't get connection channel!` on the demo stand when no LDAP servers are configured. Treat LDAP search/sync examples as fixture-needed until an LDAP test fixture exists.
- `api-audit/security-mutation-smoke-latest.md` verifies a controlled `SecurityService.ChangeConfig` lifecycle with a temporary UUID-indexed `codex-*` role and user: create role, create user, set generated in-memory password, assign user to role, verify assignment, remove assignment, remove user, remove role, and restore counts. The first attempted run showed that role/user `index` fields must be UUID-shaped; keep the `codex-*` marker in role names, logins, and comments rather than in the index.
- The same smoke now verifies `SetGlobalPermissions`, `SetObjectPermissions`, `SetGroupsPermissions`, and `SetMacrosPermissions` against the temporary role only. It also verifies no-op `ChangeConfig` writes for current password policy, IP filters, and trusted IP list, plus temporary LDAP directory add/edit/remove. Password/login changes for real users, LDAP sync/search against a real LDAP server, and TFA operations still require isolated fixtures plus rollback.
- The configuration detail sweep stores only security counts and response shapes, not full user or permission payloads.
- LDAP search/sync warnings are fixture or subsystem availability findings, not transport failures.

## External Client And Component Fixtures

Some PDF surfaces are not server-only APIs:

- Client HTTP API for layouts and videowalls needs an Axxon Client HTTP endpoint, usually `127.0.0.1:8888`. Fixture requirements are documented in `api-audit/client-http-fixtures.md`; the focused `api-audit/external-client-preflight-latest.md` check found TCP connection refused on both `127.0.0.1:8888` and `<demo-host>:8888`.
- The embeddable video component needs a browser-renderable host page and Web server/component auth behavior. Fixture requirements are documented in `api-audit/embeddable-video-component-fixtures.md`; the focused preflight now verifies the PDF entrypoint `/embedded.html` on the demo Web server with HTTP 200, a Video component title, `embedded.js`, and component/embed/video signatures.

Keep Client HTTP API as `fixture-needed` until a real Axxon Client HTTP API target exists. Do not infer it from server-side layout/map/media API coverage.

## Fixture Discovery And Mutation Playbooks

Current fixture discovery is in `api-audit/fixture-discovery-latest.md`.

Demo findings:

- Found map fixtures: 5 maps.
- Found detector fixtures: 35 detector-like components and 12 VMDA endpoints.
- Found on the demo stand: export agent `MMExportAgent.0`, maps, detectors, RTSP playback reachability on ports `554` and `8554`, and the embeddable video component at `/embedded.html`.
- Missing on the demo stand: PTZ telemetry, control panels, water-level devices, and Client HTTP API. Device-template lifecycle is covered with a temporary template and temporary virtual camera even though no persistent template fixture is present.
- `api-audit/external-client-preflight-latest.md` is the focused external-client preflight. It found no reachable Client HTTP API on port `8888`; it verifies the embeddable component host at `/embedded.html`.
- `api-audit/ptz-preflight-latest.md` is the focused PTZ/Tag&Track preflight. It found zero telemetry/PTZ access points and zero control panels, so telemetry position/preset/operation/tour reads and Tag&Track tracker reads are skipped until a non-production PTZ fixture exists.
- `api-audit/config-model-study-latest.md` maps the real configuration object tree: 95 units, 14 host-level factories, and exact factory/property shapes for cameras, archives, `AVDetector`, `AppDataDetector`, `RealtimeRecognizerExternal`, and `Plugin`. `BatchGetFactories` returns `NOT_FOUND` for `DetectorEx` and `ExternalDetector`; the Plugin factory exposes only `LocalMonitoring` as `module_name`.

Mutation playbooks live under `api-audit/mutation-playbooks/` and are linked from `api-audit/mutating-api-fixtures.md`. They define fixture requirements, preflight snapshots, mutation request shape, verification, rollback, post-rollback verification, risk level, and approval requirement. The skeleton runner is `arm64-docker/tools/axxon_mutation_playbook_runner.py`; it lists and validates playbooks. The controlled configuration mutation smoke is `arm64-docker/tools/axxon_config_mutation_smoke.py`.

## Health, License, And Operations

Primary APIs:

- `grpc.health.v1.Health.Check`
- `StatisticService.GetStatistics`
- `LicenseService.GetGlobalRestrictions`
- `LicenseService.GetDomainLicenseKeyInfo`
- `LicenseService.GetNodeRestrictions`
- `LicenseService.IsPossibleToLaunch`
- `TimeZoneManager.GetTimeZone`
- `TimeZoneManager.GetNTP`

Use this for:

- Integration readiness checks.
- License-gated feature checks.
- Node status dashboards.
- Deployment diagnostics.

Rules:

- Do not persist license keys, hardware serials, or host identifiers.
- Prefer status enums, counts, and response shapes in docs.

## Configuration And Mutations

Primary APIs:

- `ConfigurationService.ChangeConfig`
- `ConfigurationService.ChangeTemplates`
- `ConfigurationService.SetTemplateAssignments`
- `ConfigurationService.BatchGetTemplates`
- `ConfigurationService.ListUnits`
- `ConfigurationService.ListUnitsByAccessPoints`
- `SharedKVStorageService.Commit`
- `SharedKVStorageService.BatchGetRecords`
- `SharedKVStorageService.GetRecordsStream`
- `SharedKVStorageService.Remove`

PDF sources:

- `integration-apis-3.0/pages/page-370.md`
- `integration-apis-3.0/pages/page-380.md`
- `integration-apis-3.0/pages/page-384.md`
- `integration-apis-3.0/pages/page-482.md`
- `integration-apis-3.0/pages/page-483.md`
- `integration-apis-3.0/pages/page-484.md`
- `integration-apis-3.0/pages/page-485.md`
- `integration-apis-3.0/pages/page-487.md`

Use this for:

- Device and detector configuration.
- Controlled safe write/read tests.
- Future camera, archive, user, layout, macro, and detector-mask edits.

Rules:

- Do not run configuration mutations on the demo stand without explicit user approval.
- Every mutation needs a fixture, backup/read-before-write, rollback operation, and verification command.
- Use SharedKV first when proving write capability because it is isolated and reversible.
- For `ConfigurationService.ChangeConfig`, add objects by sending the parent unit UID in `added[].uid` and the new child object in `added[].units[]`.
- For detector and AppDataDetector creation, include the nested PDF-style `input` property. Example: `input=Video -> camera_ref -> streaming_id` for `AVDetector`; `input=TargetList -> camera_ref -> streaming_id=<AVDetector.vmda> -> detector=MoveInZone` for child `AppDataDetector`.
- Read exact writable detector parameters with `ListUnitsByAccessPoints` on the object `EventSupplier` or source endpoint. The host tree can show stripped detector descriptors, but exact AP reads on child `AppDataDetector.*` event suppliers expose writable parameter descriptors such as `enabled`, `measurementsCount`, size bounds, speed bounds, and time-alarm settings.
- For AppDataDetector studies, keep the config tree and the camera-view detector inventory separate: the demo stand has 16 `AppDataDetector` units in `ConfigurationService.ListUnits`, but only 15 child `AppDataDetector.*` subjects in the full-camera detector inventory. The extra config-tree unit is `hosts/Server/AppDataDetector.4/EventSupplier`.
- Device templates are not changed through `ChangeConfig`; use `ChangeTemplates` to create/edit/delete template bodies, `BatchGetTemplates` to obtain and refresh the `etag`, and `SetTemplateAssignments` to link or unlink template ids on an isolated unit.

Safe write smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_mutating_fixture_sweep.py
```

Controlled config mutation smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_config_mutation_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-config-mutation-smoke
```

Controlled device-template smoke:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_device_template_smoke.py \
  --i-understand-this-mutates \
  --confirm CONFIRM-device-template-smoke
```

Template create example through HTTP `/grpc`:

```json
{
  "method": "axxonsoft.bl.config.ConfigurationService.ChangeTemplates",
  "data": {
    "created": [
      {
        "id": "codex-<uuid>",
        "name": "codex-template-geodata",
        "unit": {
          "uid": "hosts/Server/DeviceIpint.<temp>",
          "type": "DeviceIpint",
          "properties": [
            {"id": "geoLocationLatitude", "value_double": 35.0},
            {"id": "geoLocationLongitude", "value_double": 45.0}
          ],
          "units": [],
          "opaque_params": [{"id": "color", "value_string": "#00bcd4", "properties": []}]
        }
      }
    ]
  }
}
```

Template assign/unassign example:

```json
{
  "method": "axxonsoft.bl.config.ConfigurationService.SetTemplateAssignments",
  "data": {
    "items": [
      {"unit_id": "hosts/Server/DeviceIpint.<temp>", "template_ids": ["codex-<uuid>"]}
    ]
  }
}
```

To unassign, send the same `unit_id` with an empty `template_ids` array. The demo stand can briefly return current-state contention immediately after assignment; retrying the unassign after re-authentication succeeded in the controlled smoke.

Demo-stand proof:

- On 2026-05-02, the controlled SharedKV fixture was run against the demo stand after explicit approval.
- The fixture wrote one temporary record, read it through `BatchGetRecords`, streamed it through `GetRecordsStream`, removed it, and verified rollback.
- Sanitized reports: `api-audit/demo-mutating-fixture-2026-05-02.md` and `api-audit/demo-mutating-fixture-2026-05-02.json`.
- A concurrent 25-second `DomainNotifier.PullEvents` wait produced no events, so event subscriptions still need a detector/event-specific active fixture.
- On 2026-05-02, the controlled `ChangeConfig` smoke created/changed/removed a temporary archive, virtual camera, three `AVDetector` instances, and one `AppDataDetector.MoveInZone`.
- The temporary AppDataDetector produced detector events before rollback. The smoke also changed the generated child `VisualElement.*` polygon mask with `value_simple_polygon` and read back 4 points. Sanitized reports: `api-audit/config-mutation-smoke-demo-2026-05-02.md` and `api-audit/config-mutation-smoke-demo-2026-05-02.json`.
- On 2026-05-07, the latest detector-parameter group changed and read back a temporary AVDetector main parameter (`enabled`, using `value_bool`) and changed/read back a detector visual `polyline` through a temporary AppDataDetector fallback. The fallback is expected on this stand because the temporary `MotionDetection` AVDetector did not materialize a `VisualElement` child. Use a longer timeout such as `--timeout 60` for this group because detector fanout cleanup can exceed the default 10 seconds.
- On 2026-05-02, the controlled device-template smoke created an isolated virtual camera, created a `codex-*` geodata template, batch-read its `etag`, edited it with that `etag`, assigned and unassigned it, verified assignment readback through `ListUnits.assigned_templates`, deleted the template, verified `BatchGetTemplates.not_found`, and removed the camera. Sanitized reports: `api-audit/device-template-smoke-demo-2026-05-02.md` and `api-audit/device-template-smoke-demo-2026-05-02.json`.

Configuration object model findings:

- `DomainService.ListCameras(view=FULL)` is required to see all detector relationships; stripped inventory misses child subdetectors.
- Demo counts: 33 cameras, 14 archives, 200 components, 95 config units, 30 parent `AVDetector` objects, and 15 child `AppDataDetector` objects.
- Host-level factories include `DeviceIpint`, `MultimediaStorage`, `AVDetector`, `AppDataDetector`, `OfflineAnalytics`, `GlobalTracker`, `MMExportAgent`, `GSMModule`, `EMailModule`, `ACFA`, `RealtimeRecognizerExternal`, `Plugin`, and `Script`.
- For this demo, temporary virtual cameras must use `vendor=Virtual`; the PDF example value `vendor=axxonsoft` returned a server `fanout request has failed` error.
- The PDF `Get tracks using GO` section is `MetadataService.PullMetadata` receiving `MetadataSample_Tracklets`. `api-audit/demo-metadata-tracklets-2026-05-02.md` verifies 3 samples with 21 tracklets per sample from `hosts/Server/AVDetector.1/SourceEndpoint.vmda`.

Important local finding:

- SharedKV writes work with an empty prefix.
- Non-empty prefixes returned conflict in local testing.
- Deletion can leave key-only tombstones in some read paths, so verify by list absence and missing value.

## Error And Warning Patterns

Common warning classes:

- Empty or unresolved access point.
- Valid service but missing subsystem.
- Valid service but unconfigured feature.
- Wrapper-specific HTTP 500 while direct gRPC passes.
- Permission-denied on object image or map operations without a valid id.
- Unimplemented method in this build.
- LDAP or notification subsystem unavailable.

How to record them:

- If transport, auth, and method dispatch work, prefer `fixture-needed` over `fail`.
- If direct gRPC passes and HTTP wrapper fails, record a transport parity note.
- If a method changes configuration, do not test it in generic sweeps.

## Recommended Build Order

1. Implement target profile and TLS/auth handling.
2. Load inventory with `DomainService`.
3. Resolve cameras, archives, detectors, and VMDA endpoints.
4. Add event search.
5. Add archive history and calendar.
6. Add metadata streams only after endpoint mapping is correct.
7. Add HTTP `/grpc` or `/v1` parity where the integration runtime requires it.
8. Add security/permission reads for installer checks.
9. Add mutating operations only with rollback.

## PDF Coverage Gap Backlog

This book does not yet turn every `Integration APIs 3.0.pdf` topic into a verified runnable example. The table below is the current gap list after comparing the book with the PDF table of contents.

The machine-trackable version is [`api-audit/pdf-gap-coverage-matrix.md`](api-audit/pdf-gap-coverage-matrix.md).

| PDF area | PDF pages | Current evidence | Missing book work |
| --- | --- | --- | --- |
| Legacy Server HTTP API: unique id, hosts, server usage, product version, webserver statistics | 38-44 | Bearer-mode legacy sweep verifies hosts, product version, webserver statistics, and hardware statistics | Add only version-shape notes as needed |
| Legacy HTTP camera stream info, live HLS/RTSP/HTTP, snapshots, frame timestamps, composite stream | 60-77 | Bounded Bearer media smoke verifies stream-info, snapshot, live MJPEG, HLS, MP4, RTSP descriptor, RTSP statistics, direct RTSP playback, composite RTSP playback, ONVIF RTP frame timestamp extraction, archive JPEG frame, and archive MJPEG | Covered by `media-stream-smoke-latest.md` |
| Legacy HTTP PTZ camera control | 80-87 | PTZ preflight found no telemetry/PTZ access points or control panels on the demo stand; movement is covered by a rollback playbook | Add only when a non-production PTZ fixture is present and approved |
| Legacy HTTP archive contents, archive stats, archive stream, frame review, bookmarks, delete-video endpoint | 88-128 | Bearer-mode legacy sweep verifies archive list, contents intervals, frame registration time, depth, capacity, calendar reads; media smoke verifies archive JPEG frame and archive MJPEG from a resolved interval timestamp; bookmark smoke verifies bookmark reads and that documented create endpoints return HTTP 501 on the demo stand; gRPC BookmarkService create/list/update/delete is verified as the runnable bookmark lifecycle fallback; delete-video no-op probe verifies the documented DELETE shape against a `codex-nonexistent-*` endpoint/storage pair | Covered by `legacy-http-sweep-latest.md`, `media-stream-smoke-latest.md`, `bookmark-smoke-latest.md`, `grpc-bookmark-smoke-latest.md`, and `delete-video-noop-probe-latest.md`; real archive deletion remains maintenance-window work |
| Legacy HTTP archive search: face, LP, VMDA, stranger/familiar face, heatmap, calendar | 129-157 | Archive search smoke verifies direct gRPC LPR/VMDA/ExecuteHeatmapQuery, bounded BuildHeatmap image generation, legacy HTTP async auto/face/VMDA/stranger/heatmap start/result/delete lifecycle, image-body face matching, and `faceAppearanceRate` | Covered by `archive-search-smoke-latest.md`; keep image fixtures temporary and record only size/hash |
| Virtual trigger and external event injection | 168 | With real `DetectorEx.1`, `RaiseOccasionalEvent(Event1)` is verified through event history and `RaisePeriodicalEvent(TargetList)` is verified through DetectorEx VMDA metadata; false fixture paths are documented | Covered by `external-event-detectorex-20260508.md`; DetectorEx setup/import remains separate fixture work |
| Legacy HTTP audit/system log and alarms endpoints | 170-173 | Bearer-mode legacy sweep verifies `/audit/{host}/...`, detector event reads, and PDF `/archive/events/alerts/...` alarm reads | Add only additional filter examples as needed |
| HTTP export workflow | 176-180 | Legacy HTTP `POST /export/archive/...`, status polling, bounded file download, and `DELETE /export/{id}` cleanup are verified with a one-frame JPEG export | Covered by `http-export-smoke-latest.md`; keep byte caps and cleanup mandatory |
| HTTP macros and virtual IP device state switch | 181-183 | Macro list/config reads, gRPC macro create/change/launch/remove, and temporary virtual-camera `LogicService.ChangeArmState` are verified with rollback | Covered by `macro-smoke-latest.md` and `armstate-smoke-latest.md`; do not switch real device state from generic sweeps |
| HTTP WebSocket camera-event subscription | 184-188 | gRPC `PullEvents` receives detector events; WebSocket `/events` returns HTTP 101 and then closes immediately across auth/schema/command variants | Resolve Web server WebSocket behavior or test through a Web server fixture with active `/events` streaming |
| Client HTTP API for layouts and videowalls | 189-205 | Fixture requirements documented; server-side layout lists are verified; focused external-client preflight shows `127.0.0.1:8888` and `<demo-host>:8888` refuse TCP connections | Requires Axxon Client HTTP API target, usually port `8888`; add only when that client fixture is available |
| gRPC macro configuration and macro mutations | 213-217, 390-395 | `ListMacros`, `ListMacrosV2`, `BatchGetMacros`, `GetConfig`, `ChangeMacros` create/change/remove, and `LaunchMacro` against a disabled empty macro are verified | Covered by `macro-smoke-latest.md`; do not launch real macros without explicit side-effect review |
| gRPC export start/download/stop/destroy | 218-222 | `MMExportAgent.0` is present; `StartSession`, `GetSessionState`, bounded `DownloadFile`, `StopSession`, and `DestroySession` are verified with temporary `codex-*` sessions; ETag-guarded no-op `UpdateExportSettings` is verified separately | Covered by `export-smoke-latest.md` and `export-settings-update-20260511.md`; real default-setting changes still need restore |
| gRPC archive creation, volume changes, cloud archive examples, reindex, remove/link operations | 420-439 | Archive read APIs are verified; `ChangeConfig` smoke created/renamed/removed a temporary archive; archive-management preflight verified AliceBlue traits, one mounted volume, and disk-space status OK; no-op `FormatVolumes`, `Reindex`, and `CancelReindex` dispatch against a `codex-nonexistent-*` volume id is verified | Real format/reindex/cancel-reindex/cloud/link operations remain approval-only until isolated storage fixtures or explicit maintenance-window approval |
| gRPC users, roles, permissions, security policy, IP filtering, LDAP directory mutations | 449-463 | Security preflight verifies read-side users/roles, policies, global/group/object/macro permissions, and restricted config; temporary user/role create/password/assign/remove, temp-role permission updates, no-op policy/IP-filter writes, and temporary LDAP directory add/edit/remove are verified with rollback | Covered by `security-mutation-smoke-latest.md`; LDAP sync/search against a real LDAP server still needs a dedicated fixture; TFA mutations are tracked as their own fixture-needed row |
| gRPC TFA mutations (`EnableGoogleAuth`/`DisableGoogleAuth`) | 449-463 | Proto surface exists in `SecurityService.proto:1000-1002` with `EEnableTFAResult`/`EDisableTFAResult` enums; no live TFA mutation evidence recorded | Requires a Google Authenticator/OTP fixture and an isolated test user before enable/disable can be exercised with rollback |
| gRPC heatmap | 463-470 | `HeatMapService.ExecuteHeatmapQuery` returned 3 streamed pages and bounded `BuildHeatmap` returned a 64x48 image summary through `hosts/Server/HeatMapBuilder.0/HeatMapBuilder` | Covered by `archive-search-smoke-latest.md`; keep larger time windows bounded because a 24-hour image build exceeded the 30-second live timeout |
| gRPC control panels and water level | 470-474 | PTZ preflight found no control panels; fixture discovery found no water-level fixture on the demo stand | Add only after a configured device exists |
| gRPC event subscriptions | 479-482 | Filtered `DomainNotifier.PullEvents` against active detector traffic received events in bounded runs, including 20 events from `hosts/Server/AppDataDetector.27/EventSupplier` on 2026-05-08 | Extend filtered examples to other event types as needed; keep duration and event limits |
| gRPC device templates | 482-487 | `ListTemplates`, `ChangeTemplates`, `BatchGetTemplates`, and `SetTemplateAssignments` create/edit/assign/unassign/delete are verified with rollback | Add narrative examples only for additional template body variants |
| gRPC Tag&Track Pro PTZ mode | 487-488 | Tag&Track tracker reads require a telemetry/PTZ access point; PTZ preflight found none | Add only after a Tag&Track/PTZ fixture is present and approved |
| gRPC detector parameter management and `Get tracks using GO` | 488-503 | Detector inventory/events, metadata streams, controlled detector create/change/remove, AVDetector main-parameter edit/readback, detector visual-parameter edit/readback, AppDataDetector visual-element mask change, and `PullMetadata` tracklets are verified | Covered by `config-mutation-smoke-latest.md`; keep broader detector changes behind rollback |
| gRPC interactive map create/change/remove, markers, map image, layout display control | 505-519 | `ChangeMaps`, `GetMapImage`, `GetMarkers`, `UpdateMarkers`, layout list, layout batch-get, layout images, map-arrangement reads, temporary layout `Update`, `LayoutsOnView`, and rollback are verified | Covered by map/marker, layout-read, and layout-mutation smokes |
| Direct gRPC environment walkthrough from the PDF | 519-524 | Covered by this book and `client-sdk-usage.md` | Keep examples aligned with `AuthenticateEx2` and current client helper |
| Embeddable video component for Web server | 525-528 | Focused external-client preflight verifies the demo Web server's PDF entrypoint `/embedded.html` with HTTP 200, a Video component title, `embedded.js`, and component/embed/video signatures | Covered by `external-client-preflight-latest.md` and `fixture-discovery-latest.md`; browser-rendered screenshot checks remain optional and approval-gated |

Priority for the next API-book pass:

1. Add safe read-only examples first: legacy HTTP hosts/product/statistics, camera snapshot, archive contents/calendar, macro config reads, template list/batch-get, map image with a valid id.
2. Add stream examples with byte/time limits: live media, archive media, WebSocket events, gRPC event subscriptions.
3. Add fixture-heavy analytics: heatmap, VMDA archive query, face similarity, redacted LPR predicate.
4. Add mutation chapters last: bookmarks, external events, export start/destroy, macros, templates, users/roles, archive creation/removal, detector parameters, maps/markers, PTZ movement.

## Verification Commands

Comprehensive probe:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_api_probe.py --verbose
```

Direct gRPC read sweep:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_readonly_sweep.py --timeout 10
```

HTTP `/grpc` sweep:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_grpc_sweep.py --timeout 10
```

HTTP `/v1` sweep:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_http_v1_sweep.py --timeout 10
```

Event search:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_event_search.py --hours 24 --limit 10
```

Metadata stream:

```bash
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py --samples 1
```

## Source Map

Use this map when expanding the book:

| Topic | PDF / repo source |
| --- | --- |
| HTTP API overview | `integration-apis-3.0/sections/01-http-api.md` |
| gRPC API overview | `integration-apis-3.0/sections/02-grpc-api.md` |
| Auth | `integration-apis-3.0/pages/page-355.md` |
| Legacy server HTTP API | `integration-apis-3.0/pages/page-038.md`, `page-041.md`, `page-043.md`, `page-044.md` |
| Legacy HTTP camera media and snapshots | `integration-apis-3.0/pages/page-060.md`, `page-063.md`, `page-064.md`, `page-065.md`, `page-066.md`, `page-067.md`, `page-068.md`, `page-077.md` |
| Legacy HTTP PTZ | `integration-apis-3.0/pages/page-080.md`, `page-081.md`, `page-083.md`, `page-084.md`, `page-085.md`, `page-086.md`, `page-087.md` |
| Domain camera list | `integration-apis-3.0/pages/page-357.md` |
| Configuration examples | `integration-apis-3.0/pages/page-370.md` |
| Device creation and detector config | `integration-apis-3.0/pages/page-380.md`, `page-384.md` |
| Legacy HTTP archive media, bookmarks, and statistics | `integration-apis-3.0/pages/page-088.md`, `page-096.md`, `page-114.md`, `page-118.md`, `page-122.md`, `page-124.md`, `page-126.md`, `page-127.md`, `page-128.md` |
| HTTP detector events | `integration-apis-3.0/pages/page-158.md`, `page-159.md` |
| HTTP virtual trigger, audit, alarms, export, macros, WebSocket | `integration-apis-3.0/pages/page-168.md`, `page-170.md`, `page-173.md`, `page-176.md`, `page-181.md`, `page-184.md` |
| Client HTTP layouts and videowalls | `integration-apis-3.0/pages/page-189.md`, `page-198.md`, `page-199.md`, `page-200.md`, `page-201.md`, `page-203.md`, `page-204.md`, `page-205.md` |
| Archive gRPC | `integration-apis-3.0/pages/page-399.md`, `page-401.md`, `page-414.md`, `page-417.md` |
| Archive search | `integration-apis-3.0/pages/page-439.md`, `page-440.md`, `page-442.md`, `page-446.md` |
| gRPC users, roles, permissions, security policy, LDAP | `integration-apis-3.0/pages/page-449.md`, `page-450.md`, `page-451.md`, `page-452.md`, `page-453.md`, `page-454.md`, `page-455.md`, `page-456.md`, `page-457.md`, `page-458.md`, `page-459.md`, `page-460.md`, `page-461.md`, `page-462.md`, `page-463.md` |
| gRPC heatmap, control panels, water level, events/subscriptions | `integration-apis-3.0/pages/page-463.md`, `page-470.md`, `page-474.md`, `page-475.md`, `page-476.md`, `page-477.md`, `page-478.md`, `page-479.md`, `page-480.md`, `page-481.md`, `page-482.md` |
| gRPC device templates, Tag&Track, detectors, interactive maps | `integration-apis-3.0/pages/page-482.md`, `page-487.md`, `page-488.md`, `page-489.md`, `page-500.md`, `page-501.md`, `page-503.md`, `page-505.md`, `page-508.md`, `page-509.md`, `page-510.md`, `page-511.md`, `page-517.md`, `page-519.md` |
| Direct gRPC environment walkthrough | `integration-apis-3.0/pages/page-519.md`, `page-520.md`, `page-523.md` |
| Embeddable video component | `integration-apis-3.0/pages/page-525.md`, `page-527.md`, `page-528.md` |
| Full proto RPC catalog | `api-audit/grpc-api-catalog.md` |
| HTTP endpoint catalog | `api-audit/http-endpoints-catalog.md` |
| Client helper examples | `api-audit/client-sdk-usage.md` |
| Current playbooks | `api-audit/integration-playbooks.md` |
| Demo stand evidence | `api-audit/demo-stand-2026-05-01.md` |
