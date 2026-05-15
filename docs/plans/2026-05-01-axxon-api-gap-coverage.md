# Axxon API Gap Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close every `Integration APIs 3.0.pdf` coverage gap now listed in `AXXON_ONE_API_BOOK.md`, with live verification where safe and explicit fixture/rollback plans where live execution is risky. After the current `19 verified / 0 partial / 6 fixture-needed` coverage backlog is finished or explicitly dispositioned, transition into a public Axxon One MCP server project that exposes the structured API corpus, verified examples, live read-only inspection, and controlled configuration/integration tools for LLM clients.

**Architecture:** Treat the API book gap backlog as the control plane. Add small, focused probe tools that reuse `AxxonApiClient`, write sanitized reports under `arm64-docker/docs/api-audit`, and update the book only after each API family is verified or explicitly marked fixture-needed. Split work into safe read-only probes, bounded stream probes, fixture-heavy analytics probes, client-only probes, and mutation playbooks. The MCP phase must consume this verified corpus as structured data rather than rediscovering API behavior from chat history.

**Tech Stack:** Python 3.12, `grpcio`, generated Axxon protobuf stubs, `urllib`, optional `websocket-client` only if needed, `unittest`, Markdown/JSON audit reports.

**Post-Coverage Target:** A public repository, likely named `axxon-one-mcp` or similar, containing a sanitized MCP server, structured Axxon One API documentation, verified examples, live-inspection tools, safety policies, tests, and publishing instructions for common LLM clients.

---

## Scope

Cover the gap backlog in:

- `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- `arm64-docker/docs/integration-apis-3.0/toc.md`
- `arm64-docker/docs/api-audit/demo-stand-2026-05-01.md`

Do not store:

- Plaintext passwords.
- Bearer tokens or gRPC token metadata.
- License keys.
- Hardware serial numbers.
- Full plate values.
- Full user/role/security payloads.

Use the demo stand for broad read coverage, and the local Docker stand for destructive or rollback-sensitive experiments unless the user explicitly approves demo mutations.

## Execution Rules

- Run from `/Users/jerrygergov/Documents/GitHub/axxonnext.docker`.
- Use `/tmp/axxon-grpc-venv/bin/python`.
- Use `AXXON_PASSWORD='<password>'` in docs and commands.
- Write raw exploratory reports to `/tmp` first.
- Copy only sanitized summaries into repo docs.
- For each task: write or update a test, run it, implement the minimal tool/docs change, run the targeted test, then update docs.
- Commit after each completed task if the user wants commits; otherwise leave a clean, reviewable diff.

## Target Profiles

Local Docker:

```bash
export AXXON_HOST=127.0.0.1
export AXXON_GRPC_PORT=20109
export AXXON_HTTP_PORT=8000
export AXXON_HTTP_URL=http://127.0.0.1:8000
export AXXON_TLS_CN=F4E66972EC19
export AXXON_CA=arm64-docker/docs/grpc-proto-files/api.ngp.root-ca.crt
export AXXON_USERNAME=root
export AXXON_PASSWORD='<password>'
```

Demo stand:

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

---

## Phase 1: Make The Gap Backlog Machine-Trackable

### Task 1: Create PDF Gap Coverage Matrix

**Files:**
- Create: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`
- Create: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.md`
- Create: `arm64-docker/tools/tests/test_pdf_gap_coverage.py`
- Modify: `arm64-docker/docs/api-audit/README.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`

**Step 1: Write the failing test**

Add a test that loads the JSON matrix and requires every row to include `pdf_area`, `pages`, `status`, `risk`, `tooling`, `report`, and `next_step`.

```python
from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/api-audit/pdf-gap-coverage-matrix.json"


class PdfGapCoverageTests(unittest.TestCase):
    def test_matrix_rows_have_required_fields(self) -> None:
        rows = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 24)
        required = {"pdf_area", "pages", "status", "risk", "tooling", "report", "next_step"}
        for row in rows:
            with self.subTest(area=row.get("pdf_area")):
                self.assertTrue(required.issubset(row))
                self.assertIn(row["status"], {"verified", "partial", "fixture-needed", "not-verified", "unsafe"})
                self.assertIn(row["risk"], {"safe-read", "bounded-stream", "fixture-heavy", "mutation", "external-client"})

    def test_book_links_matrix(self) -> None:
        book = (ROOT / "docs/AXXON_ONE_API_BOOK.md").read_text(encoding="utf-8")
        self.assertIn("pdf-gap-coverage-matrix.md", book)
```

**Step 2: Run the test to verify it fails**

```bash
/tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_pdf_gap_coverage.py -v
```

Expected: FAIL because the matrix does not exist.

**Step 3: Add the JSON and Markdown matrix**

Seed the matrix directly from the `PDF Coverage Gap Backlog` table in `AXXON_ONE_API_BOOK.md`.

Status mapping:

- `verified`: live proof exists and runnable example is in the book.
- `partial`: some related APIs are verified, but this exact PDF surface is not complete.
- `fixture-needed`: method dispatch works, but a configured object/input is missing.
- `not-verified`: no live smoke yet.
- `unsafe`: changes server state and needs rollback.

Risk mapping:

- `safe-read`: GET/read-only RPC.
- `bounded-stream`: stream, WebSocket, media, or subscription with byte/time limits.
- `fixture-heavy`: needs image, known plate predicate, known object, map id, PTZ device, export agent, etc.
- `mutation`: write/delete/control operation.
- `external-client`: needs Axxon Client or embeddable component fixture.

**Step 4: Link the matrix from docs**

Add `pdf-gap-coverage-matrix.md` to:

- `arm64-docker/docs/api-audit/README.md`
- `arm64-docker/docs/AXXON_ONE_API_BOOK.md`

**Step 5: Run the test**

```bash
/tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_pdf_gap_coverage.py -v
```

Expected: PASS.

---

## Phase 2: Safe Legacy HTTP Read Coverage

### Task 2: Add HTTP Binary/Raw Response Support

**Files:**
- Modify: `arm64-docker/tools/axxon_api_client.py`
- Create: `arm64-docker/tools/tests/test_http_client_raw_response.py`

**Step 1: Write the failing test**

Test that `http_request(raw_body=True)` returns bytes metadata without trying to JSON-parse snapshots, MP4, HLS playlists, JPEGs, or binary downloads.

```python
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class HttpClientRawResponseTests(unittest.TestCase):
    def test_http_request_accepts_raw_body_flag(self) -> None:
        config = AxxonClientConfig.from_env(repo_root=Path("arm64-docker"))
        config = AxxonClientConfig(
            host=config.host,
            grpc_port=config.grpc_port,
            http_port=config.http_port,
            http_url="http://example.invalid",
            username="root",
            password="pw",
            tls_cn=config.tls_cn,
            ca=config.ca,
            proto_dir=config.proto_dir,
            stubs_dir=config.stubs_dir,
            timeout=config.timeout,
        )
        client = AxxonApiClient(config)
        self.assertIn("raw_body", AxxonApiClient.http_request.__code__.co_varnames)
```

**Step 2: Run the test to verify it fails**

```bash
/tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_http_client_raw_response.py -v
```

Expected: FAIL because `raw_body` is not implemented.

**Step 3: Implement minimal raw response handling**

Add parameters to `AxxonApiClient.http_request`:

- `raw_body: bool = False`
- `max_bytes: int | None = None`

Behavior:

- If `max_bytes` is set, read only that many bytes from the response.
- If `raw_body=True`, return `body` as `{"raw_bytes": len(raw), "sha256": "<hex>", "text_prefix": "..."}` for textual content and never include full bytes.
- Keep existing JSON/multipart/event-stream parsing as default.
- Apply identical behavior in HTTP error handling.

**Step 4: Run focused tests**

```bash
/tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_http_client_raw_response.py -v
/tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_probe_readonly_client_refactor.py -v
```

Expected: PASS.

### Task 3: Implement Legacy HTTP Read Sweep

**Files:**
- Create: `arm64-docker/tools/axxon_legacy_http_sweep.py`
- Create: `arm64-docker/tools/tests/test_legacy_http_sweep.py`
- Create output: `arm64-docker/docs/api-audit/legacy-http-sweep-latest.md`
- Create output: `arm64-docker/docs/api-audit/legacy-http-sweep-latest.json`
- Modify: `arm64-docker/docs/api-audit/README.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing tests**

Require the tool to define safe endpoint groups and to avoid mutation paths by default.

```python
from __future__ import annotations

import importlib
import unittest


class LegacyHttpSweepTests(unittest.TestCase):
    def test_sweep_has_safe_endpoint_groups(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        groups = module.safe_endpoint_groups()
        names = {group["name"] for group in groups}
        self.assertIn("server", names)
        self.assertIn("camera_inventory", names)
        self.assertIn("archive_read", names)
        self.assertIn("events_read", names)
        self.assertNotIn("delete_video", names)

    def test_sweep_uses_reusable_client(self) -> None:
        module = importlib.import_module("axxon_legacy_http_sweep")
        self.assertTrue(hasattr(module, "LegacyHttpSweep"))
```

Run:

```bash
PYTHONPATH=arm64-docker/tools /tmp/axxon-grpc-venv/bin/python -m unittest arm64-docker/tools/tests/test_legacy_http_sweep.py -v
```

Expected: FAIL because the module does not exist.

**Step 2: Implement safe endpoint groups**

Include only read-only legacy HTTP endpoints first:

- Server:
  - `/hosts/`
  - `/product/version`
  - `/statistics/webserver`
  - `/statistics/hardware`
- Camera:
  - `/camera/list`
  - `/camera/list?filter=<camera_ap>`
  - `/detectors/<host/device>`
  - `/statistics/<camera_ap>`
- Archive:
  - `/archive/list/<camera_ap>`
  - `/archive/contents/intervals/<camera_ap>/past/future`
  - `/archive/statistics/depth/<camera_ap>`
  - `/archive/statistics/capacity/<camera_ap>/past/future`
  - `/archive/calendar/<camera_ap>/<begin>/<end>`
- Events:
  - `/archive/events/detectors/<end>/<begin>`
  - `/archive/events/detectors/<camera_ap>/<end>/<begin>`
  - audit/system-log and alarms endpoints from pages 170-173 if paths are clear from converted pages.
- Macros:
  - list macros only.

Do not include:

- Bookmark create/edit/delete.
- Delete video.
- Macro execution.
- Virtual device state switch.
- Virtual trigger.

**Step 3: Add fixtures**

Build fixtures from `client.load_inventory()`:

- `camera_ap`: first enabled camera, or demo preferred camera if names match.
- `camera_device`: first two components from camera AP, e.g. `Server/DeviceIpint.1`.
- `archive_ap`: `client.archive_access_point()`.
- `begin`, `end`: `client.archive_time_range_legacy(hours=24)`.

**Step 4: Run against demo into `/tmp`**

```bash
AXXON_HOST=<demo-host> \
AXXON_GRPC_PORT=20109 \
AXXON_HTTP_PORT=80 \
AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_TLS_CN=<your-tls-cn> \
AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root \
AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_legacy_http_sweep.py \
  --report-dir /tmp/axxon-demo-api-audit \
  --timeout 10
```

Expected:

- PASS/WARN report with no FAIL for implemented read-only endpoints unless endpoint paths need adjustment.
- No raw passwords, tokens, or full plates in report.

**Step 5: Sanitize and commit latest docs only if useful**

If output is stable and sanitized, copy the Markdown and JSON latest reports into:

- `arm64-docker/docs/api-audit/legacy-http-sweep-latest.md`
- `arm64-docker/docs/api-audit/legacy-http-sweep-latest.json`

Update:

- `AXXON_ONE_API_BOOK.md`
- `api-audit/README.md`
- `pdf-gap-coverage-matrix.json`

---

## Phase 3: Bounded Stream And Subscription Coverage

### Task 4: Implement Media And Snapshot Smoke Tool

**Files:**
- Create: `arm64-docker/tools/axxon_media_stream_smoke.py`
- Create: `arm64-docker/tools/tests/test_media_stream_smoke.py`
- Create output: `arm64-docker/docs/api-audit/media-stream-smoke-latest.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing test**

Require the tool to expose named checks and byte limits.

```python
from __future__ import annotations

import importlib
import unittest


class MediaStreamSmokeTests(unittest.TestCase):
    def test_checks_are_bounded(self) -> None:
        module = importlib.import_module("axxon_media_stream_smoke")
        checks = module.media_checks()
        self.assertTrue(all("max_bytes" in item for item in checks))
        self.assertTrue(all(item["max_bytes"] <= 1048576 for item in checks))
```

**Step 2: Implement read-only bounded checks**

Use `AxxonApiClient.http_request(raw_body=True, max_bytes=...)`.

Checks:

- Camera snapshot from page 77.
- Camera live stream info from pages 61-62.
- HLS live playlist or first response chunk from pages 63-64.
- HTTP live media first chunk from page 66, if endpoint responds.
- Archive stream info/first chunk from pages 118-121.
- Frame by timestamp and frame registration time from pages 122-123 where fixture exists.

Rules:

- Default `--max-bytes 1048576`.
- Default `--timeout 5`.
- Never persist signed media URLs containing tokens.
- Store only status, content type, size, and hash.

**Step 3: Run against demo**

```bash
AXXON_HOST=<demo-host> AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_GRPC_PORT=20109 AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_media_stream_smoke.py \
  --report-dir /tmp/axxon-demo-api-audit \
  --timeout 5 \
  --max-bytes 1048576
```

Expected:

- Snapshot/media checks are PASS or WARN with clear fixture/path reason.
- No full bytes or signed URLs are stored.

### Task 5: Implement WebSocket And gRPC Subscription Smoke Tool

**Files:**
- Create: `arm64-docker/tools/axxon_subscription_smoke.py`
- Create: `arm64-docker/tools/tests/test_subscription_smoke.py`
- Create output: `arm64-docker/docs/api-audit/subscription-smoke-latest.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing test**

Require the tool to expose subscription modes without opening network connections during import.

```python
from __future__ import annotations

import importlib
import unittest


class SubscriptionSmokeTests(unittest.TestCase):
    def test_modes_are_declared(self) -> None:
        module = importlib.import_module("axxon_subscription_smoke")
        self.assertIn("websocket_camera_events", module.subscription_modes())
        self.assertIn("grpc_event_subscription", module.subscription_modes())
```

**Step 2: Implement modes**

Modes:

- `websocket_camera_events`: pages 184-188, subscribe then unsubscribe, read at most N events or seconds.
- `grpc_event_subscription`: pages 479-482, test LPR, counter, state, and POS-style event subscriptions only if fixtures exist.

Rules:

- Default `--duration 10`.
- Default `--max-events 5`.
- Always unsubscribe/close in `finally`.
- If the WebSocket package is absent, report `SKIP` with install guidance instead of failing.

**Step 3: Run against demo**

```bash
AXXON_HOST=<demo-host> AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_GRPC_PORT=20109 AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_subscription_smoke.py \
  --report-dir /tmp/axxon-demo-api-audit \
  --duration 10 \
  --max-events 5
```

Expected:

- PASS if events arrive.
- WARN/SKIP if no event source, no dependency, or endpoint path needs adjustment.
- No long-running sessions left open.

---

## Phase 4: Fixture-Heavy Search And Analytics

### Task 6: Improve Active Metadata Endpoint Selection

**Files:**
- Modify: `arm64-docker/tools/examples/metadata_tracker_stream.py`
- Modify: `arm64-docker/tools/axxon_api_probe.py`
- Create: `arm64-docker/tools/tests/test_metadata_endpoint_selection.py`
- Modify: `arm64-docker/docs/api-audit/demo-stand-2026-05-01.md`

**Step 1: Write the failing test**

Test that endpoint selection can prefer a successful sample rather than the first VMDA candidate.

```python
from __future__ import annotations

import importlib
import unittest


class MetadataEndpointSelectionTests(unittest.TestCase):
    def test_example_exports_candidate_selection(self) -> None:
        module = importlib.import_module("examples.metadata_tracker_stream")
        self.assertTrue(callable(getattr(module, "choose_vmda_endpoint", None)))
        self.assertTrue(callable(getattr(module, "try_pull_metadata_sample", None)))
```

**Step 2: Implement active sampling**

Add optional flags:

- `--try-candidates`
- `--candidate-timeout`
- `--preferred-camera`

Behavior:

- Resolve all VMDA endpoints.
- Map them with `DomainService.GetCamerasByComponents`.
- Try each candidate with a short timeout.
- Pick first endpoint returning a sample.
- Report no-sample endpoints as fixture-needed, not failure.

**Step 3: Run against demo**

```bash
AXXON_HOST=<demo-host> AXXON_GRPC_PORT=20109 AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/examples/metadata_tracker_stream.py \
  --try-candidates \
  --samples 1 \
  --candidate-timeout 5
```

Expected: Finds `hosts/Server/AVDetector.1/SourceEndpoint.vmda` or another live endpoint and returns at least one sample.

### Task 7: Implement Archive Search Smoke Tool

**Files:**
- Create: `arm64-docker/tools/axxon_archive_search_smoke.py`
- Create: `arm64-docker/tools/tests/test_archive_search_smoke.py`
- Create output: `arm64-docker/docs/api-audit/archive-search-smoke-latest.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing test**

Require search modes for every PDF archive-search family.

```python
from __future__ import annotations

import importlib
import unittest


class ArchiveSearchSmokeTests(unittest.TestCase):
    def test_search_modes_cover_pdf_families(self) -> None:
        module = importlib.import_module("axxon_archive_search_smoke")
        modes = set(module.search_modes())
        self.assertTrue({"lpr", "face", "vmda", "heatmap", "build_heatmap", "stranger"}.issubset(modes))
```

**Step 2: Implement fixture-driven modes**

Modes:

- `lpr`: use `EventHistoryService.ReadLprEvents` and a redacted predicate argument.
- `face`: require `--face-image` path; report SKIP if not supplied.
- `vmda`: use known camera/time/VMDA endpoint; prefer `VMDAService.ExecuteQueryTyped`.
- `heatmap`: require VMDA endpoint and time window for `ExecuteHeatmapQuery`.
- `build_heatmap`: require VMDA endpoint, HeatMapBuilder access point, short time window, and bounded image/mask dimensions.
- `stranger`: require face/image fixture or known object fixture.

Rules:

- No full plate values in reports.
- Store image size/hash only, not image bytes.
- Default to SKIP when required fixtures are absent.

**Step 3: Run safe modes against demo**

```bash
AXXON_HOST=<demo-host> AXXON_GRPC_PORT=20109 AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_archive_search_smoke.py \
  --report-dir /tmp/axxon-demo-api-audit \
  --mode lpr \
  --camera 'LPR + MMR' \
  --predicate '<redacted-pattern>'
```

Expected: PASS/WARN with no raw plate values in output.

---

## Phase 5: Read-Only Configuration, Templates, Maps, Users, And Macros

### Task 8: Add Read-Only Configuration Detail Sweep

**Files:**
- Create: `arm64-docker/tools/axxon_config_detail_sweep.py`
- Create: `arm64-docker/tools/tests/test_config_detail_sweep.py`
- Create output: `arm64-docker/docs/api-audit/config-detail-sweep-latest.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing test**

Require safe read groups:

```python
from __future__ import annotations

import importlib
import unittest


class ConfigDetailSweepTests(unittest.TestCase):
    def test_read_groups_cover_pdf_config_sections(self) -> None:
        module = importlib.import_module("axxon_config_detail_sweep")
        groups = set(module.read_groups())
        self.assertTrue({"templates", "macros", "users", "maps", "detectors"}.issubset(groups))
```

**Step 2: Implement read-only groups**

Groups:

- `templates`: `ListTemplates`, batch-get where available.
- `macros`: `ListMacros`, `ListMacrosV2`, `BatchGetMacros`, macro config reads.
- `users`: `ListRoles`, `ListUsers`, permissions, restricted config, LDAP list/search only where safe.
- `maps`: `ListMaps`, `BatchGetMaps`, `ListMapProviders`, `GetMapImage` only with valid map id and permission.
- `detectors`: detector parameter list/read shapes from pages 488-499.

Rules:

- Store shape/count only for users/security.
- Do not execute creates, edits, assigns, launches, deletes, or policy changes.

**Step 3: Run against demo**

```bash
AXXON_HOST=<demo-host> AXXON_GRPC_PORT=20109 AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_config_detail_sweep.py \
  --report-dir /tmp/axxon-demo-api-audit \
  --timeout 10
```

Expected:

- PASS for available read groups.
- WARN for missing fixture ids or permissions.
- No full user/permission payloads.

---

## Phase 6: External Client And Component-Only Surfaces

### Task 9: Add Client HTTP And Embeddable Component Fixture Notes

**Files:**
- Create: `arm64-docker/docs/api-audit/client-http-fixtures.md`
- Create: `arm64-docker/docs/api-audit/embeddable-video-component-fixtures.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Document fixture requirements**

For Client HTTP API pages 189-205:

- Need Axxon Client HTTP API target, usually `127.0.0.1:8888`.
- Need active display id.
- Need layout id.
- Need permission to switch layouts, add/remove cameras, switch archive/search/immersion modes.

For embeddable video component pages 525-528:

- Need a browser-renderable host page.
- Need Web server access.
- Need camera AP and auth behavior documented.
- Use in-app browser or Playwright only after the fixture exists.

**Step 2: Add optional smoke commands**

Document only, do not implement live tool until the fixture exists:

```bash
nc -zv 127.0.0.1 8888
curl -s 'http://127.0.0.1:8888/GetDisplays'
```

Expected:

- If no client fixture exists, status remains `external-client` / `fixture-needed`.

---

## Phase 7: PTZ, Control Panel, Water Level, And Device Fixtures

### Task 10: Add Fixture Discovery Tool

**Files:**
- Create: `arm64-docker/tools/axxon_fixture_discovery.py`
- Create: `arm64-docker/tools/tests/test_fixture_discovery.py`
- Create output: `arm64-docker/docs/api-audit/fixture-discovery-latest.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Write the failing test**

```python
from __future__ import annotations

import importlib
import unittest


class FixtureDiscoveryTests(unittest.TestCase):
    def test_discovery_declares_fixture_types(self) -> None:
        module = importlib.import_module("axxon_fixture_discovery")
        fixture_types = set(module.fixture_types())
        self.assertTrue({"ptz", "control_panel", "water_level", "export_agent", "map", "template"}.issubset(fixture_types))
```

**Step 2: Implement discovery**

Use inventory and read APIs to find:

- PTZ telemetry access points.
- Control panel access points.
- Water-level devices.
- Export agents.
- Valid map ids and image ids.
- Device templates.
- Detector parameter roots.

**Step 3: Run against demo**

```bash
AXXON_HOST=<demo-host> AXXON_GRPC_PORT=20109 AXXON_HTTP_URL=http://<demo-host>:80 \
AXXON_TLS_CN=<your-tls-cn> AXXON_CA=/tmp/axxon-demo-server.crt \
AXXON_USERNAME=root AXXON_PASSWORD='<password>' \
/tmp/axxon-grpc-venv/bin/python arm64-docker/tools/axxon_fixture_discovery.py \
  --report-dir /tmp/axxon-demo-api-audit
```

Expected:

- Report identifies which PDF areas can be live-tested next.
- Missing fixture areas are explicit, not guessed.

---

## Phase 8: Mutation Playbooks With Rollback

### Task 11: Add Mutation Playbooks For Each Unsafe Gap

**Files:**
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/bookmarks.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/external-events.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/export.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/macros.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/device-templates.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/users-roles-security.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/archive-management.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/detector-parameters.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/maps-markers.md`
- Create: `arm64-docker/docs/api-audit/mutation-playbooks/ptz-control.md`
- Modify: `arm64-docker/docs/api-audit/mutating-api-fixtures.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: Create a standard playbook template**

Every playbook must include:

- PDF pages.
- APIs involved.
- Fixture requirements.
- Preflight read snapshot.
- Mutation request.
- Verification command.
- Rollback request.
- Post-rollback verification.
- Risk level.
- Approval requirement.

**Step 2: Fill playbooks without executing mutations**

Unsafe groups:

- Bookmarks create/edit/delete and delete video.
- External event injection / virtual trigger.
- Export start/stop/download/destroy.
- Macro create/change/launch/remove.
- Device template create/edit/assign/delete.
- User/role/security policy/IP filter/LDAP changes.
- Archive create/volume/link/reindex/remove.
- Detector parameter changes.
- Interactive map create/change/remove/markers/display control.
- PTZ movement/session actions.

**Step 3: Add a review checklist**

Add a checklist to `mutating-api-fixtures.md`:

```text
[ ] User approved the exact target stand.
[ ] Preflight snapshot saved.
[ ] Rollback request generated before mutation.
[ ] Mutation scoped to a test object.
[ ] Verification command identified.
[ ] Cleanup command identified.
[ ] No secrets in report.
```

Expected:

- No mutating commands are run in this task.
- The book can mark these areas as planned with rollback, not simply missing.

### Task 12: Add Opt-In Mutation Runner Skeleton

**Files:**
- Create: `arm64-docker/tools/axxon_mutation_playbook_runner.py`
- Create: `arm64-docker/tools/tests/test_mutation_playbook_runner.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

import importlib
import unittest


class MutationPlaybookRunnerTests(unittest.TestCase):
    def test_runner_requires_explicit_approval_flag(self) -> None:
        module = importlib.import_module("axxon_mutation_playbook_runner")
        self.assertIn("--i-understand-this-mutates", module.build_parser().format_help())
```

**Step 2: Implement skeleton only**

The runner should:

- List available playbooks.
- Validate required fixture env vars.
- Refuse to run unless `--i-understand-this-mutates` and a playbook-specific confirmation string are provided.
- Support `--dry-run` by default.

Do not implement actual mutation calls in this task.

---

## Phase 9: Documentation Integration And Final Verification

### Task 13: Update API Book Chapters From Reports

**Files:**
- Modify: `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- Modify: `arm64-docker/docs/api-audit/README.md`
- Modify: `arm64-docker/docs/api-audit/integration-playbooks.md`
- Modify: `arm64-docker/docs/AXXON_ONE_API_EXPERT_CONTEXT.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`

**Step 1: For each new report, update the matrix**

Statuses:

- PASS and example documented: `verified`.
- PASS but not fully documented: `partial`.
- WARN due to fixture: `fixture-needed`.
- Unsafe playbook only: `unsafe`.

**Step 2: Update the book**

Add or expand chapters:

- Legacy HTTP server/camera/archive.
- Media and stream smoke.
- WebSocket and event subscriptions.
- Archive search and analytics fixtures.
- Config detail reads.
- Client HTTP and embeddable component fixture notes.
- Mutation playbooks.

**Step 3: Add read order**

Add any new docs to `AXXON_ONE_API_EXPERT_CONTEXT.md`.

### Task 14: Run Full Verification

**Files:**
- Read all changed files.

**Commands:**

```bash
/tmp/axxon-grpc-venv/bin/python -m unittest discover arm64-docker/tools/tests -v
git diff --check
rg -n "AXXON_PASSWORD=[^'<]|password[=:][^'<]|eyJ|Bearer [A-Za-z0-9_-]{20,}|\\b[A-Z]{2}[0-9]{5}\\b" arm64-docker/docs arm64-docker/tools
LC_ALL=C rg -n "[^ -~\\t]" arm64-docker/docs/AXXON_ONE_API_BOOK.md arm64-docker/docs/api-audit
```

Expected:

- Unit tests pass.
- No whitespace errors.
- No known secret patterns.
- Non-ASCII check is either empty or limited to pre-existing converted PDF docs not touched by this work.

### Task 15: Final Coverage Report

**Files:**
- Create or update: `arm64-docker/docs/api-audit/pdf-gap-coverage-summary.md`

**Content:**

- Matrix summary counts by status.
- Matrix summary counts by risk.
- List of verified PDF areas.
- List of fixture-needed areas.
- List of unsafe areas awaiting approval.
- Commands run and reports generated.

**Final expected state:**

- Every PDF gap is either verified with a runnable example, linked to a report, marked fixture-needed with exact fixture requirements, or represented by a rollback-safe mutation playbook.
- Future sessions can continue from docs, not chat history.

---

## Post-Coverage Program: Axxon One MCP Server

Start this program only after the active coverage backlog is closed or deliberately dispositioned:

- Current target state from this continuation: `verified=15`, `partial=3`, `fixture-needed=6`, `unsafe=0`.
- Current disposition: `verified=19`, `partial=0`, `fixture-needed=6`, `unsafe=0`. Embeddable video component closed on 2026-05-12 after the external-client preflight was extended to probe `/embedded.html`. TFA mutations (`EnableGoogleAuth`/`DisableGoogleAuth`) split into their own fixture-needed row on 2026-05-12 because the existing security row never had live TFA evidence. The six remaining items (PTZ control, HTTP WebSocket `/events`, Client HTTP API, control panels & water level, Tag&Track Pro PTZ, TFA mutations) are blocked by missing fixtures and are recorded in `mcp-corpus/fixtures.json`.
- Partial rows must either become verified or remain partial with an explicit reason, tool/report link, and next fixture/approval requirement.
- Fixture-needed rows must name the missing fixture exactly, such as PTZ telemetry, Axxon Client HTTP API, control panel, water-level device, Tag&Track/PTZ fixture, WebSocket-capable `/events` server behavior, or embeddable component host.

The MCP goal is not only to expose documentation. It should become a controlled Axxon One operating layer for LLM clients: structured docs, verified examples, live server inspection, event send/receive helpers, integration scaffolding, and gated configuration mutations.

### MCP Phase 0: Freeze And Normalize The API Corpus

**Purpose:** turn the verified docs into machine-readable data that an MCP server can serve reliably.

**Inputs:**
- `arm64-docker/docs/AXXON_ONE_API_BOOK.md`
- `arm64-docker/docs/api-audit/pdf-gap-coverage-matrix.json`
- `arm64-docker/docs/api-audit/grpc-api-catalog.csv`
- `arm64-docker/docs/api-audit/http-endpoints-catalog.md`
- `arm64-docker/docs/api-audit/integration-playbooks.md`
- `arm64-docker/docs/api-audit/mutation-playbooks/*.md`
- Sanitized reports under `arm64-docker/docs/api-audit/*latest.{md,json}`

**Outputs:**
- `api_methods.json`: gRPC methods, request/response names, streaming mode, safety class, HTTP annotations, live status.
- `http_endpoints.json`: legacy HTTP and `/v1` endpoints with auth mode, body shape, response shape, and verified status.
- `task_recipes.json`: task-first workflows such as add camera, export video, subscribe detector events, inject external event, create detector, create archive, configure macro.
- `fixtures.json`: required fixture types, discovery tools, known demo/local fixture IDs, and missing fixture notes.
- `safety_policies.json`: read-only, bounded-stream, mutation, approval, rollback, and redaction rules.
- `known_behaviors.json`: product quirks, unsupported PDF-era endpoints, demo-stand differences, and verified false paths.

**Current output:** `arm64-docker/tools/generate_mcp_corpus.py` generates these files under `arm64-docker/docs/api-audit/mcp-corpus/` from the verified audit sources. The current corpus snapshot contains 361 gRPC methods, 221 annotated HTTP endpoints, 13 task recipe sections, 10 mutation playbooks, 6 fixture-needed rows, safety policies, and known behavior notes.

### MCP Phase 1: Docs-Only MCP MVP

**Purpose:** let LLM clients query the Axxon One API book and verified examples without connecting to a live Axxon server.

**MCP resources:**
- API book sections.
- gRPC catalog.
- HTTP endpoint catalog.
- PDF coverage matrix.
- Mutation playbooks.
- Fixture notes.
- Verified reports.

**MCP tools:**
- `search_api_docs(query)`: task-oriented search over structured docs.
- `get_api_method(fqmn)`: exact gRPC method details, safety class, live status, examples.
- `get_http_endpoint(path_or_topic)`: legacy HTTP or `/v1` endpoint details.
- `get_verified_example(topic)`: runnable command or code sample with report links.
- `explain_task_recipe(task)`: recommended workflow for a natural-language task, without executing it.
- `list_remaining_gaps()`: current partial and fixture-needed rows.

**Success criteria:**
- No Axxon credentials or live server target are required.
- Every answer links back to the source doc/report.
- The server refuses to invent unsupported endpoints; unknowns are returned as gaps.

**Current output:** `arm64-docker/tools/axxon_mcp_docs.py` is the docs-only query layer over `mcp-corpus/`, and `arm64-docker/tools/axxon_mcp_server.py` wraps it in a FastMCP server. It implements the Phase 1 tool semantics: API doc search, exact gRPC method lookup, HTTP endpoint lookup, verified-example lookup, task recipe explanation, remaining-gap listing, and corpus/gap resources. It requires no Axxon credentials or live server target. Unknown method and endpoint queries return `status: gap` so the MCP server has a tested non-invention path.

### MCP Phase 2: Read-Only Live Inspection

**Purpose:** allow an LLM to understand a connected Axxon One instance safely.

**Runtime base:**
- Reuse `AxxonApiClient` for direct gRPC, HTTP `/grpc`, `/v1`, and legacy HTTP.
- Keep credentials in memory only.
- Redact tokens, passwords, license keys, serials, full plate values, and raw security payloads.

**MCP tools:**
- `connect_axxon_profile(profile)`: load a named local/demo/customer profile from environment or external config, never from repo secrets.
- `list_cameras()`
- `list_archives()`
- `list_config_units(filter)`
- `list_detectors(camera_or_host)`
- `list_appdata_detectors(camera_or_host)`
- `find_event_suppliers(camera_or_detector)`
- `find_metadata_endpoints(camera_or_detector)`
- `get_archive_intervals(camera, hours)`
- `discover_fixtures()`
- `preflight_task(task)`: check whether required fixtures exist before a tool proposes a mutation.
- `subscribe_events_bounded(filter, timeout, limit)`: bounded event subscription only.

**Success criteria:**
- All live tools are read-only or bounded-stream.
- Event and media tools have time/count/byte caps.
- Fixture discovery can explain why PTZ, Client HTTP, WebSocket, DetectorEx, or archive operations are available or blocked.

**Current output:** `arm64-docker/tools/axxon_mcp_live.py` is the first read-only live-inspection layer. It loads the environment-backed Axxon profile through `AxxonApiClient`, returns redacted profile summaries, lists cameras/archives/config units/detectors/AppDataDetector objects, finds event suppliers and metadata endpoints, performs fixture preflight for natural-language tasks, and exposes bounded `get_archive_intervals` (wrapping `ArchiveService.GetHistory2`) and `subscribe_events_bounded` (wrapping `DomainNotifier.PullEvents` with hard 30 s/500 event caps). `arm64-docker/tools/axxon_mcp_server.py --enable-live` exposes these tools only when explicitly enabled; docs-only mode still needs no credentials. The demo smoke in `arm64-docker/docs/api-audit/mcp-live-smoke-latest.md` verified read-only counts on 2026-05-12: 33 cameras, 14 archives, 35 detector entries, 18 AppDataDetector entries, 51 event suppliers, and 15 metadata endpoints.

### MCP Phase 3: Controlled Operator Tools

**Purpose:** allow natural-language configuration and integration tasks while enforcing typed plans, approvals, and rollback.

**Rule:** the LLM may describe intent, but the MCP server owns API shape validation, safety checks, dry-run output, confirmation requirements, execution, rollback, and audit logs.

**Tool pattern:**
- `plan_*`: read-only, returns a typed mutation plan and rollback plan.
- `apply_*`: executes only a plan ID generated by the server, with explicit confirmation.
- `verify_*`: proves the intended state and rollback state.

**Initial operator tools should use workflows already proven in this repo:**
- Temporary virtual camera create/change/remove.
- Temporary archive create/change/remove.
- Temporary `AVDetector` and `AppDataDetector` create/change/remove.
- Detector parameter edit/readback with rollback.
- Device template create/edit/assign/unassign/delete.
- Macro create/change/optional isolated launch/remove.
- Map/marker create/change/update/remove.
- Layout create/update/LayoutsOnView/remove.
- Export start/status/download/stop/destroy.
- External event injection through an existing real `DetectorEx.*` fixture.
- Temporary security user/role create/assign/remove.

**Keep behind separate approval or fixture gates:**
- PTZ movement and Tag&Track mode changes.
- Archive format/reindex/cancel-reindex/delete/link/cloud operations.
- Permission/policy/IP-filter/TFA/LDAP mutations. Temp-role permission updates, no-op policy/IP-filter writes, and temporary LDAP directory add/edit/remove are verified; real-user, TFA, and real LDAP sync/search remain gated.
- Video deletion.
- Real camera changes that are not temporary or rollback-scoped.
- Any operation on a production customer server.

**Current output:** `arm64-docker/tools/axxon_mcp_operator.py` implements the first operator harness with the `temp_camera` workflow as the safety reference. Plan, apply, verify, rollback, and audit-log mechanics are covered by `tools/tests/test_axxon_mcp_operator.py` (6 tests). The MCP server exposes `list_operator_workflows`, `plan_operator_workflow`, `apply_operator_plan`, `verify_operator_plan`, `rollback_operator_plan`, and an `axxon://operator/audit-log` resource only when started with `--enable-operator`; even then, `apply` and `rollback` are refused unless `AXXON_OPERATOR_APPROVE=1`. The `AxxonOperatorClient` adapter routes `ChangeConfig`/`ListUnits` through the verified HTTP `/grpc` path used by `axxon_config_mutation_smoke.py`. Live execution against the demo stand has not been run yet; that step is gated on user approval per Stop Conditions.

### MCP Phase 4: Integration And Plugin Generation

**Purpose:** use the MCP corpus and live inspection to generate correct third-party integrations.

**Generator outputs:**
- Python examples using direct gRPC.
- HTTP `/grpc` examples.
- Legacy HTTP examples where still required.
- Webhook/event bridge skeletons.
- Detector-event consumers.
- External event producers.
- Export/download jobs.
- Inventory sync jobs.
- Third-party integration templates for systems such as alarm platforms, access control, analytics, CRM/ERP, messaging, or monitoring systems.

**Rules:**
- Generated code must name required fixtures and auth mode.
- Generated code must include timeouts, stream caps, retry policy, and redaction policy.
- Generated code must avoid storing credentials, bearer tokens, raw video, raw face images, full plate values, or security payloads unless the user explicitly designs a secure storage path.

### MCP Phase 5: Public Repository Release

**Target:** publish a sanitized public GitHub repository after the MCP MVP is useful and free of internal/demo secrets.

**Recommended repo contents:**
- `README.md`: what the MCP server does, supported Axxon One version(s), quick start.
- `LICENSE`: selected before publishing.
- `src/axxon_one_mcp/` or equivalent package source.
- `data/`: generated structured API corpus.
- `examples/`: LLM client config, Claude Desktop/Codex examples, sample prompts, read-only demo workflows.
- `tests/`: unit tests for corpus search, safety policy, tool schemas, redaction, dry-run plans.
- `docs/`: architecture, safety model, supported workflows, fixture requirements, publication notes.
- `scripts/`: corpus generator, validation, secret scan, release helpers.

**Public release gates:**
- No passwords, bearer tokens, certificates with private keys, license keys, serial numbers, full plate values, raw images, raw video, or customer data.
- All mutation tools default disabled.
- Read-only docs-only mode works without Axxon One access.
- Live mode requires explicit environment/profile configuration.
- CI runs tests, JSON schema validation, linting, and secret scan.
- Public docs clearly state that configuration mutation requires approvals and rollback-capable fixtures.

---

## Execution Order

1. Task 1: Coverage matrix.
2. Task 2: Raw/binary HTTP client support.
3. Task 3: Legacy HTTP read sweep.
4. Task 4: Media/snapshot stream smoke.
5. Task 5: WebSocket and event subscriptions.
6. Task 6: Active metadata endpoint selection.
7. Task 7: Archive search smoke.
8. Task 8: Config detail read sweep.
9. Task 9: Client HTTP and embeddable component fixture notes.
10. Task 10: Fixture discovery.
11. Task 11: Mutation playbooks.
12. Task 12: Mutation runner skeleton.
13. Task 13: Documentation integration.
14. Task 14: Full verification.
15. Task 15: Final coverage report.
16. MCP Phase 0: Freeze and normalize the verified API corpus.
17. MCP Phase 1: Build docs-only MCP MVP.
18. MCP Phase 2: Add read-only live inspection tools.
19. MCP Phase 3: Add controlled operator tools with dry-run, approval, rollback, and audit logs.
20. MCP Phase 4: Add integration/plugin generation workflows.
21. MCP Phase 5: Prepare and publish a sanitized public GitHub repository.

## Stop Conditions

Pause and ask the user before:

- Running any mutating operation on the demo stand.
- Running PTZ movement, macro launch, user/role edit, archive delete/reindex, map edit, detector parameter edit, or video deletion.
- Installing new runtime dependencies.
- Persisting raw reports from `/tmp` into the repo if they include any sensitive fields.

## 2026-05-02 Continuation: AppDataDetector And ChangeConfig Findings

User feedback corrected the event model: semantic analytics events should not be probed only through parent `AVDetector.*` objects. Full camera inventory and configuration reads now show that parent `AVDetector.*` objects provide tracker metadata and VMDA endpoints, while child `AppDataDetector.*` objects are the configured semantic event producers for motion in area, line crossing, loitering, multiple objects, and similar rules.

New durable evidence:

- `arm64-docker/docs/api-audit/appdata-detectors-demo-2026-05-02.md`
- `arm64-docker/docs/api-audit/demo-appdata-subscription-2026-05-02.md`
- `arm64-docker/docs/api-audit/legacy-http-sweep-demo-bearer-2026-05-03.md`
- `arm64-docker/docs/api-audit/legacy-auth-probe-demo-2026-05-03.md`
- `arm64-docker/docs/api-audit/config-model-study-demo-2026-05-02.md`
- `arm64-docker/docs/api-audit/config-mutation-smoke-demo-2026-05-02.md`
- `arm64-docker/docs/api-audit/demo-metadata-tracklets-2026-05-02.md`
- `arm64-docker/docs/api-audit/macro-smoke-demo-2026-05-03.md`
- `arm64-docker/docs/api-audit/device-template-smoke-demo-2026-05-02.md`
- `arm64-docker/docs/api-audit/map-marker-smoke-demo-2026-05-03.md`

New tooling:

- `arm64-docker/tools/axxon_config_model_study.py`: read-only object tree, factory, property, and representative AP study.
- `arm64-docker/tools/axxon_legacy_auth_probe.py`: read-only auth-mode comparison for selected legacy HTTP paths.
- `arm64-docker/tools/axxon_legacy_http_sweep.py`: now supports `--auth-mode bearer`; on the demo stand Bearer auth raised legacy read coverage from PASS=6/WARN=12 to PASS=20/WARN=0 after correcting the PDF alarm path to `/archive/events/alerts/...`, adding `/audit/{host}/...`, and replacing the non-PDF `/macros` check with the PDF `/macro/list/` variants.
- `arm64-docker/tools/axxon_config_mutation_smoke.py`: explicit-approval `ChangeConfig` smoke that creates, changes, verifies, and removes temporary `codex-temp-*` archive, camera, `AVDetector`, and `AppDataDetector` fixtures.
- `arm64-docker/tools/axxon_macro_smoke.py`: explicit-approval macro lifecycle smoke. It creates a disabled common macro with no conditions or rules, changes it, optionally launches only that disabled empty macro, reads it back, removes it, and verifies `not_found_macros`.
- `arm64-docker/tools/axxon_device_template_smoke.py`: explicit-approval template lifecycle smoke that creates an isolated virtual camera, creates/edits/assigns/unassigns/deletes a temporary `codex-*` template, and verifies rollback.
- `arm64-docker/tools/axxon_map_marker_smoke.py`: explicit-approval map/marker lifecycle smoke. It creates a temporary `codex-*` raster map with a tiny PNG and marker, changes the map, reads image/markers, updates/removes the marker, and removes the map.
- `arm64-docker/tools/axxon_media_stream_smoke.py`: now supports `--auth-mode bearer`, resolves an archive timestamp from `/archive/contents/intervals/...`, verifies direct and composite RTSP playback with bounded `ffprobe`, and extracts ONVIF RTP frame timestamps by parsing RTSP interleaved TCP. On the demo stand, stream-info, live snapshot, live MJPEG, live HLS, live MP4, live RTSP descriptor, `/rtsp/stat`, direct RTSP, composite RTSP, ONVIF RTP timestamp extraction, archive JPEG frame, and archive MJPEG passed with 1 MiB byte caps for HTTP media.
- `arm64-docker/tools/axxon_archive_search_smoke.py`: now includes legacy HTTP async VMDA and heatmap modes plus bounded gRPC `BuildHeatmap` image generation. The legacy modes start `/search/{vmda|heatmap}/...`, poll `/result`, record only shapes/sizes/hashes, and delete the search handle. The gRPC image mode records only result status, byte count, hash, and response shape.
- `arm64-docker/tools/axxon_fixture_discovery.py`: now also checks Client HTTP API reachability, embeddable Web host presence, and RTSP playback reachability.

Verified config mutations on the demo stand:

- Create/change/remove temporary `MultimediaStorage`.
- Create/change/remove temporary virtual `DeviceIpint`; this demo requires `vendor=Virtual`, while the PDF `vendor=axxonsoft` example failed with server `fanout request has failed`.
- Create/change/remove temporary `AVDetector` units for `SceneDescription`, `MotionDetection`, and `NeuroTracker`.
- Create/change/remove temporary `AppDataDetector.MoveInZone`; bounded verification observed detector events before rollback.
- Change/read back the generated `AppDataDetector` child `VisualElement.*` polygon mask using `value_simple_polygon`.
- Verify the PDF `Get tracks using GO` section by reading `MetadataSample_Tracklets` through `MetadataService.PullMetadata`; the demo VMDA endpoint returned 3 samples with 21 tracklets each.
- Create/change/launch/remove a disabled common macro with no rules through `ChangeMacros`, `BatchGetMacros`, and `LaunchMacro`; rollback was verified with `not_found_macros`. The launch is constrained to the temporary disabled empty macro only.
- Verify legacy HTTP Bearer behavior: `/product/version`, detector list, archive list/intervals/frame registration time/statistics/calendar, audit events, detector events, alert reads, `/macro/list/`, and `/macro/list/?exclude_auto` pass with Bearer from `/grpc`; product version and macro list return 401 with Basic auth.
- Create/edit/assign/unassign/delete a temporary device template through `ChangeTemplates`, `BatchGetTemplates`, and `SetTemplateAssignments`; assignment was verified with `ListUnits.assigned_templates`, deletion was verified with `BatchGetTemplates.not_found`, and the temporary camera was removed.
- Create/change/read image/read markers/update marker/remove marker/remove map through `ChangeMaps`, `GetMapImage`, `GetMarkers`, and `UpdateMarkers`; rollback was verified by unchanged map count and `BatchGetMaps.failed_map_ids` for the removed temporary map.
- Verify bounded legacy media with Bearer auth: `/stream-info/{camera}`, `/live/media/snapshot/{camera}`, `/live/media/{camera}` MJPEG, `/live/media/{camera}?format=hls`, `/live/media/{camera}?format=mp4`, `/live/media/{camera}?format=rtsp`, `/rtsp/stat`, direct RTSP playback, composite RTSP playback, ONVIF RTP timestamp extraction, `/archive/media/{camera}/{timestamp}` JPEG frame, and `/archive/media/{camera}/{timestamp}?speed=1` MJPEG all pass when `timestamp` is selected from the current archive interval.
- Verify legacy HTTP bookmarks with an opt-in mutation smoke: Bearer auth can read `/archive/contents/bookmarks/{host}/{end}/{begin}`, but the documented create endpoints `/archive/contents/bookmarks/create` and `/archive/contents/bookmarks/create/` return HTTP 501 on the demo stand. Basic auth returns HTTP 403. A broad post-smoke read found zero sampled `codex-` bookmarks, so no temporary bookmark was left behind.
- Verify gRPC bookmark lifecycle with an opt-in mutation smoke: `BookmarkService.CreateBookmark`, filtered `ListBookmarks`, `UpdateBookmark`, filtered `ListBookmarks`, `DeleteBookmark`, and post-delete filtered `ListBookmarks` pass on the demo stand with a temporary `codex-grpc-bookmark-smoke-*` bookmark. This is the runnable bookmark lifecycle fallback while legacy HTTP create remains HTTP 501.
- Verify the PDF legacy HTTP delete-video shape with a no-op dispatch probe: `DELETE /archive/contents/bookmarks/` plus `begins_at`, `ends_at`, `storage_id`, and `endpoint` query parameters reaches the server and returns HTTP 404 for a `codex-nonexistent-*` endpoint/storage pair. This proves endpoint dispatch without deleting archive data; real archive deletion remains exact-interval maintenance work only.
- Verify legacy HTTP async archive search lifecycle for auto, face, VMDA, stranger, and heatmap. Direct gRPC LPR, VMDA, `ExecuteHeatmapQuery`, and bounded `BuildHeatmap` image generation also pass. A 24-hour BuildHeatmap run exceeded the 30-second deadline, while a two-hour 64x48 image run passed, so examples should keep image builds bounded. Face and stranger async searches pass with the documented empty-body behavior. Image-body face matching and `faceAppearanceRate` now pass with a temporary camera `9.Face` snapshot against `hosts/Server/AVDetector.93/EventSupplier`; reports store only image size and hash.
- Verify archive-management preflight without mutation: `GetArchiveTraits`, `GetVolumesState`, and `GetDiskSpace` pass for AliceBlue on the demo stand. The archive reports one mounted volume and disk-space status `OK`. No-op `FormatVolumes`, `Reindex`, and `CancelReindex` dispatch against a `codex-nonexistent-*` volume id is verified; real volume changes remain approval-only because they change archive state.
- Verify security administration preflight without mutation: users/roles, policies, global/group/object/macro permission summaries, and restricted config read successfully. The demo stand has 4 roles, 35 users, 0 LDAP servers, 1 password policy, 0 IP filters, 0 trusted IPs, 36 object-permission info rows, 1 group-permission info row, and 16 macro-permission rows. `GetLDAPSynchronizationState` returns `UNAVAILABLE` with no LDAP server configured, so LDAP search/sync remains fixture-needed.
- Verify export preflight without mutation: `ExportService.ListSessions` and `DomainSettingsService.GetExportSettings` pass; the demo stand has zero export sessions, readable export settings, a current archive interval for the selected camera, and `hosts/Server/MMExportAgent.0` in the configuration tree. Earlier fixture discovery missed this config-tree export agent.
- Verify controlled gRPC export lifecycle with rollback: temporary `codex-*` archive snapshot export reached `S_COMPLETED`, bounded `DownloadFile` returned the JPEG result, and `DestroySession` cleaned it up. A temporary live export reached `S_RUNNING`, then `StopSession` and `DestroySession` passed. Latest report: `api-audit/export-smoke-latest.md`.
- Verify controlled legacy HTTP export lifecycle with rollback: one-frame JPEG `POST /export/archive/...` returned HTTP 202, `GET /export/{id}/status` reached state `2`, bounded `GET /export/{id}/file` returned JPEG bytes, and `DELETE /export/{id}` returned HTTP 204. Latest report: `api-audit/http-export-smoke-latest.md`.
- Verify ETag-guarded no-op export settings update: `DomainSettingsService.UpdateExportSettings` accepted the current `ExportSettings` with `mask.paths=["options.max_file_size_bytes"]`, returned an ETag, and follow-up `GetExportSettings` confirmed the value remained unchanged. Proof: `api-audit/export-settings-update-20260511.md`.
- Verify PTZ/Tag&Track preflight without mutation: no telemetry/PTZ access points and no control panels are configured on the demo stand. Telemetry position/preset/operation/tour reads and Tag&Track tracker reads are skipped until a telemetry access point exists; PTZ movement, presets, tours, and Tag&Track mode/follow/move remain approval-only.
- Verify external-client preflight without UI mutation: no Axxon Client HTTP API target is reachable on port `8888`, and the demo Web root returns HTTP 200 with 955 bytes but no component/video/embed signature. Client HTTP layout/videowall calls and browser-rendered component checks remain fixture-needed.
- Verify controlled layout mutation smoke with rollback: create a temporary `codex-layout-*` layout, update its map arrangement with `LayoutManager.Update`, call `LayoutsOnView` for the temporary layout, remove it, verify post-remove `not_found_items`, and verify the current layout id is unchanged.
- Verify controlled security mutation smoke with rollback: create a UUID-indexed temporary `codex-*` role and user, set a generated in-memory password, assign the user to the role, verify role-filtered user listing, update temp-role global/object/group/macro permissions, perform no-op current-snapshot password-policy/IP-filter/trusted-IP writes, add/edit/remove a temporary LDAP directory, remove the assignment/user/role, and verify role/user/LDAP counts are restored. A first run using `codex-*` as the actual role/user index failed with `SetConfigFailed`; role/user indices must be UUID-shaped on this stand.
- Verify controlled macro launch smoke with rollback: create a temporary disabled empty macro, modify it, launch only that isolated macro with no conditions and no rules, remove it, and verify post-remove `not_found_macros`.
- Verify controlled arm-state smoke with rollback: create a temporary virtual `DeviceIpint` camera through `ConfigurationService.ChangeConfig`, call `LogicService.ChangeArmState` with `CS_Arm` and a 2-second state timeout, remove the camera, and verify no cleanup failure. A first run used a non-existent generated enum name `ARMED`; the proto enum values are `CS_Disarm`, `CS_Arm`, and `CS_ArmPrivate`.
- Verify external event injection fixture boundary: create a temporary AppDataDetector, call `/v1/detectors/external:raiseOccasionalEvent`, and remove the detector. Rollback passed, but both a semantic `moveInZone` event type and PDF-style `Event1` returned HTTP 500 / gRPC 13 `BAD_OPERATION`; this proves a normal AppDataDetector is not a DetectorEx substitute on the demo stand.
- Verify RealtimeRecognizerExternal is not the DetectorEx fixture either: create a temporary disabled `RealtimeRecognizerExternal`, try its `RecognizerExternal`, unit, and `EventSupplier` AP candidates with PDF-style `Event1`, then remove it. Rollback passed, but all candidates returned HTTP 503 / gRPC 14 can't-resolve-reference.
- Verify direct DetectorEx creation boundary after explicit approval: `ConfigurationService.ChangeConfig` accepted the request shape but returned empty `added`, `failed`, and `failed_reason` arrays, so no uid was created. Follow-up `ListUnits` proved `DetectorEx.0`, `.1`, and `.2` were not present. Direct creation is not a supported fixture path on this stand; a product-supported DetectorEx fixture/config/import is still required.
- Verify explicit DetectorEx access-point spellings without config creation: `DetectorEx.1`, `hosts/Server/DetectorEx.1`, and `hosts/Server/DetectorEx.1/EventSupplier` all returned HTTP 503 / gRPC 14 can't-resolve-reference. Refreshed factory discovery shows `DetectorEx` and `ExternalDetector` factory requests return `NOT_FOUND`; the only Plugin `module_name` factory enum value is `LocalMonitoring`, not a virtual-trigger module.
- Verify destructive fixture-search paths after permission to add/delete anything on the test stand: enabled temporary `Plugin.LocalMonitoring` objects with both advertised plugin `type` values created and removed cleanly, but DetectorEx factories remained `NOT_FOUND` and no DetectorEx-like units appeared. Direct child creation of `DetectorEx`/`ExternalDetector` under host, `AVDetector.1`, `AppDataDetector.22`, `DeviceIpint.24`, and `DeviceIpint.24/TextEventSource.0` did not create objects. Direct gRPC `ExternalDetectorService.RaiseOccasionalEvent` returned the same unresolved/BAD_OPERATION behavior as HTTP.
- Verify real DetectorEx fixture after user created one for camera 1: `ListUnits` found `hosts/Server/DetectorEx.1` with `access_point=hosts/Server/DetectorEx.1/EventSupplier`, `detector=ExternalDetector`, `event_types=Event1/Event2/TargetList`, source camera `hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0`, VMDA endpoint `hosts/Server/DetectorEx.1/SourceEndpoint.vmda`, and child `AppDataDetector.27`. `RaiseOccasionalEvent(Event1)` returned OK and event history matched the injected event id. `RaisePeriodicalEvent(TargetList)` returned OK through HTTP and direct gRPC; with `PullMetadata` open during injection, DetectorEx VMDA returned the injected tracklet.
- Verify detector-parameter management with rollback: create a temporary `MotionDetection` AVDetector, change and read back its `enabled` main parameter, remove it, then change and read back a detector visual `polyline` through a temporary AppDataDetector fallback. The fallback is required on this stand because the temporary AVDetector has no `VisualElement` child. A first attempt with default timeout left a stale fanout failure, but follow-up `ListUnits` proved the object was removed; rerun with `--timeout 60` passed.
- Recheck WebSocket camera-event subscription after DetectorEx setup: gRPC `PullEvents` against `hosts/Server/AppDataDetector.27/EventSupplier` plus camera 1 received 20 detector events. Raw `/events` compatibility checks show HTTP 101 upgrade followed by immediate close across URL Basic auth, explicit Basic header, schema/no-schema, origin variants, camera include, detector include, and device track. Keep HTTP WebSocket as fixture-needed / server-behavior unresolved.

Remaining gaps after this continuation:

- Archive search is now covered end to end for the PDF surfaces: auto, face, VMDA, stranger, and heatmap start/result/delete all pass; image-body face matching returns bounded face result pages; `faceAppearanceRate` returns a rate for a camera `9.Face` snapshot.
- HTTP WebSocket camera-event subscription remains fixture-needed: the demo Web server upgrades `/events` to WebSocket but closes immediately across tested auth/schema/command variants.
- Archive format/reindex/cancel-reindex/cloud/link operations still require isolated storage fixtures or explicit maintenance-window approval.
- Security temporary user/role creation, assignment, generated password set, temp-role permission updates, no-op policy/IP-filter writes, temporary LDAP directory add/edit/remove, and removal are now covered with rollback. Real-user password/login changes, TFA operations, and LDAP sync/search against a real LDAP server still require isolated fixtures and rollback approval.
- Export start/download/stop/destroy is now covered for both gRPC and legacy HTTP export with byte caps and cleanup. `DomainSettingsService.UpdateExportSettings` is verified with an ETag-guarded no-op update; real default-setting changes still need original-setting capture and restore.
- PTZ and Tag&Track still require a non-production telemetry/PTZ access point, known home preset or saved position, and explicit physical-camera movement approval.
- Client HTTP and embeddable video component coverage still require a real Axxon Client HTTP API target or browser-renderable component host.
- External event injection is now covered when a real `DetectorEx.*` fixture exists. DetectorEx fixture creation/import remains unresolved through public `ChangeConfig`; temporary AppDataDetector, temporary RealtimeRecognizerExternal, Plugin.LocalMonitoring, and plausible child-parent creation paths are documented false paths.
- HTTP macro list, macro lifecycle, macro launch, and virtual-camera arm-state switching are now covered with isolated temporary fixtures and rollback.
- Legacy media direct RTSP playback, composite RTSP playback, and ONVIF RTP frame-timestamp extraction are now verified with bounded checks.
- Fixture discovery on 2026-05-03 found RTSP ports `554` and `8554` reachable, but still found no Client HTTP API target, embeddable component host, PTZ telemetry, control panels, water-level devices, or persistent template fixture. Export agent discovery is now corrected through `ConfigurationService.ListUnits`, which finds `MMExportAgent.0`.
- Detector-specific parameter examples, visual-element edits, and `Get tracks using GO` tracklet path are now covered with rollback.
- Device template lifecycle is now covered; remaining template work is limited to extra body variants if a future integration needs them.
- Layout display control is now covered with an isolated temporary layout; map and marker mutations are also covered.
