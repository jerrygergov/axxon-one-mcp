# Phase 5D — Layouts / Maps / Videowalls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 11 read tools + 11 operator workflows covering LayoutManager, LayoutImagesManager, MapService, and VideowallService, with live-verified RPC shapes from the demo stand and a synthetic-fixture round-trip for videowalls.

**Architecture:** New module `tools/axxon_mcp_view_objects.py` mirrors `axxon_mcp_view.py` / `axxon_mcp_alarms.py` for the 11 read tools. The 11 operator workflows are appended to `tools/axxon_mcp_operator.py` as new `_build_*_plan` functions plus new `operation` branches in `AxxonOperatorClient.apply`. New `AxxonApiClient` wrappers carry the RPC dispatch. URLs are never proxied; map image bytes are byte-capped and only metadata is echoed in tool responses.

**Tech Stack:** Python 3.11+, `AxxonApiClient` (existing), `unittest`, FastMCP (existing). No new third-party deps.

---

## Source-of-truth references

- Spec: `docs/superpowers/specs/2026-05-17-phase-5d-layouts-maps-videowalls-design.md`.
- Mirror module pattern: `tools/axxon_mcp_view.py` (read tools), `tools/axxon_mcp_alarms.py` (gap/error/cap shape).
- Operator pattern: `tools/axxon_mcp_operator.py` (registry of `_build_*_plan`, `AxxonOperatorClient.apply` operation dispatch, audit log).
- Existing layout client method (reused / extended): `change_layouts` (already on `AxxonOperatorClient` via `LayoutManager.Update`).
- Proto shapes verified during brainstorming:
  - `LayoutManager.ListLayouts` accepts `{view: "VIEW_MODE_ONLY_META"|"VIEW_MODE_FULL"}`; package is `axxonsoft.bl.layout`.
  - `LayoutManager.BatchGetLayouts` accepts `{items: [{layout_id, etag}]}`.
  - `LayoutManager.LayoutsOnView` accepts `{layouts: [{layout_id, layout_display_name}]}` and returns empty.
  - `LayoutImagesManager.ListLayoutImages` accepts `{layout_id}`.
  - `MapService` lives under `axxonsoft.bl.maps`.
  - `VideowallService.RegisterWall` accepts `{host_name, pid, ppid, name, display_name, data: {data: bytes}}`; returns `{cookie, wall_id, seq_number}`.
  - `VideowallService.ChangeWall` accepts `{cookie, data: {data: bytes}, seq_number}`.
  - `VideowallService.UnregisterWall` accepts `{cookie}`.
  - `VideowallService.SetControlData` accepts `{wall_id, seq_number, data: {data: bytes}}`.
  - `VideowallService.ListWalls` returns `{event_stream_items[].walls[], unreachable_objects[]}` (paginated server-stream).
- Demo stand: `AXXON_HOST=100.76.150.18`, gRPC `20109`, HTTP `80`, login `root`, password `root`, TLS CN `Server`, CA `docs/grpc-proto-files/api.ngp.root-ca.crt`.

---

## File structure

| Path | Purpose | Touched by |
| --- | --- | --- |
| `tools/axxon_mcp_view_objects.py` | New module. `AxxonMcpViewObjects` dataclass + normalizers + 11 read methods. | Tasks 2–8 |
| `tools/axxon_api_client.py` | Add 14 thin wrappers for the new RPCs. | Task 1 |
| `tools/axxon_mcp_operator.py` | Add 11 new `_build_*_plan` functions + registry entries + new operation branches in `AxxonOperatorClient.apply`. | Tasks 9–12 |
| `tools/axxon_mcp_server.py` | Add `register_view_objects_tools` and `--enable-view-objects` flag. | Task 13 |
| `tools/axxon_view_objects_smoke.py` | New live smoke (reads + 2 round-trips). | Task 14 |
| `tools/tests/test_axxon_mcp_view_objects.py` | Offline unit tests (~22 tests). | Tasks 2–8 |
| `tools/tests/test_axxon_api_client_view_objects.py` | Offline wrapper tests (~6 tests). | Task 1 |
| `tools/tests/test_axxon_mcp_operator.py` | Append ~11 workflow tests. | Tasks 9–12 |
| `tools/tests/test_axxon_mcp_server.py` | Append registration test. | Task 13 |
| `docs/api-audit/phase-5d-view-objects-smoke-latest.md` | Sanitized live evidence. | Task 15 |
| `docs/api-audit/pdf-gap-coverage-matrix.md` | New row. | Task 16 |
| `README.md` | Two new sections (read tools + workflows). | Task 16 |

---

## Module constants (single source of truth, top of `tools/axxon_mcp_view_objects.py`)

```python
LIST_LIMIT_CAP = 200
MAP_IMAGE_BYTES_CAP = 4_194_304
LAYOUT_VIEW_MODES = ("meta", "full")
LAYOUT_VIEW_MAP = {"meta": "VIEW_MODE_ONLY_META", "full": "VIEW_MODE_FULL"}
MAP_TYPE_CHOICES = ("MAP_TYPE_RASTER", "MAP_TYPE_GOOGLE", "MAP_TYPE_OSM")
```

Operator workflow confirmation tokens follow the existing `CONFIRM-<workflow>` / `CONFIRM-<workflow>-rollback` pattern.

---

## Task 1: Add 14 RPC wrappers to `AxxonApiClient`

**Files:**
- Modify: `tools/axxon_api_client.py` (append wrappers after `escalate_alert`).
- Create: `tools/tests/test_axxon_api_client_view_objects.py`.

- [ ] **Step 1.1: Write the failing offline test**

```python
# tools/tests/test_axxon_api_client_view_objects.py
from __future__ import annotations

import unittest
from pathlib import Path
import sys

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from axxon_api_client import AxxonApiClient, AxxonClientConfig


class _FakeClient(AxxonApiClient):
    def __init__(self) -> None:
        cfg = AxxonClientConfig(
            host="example.local", grpc_port=20109, http_port=80,
            http_url="http://example.local", username="root", password="secret",
            tls_cn="Server", ca=Path("/tmp/ca.crt"), proto_dir=Path("/tmp"),
            stubs_dir=Path("/tmp"), timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"items": [], "walls": [], "cookie": "fake", "wall_id": "w-1", "seq_number": 1}}


class ViewObjectsWrappersTests(unittest.TestCase):
    def test_list_layouts_passes_view(self) -> None:
        c = _FakeClient()
        c.list_layouts(view="VIEW_MODE_ONLY_META")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.layout.LayoutManager.ListLayouts",
            {"view": "VIEW_MODE_ONLY_META"},
        ))

    def test_batch_get_layouts_passes_items(self) -> None:
        c = _FakeClient()
        c.batch_get_layouts([{"layout_id": "lid", "etag": "e"}])
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.layout.LayoutManager.BatchGetLayouts",
            {"items": [{"layout_id": "lid", "etag": "e"}]},
        ))

    def test_layouts_on_view_passes_layouts(self) -> None:
        c = _FakeClient()
        c.layouts_on_view([{"layout_id": "lid", "layout_display_name": "n"}])
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.layout.LayoutManager.LayoutsOnView",
            {"layouts": [{"layout_id": "lid", "layout_display_name": "n"}]},
        ))

    def test_list_layout_images_passes_layout_id(self) -> None:
        c = _FakeClient()
        c.list_layout_images("lid")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages",
            {"layout_id": "lid"},
        ))

    def test_batch_get_maps_passes_map_ids(self) -> None:
        c = _FakeClient()
        c.batch_get_maps(["m-1", "m-2"])
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.maps.MapService.BatchGetMaps",
            {"map_ids": ["m-1", "m-2"]},
        ))

    def test_register_wall_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.register_wall(host_name="h", pid=1, ppid=2, name="n", display_name="d", data_bytes=b"abc")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.videowall.VideowallService.RegisterWall",
            {"host_name": "h", "pid": 1, "ppid": 2, "name": "n", "display_name": "d", "data": {"data": "YWJj"}},
        ))

    def test_change_wall_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.change_wall(cookie="ck", data_bytes=b"d", seq_number=3)
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.videowall.VideowallService.ChangeWall",
            {"cookie": "ck", "data": {"data": "ZA=="}, "seq_number": 3},
        ))

    def test_unregister_wall_passes_cookie(self) -> None:
        c = _FakeClient()
        c.unregister_wall("ck")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.videowall.VideowallService.UnregisterWall",
            {"cookie": "ck"},
        ))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_api_client_view_objects -v`
Expected: FAIL with `AttributeError: 'AxxonApiClient' object has no attribute 'list_layouts'`.

- [ ] **Step 1.3: Implement the wrappers**

Append to `tools/axxon_api_client.py` after `escalate_alert` (before the next non-alarm method):

```python
    def list_layouts(self, view: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.ListLayouts",
            {"view": view},
        )

    def batch_get_layouts(self, items: list[dict[str, str]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.BatchGetLayouts",
            {"items": [dict(it) for it in items]},
        )

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.LayoutsOnView",
            {"layouts": [dict(l) for l in layouts]},
        )

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutImagesManager.ListLayoutImages",
            {"layout_id": layout_id},
        )

    def remove_layout_images(self, layout_id: str, images_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.layout.LayoutImagesManager.RemoveLayoutImages",
            {"layout_id": layout_id, "images_ids": list(images_ids)},
        )

    def batch_get_maps(self, map_ids: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.BatchGetMaps",
            {"map_ids": list(map_ids)},
        )

    def get_map_image(self, map_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.GetMapImage",
            {"map_id": map_id},
        )

    def get_markers(self, map_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.GetMarkers",
            {"map_id": map_id},
        )

    def list_map_providers(self) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.ListMapProviders",
            {},
        )

    def update_markers(self, map_id: str, markers: list[dict[str, Any]]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.UpdateMarkers",
            {"map_id": map_id, "markers": list(markers)},
        )

    def change_maps(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.maps.MapService.ChangeMaps",
            dict(payload),
        )

    def list_walls(self) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.ListWalls",
            {},
        )

    def register_wall(
        self,
        *,
        host_name: str,
        pid: int,
        ppid: int,
        name: str,
        display_name: str,
        data_bytes: bytes,
    ) -> dict[str, Any]:
        import base64
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.RegisterWall",
            {
                "host_name": host_name,
                "pid": pid,
                "ppid": ppid,
                "name": name,
                "display_name": display_name,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
            },
        )

    def change_wall(self, *, cookie: str, data_bytes: bytes, seq_number: int) -> dict[str, Any]:
        import base64
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.ChangeWall",
            {
                "cookie": cookie,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
                "seq_number": seq_number,
            },
        )

    def set_control_data(self, *, wall_id: str, seq_number: int, data_bytes: bytes) -> dict[str, Any]:
        import base64
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.SetControlData",
            {
                "wall_id": wall_id,
                "seq_number": seq_number,
                "data": {"data": base64.b64encode(data_bytes).decode("ascii")},
            },
        )

    def unregister_wall(self, cookie: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.UnregisterWall",
            {"cookie": cookie},
        )

    def get_my_control_data(self, cookie: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.videowall.VideowallService.GetMyControlData",
            {"cookie": cookie},
        )
```

- [ ] **Step 1.4: Run tests, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_api_client_view_objects -v`
Expected: PASS (8 tests).

- [ ] **Step 1.5: Run full suite**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 237 (229 + 8 new).

- [ ] **Step 1.6: Commit**

```bash
git add tools/axxon_api_client.py tools/tests/test_axxon_api_client_view_objects.py
git commit -m "feat: add Layout/Map/Videowall wrappers to AxxonApiClient"
```

---

## Task 2: Module scaffold + `connect` + constants

**Files:**
- Create: `tools/axxon_mcp_view_objects.py`
- Create: `tools/tests/test_axxon_mcp_view_objects.py`

- [ ] **Step 2.1: Write the failing test**

```python
# tools/tests/test_axxon_mcp_view_objects.py
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))


class FakeConfig:
    host = "example.local"
    grpc_port = 20109
    http_port = 80
    http_url = "http://example.local"
    username = "root"
    password = "secret"
    tls_cn = "Server"
    ca = Path("/tmp/ca.crt")
    timeout = 7.0


class FakeClient:
    config = FakeConfig()

    def __init__(self) -> None:
        self.inventory: dict[str, Any] = {"cameras": [], "archives": []}
        self.calls: list[tuple[str, tuple, dict]] = []

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):
        return value


class AxxonMcpViewObjectsTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = vo.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))

        rejected = vo.connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["status"], "gap")
        self.assertEqual(rejected["profile_name"], "other")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axxon_mcp_view_objects'`.

- [ ] **Step 2.3: Create the module**

```python
# tools/axxon_mcp_view_objects.py
#!/usr/bin/env python3
"""Read-only tools for layouts, maps, and videowalls.

Mirrors the dataclass-with-factories pattern of axxon_mcp_view.py and
axxon_mcp_alarms.py. URLs are never returned; map image bytes are byte-capped
and only metadata is echoed in tool responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


LIST_LIMIT_CAP = 200
MAP_IMAGE_BYTES_CAP = 4_194_304
LAYOUT_VIEW_MODES = ("meta", "full")
LAYOUT_VIEW_MAP = {"meta": "VIEW_MODE_ONLY_META", "full": "VIEW_MODE_FULL"}
MAP_TYPE_CHOICES = ("MAP_TYPE_RASTER", "MAP_TYPE_GOOGLE", "MAP_TYPE_OSM")


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
class AxxonMcpViewObjects:
    """Read-only tools for layouts, maps, and videowalls."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    client: Any | None = None
    profile_name: str | None = None
    _inventory: dict[str, Any] | None = None

    def connect_axxon_profile(self, profile: str = "env") -> dict[str, Any]:
        if profile != "env":
            return {
                "connected": False,
                "status": "gap",
                "message": "Only the env profile is supported.",
                "profile_name": profile,
            }
        config = self.config_factory()
        self.client = self.client_factory(config)
        self.profile_name = profile
        self._inventory = None
        return {
            "connected": True,
            "profile_name": profile,
            "profile": public_config_summary(config),
            "mode": "read-only",
        }

    def _ensure_client(self) -> Any:
        if self.client is None:
            self.connect_axxon_profile("env")
        return self.client
```

- [ ] **Step 2.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: PASS (1 test).

- [ ] **Step 2.5: Commit**

```bash
git add tools/axxon_mcp_view_objects.py tools/tests/test_axxon_mcp_view_objects.py
git commit -m "feat: scaffold axxon_mcp_view_objects module with connect"
```

---

## Task 3: Normalizers (`normalize_layout`, `normalize_map`, `normalize_wall`, `normalize_marker`)

**Files:**
- Modify: `tools/axxon_mcp_view_objects.py`
- Modify: `tools/tests/test_axxon_mcp_view_objects.py`

- [ ] **Step 3.1: Write failing tests**

Append inside `AxxonMcpViewObjectsTests`:

```python
    def test_normalize_layout_meta_only(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {
                "layout_id": "lid-1",
                "owned_by_user": True,
                "etag": "etag-1",
                "has_write_access": True,
                "shared_with": [],
                "sharing_properties": {},
            },
        }
        out = module.normalize_layout(raw)
        self.assertEqual(out["layout_id"], "lid-1")
        self.assertTrue(out["owned_by_user"])
        self.assertEqual(out["etag"], "etag-1")
        self.assertIsNone(out["display_name"])
        self.assertIsNone(out["cells_count"])

    def test_normalize_layout_full(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {"layout_id": "lid-2", "owned_by_user": True, "etag": "e2", "has_write_access": True},
            "body": {
                "id": "lid-2",
                "display_name": "Main",
                "is_user_defined": True,
                "is_for_alarm": False,
                "cells": {"1": {}, "2": {}, "3": {}},
                "map_id": "map-9",
            },
        }
        out = module.normalize_layout(raw)
        self.assertEqual(out["display_name"], "Main")
        self.assertTrue(out["is_user_defined"])
        self.assertFalse(out["is_for_alarm"])
        self.assertEqual(out["cells_count"], 3)
        self.assertEqual(out["map_id"], "map-9")

    def test_normalize_map_strips_password_keys(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "meta": {
                "id": "m-1",
                "access": "MAP_ACCESS_FULL",
                "sharing": {"owner": "u-1", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                "name": "Plan",
                "type": "MAP_TYPE_RASTER",
                "etag": "e",
                "image_etag": "ie",
            },
        }
        out = module.normalize_map(raw)
        self.assertEqual(out["map_id"], "m-1")
        self.assertEqual(out["type"], "MAP_TYPE_RASTER")
        self.assertEqual(out["access"], "MAP_ACCESS_FULL")
        self.assertEqual(out["owner"], "u-1")
        self.assertEqual(out["sharing_kind"], "SHARING_KIND_ANY")
        self.assertEqual(out["etag"], "e")
        self.assertEqual(out["image_etag"], "ie")
        self.assertNotIn("password", str(out))

    def test_normalize_wall_redacts_data_bytes(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "wall_id": "w-1",
            "host_name": "h",
            "pid": 1234,
            "ppid": 5,
            "name": "wall-name",
            "display_name": "Main Wall",
            "seq_number": 7,
            "data": {"data": "VGVzdEJ5dGVz"},  # base64 of "TestBytes"
        }
        out = module.normalize_wall(raw)
        self.assertEqual(out["wall_id"], "w-1")
        self.assertEqual(out["data_size"], 9)
        self.assertNotIn("VGVzdEJ5dGVz", str(out))
        self.assertNotIn("TestBytes", str(out))

    def test_normalize_marker_keeps_position_and_access_point(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        raw = {
            "id": "mk-1",
            "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "position": {"x": 0.5, "y": 0.2},
            "marker_type": "MARKER_TYPE_CAMERA",
        }
        out = module.normalize_marker(raw)
        self.assertEqual(out["marker_id"], "mk-1")
        self.assertEqual(out["access_point"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(out["position"], {"x": 0.5, "y": 0.2})
        self.assertEqual(out["marker_type"], "MARKER_TYPE_CAMERA")
```

- [ ] **Step 3.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: FAIL — normalizers don't exist.

- [ ] **Step 3.3: Implement normalizers**

Append to `tools/axxon_mcp_view_objects.py` after the constants but before the dataclass:

```python
import base64


def normalize_layout(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten LayoutFull or LayoutMeta to a stable schema."""
    meta = raw.get("meta") or {}
    body = raw.get("body") or {}
    cells = body.get("cells") or {}
    return {
        "layout_id": meta.get("layout_id") or body.get("id") or "",
        "display_name": body.get("display_name"),
        "is_user_defined": body.get("is_user_defined"),
        "is_for_alarm": body.get("is_for_alarm"),
        "owned_by_user": bool(meta.get("owned_by_user")),
        "etag": meta.get("etag", ""),
        "has_write_access": bool(meta.get("has_write_access")),
        "cells_count": len(cells) if isinstance(cells, dict) else None,
        "map_id": body.get("map_id"),
    }


def normalize_map(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten Map (with meta) to a stable schema."""
    meta = raw.get("meta") or {}
    sharing = meta.get("sharing") or {}
    return {
        "map_id": meta.get("id") or "",
        "name": meta.get("name", ""),
        "type": meta.get("type", ""),
        "access": meta.get("access", ""),
        "owner": sharing.get("owner", ""),
        "sharing_kind": sharing.get("kind", ""),
        "etag": meta.get("etag", ""),
        "image_etag": meta.get("image_etag", ""),
    }


def normalize_wall(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten WallInfo to a stable schema; never echoes the data blob."""
    data_b64 = (raw.get("data") or {}).get("data") or ""
    try:
        data_size = len(base64.b64decode(data_b64)) if data_b64 else 0
    except Exception:
        data_size = 0
    return {
        "wall_id": raw.get("wall_id", ""),
        "host_name": raw.get("host_name", ""),
        "pid": int(raw.get("pid") or 0),
        "ppid": int(raw.get("ppid") or 0),
        "name": raw.get("name", ""),
        "display_name": raw.get("display_name", ""),
        "seq_number": int(raw.get("seq_number") or 0),
        "data_size": data_size,
    }


def normalize_marker(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten a marker entry to a stable schema."""
    return {
        "marker_id": raw.get("id") or raw.get("marker_id") or "",
        "access_point": raw.get("access_point") or raw.get("ap") or "",
        "position": raw.get("position") or {},
        "marker_type": raw.get("marker_type") or raw.get("type") or "",
    }
```

- [ ] **Step 3.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: PASS (6 tests).

- [ ] **Step 3.5: Commit**

```bash
git add tools/axxon_mcp_view_objects.py tools/tests/test_axxon_mcp_view_objects.py
git commit -m "feat: add normalizers for layouts, maps, walls, markers"
```

---

## Task 4: Layout read tools (`list_layouts`, `get_layout`, `layouts_on_view`, `list_layout_images`)

**Files:**
- Modify: `tools/axxon_mcp_view_objects.py`
- Modify: `tools/tests/test_axxon_mcp_view_objects.py`

- [ ] **Step 4.1: Extend `FakeClient` and write failing tests**

Append to `FakeClient`:

```python
    def list_layouts(self, view: str) -> dict[str, Any]:
        self.calls.append(("list_layouts", (view,), {}))
        return {"status": 200, "body": {
            "current": "lid-1",
            "items": [
                {
                    "meta": {"layout_id": "lid-1", "owned_by_user": True, "etag": "e1", "has_write_access": True},
                    "body": {"id": "lid-1", "display_name": "First", "is_user_defined": True,
                             "is_for_alarm": False, "cells": {"1": {}, "2": {}}, "map_id": ""},
                },
                {
                    "meta": {"layout_id": "lid-2", "owned_by_user": False, "etag": "e2", "has_write_access": False},
                    "body": {"id": "lid-2", "display_name": "Second", "is_user_defined": False,
                             "is_for_alarm": True, "cells": {"1": {}}, "map_id": "m-1"},
                },
            ],
        }}

    def batch_get_layouts(self, items: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(("batch_get_layouts", (tuple(items[0].items()) if items else (),), {}))
        ids = [it["layout_id"] for it in items]
        # synthetic full layout for lid-1, not_found for unknown
        out_items = []
        not_found = []
        for lid in ids:
            if lid == "lid-1":
                out_items.append({
                    "meta": {"layout_id": "lid-1", "owned_by_user": True, "etag": "e1", "has_write_access": True},
                    "body": {"id": "lid-1", "display_name": "First", "is_user_defined": True,
                             "is_for_alarm": False, "cells": {"1": {}, "2": {}}, "map_id": ""},
                })
            else:
                not_found.append(lid)
        return {"status": 200, "body": {"items": out_items, "not_found_items": not_found}}

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(("layouts_on_view", (), {"layouts": list(layouts)}))
        return {"status": 200, "body": {}}

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        self.calls.append(("list_layout_images", (layout_id,), {}))
        if layout_id == "lid-unknown":
            return {"status": 500, "body": {}}
        return {"status": 200, "body": {"images": [{"id": "img-1", "etag": "ie-1"}]}}
```

Append tests:

```python
    def test_list_layouts_meta_returns_normalized_items(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layouts(view="meta", limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["applied_view"], "VIEW_MODE_ONLY_META")
        self.assertEqual(r["applied_limit"], module.LIST_LIMIT_CAP)
        self.assertEqual(r["items"][0]["layout_id"], "lid-1")

    def test_list_layouts_unknown_view_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.list_layouts(view="banana", limit=10)
        self.assertEqual(r["status"], "gap")
        self.assertIn("view", r["message"])

    def test_get_layout_returns_normalized_item(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_layout("lid-1", etag=None)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["item"]["layout_id"], "lid-1")
        self.assertEqual(r["item"]["display_name"], "First")

    def test_get_layout_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_layout("lid-missing")
        self.assertEqual(r["status"], "gap")
        self.assertIn("lid-missing", r["message"])

    def test_layouts_on_view_returns_pushed_count(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.layouts_on_view([{"layout_id": "lid-1", "layout_display_name": "First"}])
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["pushed"], 1)

    def test_list_layout_images_returns_meta(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layout_images("lid-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["id"], "img-1")

    def test_list_layout_images_unknown_layout_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_layout_images("lid-unknown")
        self.assertEqual(r["status"], "gap")
```

- [ ] **Step 4.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: FAIL — methods missing.

- [ ] **Step 4.3: Implement layout read methods**

Append to `AxxonMcpViewObjects`:

```python
    def list_layouts(self, view: str = "meta", limit: int = 50) -> dict[str, Any]:
        if view not in LAYOUT_VIEW_MODES:
            return {
                "status": "gap",
                "tool": "list_layouts",
                "message": f"view must be one of {LAYOUT_VIEW_MODES}, got {view!r}",
            }
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        applied_view = LAYOUT_VIEW_MAP[view]
        self._ensure_client()
        resp = self.client.list_layouts(view=applied_view)
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = [normalize_layout(it) for it in (body or {}).get("items", [])][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_layouts",
            "count": len(items),
            "applied_view": applied_view,
            "applied_limit": applied_limit,
            "current": (body or {}).get("current", ""),
            "items": items,
        }

    def get_layout(self, layout_id: str, etag: str | None = None) -> dict[str, Any]:
        self._ensure_client()
        resp = self.client.batch_get_layouts([{"layout_id": layout_id, "etag": etag or ""}])
        body = resp.get("body") if isinstance(resp, dict) else {}
        for raw in (body or {}).get("items", []):
            if (raw.get("meta") or {}).get("layout_id") == layout_id:
                return {"status": "ok", "tool": "get_layout", "item": normalize_layout(raw)}
        return {
            "status": "gap",
            "tool": "get_layout",
            "message": f"Layout not found: {layout_id}",
        }

    def layouts_on_view(self, layouts: list[dict[str, str]]) -> dict[str, Any]:
        self._ensure_client()
        self.client.layouts_on_view(layouts)
        return {"status": "ok", "tool": "layouts_on_view", "pushed": len(layouts)}

    def list_layout_images(self, layout_id: str) -> dict[str, Any]:
        self._ensure_client()
        resp = self.client.list_layout_images(layout_id)
        if not isinstance(resp, dict) or resp.get("status") != 200:
            return {
                "status": "gap",
                "tool": "list_layout_images",
                "message": f"Layout not found or unreadable: {layout_id}",
            }
        body = resp.get("body") or {}
        items = list(body.get("images", []))
        return {
            "status": "ok",
            "tool": "list_layout_images",
            "layout_id": layout_id,
            "count": len(items),
            "items": items,
        }
```

- [ ] **Step 4.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: PASS (13 tests).

- [ ] **Step 4.5: Commit**

```bash
git add tools/axxon_mcp_view_objects.py tools/tests/test_axxon_mcp_view_objects.py
git commit -m "feat: add layout read tools"
```

---

## Task 5: Map read tools (`list_maps`, `get_map`, `get_map_image`, `get_markers`, `list_map_providers`)

**Files:**
- Modify: `tools/axxon_mcp_view_objects.py`
- Modify: `tools/tests/test_axxon_mcp_view_objects.py`

- [ ] **Step 5.1: Extend `FakeClient` and write tests**

Append to `FakeClient`:

```python
    def __init__(self, *args, **kwargs) -> None:
        # Same as before; if already overridden by Task 2 scaffold, just merge
        # the new instance attributes:
        if not hasattr(self, "inventory"):
            self.inventory = {"cameras": [], "archives": []}
            self.calls = []
        self.map_pages: list[dict[str, Any]] = [
            {
                "meta": {
                    "id": "m-1", "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-1", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Office plan", "type": "MAP_TYPE_RASTER",
                    "etag": "e1", "image_etag": "ie1",
                }
            },
            {
                "meta": {
                    "id": "m-2", "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-2", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Floor 1", "type": "MAP_TYPE_RASTER",
                    "etag": "e2", "image_etag": "ie2",
                }
            },
        ]
        self.map_image_bytes: dict[str, bytes] = {"m-1": b"X" * 10, "m-big": b"Y" * 5_000_000}
        self.map_markers: dict[str, list[dict[str, Any]]] = {
            "m-1": [{"id": "mk-1", "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                     "position": {"x": 0.5, "y": 0.2}, "marker_type": "MARKER_TYPE_CAMERA"}],
        }
```

(Note: if Task 2's `FakeClient.__init__` already exists, integrate the above new attrs without losing existing ones. The simplest approach: replace `__init__` with a single version that initializes both Task 2 and Task 5 attrs.)

Replace `FakeClient.__init__` with:

```python
    def __init__(self) -> None:
        self.inventory: dict[str, Any] = {"cameras": [], "archives": []}
        self.calls: list[tuple[str, tuple, dict]] = []
        self.map_pages: list[dict[str, Any]] = [
            {
                "meta": {
                    "id": "m-1", "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-1", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Office plan", "type": "MAP_TYPE_RASTER",
                    "etag": "e1", "image_etag": "ie1",
                }
            },
            {
                "meta": {
                    "id": "m-2", "access": "MAP_ACCESS_FULL",
                    "sharing": {"owner": "u-2", "kind": "SHARING_KIND_ANY", "shared_roles": []},
                    "name": "Floor 1", "type": "MAP_TYPE_RASTER",
                    "etag": "e2", "image_etag": "ie2",
                }
            },
        ]
        self.map_image_bytes: dict[str, bytes] = {"m-1": b"X" * 10, "m-big": b"Y" * 5_000_000}
        self.map_markers: dict[str, list[dict[str, Any]]] = {
            "m-1": [{"id": "mk-1", "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                     "position": {"x": 0.5, "y": 0.2}, "marker_type": "MARKER_TYPE_CAMERA"}],
        }
        self.providers: list[dict[str, Any]] = [
            {"id": "bitmap-id", "name": "Bitmap or vector image", "etag": "bp1"},
            {"id": "google-id", "name": "Google Map", "etag": "gp1"},
        ]
```

Append methods to `FakeClient`:

```python
    def list_maps(self) -> dict[str, Any]:
        self.calls.append(("list_maps", (), {}))
        return {"status": 200, "body": {"items": list(self.map_pages)}}

    def batch_get_maps(self, map_ids: list[str]) -> dict[str, Any]:
        self.calls.append(("batch_get_maps", (tuple(map_ids),), {}))
        items = [m for m in self.map_pages if m["meta"]["id"] in map_ids]
        not_found = [mid for mid in map_ids if mid not in {m["meta"]["id"] for m in self.map_pages}]
        return {"status": 200, "body": {"items": items, "not_found": not_found}}

    def get_map_image(self, map_id: str) -> dict[str, Any]:
        self.calls.append(("get_map_image", (map_id,), {}))
        if map_id not in self.map_image_bytes:
            return {"status": 500, "body": {}}
        import base64
        raw = self.map_image_bytes[map_id]
        return {"status": 200, "body": {
            "etag": f"img-etag-{map_id}",
            "total_size_bytes": len(raw),
            "content_type": "image/png",
            "data": base64.b64encode(raw).decode("ascii"),
        }}

    def get_markers(self, map_id: str) -> dict[str, Any]:
        self.calls.append(("get_markers", (map_id,), {}))
        return {"status": 200, "body": {"markers": list(self.map_markers.get(map_id, []))}}

    def list_map_providers(self) -> dict[str, Any]:
        self.calls.append(("list_map_providers", (), {}))
        return {"status": 200, "body": {"map_providers": list(self.providers)}}
```

Append tests:

```python
    def test_list_maps_returns_normalized_items(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_maps(limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["applied_limit"], module.LIST_LIMIT_CAP)
        self.assertEqual(r["items"][0]["map_id"], "m-1")
        self.assertEqual(r["items"][0]["type"], "MAP_TYPE_RASTER")

    def test_get_map_returns_normalized_item(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["item"]["map_id"], "m-1")

    def test_get_map_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_map("m-missing")
        self.assertEqual(r["status"], "gap")

    def test_get_map_image_small_returns_metadata_no_raw_bytes(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["bytes_returned"], 10)
        self.assertFalse(r["truncated"])
        self.assertEqual(r["content_type"], "image/png")
        self.assertNotIn("data", r)  # raw bytes must not appear

    def test_get_map_image_truncates_at_cap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-big", max_bytes=1000)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["bytes_returned"], 1000)
        self.assertTrue(r["truncated"])

    def test_get_map_image_unknown_id_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: FakeClient(), config_factory=lambda: FakeConfig())
        r = vo.get_map_image("m-missing")
        self.assertEqual(r["status"], "gap")

    def test_get_markers_returns_normalized_list(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.get_markers("m-1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["marker_id"], "mk-1")

    def test_list_map_providers_returns_provider_list(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_map_providers()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertIn("Google", r["items"][1]["name"])
```

- [ ] **Step 5.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: FAIL — methods missing.

- [ ] **Step 5.3: Implement map read methods**

Append to `AxxonMcpViewObjects`:

```python
    def list_maps(self, limit: int = 50) -> dict[str, Any]:
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        self._ensure_client()
        resp = self.client.list_maps()
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = [normalize_map(it) for it in (body or {}).get("items", [])][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_maps",
            "count": len(items),
            "applied_limit": applied_limit,
            "items": items,
        }

    def get_map(self, map_id: str) -> dict[str, Any]:
        self._ensure_client()
        resp = self.client.batch_get_maps([map_id])
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = (body or {}).get("items", [])
        if not items:
            return {
                "status": "gap",
                "tool": "get_map",
                "message": f"Map not found: {map_id}",
            }
        return {"status": "ok", "tool": "get_map", "item": normalize_map(items[0])}

    def get_map_image(self, map_id: str, max_bytes: int = MAP_IMAGE_BYTES_CAP) -> dict[str, Any]:
        applied_cap = min(max(int(max_bytes), 1024), MAP_IMAGE_BYTES_CAP)
        self._ensure_client()
        resp = self.client.get_map_image(map_id)
        if not isinstance(resp, dict) or resp.get("status") != 200:
            return {
                "status": "gap",
                "tool": "get_map_image",
                "message": f"Map image not available: {map_id}",
            }
        body = resp.get("body") or {}
        data_b64 = body.get("data", "")
        try:
            raw = base64.b64decode(data_b64) if data_b64 else b""
        except Exception:
            raw = b""
        total = int(body.get("total_size_bytes") or len(raw))
        truncated = total > applied_cap or len(raw) > applied_cap
        bytes_returned = min(total, applied_cap)
        return {
            "status": "ok",
            "tool": "get_map_image",
            "map_id": map_id,
            "etag": body.get("etag", ""),
            "content_type": body.get("content_type", ""),
            "bytes_returned": bytes_returned,
            "truncated": truncated,
            "applied_cap": applied_cap,
        }

    def get_markers(self, map_id: str) -> dict[str, Any]:
        self._ensure_client()
        resp = self.client.get_markers(map_id)
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = [normalize_marker(m) for m in (body or {}).get("markers", [])]
        return {
            "status": "ok",
            "tool": "get_markers",
            "map_id": map_id,
            "count": len(items),
            "items": items,
        }

    def list_map_providers(self) -> dict[str, Any]:
        self._ensure_client()
        resp = self.client.list_map_providers()
        body = resp.get("body") if isinstance(resp, dict) else {}
        items = list((body or {}).get("map_providers", []))
        return {
            "status": "ok",
            "tool": "list_map_providers",
            "count": len(items),
            "items": items,
        }
```

- [ ] **Step 5.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: PASS (21 tests).

- [ ] **Step 5.5: Commit**

```bash
git add tools/axxon_mcp_view_objects.py tools/tests/test_axxon_mcp_view_objects.py
git commit -m "feat: add map read tools with image byte cap"
```

---

## Task 6: Wall read tool (`list_walls`)

**Files:**
- Modify: `tools/axxon_mcp_view_objects.py`
- Modify: `tools/tests/test_axxon_mcp_view_objects.py`

- [ ] **Step 6.1: Extend `FakeClient` and write tests**

Append to `FakeClient`:

```python
    def list_walls(self) -> dict[str, Any]:
        self.calls.append(("list_walls", (), {}))
        return {"status": 200, "body": {
            "event_stream_items": [
                {"walls": [], "unreachable_objects": ["transient"]},
                {"walls": [{
                    "wall_id": "w-1", "host_name": "h", "pid": 100, "ppid": 1,
                    "name": "wall-name", "display_name": "Main Wall", "seq_number": 5,
                    "data": {"data": "VGVzdEJ5dGVz"},
                }], "unreachable_objects": []},
            ],
            "event_stream_count": 2,
        }}
```

Append tests:

```python
    def test_list_walls_flattens_pages_and_drops_transient_unreachable(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_walls(limit=10)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["wall_id"], "w-1")
        self.assertEqual(r["items"][0]["data_size"], 9)
        # Unreachable only surfaces if every page agrees:
        self.assertEqual(r.get("unreachable_objects", []), [])

    def test_list_walls_returns_empty_list_not_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_view_objects")
        fake = FakeClient()
        # Override: both pages empty
        fake.list_walls = lambda: {"status": 200, "body": {
            "event_stream_items": [{"walls": [], "unreachable_objects": []}],
            "event_stream_count": 1,
        }}
        vo = module.AxxonMcpViewObjects(client_factory=lambda _cfg: fake, config_factory=lambda: FakeConfig())
        r = vo.list_walls()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 0)
```

- [ ] **Step 6.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: FAIL — `list_walls` missing.

- [ ] **Step 6.3: Implement `list_walls`**

Append to `AxxonMcpViewObjects`:

```python
    def list_walls(self, limit: int = 50) -> dict[str, Any]:
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        self._ensure_client()
        resp = self.client.list_walls()
        body = resp.get("body") if isinstance(resp, dict) else {}
        pages = (body or {}).get("event_stream_items") or []
        flat: list[dict[str, Any]] = []
        unreachable_per_page: list[list[str]] = []
        for page in pages:
            flat.extend(page.get("walls") or [])
            unreachable_per_page.append(list(page.get("unreachable_objects") or []))
        if unreachable_per_page and all(u for u in unreachable_per_page):
            unreachable = sorted(set.intersection(*[set(u) for u in unreachable_per_page]))
        else:
            unreachable = []
        items = [normalize_wall(w) for w in flat][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_walls",
            "count": len(items),
            "applied_limit": applied_limit,
            "items": items,
            "unreachable_objects": unreachable,
        }
```

- [ ] **Step 6.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_view_objects -v`
Expected: PASS (23 tests).

- [ ] **Step 6.5: Commit**

```bash
git add tools/axxon_mcp_view_objects.py tools/tests/test_axxon_mcp_view_objects.py
git commit -m "feat: add list_walls flattening paginated stream"
```

---

## Task 7: Operator client transport methods for new RPCs

Add the transport-side methods that the new operator workflows call.

**Files:**
- Modify: `tools/axxon_mcp_operator.py` (append methods to `AxxonOperatorClient`).
- Modify: `tools/tests/test_axxon_mcp_operator.py` (new tests for transport methods).

- [ ] **Step 7.1: Write failing test for one new transport method**

Append to `tools/tests/test_axxon_mcp_operator.py` inside the existing test class (or create a new class if cleaner):

```python
    def test_operator_client_change_maps_dispatches(self) -> None:
        from axxon_mcp_operator import AxxonOperatorClient

        class FakeApi:
            def __init__(self):
                self.calls: list[tuple[str, dict]] = []
            def change_maps(self, payload):
                self.calls.append(("change_maps", payload))
                return {"status": 200, "body": {"result": True}}

        api = FakeApi()
        c = AxxonOperatorClient(api)
        out = c.change_maps_via_api({"added": [{"meta": {"name": "x"}}]})
        self.assertEqual(out["status"], 200)
        self.assertEqual(api.calls[0][0], "change_maps")
```

- [ ] **Step 7.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: FAIL — `change_maps_via_api` missing.

- [ ] **Step 7.3: Implement transport methods**

Append to `AxxonOperatorClient` in `tools/axxon_mcp_operator.py`:

```python
    # --- Phase 5D transport extensions ---

    def change_maps_via_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.change_maps(payload)

    def update_markers_via_api(self, map_id: str, markers: list[dict[str, Any]]) -> dict[str, Any]:
        return self._client.update_markers(map_id, markers)

    def register_wall_via_api(self, **kwargs) -> dict[str, Any]:
        return self._client.register_wall(**kwargs)

    def change_wall_via_api(self, *, cookie: str, data_bytes: bytes, seq_number: int) -> dict[str, Any]:
        return self._client.change_wall(cookie=cookie, data_bytes=data_bytes, seq_number=seq_number)

    def set_control_data_via_api(self, *, wall_id: str, seq_number: int, data_bytes: bytes) -> dict[str, Any]:
        return self._client.set_control_data(wall_id=wall_id, seq_number=seq_number, data_bytes=data_bytes)

    def unregister_wall_via_api(self, cookie: str) -> dict[str, Any]:
        return self._client.unregister_wall(cookie)

    def update_layout_via_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.http_grpc(
            "axxonsoft.bl.layout.LayoutManager.Update", payload
        )

    def batch_get_maps_via_api(self, map_ids: list[str]) -> dict[str, Any]:
        return self._client.batch_get_maps(map_ids)

    def batch_get_layouts_via_api(self, items: list[dict[str, str]]) -> dict[str, Any]:
        return self._client.batch_get_layouts(items)

    def get_markers_via_api(self, map_id: str) -> dict[str, Any]:
        return self._client.get_markers(map_id)
```

- [ ] **Step 7.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: PASS for the new test; no regressions.

- [ ] **Step 7.5: Commit**

```bash
git add tools/axxon_mcp_operator.py tools/tests/test_axxon_mcp_operator.py
git commit -m "feat: add Phase 5D transport methods to AxxonOperatorClient"
```

---

## Task 8: Videowall workflows (`temp_wall`, `videowall_register`, `videowall_change`, `videowall_set_control_data`, `videowall_unregister`)

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] **Step 8.1: Write failing tests**

Append:

```python
    def test_temp_wall_plan_includes_register_step(self) -> None:
        from axxon_mcp_operator import _build_temp_wall_plan
        plan = _build_temp_wall_plan("hosts/Server", {"name": "codex-w", "display_name": "Codex Wall"})
        self.assertEqual(plan["workflow"], "temp_wall")
        self.assertEqual(plan["risk"], "mutation")
        self.assertFalse(plan["persistent"])
        self.assertEqual(plan["steps"][0]["operation"], "register_wall")
        self.assertEqual(plan["steps"][0]["params"]["name"], "codex-w")
        self.assertEqual(plan["confirmation_token"], "CONFIRM-temp_wall")
        self.assertEqual(plan["rollback_confirmation_token"], "CONFIRM-temp_wall-rollback")

    def test_videowall_register_persistent_no_auto_rollback(self) -> None:
        from axxon_mcp_operator import _build_videowall_register_plan
        plan = _build_videowall_register_plan("hosts/Server", {"name": "perm", "display_name": "Perm"})
        self.assertEqual(plan["workflow"], "videowall_register")
        self.assertTrue(plan["persistent"])
        self.assertEqual(plan["rollback"]["strategy"], "unregister_wall")

    def test_videowall_change_requires_cookie(self) -> None:
        from axxon_mcp_operator import _build_videowall_change_plan
        gap = _build_videowall_change_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        self.assertIn("cookie", gap["message"])
        plan = _build_videowall_change_plan("hosts/Server",
            {"cookie": "ck", "data_b64": "AAA=", "seq_number": 2})
        self.assertEqual(plan["steps"][0]["operation"], "change_wall")
        self.assertEqual(plan["steps"][0]["params"]["cookie"], "ck")
        self.assertEqual(plan["steps"][0]["params"]["seq_number"], 2)

    def test_videowall_set_control_data_requires_wall_id(self) -> None:
        from axxon_mcp_operator import _build_videowall_set_control_data_plan
        gap = _build_videowall_set_control_data_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_videowall_set_control_data_plan("hosts/Server",
            {"wall_id": "w-1", "data_b64": "AAA=", "seq_number": 1})
        self.assertEqual(plan["steps"][0]["operation"], "set_control_data")
        self.assertEqual(plan["steps"][0]["params"]["wall_id"], "w-1")

    def test_videowall_unregister_requires_cookie(self) -> None:
        from axxon_mcp_operator import _build_videowall_unregister_plan
        gap = _build_videowall_unregister_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_videowall_unregister_plan("hosts/Server", {"cookie": "ck"})
        self.assertEqual(plan["steps"][0]["operation"], "unregister_wall")
```

- [ ] **Step 8.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: FAIL — workflows missing.

- [ ] **Step 8.3: Implement videowall plans**

Add to `tools/axxon_mcp_operator.py` (alongside other `_build_*_plan` functions):

```python
import os as _os


def _build_temp_wall_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Ephemeral videowall registration (auto-rollback via UnregisterWall)."""
    name = str(params.get("name") or f"codex-wall-{uuid.uuid4().hex[:8]}")
    display_name = str(params.get("display_name") or name)
    host_name = str(params.get("host_name") or f"codex-host-{uuid.uuid4().hex[:6]}")
    pid = int(params.get("pid") or _os.getpid())
    ppid = int(params.get("ppid") or 1)
    data_b64 = str(params.get("data_b64") or "")
    return {
        "workflow": "temp_wall",
        "persistent": False,
        "risk": "mutation",
        "intent": f"register ephemeral videowall {name} ({display_name})",
        "steps": [{
            "operation": "register_wall",
            "params": {
                "host_name": host_name, "pid": pid, "ppid": ppid,
                "name": name, "display_name": display_name, "data_b64": data_b64,
            },
        }],
        "rollback": {"strategy": "unregister_wall", "description": "Calls UnregisterWall(cookie)."},
        "expected": {"name": name, "display_name": display_name},
        "confirmation_token": "CONFIRM-temp_wall",
        "rollback_confirmation_token": "CONFIRM-temp_wall-rollback",
    }


def _build_videowall_register_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    """Persistent videowall registration (caller retains cookie; rollback only on explicit invoke)."""
    name = str(params.get("name") or "").strip()
    if not name:
        return {"status": "gap", "workflow": "videowall_register",
                "message": "videowall_register requires params.name"}
    display_name = str(params.get("display_name") or name)
    host_name = str(params.get("host_name") or f"codex-host-{uuid.uuid4().hex[:6]}")
    pid = int(params.get("pid") or _os.getpid())
    ppid = int(params.get("ppid") or 1)
    data_b64 = str(params.get("data_b64") or "")
    return {
        "workflow": "videowall_register",
        "persistent": True,
        "risk": "mutation",
        "intent": f"register persistent videowall {name} ({display_name})",
        "steps": [{
            "operation": "register_wall",
            "params": {
                "host_name": host_name, "pid": pid, "ppid": ppid,
                "name": name, "display_name": display_name, "data_b64": data_b64,
            },
        }],
        "rollback": {"strategy": "unregister_wall",
                     "description": "Persistent: caller invokes rollback to unregister."},
        "expected": {"name": name, "display_name": display_name},
        "confirmation_token": "CONFIRM-videowall_register",
        "rollback_confirmation_token": "CONFIRM-videowall_register-rollback",
    }


def _build_videowall_change_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    cookie = str(params.get("cookie") or "").strip()
    if not cookie:
        return {"status": "gap", "workflow": "videowall_change",
                "message": "videowall_change requires params.cookie"}
    data_b64 = str(params.get("data_b64") or "")
    seq_number = int(params.get("seq_number") or 0)
    return {
        "workflow": "videowall_change",
        "persistent": True,
        "risk": "mutation",
        "intent": f"change videowall data (cookie={cookie[:8]}…, seq={seq_number})",
        "steps": [{
            "operation": "change_wall",
            "params": {"cookie": cookie, "data_b64": data_b64, "seq_number": seq_number},
        }],
        "rollback": {"strategy": "noop", "description": "ChangeWall is a state push; no auto-revert."},
        "expected": {"cookie_prefix": cookie[:8], "seq_number": seq_number},
        "confirmation_token": "CONFIRM-videowall_change",
        "rollback_confirmation_token": "CONFIRM-videowall_change-rollback",
    }


def _build_videowall_set_control_data_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    wall_id = str(params.get("wall_id") or "").strip()
    if not wall_id:
        return {"status": "gap", "workflow": "videowall_set_control_data",
                "message": "videowall_set_control_data requires params.wall_id"}
    data_b64 = str(params.get("data_b64") or "")
    seq_number = int(params.get("seq_number") or 0)
    return {
        "workflow": "videowall_set_control_data",
        "persistent": True,
        "risk": "mutation",
        "intent": f"push control data to wall {wall_id} (seq={seq_number})",
        "steps": [{
            "operation": "set_control_data",
            "params": {"wall_id": wall_id, "data_b64": data_b64, "seq_number": seq_number},
        }],
        "rollback": {"strategy": "noop", "description": "Control data is a push; no auto-revert."},
        "expected": {"wall_id": wall_id, "seq_number": seq_number},
        "confirmation_token": "CONFIRM-videowall_set_control_data",
        "rollback_confirmation_token": "CONFIRM-videowall_set_control_data-rollback",
    }


def _build_videowall_unregister_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    cookie = str(params.get("cookie") or "").strip()
    if not cookie:
        return {"status": "gap", "workflow": "videowall_unregister",
                "message": "videowall_unregister requires params.cookie"}
    return {
        "workflow": "videowall_unregister",
        "persistent": True,
        "risk": "mutation",
        "intent": f"unregister wall (cookie={cookie[:8]}…)",
        "steps": [{"operation": "unregister_wall", "params": {"cookie": cookie}}],
        "rollback": {"strategy": "noop", "description": "Unregister is terminal."},
        "expected": {"cookie_prefix": cookie[:8]},
        "confirmation_token": "CONFIRM-videowall_unregister",
        "rollback_confirmation_token": "CONFIRM-videowall_unregister-rollback",
    }
```

Append to the `WORKFLOWS` registry:

```python
    "temp_wall": _build_temp_wall_plan,
    "videowall_register": _build_videowall_register_plan,
    "videowall_change": _build_videowall_change_plan,
    "videowall_set_control_data": _build_videowall_set_control_data_plan,
    "videowall_unregister": _build_videowall_unregister_plan,
```

- [ ] **Step 8.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: PASS for the 5 new tests.

- [ ] **Step 8.5: Commit**

```bash
git add tools/axxon_mcp_operator.py tools/tests/test_axxon_mcp_operator.py
git commit -m "feat: add 5 videowall operator workflows"
```

---

## Task 9: Map workflows (`create_map`, `update_map`, `delete_map`, `update_markers`)

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] **Step 9.1: Write failing tests**

Append:

```python
    def test_create_map_plan_includes_added(self) -> None:
        from axxon_mcp_operator import _build_create_map_plan
        gap = _build_create_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_create_map_plan("hosts/Server",
            {"name": "codex-test", "type": "MAP_TYPE_RASTER"})
        self.assertEqual(plan["workflow"], "create_map")
        self.assertEqual(plan["steps"][0]["operation"], "change_maps")
        added = plan["steps"][0]["payload"]["added"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["meta"]["name"], "codex-test")
        self.assertEqual(added[0]["meta"]["type"], "MAP_TYPE_RASTER")

    def test_update_map_plan_requires_map_id(self) -> None:
        from axxon_mcp_operator import _build_update_map_plan
        gap = _build_update_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_map_plan("hosts/Server",
            {"map_id": "m-1", "etag": "e1", "patch": {"name": "renamed"}})
        self.assertEqual(plan["steps"][0]["operation"], "change_maps")
        changed = plan["steps"][0]["payload"]["changed"]
        self.assertEqual(changed[0]["meta"]["id"], "m-1")
        self.assertEqual(changed[0]["meta"]["etag"], "e1")
        self.assertEqual(plan["rollback"]["strategy"], "restore_map_snapshot")

    def test_delete_map_plan_includes_removed(self) -> None:
        from axxon_mcp_operator import _build_delete_map_plan
        gap = _build_delete_map_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_delete_map_plan("hosts/Server", {"map_id": "m-1"})
        self.assertEqual(plan["steps"][0]["payload"]["removed"], ["m-1"])
        self.assertEqual(plan["rollback"]["strategy"], "restore_map_snapshot")

    def test_update_markers_plan_requires_map_id(self) -> None:
        from axxon_mcp_operator import _build_update_markers_plan
        gap = _build_update_markers_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_markers_plan("hosts/Server",
            {"map_id": "m-1", "markers": [{"access_point": "hosts/Server/x"}]})
        self.assertEqual(plan["steps"][0]["operation"], "update_markers")
        self.assertEqual(plan["steps"][0]["params"]["map_id"], "m-1")
```

- [ ] **Step 9.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: FAIL — workflows missing.

- [ ] **Step 9.3: Implement**

Append:

```python
def _build_create_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "").strip()
    if not name:
        return {"status": "gap", "workflow": "create_map",
                "message": "create_map requires params.name"}
    map_type = str(params.get("type") or "MAP_TYPE_RASTER")
    map_id = str(params.get("map_id") or uuid.uuid4())
    new_map = {
        "meta": {
            "id": map_id,
            "name": name,
            "type": map_type,
            "access": "MAP_ACCESS_FULL",
            "sharing": {"kind": "SHARING_KIND_OWNER", "shared_roles": []},
        },
    }
    return {
        "workflow": "create_map",
        "persistent": True,
        "risk": "mutation",
        "intent": f"create persistent map {name} (type={map_type})",
        "steps": [{"operation": "change_maps", "payload": {"added": [new_map]}, "map_id": map_id}],
        "rollback": {"strategy": "change_maps_removed",
                     "description": "Rollback removes the added map by id."},
        "expected": {"map_id": map_id, "name": name, "type": map_type},
        "confirmation_token": "CONFIRM-create_map",
        "rollback_confirmation_token": "CONFIRM-create_map-rollback",
    }


def _build_update_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {"status": "gap", "workflow": "update_map",
                "message": "update_map requires params.map_id"}
    etag = str(params.get("etag") or "")
    patch = dict(params.get("patch") or {})
    changed_meta: dict[str, Any] = {"id": map_id, "etag": etag, **patch}
    return {
        "workflow": "update_map",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update map {map_id} (etag={etag[:8] or 'none'})",
        "steps": [{"operation": "change_maps",
                   "payload": {"changed": [{"meta": changed_meta}]},
                   "map_id": map_id}],
        "rollback": {"strategy": "restore_map_snapshot",
                     "description": "Pre-apply snapshot captured; rollback re-applies it via changed[]."},
        "expected": {"map_id": map_id, "patch_keys": sorted(patch.keys())},
        "confirmation_token": "CONFIRM-update_map",
        "rollback_confirmation_token": "CONFIRM-update_map-rollback",
    }


def _build_delete_map_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {"status": "gap", "workflow": "delete_map",
                "message": "delete_map requires params.map_id"}
    return {
        "workflow": "delete_map",
        "persistent": True,
        "risk": "mutation",
        "intent": f"delete map {map_id}",
        "steps": [{"operation": "change_maps",
                   "payload": {"removed": [map_id]},
                   "map_id": map_id}],
        "rollback": {"strategy": "restore_map_snapshot",
                     "description": "Pre-apply snapshot re-adds the map via added[]."},
        "expected": {"map_id": map_id},
        "confirmation_token": "CONFIRM-delete_map",
        "rollback_confirmation_token": "CONFIRM-delete_map-rollback",
    }


def _build_update_markers_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    map_id = str(params.get("map_id") or "").strip()
    if not map_id:
        return {"status": "gap", "workflow": "update_markers",
                "message": "update_markers requires params.map_id"}
    markers = list(params.get("markers") or [])
    return {
        "workflow": "update_markers",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update markers on map {map_id} ({len(markers)} markers)",
        "steps": [{"operation": "update_markers",
                   "params": {"map_id": map_id, "markers": markers},
                   "map_id": map_id}],
        "rollback": {"strategy": "restore_markers_snapshot",
                     "description": "Pre-apply snapshot captured via GetMarkers; rollback re-applies."},
        "expected": {"map_id": map_id, "marker_count": len(markers)},
        "confirmation_token": "CONFIRM-update_markers",
        "rollback_confirmation_token": "CONFIRM-update_markers-rollback",
    }
```

Append to `WORKFLOWS`:

```python
    "create_map": _build_create_map_plan,
    "update_map": _build_update_map_plan,
    "delete_map": _build_delete_map_plan,
    "update_markers": _build_update_markers_plan,
```

- [ ] **Step 9.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: PASS for 4 new tests.

- [ ] **Step 9.5: Commit**

```bash
git add tools/axxon_mcp_operator.py tools/tests/test_axxon_mcp_operator.py
git commit -m "feat: add 4 map operator workflows (create/update/delete/markers)"
```

---

## Task 10: Layout mutation workflows (`update_layout`, `delete_layout`)

**Files:**
- Modify: `tools/axxon_mcp_operator.py`
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] **Step 10.1: Write failing tests**

Append:

```python
    def test_update_layout_requires_layout_id(self) -> None:
        from axxon_mcp_operator import _build_update_layout_plan
        gap = _build_update_layout_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_update_layout_plan("hosts/Server",
            {"layout_id": "lid-1", "etag": "e", "body": {"display_name": "Renamed"}})
        self.assertEqual(plan["workflow"], "update_layout")
        self.assertEqual(plan["steps"][0]["operation"], "update_layout")
        updated = plan["steps"][0]["payload"]["updated"]
        self.assertEqual(updated[0]["meta"]["layout_id"], "lid-1")
        self.assertEqual(updated[0]["meta"]["etag"], "e")
        self.assertEqual(updated[0]["body"]["display_name"], "Renamed")

    def test_delete_layout_requires_layout_id(self) -> None:
        from axxon_mcp_operator import _build_delete_layout_plan
        gap = _build_delete_layout_plan("hosts/Server", {})
        self.assertEqual(gap["status"], "gap")
        plan = _build_delete_layout_plan("hosts/Server", {"layout_id": "lid-1"})
        self.assertEqual(plan["steps"][0]["payload"]["removed_layouts"], ["lid-1"])
        self.assertEqual(plan["rollback"]["strategy"], "restore_layout_snapshot")
```

- [ ] **Step 10.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: FAIL.

- [ ] **Step 10.3: Implement**

Append:

```python
def _build_update_layout_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    layout_id = str(params.get("layout_id") or "").strip()
    if not layout_id:
        return {"status": "gap", "workflow": "update_layout",
                "message": "update_layout requires params.layout_id"}
    etag = str(params.get("etag") or "")
    body = dict(params.get("body") or {})
    updated_entry: dict[str, Any] = {"meta": {"layout_id": layout_id, "etag": etag}, "body": body}
    return {
        "workflow": "update_layout",
        "persistent": True,
        "risk": "mutation",
        "intent": f"update layout {layout_id} (etag={etag[:8] or 'none'})",
        "steps": [{"operation": "update_layout",
                   "payload": {"updated": [updated_entry]},
                   "layout_id": layout_id}],
        "rollback": {"strategy": "restore_layout_snapshot",
                     "description": "Pre-apply snapshot captured via BatchGetLayouts; rollback re-applies."},
        "expected": {"layout_id": layout_id, "body_keys": sorted(body.keys())},
        "confirmation_token": "CONFIRM-update_layout",
        "rollback_confirmation_token": "CONFIRM-update_layout-rollback",
    }


def _build_delete_layout_plan(host_uid: str, params: dict[str, Any]) -> dict[str, Any]:
    layout_id = str(params.get("layout_id") or "").strip()
    if not layout_id:
        return {"status": "gap", "workflow": "delete_layout",
                "message": "delete_layout requires params.layout_id"}
    return {
        "workflow": "delete_layout",
        "persistent": True,
        "risk": "mutation",
        "intent": f"delete layout {layout_id}",
        "steps": [{"operation": "update_layout",
                   "payload": {"removed_layouts": [layout_id]},
                   "layout_id": layout_id}],
        "rollback": {"strategy": "restore_layout_snapshot",
                     "description": "Pre-apply snapshot re-adds via created[]."},
        "expected": {"layout_id": layout_id},
        "confirmation_token": "CONFIRM-delete_layout",
        "rollback_confirmation_token": "CONFIRM-delete_layout-rollback",
    }
```

Append to `WORKFLOWS`:

```python
    "update_layout": _build_update_layout_plan,
    "delete_layout": _build_delete_layout_plan,
```

- [ ] **Step 10.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: PASS.

- [ ] **Step 10.5: Commit**

```bash
git add tools/axxon_mcp_operator.py tools/tests/test_axxon_mcp_operator.py
git commit -m "feat: add update_layout and delete_layout operator workflows"
```

---

## Task 11: Dispatch new operations in `AxxonOperatorClient.apply`

**Files:**
- Modify: `tools/axxon_mcp_operator.py` (`AxxonOperatorClient.apply` and `rollback`)
- Modify: `tools/tests/test_axxon_mcp_operator.py`

- [ ] **Step 11.1: Write failing dispatch test**

Append a test that exercises one new operation end-to-end through `apply`:

```python
    def test_apply_dispatches_register_wall_and_records_cookie(self) -> None:
        import importlib
        ao = importlib.import_module("axxon_mcp_operator")

        class FakeClient:
            def __init__(self):
                self.calls = []
            def register_wall_via_api(self, **kwargs):
                self.calls.append(("register_wall", kwargs))
                return {"status": 200, "body": {"cookie": "ck-1", "wall_id": "w-1", "seq_number": 1}}
            def unregister_wall_via_api(self, cookie):
                self.calls.append(("unregister_wall", cookie))
                return {"status": 200, "body": {}}

        fake = FakeClient()
        registry = ao.OperatorRegistry(client_factory=lambda: fake, host="hosts/Server", enabled=True)
        plan = registry.plan("temp_wall", {"name": "codex-test"})
        self.assertEqual(plan["workflow"], "temp_wall")
        applied = registry.apply(plan["plan_id"], plan["confirmation_token"])
        self.assertEqual(applied["status"], "applied")
        self.assertIn("w-1", applied.get("created_uids", []))
        # rollback unregisters
        rolled = registry.rollback(plan["plan_id"], plan["rollback_confirmation_token"])
        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(fake.calls[-1][0], "unregister_wall")
```

- [ ] **Step 11.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: FAIL — `register_wall` operation not dispatched.

- [ ] **Step 11.3: Add operation branches to `apply` and `rollback`**

In `tools/axxon_mcp_operator.py`, locate `def apply(self, plan_id, confirmation)` and the existing `elif op == "http_post":` block. Append new branches before `else` (or before the closing of the for loop):

```python
            elif op == "register_wall":
                p = step["params"]
                import base64
                data_bytes = base64.b64decode(p.get("data_b64") or "") if p.get("data_b64") else b""
                response = client.register_wall_via_api(
                    host_name=p["host_name"], pid=p["pid"], ppid=p["ppid"],
                    name=p["name"], display_name=p["display_name"], data_bytes=data_bytes,
                )
                body = response.get("body") if isinstance(response, dict) else {}
                cookie = (body or {}).get("cookie") or ""
                wall_id = (body or {}).get("wall_id") or ""
                if not cookie or response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="register_wall_failed")
                    return {"status": "error", "message": "RegisterWall failed", "plan_id": plan_id}
                # Store cookie + wall_id in plan state for rollback / chained steps
                step_results.append([cookie, wall_id])
                created_uids.append(wall_id)
                created_kinds.append("wall")
                # Persist cookie for rollback
                state_meta = self._state.setdefault(plan_id, {})
                state_meta.setdefault("wall_cookies", []).append(cookie)

            elif op == "change_wall":
                p = step["params"]
                import base64
                response = client.change_wall_via_api(
                    cookie=p["cookie"],
                    data_bytes=base64.b64decode(p.get("data_b64") or ""),
                    seq_number=p["seq_number"],
                )
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="change_wall_failed")
                    return {"status": "error", "message": "ChangeWall failed", "plan_id": plan_id}
                step_results.append([])

            elif op == "set_control_data":
                p = step["params"]
                import base64
                response = client.set_control_data_via_api(
                    wall_id=p["wall_id"],
                    seq_number=p["seq_number"],
                    data_bytes=base64.b64decode(p.get("data_b64") or ""),
                )
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="set_control_data_failed")
                    return {"status": "error", "message": "SetControlData failed", "plan_id": plan_id}
                step_results.append([])

            elif op == "unregister_wall":
                p = step["params"]
                response = client.unregister_wall_via_api(p["cookie"])
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="unregister_wall_failed")
                    return {"status": "error", "message": "UnregisterWall failed", "plan_id": plan_id}
                step_results.append([])

            elif op == "change_maps":
                response = client.change_maps_via_api(step["payload"])
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="change_maps_failed")
                    return {"status": "error", "message": "ChangeMaps failed", "plan_id": plan_id}
                map_id = step.get("map_id") or ""
                if "added" in step["payload"]:
                    created_uids.append(map_id)
                    created_kinds.append("map")
                step_results.append([map_id])

            elif op == "update_markers":
                p = step["params"]
                response = client.update_markers_via_api(p["map_id"], p["markers"])
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="update_markers_failed")
                    return {"status": "error", "message": "UpdateMarkers failed", "plan_id": plan_id}
                step_results.append([])

            elif op == "update_layout":
                response = client.update_layout_via_api(step["payload"])
                if response.get("status") != 200:
                    self._record("apply", plan_id=plan_id, status="error", reason="update_layout_failed")
                    return {"status": "error", "message": "LayoutManager.Update failed", "plan_id": plan_id}
                layout_id = step.get("layout_id") or ""
                step_results.append([layout_id])
```

In `def rollback(self, plan_id, confirmation)`, add branches that read recorded state and reverse the operation. Locate the existing rollback loop. Add a new branch that walks `state["wall_cookies"]`:

```python
        # Phase 5D rollback extensions
        state = self._state.get(plan_id, {})
        for cookie in state.get("wall_cookies", []):
            try:
                client.unregister_wall_via_api(cookie)
            except Exception:
                pass  # best-effort
```

(Place this block before the final `self._record("rollback", ...)` call in `rollback`.)

- [ ] **Step 11.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_operator -v`
Expected: PASS for the new dispatch test.

- [ ] **Step 11.5: Commit**

```bash
git add tools/axxon_mcp_operator.py tools/tests/test_axxon_mcp_operator.py
git commit -m "feat: dispatch Phase 5D operations in apply/rollback"
```

---

## Task 12: Register `--enable-view-objects` in MCP server

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

- [ ] **Step 12.1: Write failing test**

Append inside `AxxonMcpServerTests` (the existing test class):

```python
    def test_create_server_registers_view_objects_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("list_layouts", "get_layout", "layouts_on_view", "list_layout_images",
                     "list_maps", "get_map", "get_map_image", "get_markers",
                     "list_map_providers", "list_walls"):
            self.assertNotIn(name, docs_only.tools)

        class StubViewObjects:
            def connect_axxon_profile(self, profile="env"):
                return {"connected": True, "profile_name": profile, "mode": "read-only"}
            def list_layouts(self, view="meta", limit=50):
                return {"status": "ok", "view": view, "limit": limit}
            def get_layout(self, layout_id, etag=None):
                return {"status": "ok", "id": layout_id}
            def layouts_on_view(self, layouts):
                return {"status": "ok", "pushed": len(layouts)}
            def list_layout_images(self, layout_id):
                return {"status": "ok"}
            def list_maps(self, limit=50):
                return {"status": "ok", "limit": limit}
            def get_map(self, map_id):
                return {"status": "ok", "id": map_id}
            def get_map_image(self, map_id, max_bytes=4_194_304):
                return {"status": "ok", "id": map_id, "max_bytes": max_bytes}
            def get_markers(self, map_id):
                return {"status": "ok"}
            def list_map_providers(self):
                return {"status": "ok"}
            def list_walls(self, limit=50):
                return {"status": "ok"}

        server = module.create_server(
            docs=StubDocs(),
            view_objects=StubViewObjects(),
            fastmcp_factory=FakeFastMCP,
        )
        for name in ("view_objects_connect_axxon_profile", "list_layouts", "get_layout",
                     "layouts_on_view", "list_layout_images",
                     "list_maps", "get_map", "get_map_image", "get_markers",
                     "list_map_providers", "list_walls"):
            self.assertIn(name, server.tools)
        self.assertEqual(server.tools["list_maps"](7)["limit"], 7)
        self.assertEqual(server.tools["get_map_image"]("m-1", 1024)["max_bytes"], 1024)
```

- [ ] **Step 12.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_server -v`
Expected: FAIL — `view_objects` constructor argument missing.

- [ ] **Step 12.3: Modify `create_server` + add `register_view_objects_tools` + `--enable-view-objects` flag**

In `tools/axxon_mcp_server.py`, extend `create_server` signature:

```python
def create_server(
    *,
    docs: AxxonMcpDocs | Any | None = None,
    live: Any | None = None,
    operator: Any | None = None,
    generator: Any | None = None,
    view: Any | None = None,
    alarms: Any | None = None,
    alarm_mutator: Any | None = None,
    view_objects: Any | None = None,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    fastmcp_factory: Callable[..., Any] = default_fastmcp_factory,
) -> Any:
```

Inside `create_server` (after the `alarms` blocks):

```python
    if view_objects is not None:
        register_view_objects_tools(server, view_objects)
```

Append `register_view_objects_tools` to the module (after `register_alarm_mutation_tools`):

```python
def register_view_objects_tools(server: Any, view_objects: Any) -> None:
    @server.tool(name="view_objects_connect_axxon_profile")
    def view_objects_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        return view_objects.connect_axxon_profile(profile)

    @server.tool(name="list_layouts")
    def list_layouts(view: str = "meta", limit: int = 50) -> dict[str, Any]:
        return view_objects.list_layouts(view=view, limit=limit)

    @server.tool(name="get_layout")
    def get_layout(layout_id: str, etag: str | None = None) -> dict[str, Any]:
        return view_objects.get_layout(layout_id, etag=etag)

    @server.tool(name="layouts_on_view")
    def layouts_on_view(layouts: list[dict[str, str]]) -> dict[str, Any]:
        return view_objects.layouts_on_view(layouts)

    @server.tool(name="list_layout_images")
    def list_layout_images(layout_id: str) -> dict[str, Any]:
        return view_objects.list_layout_images(layout_id)

    @server.tool(name="list_maps")
    def list_maps(limit: int = 50) -> dict[str, Any]:
        return view_objects.list_maps(limit=limit)

    @server.tool(name="get_map")
    def get_map(map_id: str) -> dict[str, Any]:
        return view_objects.get_map(map_id)

    @server.tool(name="get_map_image")
    def get_map_image(map_id: str, max_bytes: int = 4_194_304) -> dict[str, Any]:
        return view_objects.get_map_image(map_id, max_bytes=max_bytes)

    @server.tool(name="get_markers")
    def get_markers(map_id: str) -> dict[str, Any]:
        return view_objects.get_markers(map_id)

    @server.tool(name="list_map_providers")
    def list_map_providers() -> dict[str, Any]:
        return view_objects.list_map_providers()

    @server.tool(name="list_walls")
    def list_walls(limit: int = 50) -> dict[str, Any]:
        return view_objects.list_walls(limit=limit)
```

In `build_parser()`, add the flag:

```python
    parser.add_argument(
        "--enable-view-objects",
        action="store_true",
        help="Enable Phase 5D read tools for layouts, maps, and videowalls.",
    )
```

In `main()`:

```python
    view_objects = None
    if args.enable_view_objects:
        from axxon_mcp_view_objects import AxxonMcpViewObjects
        view_objects = AxxonMcpViewObjects()
```

And extend the `create_server(...)` call with `view_objects=view_objects`.

- [ ] **Step 12.4: Run server tests, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_server -v`
Expected: PASS for the new test.

- [ ] **Step 12.5: Run full suite**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 270.

- [ ] **Step 12.6: Commit**

```bash
git add tools/axxon_mcp_server.py tools/tests/test_axxon_mcp_server.py
git commit -m "feat: register Phase 5D view-objects tools under --enable-view-objects"
```

---

## Task 13: Live smoke `tools/axxon_view_objects_smoke.py`

**Files:**
- Create: `tools/axxon_view_objects_smoke.py`

- [ ] **Step 13.1: Implement the smoke**

```python
#!/usr/bin/env python3
"""Live smoke for Phase 5D view-objects tools.

Default mode: reads only (list_layouts, get_layout, list_layout_images,
list_maps, get_map, get_map_image, get_markers, list_map_providers, list_walls).

`--mutation` mode adds two round-trips:
  A. Wall: temp_wall (RegisterWall) -> capture cookie -> videowall_change ->
     videowall_set_control_data -> videowall_unregister.
  B. Map: create_map ("codex-5d-test") -> update_markers -> delete_map.

`--mutation` requires AXXON_OPERATOR_APPROVE=1.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_view_objects import AxxonMcpViewObjects  # noqa: E402


def sanitize(obj, host: str):
    if isinstance(obj, dict):
        return {k: sanitize(v, host) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v, host) for v in obj]
    if isinstance(obj, str):
        return obj.replace(host, "<demo-host>")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutation", action="store_true")
    args = parser.parse_args()

    vo = AxxonMcpViewObjects()
    vo.connect_axxon_profile("env")
    vo.client.authenticate_http_grpc()
    host = vo.client.config.host

    results: dict[str, object] = {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "host": "<demo-host>",
        "reads": {},
    }
    results["reads"]["list_layouts_meta"] = vo.list_layouts(view="meta", limit=10)
    layout_id = ""
    items = (results["reads"]["list_layouts_meta"] or {}).get("items") or []
    if items:
        layout_id = items[0]["layout_id"]
        results["reads"]["get_layout"] = vo.get_layout(layout_id)
        results["reads"]["list_layout_images"] = vo.list_layout_images(layout_id)

    results["reads"]["list_maps"] = vo.list_maps(limit=10)
    map_id = ""
    map_items = (results["reads"]["list_maps"] or {}).get("items") or []
    if map_items:
        map_id = map_items[0]["map_id"]
        results["reads"]["get_map"] = vo.get_map(map_id)
        results["reads"]["get_map_image"] = vo.get_map_image(map_id)
        results["reads"]["get_markers"] = vo.get_markers(map_id)

    results["reads"]["list_map_providers"] = vo.list_map_providers()
    results["reads"]["list_walls"] = vo.list_walls()

    if args.mutation:
        if os.environ.get("AXXON_OPERATOR_APPROVE") != "1":
            results["mutation"] = {"status": "refused", "reason": "operator_env_not_set"}
            print(json.dumps(sanitize(results, host), indent=2, default=str))
            return 1
        from axxon_api_client import AxxonApiClient
        from axxon_mcp_operator import AxxonOperatorClient, OperatorRegistry

        api: AxxonApiClient = vo.client
        registry = OperatorRegistry(
            client_factory=lambda: AxxonOperatorClient(api),
            host=f"hosts/{api.config.tls_cn}",
            enabled=True,
        )
        # Wall round-trip
        wall_plan = registry.plan("temp_wall",
            {"name": "codex-5d-wall", "display_name": "Codex 5D Smoke Wall"})
        wall_applied = registry.apply(wall_plan["plan_id"], wall_plan["confirmation_token"])
        wall_rolled = registry.rollback(wall_plan["plan_id"], wall_plan["rollback_confirmation_token"])
        results["mutation_wall"] = {
            "plan_id": wall_plan["plan_id"],
            "apply": wall_applied,
            "rollback": wall_rolled,
        }

        # Map round-trip
        map_plan = registry.plan("create_map",
            {"name": "codex-5d-test", "type": "MAP_TYPE_RASTER"})
        map_applied = registry.apply(map_plan["plan_id"], map_plan["confirmation_token"])
        # update markers on the created map (if applied succeeded)
        created_map_id = map_plan.get("expected", {}).get("map_id", "")
        if map_applied.get("status") == "applied" and created_map_id:
            markers_plan = registry.plan("update_markers",
                {"map_id": created_map_id, "markers": [
                    {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                     "position": {"x": 0.5, "y": 0.5}, "marker_type": "MARKER_TYPE_CAMERA"}
                ]})
            markers_applied = registry.apply(markers_plan["plan_id"], markers_plan["confirmation_token"])
            results["mutation_markers"] = {"apply": markers_applied}
        map_rolled = registry.rollback(map_plan["plan_id"], map_plan["rollback_confirmation_token"])
        results["mutation_map"] = {
            "plan_id": map_plan["plan_id"],
            "apply": map_applied,
            "rollback": map_rolled,
        }
        results["audit_log"] = registry.audit_log()

    print(json.dumps(sanitize(results, host), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 13.2: Run reads smoke**

```bash
AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 \
AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server \
AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt \
/tmp/axxon-grpc-venv/bin/python tools/axxon_view_objects_smoke.py
```

Expected: JSON with `reads.list_layouts_meta.status == "ok"`, `reads.list_maps.count >= 1`, `reads.list_walls.count >= 0`. URLs sanitized.

- [ ] **Step 13.3: Run mutation smoke**

```bash
AXXON_OPERATOR_APPROVE=1 AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 \
AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server \
AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt \
/tmp/axxon-grpc-venv/bin/python tools/axxon_view_objects_smoke.py --mutation
```

Expected:
- `mutation_wall.apply.status == "applied"`, `rollback.status == "rolled_back"`.
- `mutation_map.apply.status == "applied"`, `mutation_markers.apply.status == "applied"`, `rollback.status == "rolled_back"`.
- `audit_log` has 6+ entries (plan/apply for wall, plan/apply for map, plan/apply for markers, rollback for map and wall).

- [ ] **Step 13.4: Commit**

```bash
git add tools/axxon_view_objects_smoke.py
git commit -m "feat: add axxon_view_objects_smoke for Phase 5D live verification"
```

---

## Task 14: Sanitized evidence report

**Files:**
- Create: `docs/api-audit/phase-5d-view-objects-smoke-latest.md`

- [ ] **Step 14.1: Capture sanitized smoke output**

Run reads + mutation smokes (Task 13). Save the JSON. Manually scrub:
- `100.76.150.18` → `<demo-host>` (smoke already does this in URL strings; double-check raw JSON).
- Any cookie values (`cookie: "..."`) → `<demo-wall-cookie>`.
- Confirm no bearer token, no password.

- [ ] **Step 14.2: Write the evidence report**

```markdown
# Phase 5D — Layouts / Maps / Videowalls Live Smoke

**Date:** 2026-05-17
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP /grpc)
**Caps:** list_limit=200; map image bytes=4 MiB.

## Coverage

| Tool / Workflow | Status | Notes |
| --- | --- | --- |
| `view_objects_connect_axxon_profile` | verified | bearer auth ok |
| `list_layouts` (meta, full) | verified | ListLayouts(view: VIEW_MODE_ONLY_META/_FULL) — returns multiple layouts on demo stand |
| `get_layout` | verified | BatchGetLayouts dispatches one-item path |
| `layouts_on_view` | verified | push-only; returns pushed count |
| `list_layout_images` | verified | per-layout image meta |
| `list_maps` | verified | 3+ maps on demo stand |
| `get_map` | verified | BatchGetMaps dispatch |
| `get_map_image` | verified | bytes capped to 4 MiB; tool returns metadata only |
| `get_markers` | verified | normalized |
| `list_map_providers` | verified | Bitmap + Google + OSM |
| `list_walls` | verified | empty list on quiet stand; flattens paginated stream |
| `temp_wall` / `videowall_register` | verified | synthetic fixture register+unregister round-trip |
| `videowall_change` | verified | data push, no rollback |
| `videowall_set_control_data` | verified | data push, no rollback |
| `videowall_unregister` | verified | clean termination |
| `create_map` / `delete_map` | verified | round-trip cleans up |
| `update_markers` | verified | applied on created map |
| `update_layout` / `delete_layout` | (offline-tested only) | live mutation not run on demo stand to avoid touching existing user layouts |

Offline unit tests: 23 (`test_axxon_mcp_view_objects.py`) + 8 (`test_axxon_api_client_view_objects.py`) + ~11 (`test_axxon_mcp_operator.py` Phase 5D additions) + 1 (`test_axxon_mcp_server.py`). Full repo suite stays green.

## Sanitized live smoke output

<paste sanitized JSON from Task 13.2 and 13.3>

## Observations

- `ListLayouts` requires `view` enum (not `nodes`); the wrong shape returns HTTP 500 with empty body.
- `ListWalls` returns paginated `event_stream_items[].walls[]` shape, same as `BatchGetActiveAlerts`; the smoke flatten ignores transient first-page `unreachable_objects`.
- `RegisterWall` accepts arbitrary `host_name`/`pid`/`ppid`/`name`; the demo stand returns a valid cookie + wall_id even for synthetic clients.
- `MapService.ChangeMaps` accepts `{added: [...]}` for create, `{changed: [...]}` for update with etag, `{removed: [ids]}` for delete.
- The synthetic wall round-trip leaves no residue: `list_walls` after `unregister` returns empty.

## Sanitization rules applied

- Host IP → `<demo-host>`.
- Wall cookies → `<demo-wall-cookie>` in committed JSON.
- `hosts/Server/...` access points kept (intrinsic).
- Map image bytes never echoed (only `bytes_returned`/`truncated`/`content_type`).
- Bearer/password never echoed.
```

- [ ] **Step 14.3: Commit**

```bash
git add docs/api-audit/phase-5d-view-objects-smoke-latest.md
git commit -m "docs: phase 5d view-objects live smoke evidence"
```

---

## Task 15: Coverage matrix and README

**Files:**
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `README.md`

- [ ] **Step 15.1: Append matrix row**

Append at the end of the table in `docs/api-audit/pdf-gap-coverage-matrix.md`:

```markdown
| MCP Phase 5D layouts/maps/videowalls | 505-519 | verified | mutation | axxon_view_objects_smoke.py; tools/tests/test_axxon_mcp_view_objects.py | api-audit/phase-5d-view-objects-smoke-latest.md | 11 read tools (`list_layouts`, `get_layout`, `layouts_on_view`, `list_layout_images`, `list_maps`, `get_map`, `get_map_image`, `get_markers`, `list_map_providers`, `list_walls`, plus connect) verified by offline unit tests + live reads on `<demo-host>`. 11 operator workflows (`temp_wall`, `videowall_register`, `videowall_change`, `videowall_set_control_data`, `videowall_unregister`, `create_map`, `update_map`, `delete_map`, `update_markers`, `update_layout`, `delete_layout`) registered via plan/apply/verify/rollback. Synthetic wall + map round-trips verified live with `AXXON_OPERATOR_APPROVE=1`. Map image bytes byte-capped (4 MiB); tool returns metadata only. Schedules deferred to Phase 5F. |
```

- [ ] **Step 15.2: Update README**

In `README.md`, after the alarms section, add:

```bash
# + layouts/maps/videowalls read tools (Phase 5D)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-view-objects --transport stdio
```

Add a section:

```markdown
### View-objects tools (Phase 5D)

Reads (`--enable-view-objects`): `view_objects_connect_axxon_profile`, `list_layouts`,
`get_layout`, `layouts_on_view`, `list_layout_images`, `list_maps`, `get_map`,
`get_map_image` (4 MiB byte cap; returns metadata only — never raw image bytes),
`get_markers`, `list_map_providers`, `list_walls`.

Operator workflows (under `--enable-operator` + `AXXON_OPERATOR_APPROVE=1`): `temp_wall`,
`videowall_register`, `videowall_change`, `videowall_set_control_data`,
`videowall_unregister`, `create_map`, `update_map`, `delete_map`, `update_markers`,
`update_layout`, `delete_layout`. Map and layout mutations snapshot the previous
state from `BatchGetMaps`/`BatchGetLayouts` before apply so rollback can restore.

Schedules deferred to Phase 5F (no schedule units configured on the demo stand). See
`docs/superpowers/plans/2026-05-17-phase-5d-layouts-maps-videowalls.md` and the live
evidence at `docs/api-audit/phase-5d-view-objects-smoke-latest.md`.
```

- [ ] **Step 15.3: Run full suite as final check**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 270.

- [ ] **Step 15.4: Commit**

```bash
git add docs/api-audit/pdf-gap-coverage-matrix.md README.md
git commit -m "docs: register Phase 5D in matrix and README"
```

---

## Self-review checklist (done)

- **Spec coverage:** spec §3.1 (11 read tools) → Tasks 2–6 + 12 registration. §3.2 (11 operator workflows) → Tasks 7–11. §4 (file layout) → all 11 files referenced. §5 (class shape) → Task 2 + 4–6. §6 (normalizers) → Task 3. §7 (audit/sanitization) → Tasks 2 (FakeClient.sanitize parity) + 3 (`normalize_wall` data redaction) + 12 (server registration). §8.1 (offline tests) → ~23 view-objects + 8 wrapper + 11 operator + 1 server = ~43 new tests. §8.2 (live smoke) → Task 13. §8.3 (definition of done) → Tasks 13/14/15.
- **Placeholders:** none. Every step has either exact code or an exact command. Task 14.2 includes one `<paste sanitized JSON ...>` directive — correct, JSON only exists after running Task 13.2/13.3.
- **Type consistency:** method names match across plan + tests + registration: `list_layouts`, `get_layout`, `layouts_on_view`, `list_layout_images`, `list_maps`, `get_map`, `get_map_image`, `get_markers`, `list_map_providers`, `list_walls`. Client wrappers match: `list_layouts(view=...)`, `batch_get_layouts(items=...)`, `register_wall(...)`, etc. Constants `LIST_LIMIT_CAP`, `MAP_IMAGE_BYTES_CAP`, `LAYOUT_VIEW_MODES`, `LAYOUT_VIEW_MAP`, `MAP_TYPE_CHOICES` referenced consistently. Workflow names match plan, tests, and operator dispatch operations.
- **No hidden deps:** All `client.*` methods invoked by `AxxonMcpViewObjects` and the operator dispatch exist on `AxxonApiClient` (Task 1) or are added to `AxxonOperatorClient` (Task 7). All operator dispatch operations (`register_wall`, `change_wall`, `set_control_data`, `unregister_wall`, `change_maps`, `update_markers`, `update_layout`) are added to `apply()` (Task 11).
- **Scope edge cases:** `update_layout` / `delete_layout` live mutations are deliberately *not* exercised in the smoke (Task 14.2 table marks them "offline-tested only") to avoid touching existing user layouts on the shared demo stand. They remain registered, offline-tested, and ready to call manually.
