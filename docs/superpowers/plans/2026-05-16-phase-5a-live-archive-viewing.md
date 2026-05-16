# Phase 5A — Live + Archive Viewing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six read-only MCP tools that expose Axxon One's live video, snapshots, archive scrub, archive frame, bounded archive MJPEG, and per-camera stream health — every tool returns URLs (not proxied bytes) with explicit byte/time caps, reuses `AxxonApiClient`, and is verified against the demo stand at `100.76.150.18`.

**Architecture:** A new `axxon_mcp_view.py` module mirrors the dataclass-with-factories pattern of `axxon_mcp_live.py`. It composes existing legacy HTTP endpoints (`/stream-info/...`, `/live/media/...`, `/archive/media/...`, `/statistics/...`, `/rtsp/stat`) into MCP-shaped tools that return summarized JSON: a sanitized URL, the auth header name to use, the cap that was applied, and a fixture-status field when no access point is available. The MCP server registers these tools behind `--enable-view`. Live verification runs through a new `axxon_view_smoke.py` script.

**Tech Stack:** Python 3.11+, `AxxonApiClient` (existing), `unittest`, FastMCP (existing). No new third-party deps.

---

## Source-of-truth references

- Existing live module pattern: `tools/axxon_mcp_live.py` (dataclass, `client_factory`/`config_factory`, `sanitize`, redacted summaries).
- Existing media verification: `tools/axxon_media_stream_smoke.py` (URL shapes already proven against demo stand).
- Existing MCP registration pattern: `tools/axxon_mcp_server.py` (`register_live_tools`, `--enable-live` flag).
- Existing test pattern: `tools/tests/test_axxon_mcp_live.py` (`FakeConfig`, `FakeClient`, no network).
- Demo stand: host `100.76.150.18`, gRPC `20109`, HTTP `80`, login `root` / password `root`. Sanitized to `<demo-host>` / `<your-tls-cn>` in evidence.
- Cap defaults from `axxon_media_stream_smoke.py`: `DEFAULT_MAX_BYTES = 1_048_576` (1 MiB).

---

## File structure

| Path | Purpose | Touched by |
| --- | --- | --- |
| `tools/axxon_mcp_view.py` | New module. `AxxonMcpView` dataclass with six tool methods. | Tasks 1–7 |
| `tools/axxon_mcp_server.py` | Register view tools under `--enable-view`. | Task 8 |
| `tools/axxon_view_smoke.py` | New live smoke; runs all six tools against a real stand. | Task 9 |
| `tools/tests/test_axxon_mcp_view.py` | New unit tests; offline, no network. | Tasks 1–7 |
| `tools/tests/test_axxon_mcp_server.py` | Add registration test for view tools. | Task 8 |
| `docs/api-audit/phase-5a-view-smoke-latest.md` | New live evidence. | Task 10 |
| `docs/api-audit/pdf-gap-coverage-matrix.md` | Add a row for "MCP view tools". | Task 11 |
| `README.md` | Document `--enable-view` and the six tools. | Task 11 |

Each tool returns a dict with this shape:

```python
{
    "status": "ok" | "fixture-needed" | "gap",
    "tool": "live_view",
    "camera": "<camera access point>",
    "url": "<full URL with caps applied>",
    "auth": {"header": "Authorization", "scheme": "Bearer"},
    "caps": {"bytes": int | None, "time_s": int | None, "fps": int | None},
    "stream_info": {...} | None,
    "fixture": {"required": [...], "missing": [...]} | None,
}
```

URLs are returned, never bytes. The MCP never proxies media. Callers fetch the URL themselves with the Bearer token they already have from `connect_axxon_profile`.

---

## Cap defaults and limits

These constants live at the top of `axxon_mcp_view.py`:

```python
DEFAULT_MAX_BYTES = 1_048_576       # 1 MiB; matches media smoke
DEFAULT_DURATION_S = 10             # bounded subscription window
DEFAULT_FPS = 5                     # for live MJPEG/HLS
DEFAULT_SNAPSHOT_WIDTH = 640
SNAPSHOT_BATCH_LIMIT = 8            # max cameras in one snapshot_batch call
ARCHIVE_MJPEG_BYTE_CAP = 4_194_304  # 4 MiB cap for archive MJPEG
ARCHIVE_FRAME_THRESHOLD_MS = 60_000
```

Every public method clamps its inputs against these. A request that exceeds a cap is silently clamped and the applied value is reported back in `caps`.

---

## Task 1: Module scaffold + `connect` reuse

**Files:**
- Create: `tools/axxon_mcp_view.py`
- Create: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 1.1: Write the failing test for module load and connect**

```python
# tools/tests/test_axxon_mcp_view.py
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "demo.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://demo.local"
    username = "root"
    password = "secret"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self) -> None:
        self.inventory = {
            "cameras": [
                {
                    "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                    "display_name": "Camera 1",
                    "enabled": True,
                    "serial_number": "SHOULD_NOT_LEAK",
                },
                {
                    "access_point": "hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0",
                    "display_name": "Camera 2",
                    "enabled": True,
                },
            ],
            "archives": [
                {"access_point": "hosts/Server/MultimediaStorage.Main/MultimediaStorage", "enabled": True},
            ],
        }

    def load_inventory(self):
        return self.inventory

    def sanitize(self, value):
        if isinstance(value, dict):
            return {k: ("<redacted>" if k == "serial_number" else self.sanitize(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.sanitize(v) for v in value]
        return value


class AxxonMcpViewTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = view.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axxon_mcp_view'`

- [ ] **Step 1.3: Create minimal module**

```python
# tools/axxon_mcp_view.py
#!/usr/bin/env python3
"""Read-only live and archive viewing tools for the Axxon One MCP server.

URLs only — this module never proxies media bytes. Callers fetch URLs
directly with the Bearer token issued by AxxonApiClient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from axxon_api_client import AxxonApiClient, AxxonClientConfig


DEFAULT_MAX_BYTES = 1_048_576
DEFAULT_DURATION_S = 10
DEFAULT_FPS = 5
DEFAULT_SNAPSHOT_WIDTH = 640
SNAPSHOT_BATCH_LIMIT = 8
ARCHIVE_MJPEG_BYTE_CAP = 4_194_304
ARCHIVE_FRAME_THRESHOLD_MS = 60_000


def default_config_factory() -> AxxonClientConfig:
    return AxxonClientConfig.from_env(repo_root=Path(__file__).resolve().parents[1])


def default_client_factory(config: AxxonClientConfig) -> AxxonApiClient:
    return AxxonApiClient(config)


def public_config_summary(config: Any) -> dict[str, Any]:
    return {
        "host": getattr(config, "host", ""),
        "grpc_port": getattr(config, "grpc_port", None),
        "http_port": getattr(config, "http_port", None),
        "http_url": getattr(config, "http_url", ""),
        "username": getattr(config, "username", ""),
        "password_present": bool(getattr(config, "password", "")),
        "tls_cn": getattr(config, "tls_cn", ""),
        "ca": str(getattr(config, "ca", "")),
        "timeout": getattr(config, "timeout", None),
    }


@dataclass
class AxxonMcpView:
    """URL-only live and archive viewing tools."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = field(default=None, repr=False)

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        self._inventory = None
        return {
            "connected": True,
            "profile": public_config_summary(config),
        }

    def _ensure_inventory(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        if self._inventory is None:
            self._inventory = self.client.load_inventory()
        return self._inventory
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS

- [ ] **Step 1.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: scaffold axxon_mcp_view module with connect"
```

---

## Task 2: `live_view` — URL with caps

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 2.1: Write the failing test**

Append to `tools/tests/test_axxon_mcp_view.py` inside `AxxonMcpViewTests`:

```python
    def test_live_view_returns_url_with_caps_for_known_camera(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            duration_s=999,
            fps=999,
            format="mjpeg",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "live_view")
        self.assertIn("/live/media/", result["url"])
        self.assertIn("Server/DeviceIpint.1/SourceEndpoint.video:0:0", result["url"])
        self.assertEqual(result["caps"]["time_s"], module.DEFAULT_DURATION_S)
        self.assertEqual(result["caps"]["fps"], module.DEFAULT_FPS)
        self.assertEqual(result["auth"], {"header": "Authorization", "scheme": "Bearer"})
        self.assertNotIn("secret", str(result))

    def test_live_view_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view("hosts/Server/NotACamera", format="mjpeg")
        self.assertEqual(result["status"], "gap")
        self.assertIn("NotACamera", result["message"])

    def test_live_view_rejects_unknown_format(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.live_view(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            format="webp",
        )
        self.assertEqual(result["status"], "gap")
        self.assertIn("format", result["message"])
```

- [ ] **Step 2.2: Run tests, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `AttributeError: 'AxxonMcpView' object has no attribute 'live_view'`

- [ ] **Step 2.3: Implement `live_view`**

Append to `AxxonMcpView`:

```python
    _SUPPORTED_LIVE_FORMATS = ("mjpeg", "hls", "mp4", "rtsp")

    def _legacy_ap(self, access_point: str) -> str:
        return access_point.removeprefix("hosts/")

    def _camera_index(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {cam.get("access_point", ""): cam for cam in inventory.get("cameras", []) if cam.get("access_point")}

    def _auth(self) -> dict[str, str]:
        return {"header": "Authorization", "scheme": "Bearer"}

    def live_view(
        self,
        camera_access_point: str,
        duration_s: int = DEFAULT_DURATION_S,
        fps: int = DEFAULT_FPS,
        width: int = DEFAULT_SNAPSHOT_WIDTH,
        format: str = "mjpeg",
    ) -> dict[str, Any]:
        if format not in self._SUPPORTED_LIVE_FORMATS:
            return {
                "status": "gap",
                "tool": "live_view",
                "message": f"Unsupported format '{format}'. Supported: {self._SUPPORTED_LIVE_FORMATS}",
            }
        inventory = self._ensure_inventory()
        cameras = self._camera_index(inventory)
        if camera_access_point not in cameras:
            return {
                "status": "gap",
                "tool": "live_view",
                "message": f"Camera not found in inventory: {camera_access_point}",
            }
        applied_duration = min(max(duration_s, 1), DEFAULT_DURATION_S)
        applied_fps = min(max(fps, 1), DEFAULT_FPS)
        applied_width = min(max(width, 64), 1920)
        legacy = self._legacy_ap(camera_access_point)
        base = self.client.config.http_url.rstrip("/")
        if format == "mjpeg":
            url = f"{base}/live/media/{legacy}?w={applied_width}&h=0&fps={applied_fps}"
        elif format == "hls":
            url = f"{base}/live/media/{legacy}?format=hls"
        elif format == "mp4":
            url = f"{base}/live/media/{legacy}?format=mp4"
        else:  # rtsp
            url = f"{base}/live/media/{legacy}?format=rtsp"
        return {
            "status": "ok",
            "tool": "live_view",
            "camera": camera_access_point,
            "url": url,
            "auth": self._auth(),
            "caps": {
                "bytes": DEFAULT_MAX_BYTES,
                "time_s": applied_duration,
                "fps": applied_fps,
            },
        }
```

- [ ] **Step 2.4: Run tests, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (4 tests).

- [ ] **Step 2.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add live_view tool returning capped URL"
```

---

## Task 3: `snapshot_batch` — parallel snapshots, count cap

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 3.1: Write the failing test**

Append:

```python
    def test_snapshot_batch_returns_one_url_per_known_camera_and_caps_count(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        # Pass a 10-camera list; only 2 exist in fixture and SNAPSHOT_BATCH_LIMIT clamps to 8.
        aps = [f"hosts/Server/DeviceIpint.{i}/SourceEndpoint.video:0:0" for i in range(1, 11)]
        result = view.snapshot_batch(aps)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "snapshot_batch")
        self.assertLessEqual(len(result["items"]), module.SNAPSHOT_BATCH_LIMIT)
        ok_items = [item for item in result["items"] if item["status"] == "ok"]
        gap_items = [item for item in result["items"] if item["status"] == "gap"]
        self.assertEqual(len(ok_items), 2)
        self.assertGreaterEqual(len(gap_items), 1)
        for item in ok_items:
            self.assertIn("/live/media/snapshot/", item["url"])
            self.assertEqual(item["caps"]["bytes"], module.DEFAULT_MAX_BYTES)
```

- [ ] **Step 3.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `AttributeError: ... 'snapshot_batch'`.

- [ ] **Step 3.3: Implement**

Append:

```python
    def snapshot_batch(
        self,
        camera_access_points: list[str],
        ts: str = "now",
        width: int = DEFAULT_SNAPSHOT_WIDTH,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        cameras = self._camera_index(inventory)
        clamped = list(camera_access_points)[:SNAPSHOT_BATCH_LIMIT]
        applied_width = min(max(width, 64), 1920)
        base = self.client.config.http_url.rstrip("/")
        items: list[dict[str, Any]] = []
        for ap in clamped:
            if ap not in cameras:
                items.append({"status": "gap", "camera": ap, "message": "not in inventory"})
                continue
            legacy = self._legacy_ap(ap)
            if ts == "now":
                url = f"{base}/live/media/snapshot/{legacy}?w={applied_width}&h=0"
            else:
                ts_q = quote(ts, safe="")
                url = f"{base}/archive/media/{legacy}/{ts_q}?threshold={ARCHIVE_FRAME_THRESHOLD_MS}&w={applied_width}&h=0"
            items.append(
                {
                    "status": "ok",
                    "camera": ap,
                    "url": url,
                    "auth": self._auth(),
                    "caps": {"bytes": DEFAULT_MAX_BYTES, "time_s": None, "fps": None},
                }
            )
        return {
            "status": "ok",
            "tool": "snapshot_batch",
            "ts": ts,
            "items": items,
            "applied_limit": SNAPSHOT_BATCH_LIMIT,
        }
```

- [ ] **Step 3.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (5 tests).

- [ ] **Step 3.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add snapshot_batch tool with count cap"
```

---

## Task 4: `archive_scrub` — calendar + intervals + frame probe

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 4.1: Write the failing test**

Append to `FakeClient`:

```python
    def archive_calendar(self, source_ap: str, archive_ap: str) -> dict[str, Any]:
        return {"days": ["2026-05-15", "2026-05-16"], "source": source_ap, "archive": archive_ap}

    def archive_intervals(self, camera_legacy_ap: str, begin: str, end: str, archive_ap: str | None = None) -> list[dict[str, str]]:
        return [{"begin": "2026-05-16T10:00:00.000000Z", "end": "2026-05-16T10:00:05.000000Z"}]

    def archive_time_range_legacy(self, hours: int = 1) -> tuple[str, str]:
        return ("2026-05-16T09:00:00.000000Z", "2026-05-16T10:00:00.000000Z")
```

Append to tests:

```python
    def test_archive_scrub_combines_calendar_intervals_and_frame_probe(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_scrub(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            hours=2,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "archive_scrub")
        self.assertIn("days", result["calendar"])
        self.assertEqual(len(result["intervals"]), 1)
        self.assertIn("/archive/media/", result["sample_frame_url"])
        self.assertEqual(result["caps"]["bytes"], module.DEFAULT_MAX_BYTES)

    def test_archive_scrub_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_scrub("hosts/Server/NotACamera")
        self.assertEqual(result["status"], "gap")
```

- [ ] **Step 4.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `AttributeError: ... 'archive_scrub'`.

- [ ] **Step 4.3: Implement**

Append:

```python
    def _default_archive_ap(self, inventory: dict[str, Any]) -> str | None:
        for arc in inventory.get("archives", []):
            ap = arc.get("access_point")
            if ap:
                return ap
        return None

    def archive_scrub(
        self,
        camera_access_point: str,
        hours: int = 1,
        archive_access_point: str | None = None,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inventory):
            return {
                "status": "gap",
                "tool": "archive_scrub",
                "message": f"Camera not found in inventory: {camera_access_point}",
            }
        archive_ap = archive_access_point or self._default_archive_ap(inventory)
        if archive_ap is None:
            return {
                "status": "fixture-needed",
                "tool": "archive_scrub",
                "message": "No archive access point in inventory.",
                "fixture": {"required": ["MultimediaStorage.*/MultimediaStorage"], "missing": ["archive"]},
            }
        applied_hours = min(max(hours, 1), 24)
        begin, end = self.client.archive_time_range_legacy(hours=applied_hours)
        legacy = self._legacy_ap(camera_access_point)
        calendar = self.client.archive_calendar(camera_access_point, archive_ap)
        intervals = self.client.archive_intervals(legacy, begin, end, archive_ap=archive_ap)
        sample_ts = (intervals[-1].get("end") if intervals else end)
        sample_ts_q = quote(sample_ts, safe="")
        base = self.client.config.http_url.rstrip("/")
        sample_url = f"{base}/archive/media/{legacy}/{sample_ts_q}?threshold={ARCHIVE_FRAME_THRESHOLD_MS}&w={DEFAULT_SNAPSHOT_WIDTH}&h=0"
        return {
            "status": "ok",
            "tool": "archive_scrub",
            "camera": camera_access_point,
            "archive": archive_ap,
            "calendar": calendar,
            "intervals": intervals,
            "sample_frame_url": sample_url,
            "auth": self._auth(),
            "caps": {"bytes": DEFAULT_MAX_BYTES, "time_s": None, "fps": None, "hours": applied_hours},
        }
```

- [ ] **Step 4.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (7 tests).

- [ ] **Step 4.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add archive_scrub combining calendar intervals and frame probe"
```

---

## Task 5: `archive_frame` — single-frame URL with threshold

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 5.1: Write the failing test**

```python
    def test_archive_frame_returns_url_with_threshold(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_frame(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            ts="2026-05-16T10:00:00.000000Z",
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("/archive/media/", result["url"])
        self.assertIn("threshold=", result["url"])
        self.assertEqual(result["caps"]["bytes"], module.DEFAULT_MAX_BYTES)
```

- [ ] **Step 5.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `AttributeError: ... 'archive_frame'`.

- [ ] **Step 5.3: Implement**

```python
    def archive_frame(
        self,
        camera_access_point: str,
        ts: str,
        width: int = DEFAULT_SNAPSHOT_WIDTH,
        threshold_ms: int = ARCHIVE_FRAME_THRESHOLD_MS,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inventory):
            return {"status": "gap", "tool": "archive_frame", "message": "camera not in inventory"}
        applied_width = min(max(width, 64), 1920)
        applied_threshold = min(max(threshold_ms, 1_000), 600_000)
        legacy = self._legacy_ap(camera_access_point)
        ts_q = quote(ts, safe="")
        base = self.client.config.http_url.rstrip("/")
        url = f"{base}/archive/media/{legacy}/{ts_q}?threshold={applied_threshold}&w={applied_width}&h=0"
        return {
            "status": "ok",
            "tool": "archive_frame",
            "camera": camera_access_point,
            "url": url,
            "auth": self._auth(),
            "caps": {"bytes": DEFAULT_MAX_BYTES, "time_s": None, "fps": None, "threshold_ms": applied_threshold},
        }
```

- [ ] **Step 5.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (8 tests).

- [ ] **Step 5.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add archive_frame tool"
```

---

## Task 6: `archive_mjpeg_bounded` — bounded archive MJPEG

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 6.1: Write the failing test**

```python
    def test_archive_mjpeg_bounded_returns_capped_url(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.archive_mjpeg_bounded(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            begin_ts="2026-05-16T10:00:00.000000Z",
            speed=99,
            fps=99,
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("/archive/media/", result["url"])
        self.assertEqual(result["caps"]["bytes"], module.ARCHIVE_MJPEG_BYTE_CAP)
        self.assertLessEqual(result["caps"]["fps"], module.DEFAULT_FPS)
        self.assertLessEqual(result["caps"]["speed"], 8)
```

- [ ] **Step 6.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL.

- [ ] **Step 6.3: Implement**

```python
    def archive_mjpeg_bounded(
        self,
        camera_access_point: str,
        begin_ts: str,
        speed: int = 1,
        fps: int = DEFAULT_FPS,
        width: int = DEFAULT_SNAPSHOT_WIDTH,
    ) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inventory):
            return {"status": "gap", "tool": "archive_mjpeg_bounded", "message": "camera not in inventory"}
        applied_speed = min(max(speed, 1), 8)
        applied_fps = min(max(fps, 1), DEFAULT_FPS)
        applied_width = min(max(width, 64), 1920)
        legacy = self._legacy_ap(camera_access_point)
        ts_q = quote(begin_ts, safe="")
        base = self.client.config.http_url.rstrip("/")
        url = (
            f"{base}/archive/media/{legacy}/{ts_q}"
            f"?w={applied_width}&h=0&speed={applied_speed}&fps={applied_fps}"
        )
        return {
            "status": "ok",
            "tool": "archive_mjpeg_bounded",
            "camera": camera_access_point,
            "url": url,
            "auth": self._auth(),
            "caps": {
                "bytes": ARCHIVE_MJPEG_BYTE_CAP,
                "time_s": DEFAULT_DURATION_S,
                "fps": applied_fps,
                "speed": applied_speed,
            },
        }
```

- [ ] **Step 6.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (9 tests).

- [ ] **Step 6.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add archive_mjpeg_bounded tool"
```

---

## Task 7: `stream_health` — `/statistics/...` + `/rtsp/stat`

**Files:**
- Modify: `tools/axxon_mcp_view.py`
- Modify: `tools/tests/test_axxon_mcp_view.py`

- [ ] **Step 7.1: Write the failing test**

Append to `FakeClient`:

```python
    def http_get_json(self, path: str) -> dict[str, Any]:
        if path.startswith("/statistics/"):
            return {"bitrate": 1234, "fps": 10, "width": 640, "height": 360, "mediaType": "video", "streamType": "live"}
        if path == "/rtsp/stat":
            return {"sessions": []}
        return {}
```

Append to tests:

```python
    def test_stream_health_returns_statistics_and_rtsp_summary(self) -> None:
        module = importlib.import_module("axxon_mcp_view")
        view = module.AxxonMcpView(
            client_factory=lambda _config: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        result = view.stream_health("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["statistics"]["bitrate"], 1234)
        self.assertEqual(result["rtsp"]["sessions"], [])
        self.assertNotIn("password", str(result))
```

- [ ] **Step 7.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: FAIL with `AttributeError: ... 'stream_health'`.

- [ ] **Step 7.3: Implement**

```python
    def stream_health(self, camera_access_point: str) -> dict[str, Any]:
        inventory = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inventory):
            return {"status": "gap", "tool": "stream_health", "message": "camera not in inventory"}
        legacy = self._legacy_ap(camera_access_point)
        statistics = self.client.http_get_json(f"/statistics/{legacy}")
        rtsp = self.client.http_get_json("/rtsp/stat")
        return {
            "status": "ok",
            "tool": "stream_health",
            "camera": camera_access_point,
            "statistics": statistics,
            "rtsp": rtsp,
        }
```

- [ ] **Step 7.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_view -v`
Expected: PASS (10 tests).

- [ ] **Step 7.5: Commit**

```bash
git add tools/axxon_mcp_view.py tools/tests/test_axxon_mcp_view.py
git commit -m "feat: add stream_health tool"
```

---

## Task 8: Register tools in `axxon_mcp_server.py` behind `--enable-view`

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

- [ ] **Step 8.1: Write the failing registration test**

Append to `tools/tests/test_axxon_mcp_server.py`:

```python
    def test_register_view_tools_adds_six_tools(self) -> None:
        from axxon_mcp_server import register_view_tools

        class FakeServer:
            def __init__(self) -> None:
                self.tools: list[str] = []
            def tool(self, fn=None, **_kwargs):
                def wrap(func):
                    self.tools.append(func.__name__)
                    return func
                return wrap if fn is None else (self.tools.append(fn.__name__) or fn)

        class FakeView:
            def connect_axxon_profile(self, profile="env"): return {"connected": True}
            def live_view(self, *a, **k): return {"status": "ok"}
            def snapshot_batch(self, *a, **k): return {"status": "ok"}
            def archive_scrub(self, *a, **k): return {"status": "ok"}
            def archive_frame(self, *a, **k): return {"status": "ok"}
            def archive_mjpeg_bounded(self, *a, **k): return {"status": "ok"}
            def stream_health(self, *a, **k): return {"status": "ok"}

        server = FakeServer()
        register_view_tools(server, FakeView())
        for name in (
            "view_connect_axxon_profile",
            "live_view",
            "snapshot_batch",
            "archive_scrub",
            "archive_frame",
            "archive_mjpeg_bounded",
            "stream_health",
        ):
            self.assertIn(name, server.tools)
```

- [ ] **Step 8.2: Run, verify failure**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_server -v`
Expected: FAIL with `ImportError: cannot import name 'register_view_tools'`.

- [ ] **Step 8.3: Implement registration**

Add to `tools/axxon_mcp_server.py` (after `register_live_tools`):

```python
def register_view_tools(server: Any, view: Any) -> None:
    @server.tool()
    def view_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        return view.connect_axxon_profile(profile)

    @server.tool()
    def live_view(
        camera_access_point: str,
        duration_s: int = 10,
        fps: int = 5,
        width: int = 640,
        format: str = "mjpeg",
    ) -> dict[str, Any]:
        return view.live_view(camera_access_point, duration_s=duration_s, fps=fps, width=width, format=format)

    @server.tool()
    def snapshot_batch(
        camera_access_points: list[str],
        ts: str = "now",
        width: int = 640,
    ) -> dict[str, Any]:
        return view.snapshot_batch(camera_access_points, ts=ts, width=width)

    @server.tool()
    def archive_scrub(
        camera_access_point: str,
        hours: int = 1,
        archive_access_point: str | None = None,
    ) -> dict[str, Any]:
        return view.archive_scrub(camera_access_point, hours=hours, archive_access_point=archive_access_point)

    @server.tool()
    def archive_frame(
        camera_access_point: str,
        ts: str,
        width: int = 640,
        threshold_ms: int = 60_000,
    ) -> dict[str, Any]:
        return view.archive_frame(camera_access_point, ts=ts, width=width, threshold_ms=threshold_ms)

    @server.tool()
    def archive_mjpeg_bounded(
        camera_access_point: str,
        begin_ts: str,
        speed: int = 1,
        fps: int = 5,
        width: int = 640,
    ) -> dict[str, Any]:
        return view.archive_mjpeg_bounded(camera_access_point, begin_ts=begin_ts, speed=speed, fps=fps, width=width)

    @server.tool()
    def stream_health(camera_access_point: str) -> dict[str, Any]:
        return view.stream_health(camera_access_point)
```

Then wire it into `create_server`. Locate the existing `--enable-live` block. Add a sibling `--enable-view` flag and call `register_view_tools` when set:

```python
# In the argparse setup near --enable-live:
parser.add_argument("--enable-view", action="store_true", help="Enable Phase 5A live/archive viewing tools.")

# In create_server, after the live registration block:
if getattr(args, "enable_view", False):
    from axxon_mcp_view import AxxonMcpView
    register_view_tools(server, AxxonMcpView())
```

(Use the exact attribute name your argparse produces — Python turns `--enable-view` into `enable_view`.)

- [ ] **Step 8.4: Run, verify pass**

Run: `cd tools && python -m unittest tests.test_axxon_mcp_server -v`
Expected: PASS for the new test, no regressions in other tests.

- [ ] **Step 8.5: Run the full test suite**

Run: `cd tools && python -m unittest discover -s tests -v 2>&1 | tail -20`
Expected: All tests pass, count >= previous 174.

- [ ] **Step 8.6: Commit**

```bash
git add tools/axxon_mcp_server.py tools/tests/test_axxon_mcp_server.py
git commit -m "feat: register Phase 5A view tools under --enable-view"
```

---

## Task 9: Live smoke `axxon_view_smoke.py` against `100.76.150.18`

**Files:**
- Create: `tools/axxon_view_smoke.py`

- [ ] **Step 9.1: Implement the smoke**

```python
#!/usr/bin/env python3
"""Live smoke for Phase 5A view tools against a configured Axxon stand."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.request

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_view import AxxonMcpView


def sanitize_url(url: str, host: str) -> str:
    return url.replace(host, "<demo-host>")


def fetch_head(url: str, token: str, byte_cap: int) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(byte_cap + 1)
        return {
            "http_status": resp.status,
            "content_type": resp.headers.get("Content-Type"),
            "bytes_read": len(data),
            "truncated": len(data) > byte_cap,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-cameras", type=int, default=2)
    parser.add_argument("--fetch", action="store_true", help="Also fetch HEAD-equivalent for each URL.")
    args = parser.parse_args()

    view = AxxonMcpView()
    view.connect_axxon_profile("env")
    inventory = view._ensure_inventory()
    cameras = [c.get("access_point") for c in inventory.get("cameras", []) if c.get("access_point")][: args.max_cameras]
    if not cameras:
        print(json.dumps({"status": "fixture-needed", "message": "no cameras"}, indent=2))
        return 2

    results: list[dict[str, object]] = []
    results.append({"name": "live_view_mjpeg", "result": view.live_view(cameras[0], format="mjpeg")})
    results.append({"name": "live_view_hls", "result": view.live_view(cameras[0], format="hls")})
    results.append({"name": "snapshot_batch_now", "result": view.snapshot_batch(cameras)})
    results.append({"name": "archive_scrub", "result": view.archive_scrub(cameras[0], hours=1)})
    scrub = results[-1]["result"]
    intervals = scrub.get("intervals", []) if isinstance(scrub, dict) else []
    sample_ts = intervals[-1]["end"] if intervals else None
    if sample_ts:
        results.append({"name": "archive_frame", "result": view.archive_frame(cameras[0], ts=sample_ts)})
        results.append({"name": "archive_mjpeg_bounded", "result": view.archive_mjpeg_bounded(cameras[0], begin_ts=sample_ts)})
    results.append({"name": "stream_health", "result": view.stream_health(cameras[0])})

    if args.fetch:
        token = view.client.bearer_token
        host = view.client.config.host
        for entry in results:
            r = entry["result"]
            if isinstance(r, dict) and r.get("status") == "ok" and "url" in r:
                try:
                    head = fetch_head(r["url"], token, byte_cap=r["caps"].get("bytes") or 1_048_576)
                    entry["fetch"] = head
                    r["url"] = sanitize_url(r["url"], host)
                except Exception as exc:
                    entry["fetch"] = {"error": type(exc).__name__, "message": str(exc)[:160]}
            if isinstance(r, dict) and "url" in r:
                r["url"] = sanitize_url(r["url"], host)

    report = {
        "started_at": dt.datetime.now(dt.UTC).isoformat(),
        "host": "<demo-host>",
        "results": results,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9.2: Run static-only (no fetch) against the demo stand**

Pre-req: env vars set —

```bash
export AXXON_HOST=100.76.150.18
export AXXON_HTTP_URL=http://100.76.150.18
export AXXON_USERNAME=root
export AXXON_PASSWORD=root
export AXXON_TLS_CN=$(python -c "import os; print(os.environ.get('AXXON_TLS_CN',''))")  # use stand value
```

Run: `python tools/axxon_view_smoke.py`
Expected: JSON report with `status: ok` for `live_view_mjpeg`, `live_view_hls`, `snapshot_batch_now`, `archive_scrub`, `archive_frame`, `archive_mjpeg_bounded`, `stream_health`. URLs sanitized to `<demo-host>`.

- [ ] **Step 9.3: Run with `--fetch` to confirm URLs are real**

Run: `python tools/axxon_view_smoke.py --fetch`
Expected: Each fetched entry shows `http_status: 200` and `bytes_read <= caps.bytes`. Any `404` or `401` is a real bug — fix before continuing.

- [ ] **Step 9.4: Commit**

```bash
git add tools/axxon_view_smoke.py
git commit -m "feat: add axxon_view_smoke for live Phase 5A verification"
```

---

## Task 10: Sanitized evidence report

**Files:**
- Create: `docs/api-audit/phase-5a-view-smoke-latest.md`

- [ ] **Step 10.1: Capture sanitized smoke output**

Run: `python tools/axxon_view_smoke.py --fetch > /tmp/phase-5a.json`
Manually scrub any remaining `100.76.150.18` to `<demo-host>`, `hosts/Server/...` UIDs to `<demo-camera-ap>`, and confirm no bearer token or password appears.

- [ ] **Step 10.2: Write the report**

```markdown
# Phase 5A — View Tools Live Smoke

**Date:** 2026-05-16
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer
**Cap defaults:** bytes=1 MiB, duration=10 s, fps=5, archive_mjpeg=4 MiB

## Coverage

| Tool | Status | Notes |
| --- | --- | --- |
| `live_view` (mjpeg, hls) | verified | URL returned, HTTP 200 on fetch, bytes_read <= cap |
| `snapshot_batch` | verified | URLs returned per camera; gap entries for unknown APs |
| `archive_scrub` | verified | calendar + intervals + sample_frame_url combined |
| `archive_frame` | verified | threshold applied, HTTP 200 |
| `archive_mjpeg_bounded` | verified | speed/fps/byte cap applied |
| `stream_health` | verified | `/statistics/...` + `/rtsp/stat` returned |

## Sanitized smoke output

<paste sanitized JSON from /tmp/phase-5a.json>
```

- [ ] **Step 10.3: Commit**

```bash
git add docs/api-audit/phase-5a-view-smoke-latest.md
git commit -m "docs: phase 5a view-tools live smoke evidence"
```

---

## Task 11: Update coverage matrix and README

**Files:**
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `README.md`

- [ ] **Step 11.1: Add coverage matrix row**

Append at the end of the table in `docs/api-audit/pdf-gap-coverage-matrix.md`:

```markdown
| MCP view tools (live + archive viewing) | n/a | verified | bounded-stream | axxon_view_smoke.py | api-audit/phase-5a-view-smoke-latest.md | `live_view`, `snapshot_batch`, `archive_scrub`, `archive_frame`, `archive_mjpeg_bounded`, and `stream_health` are verified against the demo stand with byte/time/fps caps. URLs only — the MCP never proxies media bytes. |
```

- [ ] **Step 11.2: Update README**

In `README.md`, under the MCP server section, add a `--enable-view` line:

```bash
# + live + archive viewing tools (Phase 5A)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-view --transport stdio
```

And add a section:

```markdown
### View tools (Phase 5A)

`view_connect_axxon_profile`, `live_view`, `snapshot_batch`, `archive_scrub`,
`archive_frame`, `archive_mjpeg_bounded`, `stream_health`. URL-only — callers
fetch media with the Bearer token from `view_connect_axxon_profile`.
```

- [ ] **Step 11.3: Run full test suite as final check**

Run: `cd tools && python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: All tests pass; count is the previous 174 + ~10 new view tests + 1 new server registration test.

- [ ] **Step 11.4: Commit**

```bash
git add docs/api-audit/pdf-gap-coverage-matrix.md README.md
git commit -m "docs: register Phase 5A view tools in matrix and README"
```

---

## Self-review checklist (done)

- **Spec coverage.** Section 5A of the roadmap lists six tools: `live_view`, `snapshot_batch`, `archive_scrub`, `archive_frame`, `archive_mjpeg_bounded`, `stream_health`. Plan implements all six (Tasks 2–7) plus connect (Task 1), registration (Task 8), live smoke (Task 9), evidence (Task 10), and matrix/README (Task 11).
- **Caps.** Every tool clamps inputs against module-level constants and reports the applied value in `caps`. Smoke verifies `bytes_read <= caps.bytes`.
- **URL-only.** No tool proxies bytes; all return URLs plus an auth descriptor.
- **Sanitization.** Smoke replaces host with `<demo-host>` before printing; evidence report scrubs `hosts/Server/...` UIDs.
- **Test idioms.** `FakeConfig` and `FakeClient` follow `test_axxon_mcp_live.py` exactly; tests are offline.
- **No placeholders.** Every step has actual code. The only "paste" instruction is in Task 10.2 (sanitized JSON), which is correct — the JSON only exists after a live run.
- **Type consistency.** All tool return shapes share `status`, `tool`, `auth`, `caps`. All access points use the same `_legacy_ap` helper. The `FakeClient` gains methods in Tasks 4 and 7 — additive, no rename.
- **Demo stand.** Section "Source-of-truth references" lists `100.76.150.18:20109` / HTTP `80` / root/root. Smoke reads from env (`AXXON_HOST` etc.), never hard-codes.
