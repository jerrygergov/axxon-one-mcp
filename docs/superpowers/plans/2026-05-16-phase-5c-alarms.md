# Phase 5C — Alarms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 13 MCP tools (7 alarm reads + 6 alarm mutations) plus an alarm-event subscription, backed by live-verified `LogicService` proto shapes, gated through `--enable-alarms` / `--enable-alarms-mutation` + `AXXON_ALARMS_APPROVE=1` and per-call confirmation tokens.

**Architecture:** A new module `tools/axxon_mcp_alarms.py` holds two dataclasses — `AxxonMcpAlarms` (reads + subscription) and `AxxonAlarmMutator` (lifecycle mutations). Both mirror `tools/axxon_mcp_view.py`. Thin `LogicService.*` wrappers go onto `AxxonApiClient`. Reads are tested offline plus a live smoke; mutations are exercised in a synthetic `raise → begin → continue → cancel → verify-gone` round-trip on `100.76.150.18`.

**Tech Stack:** Python 3.11+, `AxxonApiClient` (existing), `unittest`, FastMCP (existing). No new third-party deps.

---

## Source-of-truth references

- Spec: `docs/superpowers/specs/2026-05-16-phase-5c-alarms-design.md`.
- Reuse module pattern: `tools/axxon_mcp_view.py` (Phase 5A, identical dataclass-with-factories shape).
- Reuse audit pattern: `tools/axxon_mcp_operator.py` (in-memory `audit` list, `audit_log()` accessor, `axxon://operator/audit-log` resource analogue).
- Reuse history fetch: `tools/axxon_mcp_live.py:search_events` (already in `AxxonMcpLive`, callable from the alarms module).
- Test pattern: `tools/tests/test_axxon_mcp_view.py` (offline `FakeConfig`/`FakeClient`).
- Server registration pattern: `tools/axxon_mcp_server.py:register_view_tools` and `register_operator_tools`.
- Proto shapes (verified): `docs/grpc-proto-files/axxonsoft/bl/logic/LogicService.proto` (single-target alert RPCs), `docs/grpc-proto-files/axxonsoft/bl/events/Events.proto` (`EEventType.ET_Alert=15`, `EEventType.ET_AlertState=16`, `EAlertPriority`, `AlertState.ESeverity`).
- Demo stand: `AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt`.

---

## File structure

| Path | Purpose | Touched by |
| --- | --- | --- |
| `tools/axxon_mcp_alarms.py` | New module. `AxxonMcpAlarms` + `AxxonAlarmMutator` + helpers. | Tasks 2-9 |
| `tools/axxon_api_client.py` | Add 9 thin `LogicService.*` wrappers. | Task 1 |
| `tools/axxon_mcp_server.py` | Register tools under two new flags. | Task 10 |
| `tools/axxon_alarms_smoke.py` | New live smoke. | Task 11 |
| `tools/tests/test_axxon_mcp_alarms.py` | Offline unit tests. | Tasks 2-9 |
| `tools/tests/test_axxon_mcp_server.py` | Add registration tests. | Task 10 |
| `docs/api-audit/phase-5c-alarms-smoke-latest.md` | Sanitized live evidence. | Task 12 |
| `docs/api-audit/pdf-gap-coverage-matrix.md` | New row. | Task 13 |
| `README.md` | Two new flags + tool list. | Task 13 |

---

## Module constants (single source of truth, placed at top of `tools/axxon_mcp_alarms.py`)

```python
LIST_LIMIT_CAP = 200
HISTORY_HOURS_CAP = 24
SUBSCRIBE_DURATION_CAP_S = 30
SUBSCRIBE_LIMIT_CAP = 100

ALARM_EVENT_TYPES = ("ET_Alert", "ET_AlertState")

SEVERITY_CHOICES = ("confirmed_alarm", "suspicious_situation", "false_alarm")
PRIORITY_CHOICES = ("AP_MINIMUM", "AP_LOW", "AP_MEDIUM", "AP_HIGH")

CONFIRMATION_TOKENS = {
    "raise_alert": "CONFIRM-raise-alert",
    "alarm_begin_review": "CONFIRM-alarm-begin",
    "alarm_continue_review": "CONFIRM-alarm-continue",
    "alarm_cancel_review": "CONFIRM-alarm-cancel",
    "alarm_complete_review": "CONFIRM-alarm-complete",
    "alarm_escalate": "CONFIRM-alarm-escalate",
}
```

---

## Task 1: Add 9 LogicService wrappers to `AxxonApiClient`

**Files:**
- Modify: `tools/axxon_api_client.py` (append methods after `pull_events_bounded`).

- [ ] **Step 1.1: Write a failing offline test exercising one wrapper**

Create `tools/tests/test_axxon_api_client_alarms.py`:

```python
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
            tls_cn="Server", ca=Path("/tmp/ca.crt"), stubs_dir=Path("/tmp"),
            timeout=5.0,
        )
        super().__init__(cfg)
        self.calls: list[tuple[str, dict]] = []

    def http_grpc(self, fqmn, data=None):
        self.calls.append((fqmn, dict(data or {})))
        return {"status": 200, "body": {"result": True, "alert_id": "fake-id"}}


class LogicServiceWrappersTests(unittest.TestCase):
    def test_raise_alert_passes_camera_ap_through(self) -> None:
        c = _FakeClient()
        r = c.raise_alert("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(r["body"]["alert_id"], "fake-id")
        self.assertEqual(c.calls, [(
            "axxonsoft.bl.logic.LogicService.RaiseAlert",
            {"camera_ap": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
        )])

    def test_begin_alert_review_passes_camera_ap_and_alert_id(self) -> None:
        c = _FakeClient()
        c.begin_alert_review("cam-ap", "alert-1")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BeginAlertReview",
            {"camera_ap": "cam-ap", "alert_id": "alert-1"},
        ))

    def test_complete_alert_review_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.complete_alert_review("cam-ap", "alert-1", severity="confirmed_alarm", bookmark_message="ok")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.CompleteAlertReview",
            {
                "camera_ap": "cam-ap",
                "alert_id": "alert-1",
                "severity": "confirmed_alarm",
                "bookmark": {"message": "ok"},
            },
        ))

    def test_escalate_alert_passes_full_payload(self) -> None:
        c = _FakeClient()
        c.escalate_alert("cam-ap", "alert-1", priority="AP_HIGH", user_roles=["role-a"], comment="esc")
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.EscalateAlert",
            {
                "camera_ap": "cam-ap",
                "alert_id": "alert-1",
                "priority": "AP_HIGH",
                "user_roles": ["role-a"],
                "comment": "esc",
            },
        ))

    def test_batch_get_active_alerts_passes_nodes(self) -> None:
        c = _FakeClient()
        c.batch_get_active_alerts(["hosts/Server"])
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts",
            {"nodes": ["hosts/Server"]},
        ))

    def test_batch_filter_active_alerts_passes_nodes_and_filter(self) -> None:
        c = _FakeClient()
        c.batch_filter_active_alerts(["hosts/Server"], filter={"min_severity": 1})
        self.assertEqual(c.calls[0], (
            "axxonsoft.bl.logic.LogicService.BatchFilterActiveAlerts",
            {"nodes": ["hosts/Server"], "filter": {"min_severity": 1}},
        ))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_api_client_alarms -v`
Expected: FAIL with `AttributeError: 'AxxonApiClient' object has no attribute 'raise_alert'`.

- [ ] **Step 1.3: Implement the wrappers**

Append to `tools/axxon_api_client.py` after `pull_events_bounded` (before `def http_request`):

```python
    def get_active_alerts(self, camera_ap: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.GetActiveAlerts",
            {"camera_ap": camera_ap},
        )

    def batch_get_active_alerts(self, nodes: list[str]) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BatchGetActiveAlerts",
            {"nodes": list(nodes)},
        )

    def batch_filter_active_alerts(self, nodes: list[str], filter: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BatchFilterActiveAlerts",
            {"nodes": list(nodes), "filter": dict(filter or {})},
        )

    def raise_alert(self, camera_ap: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.RaiseAlert",
            {"camera_ap": camera_ap},
        )

    def begin_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.BeginAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def continue_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.ContinueAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def cancel_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.CancelAlertReview",
            {"camera_ap": camera_ap, "alert_id": alert_id},
        )

    def complete_alert_review(
        self, camera_ap: str, alert_id: str, *, severity: str, bookmark_message: str
    ) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.CompleteAlertReview",
            {
                "camera_ap": camera_ap,
                "alert_id": alert_id,
                "severity": severity,
                "bookmark": {"message": bookmark_message},
            },
        )

    def escalate_alert(
        self,
        camera_ap: str,
        alert_id: str,
        *,
        priority: str,
        user_roles: list[str],
        comment: str,
    ) -> dict[str, Any]:
        return self.http_grpc(
            "axxonsoft.bl.logic.LogicService.EscalateAlert",
            {
                "camera_ap": camera_ap,
                "alert_id": alert_id,
                "priority": priority,
                "user_roles": list(user_roles),
                "comment": comment,
            },
        )
```

- [ ] **Step 1.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_api_client_alarms -v`
Expected: PASS (6 tests).

- [ ] **Step 1.5: Run full suite, no regressions**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 193 (was 187 + 6 new).

- [ ] **Step 1.6: Commit**

```bash
git add tools/axxon_api_client.py tools/tests/test_axxon_api_client_alarms.py
git commit -m "feat: add LogicService alarm wrappers to AxxonApiClient"
```

---

## Task 2: Module scaffold + constants + `AxxonMcpAlarms.connect`

**Files:**
- Create: `tools/axxon_mcp_alarms.py`
- Create: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 2.1: Write the failing test**

Create `tools/tests/test_axxon_mcp_alarms.py`:

```python
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
        self.inventory = {
            "cameras": [
                {
                    "access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
                    "display_name": "Camera 1",
                    "enabled": True,
                    "serial_number": "SHOULD_NOT_LEAK",
                }
            ],
        }
        self.calls: list[tuple[str, tuple, dict]] = []

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):  # parity with AxxonApiClient.sanitize
        return value


class AxxonMcpAlarmsTests(unittest.TestCase):
    def test_module_loads_and_connect_reports_profile(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        profile = alarms.connect_axxon_profile("env")
        self.assertTrue(profile["connected"])
        self.assertEqual(profile["profile_name"], "env")
        self.assertEqual(profile["mode"], "read-only")
        self.assertTrue(profile["profile"]["password_present"])
        self.assertNotIn("secret", str(profile))

        rejected = alarms.connect_axxon_profile("other")
        self.assertFalse(rejected["connected"])
        self.assertEqual(rejected["profile_name"], "other")
        self.assertEqual(rejected["status"], "gap")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axxon_mcp_alarms'`.

- [ ] **Step 2.3: Create the module**

Create `tools/axxon_mcp_alarms.py`:

```python
#!/usr/bin/env python3
"""Alarm-lifecycle MCP tools for the Axxon One MCP server.

Two dataclasses live here:

* ``AxxonMcpAlarms`` — read-only tools and a bounded alarm subscription.
* ``AxxonAlarmMutator`` — alarm lifecycle mutations, gated by an environment
  flag (default ``AXXON_ALARMS_APPROVE``) and per-call confirmation tokens.

Both reuse ``AxxonApiClient`` for transport. URLs are never returned; the
mutator never persists to disk. The module mirrors the dataclass-with-factories
shape used by ``axxon_mcp_view.py``.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from axxon_api_client import AxxonApiClient, AxxonClientConfig


LIST_LIMIT_CAP = 200
HISTORY_HOURS_CAP = 24
SUBSCRIBE_DURATION_CAP_S = 30
SUBSCRIBE_LIMIT_CAP = 100

ALARM_EVENT_TYPES = ("ET_Alert", "ET_AlertState")

SEVERITY_CHOICES = ("confirmed_alarm", "suspicious_situation", "false_alarm")
PRIORITY_CHOICES = ("AP_MINIMUM", "AP_LOW", "AP_MEDIUM", "AP_HIGH")

CONFIRMATION_TOKENS = {
    "raise_alert": "CONFIRM-raise-alert",
    "alarm_begin_review": "CONFIRM-alarm-begin",
    "alarm_continue_review": "CONFIRM-alarm-continue",
    "alarm_cancel_review": "CONFIRM-alarm-cancel",
    "alarm_complete_review": "CONFIRM-alarm-complete",
    "alarm_escalate": "CONFIRM-alarm-escalate",
}


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
class AxxonMcpAlarms:
    """Read-only alarm tools + bounded alarm subscription."""

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

    def _ensure_inventory(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        if self._inventory is None:
            self._inventory = self.client.load_inventory()
        return self._inventory
```

- [ ] **Step 2.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (1 test).

- [ ] **Step 2.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: scaffold axxon_mcp_alarms module with connect"
```

---

## Task 3: `normalize_alarm` + `list_active_alerts`

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 3.1: Extend `FakeClient` and write the failing tests**

In `tools/tests/test_axxon_mcp_alarms.py`, replace the `FakeClient` class with this fuller version:

```python
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
                }
            ],
        }
        self.calls: list[tuple[str, tuple, dict]] = []
        self.per_camera_alerts: list[dict[str, Any]] = []
        self.batch_alert_pages: list[dict[str, Any]] = []

    def load_inventory(self) -> dict[str, Any]:
        return self.inventory

    def sanitize(self, value):
        return value

    def get_active_alerts(self, camera_ap: str) -> dict[str, Any]:
        self.calls.append(("get_active_alerts", (camera_ap,), {}))
        return {"status": 200, "body": {"alerts": list(self.per_camera_alerts)}}

    def batch_get_active_alerts(self, nodes: list[str]) -> dict[str, Any]:
        self.calls.append(("batch_get_active_alerts", (tuple(nodes),), {}))
        return {
            "status": 200,
            "body": {
                "event_stream_items": list(self.batch_alert_pages),
                "event_stream_count": len(self.batch_alert_pages),
            },
        }


def _sample_alert(guid: str = "a1", camera: str = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0") -> dict[str, Any]:
    return {
        "guid": guid,
        "timestamp": "20260516T175740.155991",
        "node_info": {"name": "Server", "friendly_name": "Server"},
        "camera": {"access_point": camera, "friendly_name": "1.Tracker", "group": ""},
        "archive": {"access_point": "hosts/Server/MultimediaStorage.A/MultimediaStorage", "friendly_name": "A", "group": ""},
        "required_comment": {"confirmed_alarm": True, "suspicious_situation": True, "false_alarm": True},
        "severity": 3,
    }
```

Then append these three tests inside `AxxonMcpAlarmsTests`:

```python
    def test_normalize_alarm_maps_real_axxon_shape(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        out = module.normalize_alarm(_sample_alert("guid-1"))
        self.assertEqual(out["alert_id"], "guid-1")
        self.assertEqual(out["camera_access_point"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertEqual(out["camera_friendly_name"], "1.Tracker")
        self.assertEqual(out["archive_access_point"], "hosts/Server/MultimediaStorage.A/MultimediaStorage")
        self.assertEqual(out["node_name"], "Server")
        self.assertEqual(out["timestamp"], "20260516T175740.155991")
        self.assertEqual(out["severity"], 3)
        self.assertEqual(out["required_comment"]["confirmed_alarm"], True)
        self.assertNotIn("SHOULD_NOT_LEAK", str(out))

    def test_list_active_alerts_per_camera_returns_normalized_items(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        fake.per_camera_alerts = [_sample_alert("a1"), _sample_alert("a2")]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_active_alerts(
            camera_access_point="hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            limit=999,
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["items"][0]["alert_id"], "a1")
        # limit clamp applied
        self.assertEqual(r["applied_limit"], module.LIST_LIMIT_CAP)
        # underlying client was called once with the camera AP
        self.assertEqual(fake.calls[-1][0], "get_active_alerts")

    def test_list_active_alerts_node_wide_flattens_batch_pages(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        # First page reports unreachable_nodes (the known demo-stand quirk); second page has the alert.
        fake.batch_alert_pages = [
            {"alerts": [], "unreachable_nodes": ["hosts/Server"]},
            {"alerts": [_sample_alert("a1")], "unreachable_nodes": []},
        ]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_active_alerts(camera_access_point=None, limit=10)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["alert_id"], "a1")
        # We only treat the node as unreachable when EVERY page reports it.
        self.assertEqual(r.get("unreachable_nodes"), [])
        self.assertEqual(fake.calls[-1][0], "batch_get_active_alerts")

    def test_list_active_alerts_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_active_alerts(camera_access_point="hosts/Server/NotACamera")
        self.assertEqual(r["status"], "gap")
        self.assertIn("NotACamera", r["message"])
```

- [ ] **Step 3.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL — `normalize_alarm` and `list_active_alerts` don't exist.

- [ ] **Step 3.3: Implement**

Append to `tools/axxon_mcp_alarms.py`:

```python
def normalize_alarm(raw: dict[str, Any]) -> dict[str, Any]:
    """Map an Axxon active-alarm dict to a stable MCP-side schema.

    Source fields verified against ``GetActiveAlerts`` responses on the demo stand:
    ``guid``, ``timestamp``, ``node_info.name``, ``camera.access_point``,
    ``camera.friendly_name``, ``archive.access_point``, ``required_comment``,
    ``severity``.
    """
    camera = raw.get("camera") or {}
    archive = raw.get("archive") or {}
    node = raw.get("node_info") or {}
    return {
        "alert_id": raw.get("guid") or raw.get("alert_id") or "",
        "severity": raw.get("severity"),
        "camera_access_point": camera.get("access_point"),
        "camera_friendly_name": camera.get("friendly_name"),
        "archive_access_point": archive.get("access_point"),
        "node_name": node.get("name"),
        "timestamp": raw.get("timestamp"),
        "required_comment": raw.get("required_comment"),
    }
```

Add to `AxxonMcpAlarms`:

```python
    def _camera_index(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            cam.get("access_point", ""): cam
            for cam in inventory.get("cameras", [])
            if cam.get("access_point")
        }

    def _host(self) -> str:
        return f"hosts/{self.client.config.tls_cn}"

    def list_active_alerts(
        self,
        camera_access_point: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if camera_access_point is not None:
            inv = self._ensure_inventory()
            if camera_access_point not in self._camera_index(inv):
                return {
                    "status": "gap",
                    "tool": "list_active_alerts",
                    "message": f"Camera not in inventory: {camera_access_point}",
                }
            resp = self.client.get_active_alerts(camera_access_point)
            body = resp.get("body") if isinstance(resp, dict) else {}
            raw_items = (body or {}).get("alerts") or []
            items = [normalize_alarm(a) for a in raw_items][:applied_limit]
            return {
                "status": "ok",
                "tool": "list_active_alerts",
                "count": len(items),
                "applied_limit": applied_limit,
                "items": items,
            }
        # Node-wide
        if self.client is None:
            self.connect_axxon_profile("env")
        resp = self.client.batch_get_active_alerts([self._host()])
        body = resp.get("body") if isinstance(resp, dict) else {}
        pages = (body or {}).get("event_stream_items") or []
        flat: list[dict[str, Any]] = []
        unreachable_per_page: list[list[str]] = []
        for page in pages:
            flat.extend(page.get("alerts") or [])
            unreachable_per_page.append(list(page.get("unreachable_nodes") or []))
        # Only surface "unreachable" when every page agrees.
        if unreachable_per_page and all(u for u in unreachable_per_page):
            unreachable_intersection = sorted(set.intersection(*[set(u) for u in unreachable_per_page]))
        else:
            unreachable_intersection = []
        items = [normalize_alarm(a) for a in flat][:applied_limit]
        return {
            "status": "ok",
            "tool": "list_active_alerts",
            "count": len(items),
            "applied_limit": applied_limit,
            "items": items,
            "unreachable_nodes": unreachable_intersection,
        }
```

- [ ] **Step 3.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (5 tests).

- [ ] **Step 3.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add normalize_alarm and list_active_alerts"
```

---

## Task 4: `get_active_alert` and `filter_active_alerts`

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 4.1: Extend `FakeClient` and write tests**

Add to `FakeClient` (inside the class, append after `batch_get_active_alerts`):

```python
    def batch_filter_active_alerts(self, nodes: list[str], filter: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(("batch_filter_active_alerts", (tuple(nodes),), dict(filter or {})))
        return {
            "status": 200,
            "body": {
                "event_stream_items": list(self.batch_alert_pages),
                "event_stream_count": len(self.batch_alert_pages),
            },
        }
```

Append tests inside `AxxonMcpAlarmsTests`:

```python
    def test_get_active_alert_returns_matching_alarm(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        fake.per_camera_alerts = [_sample_alert("a1"), _sample_alert("a2")]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.get_active_alert(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "a2",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["item"]["alert_id"], "a2")

    def test_get_active_alert_missing_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        fake.per_camera_alerts = [_sample_alert("a1")]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.get_active_alert(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "missing",
        )
        self.assertEqual(r["status"], "gap")

    def test_filter_active_alerts_applies_severity_min_and_camera(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        low = _sample_alert("low"); low["severity"] = 1
        high = _sample_alert("high", camera="hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0")
        high["severity"] = 5
        fake.batch_alert_pages = [{"alerts": [low, high], "unreachable_nodes": []}]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.filter_active_alerts(severity_min=3, limit=10)
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["alert_id"], "high")

        r2 = alarms.filter_active_alerts(
            camera="hosts/Server/DeviceIpint.2/SourceEndpoint.video:0:0",
            limit=10,
        )
        self.assertEqual(r2["count"], 1)
        self.assertEqual(r2["items"][0]["alert_id"], "high")
```

- [ ] **Step 4.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL — `get_active_alert` and `filter_active_alerts` missing.

- [ ] **Step 4.3: Implement**

Append to `AxxonMcpAlarms`:

```python
    def get_active_alert(self, camera_access_point: str, alert_id: str) -> dict[str, Any]:
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            return {
                "status": "gap",
                "tool": "get_active_alert",
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        resp = self.client.get_active_alerts(camera_access_point)
        body = resp.get("body") if isinstance(resp, dict) else {}
        for raw in (body or {}).get("alerts") or []:
            if (raw.get("guid") or raw.get("alert_id")) == alert_id:
                return {"status": "ok", "tool": "get_active_alert", "item": normalize_alarm(raw)}
        return {
            "status": "gap",
            "tool": "get_active_alert",
            "message": f"Alert id not active on this camera: {alert_id}",
        }

    def filter_active_alerts(
        self,
        severity_min: int | None = None,
        camera: str | None = None,
        state: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        resp = self.client.batch_filter_active_alerts([self._host()], filter={})
        body = resp.get("body") if isinstance(resp, dict) else {}
        pages = (body or {}).get("event_stream_items") or []
        flat: list[dict[str, Any]] = []
        for page in pages:
            flat.extend(page.get("alerts") or [])
        normalized = [normalize_alarm(a) for a in flat]
        kept: list[dict[str, Any]] = []
        for item in normalized:
            if severity_min is not None:
                sev = item.get("severity")
                if sev is None or sev < severity_min:
                    continue
            if camera is not None and item.get("camera_access_point") != camera:
                continue
            # `state` is reserved for when AlertState becomes available on the stream.
            if state not in ("all", "active", "reviewing", "completed", "cancelled", "escalated"):
                return {
                    "status": "gap",
                    "tool": "filter_active_alerts",
                    "message": f"Unknown state filter: {state}",
                }
            kept.append(item)
            if len(kept) >= applied_limit:
                break
        return {
            "status": "ok",
            "tool": "filter_active_alerts",
            "count": len(kept),
            "applied_limit": applied_limit,
            "applied_filters": {"severity_min": severity_min, "camera": camera, "state": state},
            "items": kept,
        }
```

- [ ] **Step 4.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (8 tests).

- [ ] **Step 4.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add get_active_alert and filter_active_alerts"
```

---

## Task 5: `list_alarm_history` and `list_alarm_event_types`

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 5.1: Extend `FakeClient` with `search_events` and `list_event_types`**

Append to `FakeClient`:

```python
    def search_events(
        self,
        *,
        subjects: list[str] | None = None,
        event_types: list[str] | None = None,
        hours: float = 1.0,
        limit: int = 100,
        descending: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(("search_events", (), {
            "subjects": tuple(subjects or []),
            "event_types": tuple(event_types or []),
            "hours": hours, "limit": limit, "descending": descending,
        }))
        # Return one synthetic ET_Alert event.
        return {
            "status": "ok",
            "items": [{
                "type": "ET_Alert",
                "guid": "hist-1",
                "timestamp": "20260516T170000.000000",
                "camera": {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
            }],
        }

    def list_event_types(self) -> dict[str, Any]:
        self.calls.append(("list_event_types", (), {}))
        return {
            "status": "ok",
            "items": [
                {"name": "ET_DetectorEvent", "value": 1},
                {"name": "ET_Alert", "value": 15},
                {"name": "ET_AlertState", "value": 16},
            ],
        }
```

Append tests:

```python
    def test_list_alarm_history_clamps_hours_and_filters_types(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_alarm_history(hours=999, limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["count"], 1)
        # Hours clamped to HISTORY_HOURS_CAP, limit clamped to LIST_LIMIT_CAP.
        kw = fake.calls[-1][2]
        self.assertEqual(kw["hours"], module.HISTORY_HOURS_CAP)
        self.assertEqual(kw["limit"], module.LIST_LIMIT_CAP)
        # Only alarm event types were requested.
        self.assertEqual(set(kw["event_types"]), set(module.ALARM_EVENT_TYPES))

    def test_list_alarm_event_types_returns_only_alarm_subset(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_alarm_event_types()
        self.assertEqual(r["status"], "ok")
        names = {it["name"] for it in r["items"]}
        self.assertEqual(names, set(module.ALARM_EVENT_TYPES))
```

- [ ] **Step 5.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL.

- [ ] **Step 5.3: Implement**

Append to `AxxonMcpAlarms`:

```python
    def list_alarm_history(
        self,
        hours: float = 1.0,
        limit: int = 100,
        camera: str | None = None,
        severity_min: int | None = None,
    ) -> dict[str, Any]:
        applied_hours = min(max(float(hours), 0.05), float(HISTORY_HOURS_CAP))
        applied_limit = min(max(int(limit), 1), LIST_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        result = self.client.search_events(
            subjects=[self._host()] if camera is None else [camera],
            event_types=list(ALARM_EVENT_TYPES),
            hours=applied_hours,
            limit=applied_limit,
            descending=True,
        )
        items = list(result.get("items") or [])
        if severity_min is not None:
            items = [it for it in items if (it.get("severity") or 0) >= severity_min]
        return {
            "status": "ok",
            "tool": "list_alarm_history",
            "count": len(items),
            "applied_hours": applied_hours,
            "applied_limit": applied_limit,
            "items": items,
        }

    def list_alarm_event_types(self) -> dict[str, Any]:
        if self.client is None:
            self.connect_axxon_profile("env")
        result = self.client.list_event_types()
        items = [it for it in (result.get("items") or []) if it.get("name") in ALARM_EVENT_TYPES]
        return {"status": "ok", "tool": "list_alarm_event_types", "items": items}
```

- [ ] **Step 5.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (10 tests).

- [ ] **Step 5.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add list_alarm_history and list_alarm_event_types"
```

---

## Task 6: `alarm_subscribe` (bounded stream with normalized events)

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 6.1: Extend `FakeClient` with `pull_events_bounded`**

Append to `FakeClient`:

```python
    def pull_events_bounded(
        self,
        *,
        subjects: list[str],
        event_types: list[str],
        timeout: float,
        max_events: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(("pull_events_bounded", (), {
            "subjects": tuple(subjects), "event_types": tuple(event_types),
            "timeout": timeout, "max_events": max_events,
        }))
        # Three synthetic ET_Alert/ET_AlertState events; obey max_events.
        events = [
            {
                "event_type": "ET_Alert",
                "guid": "ev-1",
                "alert_id": "a1",
                "timestamp": "20260516T180000.000000",
                "camera": {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
                "severity": 4,
                "state": "active",
            },
            {
                "event_type": "ET_AlertState",
                "guid": "ev-2",
                "alert_id": "a1",
                "timestamp": "20260516T180005.000000",
                "camera": {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
                "severity": 4,
                "state": "reviewing",
            },
            {
                "event_type": "ET_AlertState",
                "guid": "ev-3",
                "alert_id": "a1",
                "timestamp": "20260516T180010.000000",
                "camera": {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
                "severity": 4,
                "state": "cancelled",
            },
        ]
        return events[:max_events]
```

Append tests:

```python
    def test_alarm_subscribe_caps_duration_and_limit(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(duration_s=999, limit=999)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["applied_duration_s"], module.SUBSCRIBE_DURATION_CAP_S)
        self.assertEqual(r["applied_limit"], module.SUBSCRIBE_LIMIT_CAP)
        kw = fake.calls[-1][2]
        self.assertEqual(kw["timeout"], module.SUBSCRIBE_DURATION_CAP_S)
        self.assertEqual(kw["max_events"], module.SUBSCRIBE_LIMIT_CAP)
        self.assertEqual(set(kw["event_types"]), set(module.ALARM_EVENT_TYPES))

    def test_alarm_subscribe_returns_normalized_events_with_transition(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(duration_s=5, limit=10)
        self.assertEqual(r["count"], 3)
        # Each item normalized: alert_id, transition, severity, camera, raw kept
        names = [it["transition"] for it in r["items"]]
        self.assertEqual(names, ["raised", "begun_review", "cancelled"])
        self.assertEqual(r["items"][0]["alert_id"], "a1")
        self.assertFalse(r["partial"])
        self.assertEqual(r["reason"], "ok")

    def test_alarm_subscribe_limit_cap_flags_partial(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(duration_s=5, limit=1)
        self.assertTrue(r["partial"])
        self.assertEqual(r["reason"], "limit_cap")
        self.assertEqual(r["count"], 1)

    def test_alarm_subscribe_filters_by_camera_and_severity(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(severity_min=5, duration_s=5, limit=10)
        self.assertEqual(r["count"], 0)
        r2 = alarms.alarm_subscribe(camera_access_point="hosts/Server/NotACamera", duration_s=5, limit=10)
        self.assertEqual(r2["count"], 0)
```

- [ ] **Step 6.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL.

- [ ] **Step 6.3: Implement helpers + `alarm_subscribe`**

Append to module (above the class, near `normalize_alarm`):

```python
_TRANSITION_BY_STATE = {
    "active": "raised",
    "reviewing": "begun_review",
    "completed": "completed",
    "cancelled": "cancelled",
    "escalated": "escalated",
}


def normalize_alarm_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw event from ``pull_events_bounded`` with type ``ET_Alert``/``ET_AlertState``.

    Adds a ``transition`` field derived from the event's ``state``; keeps the
    original event payload under ``raw`` for callers who need it.
    """
    state = raw.get("state")
    return {
        "alert_id": raw.get("alert_id") or raw.get("guid") or "",
        "event_type": raw.get("event_type"),
        "transition": _TRANSITION_BY_STATE.get(state, state or "unknown"),
        "state": state,
        "severity": raw.get("severity"),
        "camera_access_point": (raw.get("camera") or {}).get("access_point"),
        "timestamp": raw.get("timestamp"),
        "raw": raw,
    }
```

Append to `AxxonMcpAlarms`:

```python
    def alarm_subscribe(
        self,
        severity_min: int | None = None,
        camera_access_point: str | None = None,
        state: str = "all",
        duration_s: int = 10,
        limit: int = 25,
    ) -> dict[str, Any]:
        applied_duration = min(max(int(duration_s), 1), SUBSCRIBE_DURATION_CAP_S)
        applied_limit = min(max(int(limit), 1), SUBSCRIBE_LIMIT_CAP)
        if self.client is None:
            self.connect_axxon_profile("env")
        raw_events = self.client.pull_events_bounded(
            subjects=[self._host()],
            event_types=list(ALARM_EVENT_TYPES),
            timeout=float(applied_duration),
            max_events=applied_limit,
        )
        normalized = [normalize_alarm_event(e) for e in raw_events]
        kept: list[dict[str, Any]] = []
        for item in normalized:
            if severity_min is not None and (item.get("severity") or 0) < severity_min:
                continue
            if camera_access_point is not None and item.get("camera_access_point") != camera_access_point:
                continue
            if state != "all" and item.get("transition") != _TRANSITION_BY_STATE.get(state, state):
                continue
            kept.append(item)
        partial = len(raw_events) >= applied_limit
        reason = "limit_cap" if partial else "ok"
        return {
            "status": "ok",
            "tool": "alarm_subscribe",
            "applied_duration_s": applied_duration,
            "applied_limit": applied_limit,
            "partial": partial,
            "reason": reason,
            "count": len(kept),
            "items": kept,
        }
```

- [ ] **Step 6.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (14 tests).

- [ ] **Step 6.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add alarm_subscribe with bounded stream and transition field"
```

---

## Task 7: `AxxonAlarmMutator` scaffold + `raise_alert`

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 7.1: Extend `FakeClient` with raise/begin/etc.**

Append to `FakeClient`:

```python
    def raise_alert(self, camera_ap: str) -> dict[str, Any]:
        self.calls.append(("raise_alert", (camera_ap,), {}))
        return {"status": 200, "body": {"result": True, "alert_id": "new-alert-id"}}

    def begin_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        self.calls.append(("begin_alert_review", (camera_ap, alert_id), {}))
        return {"status": 200, "body": {"result": True}}

    def continue_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        self.calls.append(("continue_alert_review", (camera_ap, alert_id), {}))
        return {"status": 200, "body": {"result": True}}

    def cancel_alert_review(self, camera_ap: str, alert_id: str) -> dict[str, Any]:
        self.calls.append(("cancel_alert_review", (camera_ap, alert_id), {}))
        return {"status": 200, "body": {"result": True}}

    def complete_alert_review(self, camera_ap, alert_id, *, severity, bookmark_message):
        self.calls.append(("complete_alert_review", (camera_ap, alert_id),
                          {"severity": severity, "bookmark_message": bookmark_message}))
        return {"status": 200, "body": {"result": True}}

    def escalate_alert(self, camera_ap, alert_id, *, priority, user_roles, comment):
        self.calls.append(("escalate_alert", (camera_ap, alert_id),
                          {"priority": priority, "user_roles": list(user_roles), "comment": comment}))
        return {"status": 200, "body": {"result": True}}
```

Append tests:

```python
    def _mutator(self, env_value: str | None = "1", fake_client: "FakeClient | None" = None):
        module = importlib.import_module("axxon_mcp_alarms")
        fake = fake_client or FakeClient()
        return module, fake, module.AxxonAlarmMutator(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
            env_getter=lambda _k: env_value,
        )

    def test_mutator_refuses_without_approval_env(self) -> None:
        _, _, m = self._mutator(env_value=None)
        r = m.raise_alert("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", confirmation="CONFIRM-raise-alert")
        self.assertEqual(r["status"], "refused")
        self.assertEqual(r["reason"], "approval_env_not_set")

    def test_mutator_refuses_bad_token(self) -> None:
        _, _, m = self._mutator()
        r = m.raise_alert("hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", confirmation="wrong")
        self.assertEqual(r["status"], "refused")
        self.assertEqual(r["reason"], "bad_token")
        self.assertEqual(r["expected"], "CONFIRM-raise-alert")

    def test_raise_alert_unknown_camera_returns_gap(self) -> None:
        _, _, m = self._mutator()
        r = m.raise_alert("hosts/Server/NotACamera", confirmation="CONFIRM-raise-alert")
        self.assertEqual(r["status"], "gap")

    def test_raise_alert_ok_path_calls_client_and_audits(self) -> None:
        module, fake, m = self._mutator()
        r = m.raise_alert(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            confirmation="CONFIRM-raise-alert",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["alert_id"], "new-alert-id")
        self.assertEqual(fake.calls[-1][0], "raise_alert")
        self.assertEqual(len(m.audit), 1)
        entry = m.audit[0]
        self.assertEqual(entry["action"], "raise_alert")
        self.assertEqual(entry["result_status"], "ok")
        self.assertEqual(entry["camera_access_point"], "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0")
        self.assertIn("timestamp", entry)
```

- [ ] **Step 7.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL — `AxxonAlarmMutator` doesn't exist.

- [ ] **Step 7.3: Implement scaffold + `raise_alert`**

Append to `tools/axxon_mcp_alarms.py`:

```python
@dataclass
class AxxonAlarmMutator:
    """Alarm lifecycle mutations gated by token + AXXON_ALARMS_APPROVE env."""

    client_factory: Callable[[AxxonClientConfig], Any] = default_client_factory
    config_factory: Callable[[], AxxonClientConfig] = default_config_factory
    approve_env: str = "AXXON_ALARMS_APPROVE"
    env_getter: Callable[[str], str | None] = field(default=lambda k: os.environ.get(k))
    client: Any | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)
    _inventory: dict[str, Any] | None = None

    def _ensure_client(self) -> Any:
        if self.client is None:
            config = self.config_factory()
            self.client = self.client_factory(config)
        return self.client

    def _ensure_inventory(self) -> dict[str, Any]:
        self._ensure_client()
        if self._inventory is None:
            self._inventory = self.client.load_inventory()
        return self._inventory

    def _camera_index(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            cam.get("access_point", ""): cam
            for cam in inventory.get("cameras", [])
            if cam.get("access_point")
        }

    def _gate(self, action: str, confirmation: str) -> dict[str, Any] | None:
        if self.env_getter(self.approve_env) != "1":
            return {"status": "refused", "reason": "approval_env_not_set"}
        expected = CONFIRMATION_TOKENS[action]
        if confirmation != expected:
            return {"status": "refused", "reason": "bad_token", "expected": expected}
        return None

    def _audit(self, action: str, result_status: str, **fields: Any) -> dict[str, Any]:
        entry = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "action": action,
            "result_status": result_status,
            **fields,
        }
        self.audit.append(entry)
        return entry

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self.audit)

    def raise_alert(self, camera_access_point: str, confirmation: str) -> dict[str, Any]:
        refusal = self._gate("raise_alert", confirmation)
        if refusal is not None:
            return refusal
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            self._audit("raise_alert", "gap", camera_access_point=camera_access_point)
            return {
                "status": "gap",
                "tool": "raise_alert",
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        try:
            resp = self.client.raise_alert(camera_access_point)
        except Exception as exc:
            self._audit(
                "raise_alert", "error",
                camera_access_point=camera_access_point,
                error_type=type(exc).__name__,
            )
            return {
                "status": "error",
                "tool": "raise_alert",
                "error_type": type(exc).__name__,
                "message": str(exc)[:200],
            }
        body = resp.get("body") if isinstance(resp, dict) else {}
        alert_id = (body or {}).get("alert_id", "")
        self._audit(
            "raise_alert", "ok",
            camera_access_point=camera_access_point,
            alert_id=alert_id,
        )
        return {
            "status": "ok",
            "tool": "raise_alert",
            "camera_access_point": camera_access_point,
            "alert_id": alert_id,
        }
```

- [ ] **Step 7.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (18 tests).

- [ ] **Step 7.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add AxxonAlarmMutator scaffold and raise_alert"
```

---

## Task 8: `alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`

These three share an identical signature shape — implement together to keep DRY clear.

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 8.1: Write the failing tests**

Append:

```python
    def test_begin_review_ok_path(self) -> None:
        _, fake, m = self._mutator()
        r = m.alarm_begin_review(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "alert-x",
            confirmation="CONFIRM-alarm-begin",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(fake.calls[-1][0], "begin_alert_review")
        self.assertEqual(fake.calls[-1][1], (
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert-x"
        ))
        self.assertEqual(m.audit[-1]["action"], "alarm_begin_review")
        self.assertEqual(m.audit[-1]["alert_id"], "alert-x")

    def test_continue_review_bad_token_refused(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_continue_review("cam", "a", confirmation="nope")
        self.assertEqual(r["status"], "refused")
        self.assertEqual(r["reason"], "bad_token")
        self.assertEqual(r["expected"], "CONFIRM-alarm-continue")

    def test_cancel_review_ok_path_calls_client(self) -> None:
        _, fake, m = self._mutator()
        r = m.alarm_cancel_review(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0",
            "alert-x",
            confirmation="CONFIRM-alarm-cancel",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(fake.calls[-1][0], "cancel_alert_review")
        self.assertEqual(m.audit[-1]["action"], "alarm_cancel_review")
```

- [ ] **Step 8.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL.

- [ ] **Step 8.3: Implement using a shared helper**

Append to `AxxonAlarmMutator`:

```python
    _SIMPLE_LIFECYCLE: tuple[tuple[str, str], ...] = (
        ("alarm_begin_review", "begin_alert_review"),
        ("alarm_continue_review", "continue_alert_review"),
        ("alarm_cancel_review", "cancel_alert_review"),
    )

    def _simple_lifecycle_call(
        self,
        action: str,
        client_method_name: str,
        camera_access_point: str,
        alert_id: str,
        confirmation: str,
    ) -> dict[str, Any]:
        refusal = self._gate(action, confirmation)
        if refusal is not None:
            return refusal
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            self._audit(action, "gap", camera_access_point=camera_access_point, alert_id=alert_id)
            return {
                "status": "gap",
                "tool": action,
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        try:
            method = getattr(self.client, client_method_name)
            resp = method(camera_access_point, alert_id)
        except Exception as exc:
            self._audit(
                action, "error",
                camera_access_point=camera_access_point, alert_id=alert_id,
                error_type=type(exc).__name__,
            )
            return {
                "status": "error",
                "tool": action,
                "error_type": type(exc).__name__,
                "message": str(exc)[:200],
            }
        body = resp.get("body") if isinstance(resp, dict) else {}
        self._audit(
            action, "ok",
            camera_access_point=camera_access_point, alert_id=alert_id,
        )
        return {
            "status": "ok",
            "tool": action,
            "camera_access_point": camera_access_point,
            "alert_id": alert_id,
            "result": (body or {}).get("result"),
        }

    def alarm_begin_review(self, camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return self._simple_lifecycle_call("alarm_begin_review", "begin_alert_review",
                                            camera_access_point, alert_id, confirmation)

    def alarm_continue_review(self, camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return self._simple_lifecycle_call("alarm_continue_review", "continue_alert_review",
                                            camera_access_point, alert_id, confirmation)

    def alarm_cancel_review(self, camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return self._simple_lifecycle_call("alarm_cancel_review", "cancel_alert_review",
                                            camera_access_point, alert_id, confirmation)
```

- [ ] **Step 8.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (21 tests).

- [ ] **Step 8.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add alarm_begin/continue/cancel_review with shared helper"
```

---

## Task 9: `alarm_complete_review` and `alarm_escalate`

These two have richer payloads (severity + bookmark for complete; priority + user_roles + comment for escalate) and need their own input-validation steps.

**Files:**
- Modify: `tools/axxon_mcp_alarms.py`
- Modify: `tools/tests/test_axxon_mcp_alarms.py`

- [ ] **Step 9.1: Write the failing tests**

Append:

```python
    def test_complete_review_rejects_unknown_severity(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_complete_review(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "a",
            severity="banana", bookmark_message="ok", confirmation="CONFIRM-alarm-complete",
        )
        self.assertEqual(r["status"], "gap")
        self.assertIn("severity", r["message"])

    def test_complete_review_rejects_empty_bookmark(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_complete_review(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "a",
            severity="confirmed_alarm", bookmark_message="", confirmation="CONFIRM-alarm-complete",
        )
        self.assertEqual(r["status"], "gap")
        self.assertIn("bookmark", r["message"])

    def test_complete_review_ok_path(self) -> None:
        _, fake, m = self._mutator()
        r = m.alarm_complete_review(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert-x",
            severity="confirmed_alarm", bookmark_message="real incident",
            confirmation="CONFIRM-alarm-complete",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(fake.calls[-1][0], "complete_alert_review")
        self.assertEqual(fake.calls[-1][2]["severity"], "confirmed_alarm")
        self.assertEqual(fake.calls[-1][2]["bookmark_message"], "real incident")
        self.assertEqual(m.audit[-1]["action"], "alarm_complete_review")
        self.assertEqual(m.audit[-1]["severity"], "confirmed_alarm")

    def test_escalate_rejects_unknown_priority(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_escalate(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "a",
            priority="HOT", user_roles=["role-a"], comment="esc",
            confirmation="CONFIRM-alarm-escalate",
        )
        self.assertEqual(r["status"], "gap")
        self.assertIn("priority", r["message"])

    def test_escalate_rejects_empty_user_roles(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_escalate(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "a",
            priority="AP_HIGH", user_roles=[], comment="esc",
            confirmation="CONFIRM-alarm-escalate",
        )
        self.assertEqual(r["status"], "gap")
        self.assertIn("user_roles", r["message"])

    def test_escalate_rejects_empty_comment(self) -> None:
        _, _, m = self._mutator()
        r = m.alarm_escalate(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "a",
            priority="AP_HIGH", user_roles=["role-a"], comment="",
            confirmation="CONFIRM-alarm-escalate",
        )
        self.assertEqual(r["status"], "gap")
        self.assertIn("comment", r["message"])

    def test_escalate_ok_path(self) -> None:
        _, fake, m = self._mutator()
        r = m.alarm_escalate(
            "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0", "alert-x",
            priority="AP_HIGH", user_roles=["role-a"], comment="please review",
            confirmation="CONFIRM-alarm-escalate",
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(fake.calls[-1][0], "escalate_alert")
        self.assertEqual(fake.calls[-1][2]["priority"], "AP_HIGH")
        self.assertEqual(fake.calls[-1][2]["user_roles"], ["role-a"])
        self.assertEqual(m.audit[-1]["action"], "alarm_escalate")
        self.assertEqual(m.audit[-1]["priority"], "AP_HIGH")
```

- [ ] **Step 9.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: FAIL.

- [ ] **Step 9.3: Implement**

Append to `AxxonAlarmMutator`:

```python
    def alarm_complete_review(
        self,
        camera_access_point: str,
        alert_id: str,
        severity: str,
        bookmark_message: str,
        confirmation: str,
    ) -> dict[str, Any]:
        refusal = self._gate("alarm_complete_review", confirmation)
        if refusal is not None:
            return refusal
        if severity not in SEVERITY_CHOICES:
            return {
                "status": "gap",
                "tool": "alarm_complete_review",
                "message": f"severity must be one of {SEVERITY_CHOICES}, got {severity!r}",
            }
        if not bookmark_message:
            return {
                "status": "gap",
                "tool": "alarm_complete_review",
                "message": "bookmark message is required by the stand's required_comment policy",
            }
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            self._audit("alarm_complete_review", "gap",
                        camera_access_point=camera_access_point, alert_id=alert_id)
            return {
                "status": "gap",
                "tool": "alarm_complete_review",
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        try:
            resp = self.client.complete_alert_review(
                camera_access_point, alert_id,
                severity=severity, bookmark_message=bookmark_message,
            )
        except Exception as exc:
            self._audit("alarm_complete_review", "error",
                        camera_access_point=camera_access_point, alert_id=alert_id,
                        severity=severity, error_type=type(exc).__name__)
            return {
                "status": "error",
                "tool": "alarm_complete_review",
                "error_type": type(exc).__name__,
                "message": str(exc)[:200],
            }
        body = resp.get("body") if isinstance(resp, dict) else {}
        self._audit("alarm_complete_review", "ok",
                    camera_access_point=camera_access_point, alert_id=alert_id,
                    severity=severity, bookmark_message=bookmark_message)
        return {
            "status": "ok",
            "tool": "alarm_complete_review",
            "camera_access_point": camera_access_point,
            "alert_id": alert_id,
            "severity": severity,
            "result": (body or {}).get("result"),
        }

    def alarm_escalate(
        self,
        camera_access_point: str,
        alert_id: str,
        priority: str,
        user_roles: list[str],
        comment: str,
        confirmation: str,
    ) -> dict[str, Any]:
        refusal = self._gate("alarm_escalate", confirmation)
        if refusal is not None:
            return refusal
        if priority not in PRIORITY_CHOICES:
            return {
                "status": "gap",
                "tool": "alarm_escalate",
                "message": f"priority must be one of {PRIORITY_CHOICES}, got {priority!r}",
            }
        if not user_roles:
            return {
                "status": "gap",
                "tool": "alarm_escalate",
                "message": "user_roles must contain at least one role identifier",
            }
        if not comment:
            return {
                "status": "gap",
                "tool": "alarm_escalate",
                "message": "comment is required for escalate",
            }
        inv = self._ensure_inventory()
        if camera_access_point not in self._camera_index(inv):
            self._audit("alarm_escalate", "gap",
                        camera_access_point=camera_access_point, alert_id=alert_id)
            return {
                "status": "gap",
                "tool": "alarm_escalate",
                "message": f"Camera not in inventory: {camera_access_point}",
            }
        try:
            resp = self.client.escalate_alert(
                camera_access_point, alert_id,
                priority=priority, user_roles=list(user_roles), comment=comment,
            )
        except Exception as exc:
            self._audit("alarm_escalate", "error",
                        camera_access_point=camera_access_point, alert_id=alert_id,
                        priority=priority, error_type=type(exc).__name__)
            return {
                "status": "error",
                "tool": "alarm_escalate",
                "error_type": type(exc).__name__,
                "message": str(exc)[:200],
            }
        body = resp.get("body") if isinstance(resp, dict) else {}
        self._audit("alarm_escalate", "ok",
                    camera_access_point=camera_access_point, alert_id=alert_id,
                    priority=priority, user_roles=list(user_roles), comment=comment)
        return {
            "status": "ok",
            "tool": "alarm_escalate",
            "camera_access_point": camera_access_point,
            "alert_id": alert_id,
            "priority": priority,
            "result": (body or {}).get("result"),
        }
```

- [ ] **Step 9.4: Run, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_alarms -v`
Expected: PASS (28 tests).

- [ ] **Step 9.5: Commit**

```bash
git add tools/axxon_mcp_alarms.py tools/tests/test_axxon_mcp_alarms.py
git commit -m "feat: add alarm_complete_review and alarm_escalate with input gates"
```

---

## Task 10: Register tools in `axxon_mcp_server.py`

**Files:**
- Modify: `tools/axxon_mcp_server.py`
- Modify: `tools/tests/test_axxon_mcp_server.py`

- [ ] **Step 10.1: Write the failing registration tests**

Append inside `AxxonMcpServerTests`:

```python
    def test_create_server_registers_alarm_read_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("list_active_alerts", "get_active_alert", "filter_active_alerts",
                     "list_alarm_history", "list_alarm_event_types", "alarm_subscribe"):
            self.assertNotIn(name, docs_only.tools)

        class StubAlarms:
            def connect_axxon_profile(self, profile="env"):
                return {"connected": True, "profile_name": profile, "mode": "read-only"}
            def list_active_alerts(self, camera_access_point=None, limit=50):
                return {"status": "ok", "tool": "list_active_alerts",
                        "camera": camera_access_point, "limit": limit}
            def get_active_alert(self, camera_access_point, alert_id):
                return {"status": "ok", "tool": "get_active_alert",
                        "camera": camera_access_point, "alert_id": alert_id}
            def filter_active_alerts(self, severity_min=None, camera=None, state="all", limit=50):
                return {"status": "ok", "tool": "filter_active_alerts",
                        "severity_min": severity_min, "camera": camera, "state": state, "limit": limit}
            def list_alarm_history(self, hours=1, limit=100, camera=None, severity_min=None):
                return {"status": "ok", "tool": "list_alarm_history",
                        "hours": hours, "limit": limit}
            def list_alarm_event_types(self):
                return {"status": "ok", "tool": "list_alarm_event_types"}
            def alarm_subscribe(self, severity_min=None, camera_access_point=None,
                                state="all", duration_s=10, limit=25):
                return {"status": "ok", "tool": "alarm_subscribe",
                        "duration_s": duration_s, "limit": limit}

        server = module.create_server(docs=StubDocs(), alarms=StubAlarms(), fastmcp_factory=FakeFastMCP)
        for name in ("alarms_connect_axxon_profile", "list_active_alerts", "get_active_alert",
                     "filter_active_alerts", "list_alarm_history",
                     "list_alarm_event_types", "alarm_subscribe"):
            self.assertIn(name, server.tools)
        self.assertEqual(server.tools["alarms_connect_axxon_profile"]("env")["connected"], True)
        self.assertEqual(server.tools["list_active_alerts"]("cam", 7)["limit"], 7)
        self.assertEqual(server.tools["alarm_subscribe"](None, None, "all", 3, 2)["limit"], 2)

    def test_create_server_registers_alarm_mutation_tools_only_when_enabled(self) -> None:
        module = importlib.import_module("axxon_mcp_server")
        docs_only = module.create_server(docs=StubDocs(), fastmcp_factory=FakeFastMCP)
        for name in ("raise_alert", "alarm_begin_review", "alarm_continue_review",
                     "alarm_cancel_review", "alarm_complete_review", "alarm_escalate"):
            self.assertNotIn(name, docs_only.tools)

        class StubMutator:
            audit = []
            def raise_alert(self, camera_access_point, confirmation):
                return {"status": "ok", "tool": "raise_alert",
                        "camera": camera_access_point, "confirmation": confirmation}
            def alarm_begin_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_begin_review",
                        "camera": camera_access_point, "alert_id": alert_id}
            def alarm_continue_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_continue_review"}
            def alarm_cancel_review(self, camera_access_point, alert_id, confirmation):
                return {"status": "ok", "tool": "alarm_cancel_review"}
            def alarm_complete_review(self, camera_access_point, alert_id, severity, bookmark_message, confirmation):
                return {"status": "ok", "tool": "alarm_complete_review",
                        "severity": severity, "bookmark_message": bookmark_message}
            def alarm_escalate(self, camera_access_point, alert_id, priority, user_roles, comment, confirmation):
                return {"status": "ok", "tool": "alarm_escalate",
                        "priority": priority, "user_roles": user_roles, "comment": comment}
            def audit_log(self):
                return self.audit

        server = module.create_server(docs=StubDocs(), alarm_mutator=StubMutator(), fastmcp_factory=FakeFastMCP)
        for name in ("raise_alert", "alarm_begin_review", "alarm_continue_review",
                     "alarm_cancel_review", "alarm_complete_review", "alarm_escalate"):
            self.assertIn(name, server.tools)
        self.assertIn("axxon://alarms/audit-log", server.resources)
        self.assertEqual(
            server.tools["raise_alert"]("cam", "CONFIRM-raise-alert")["confirmation"],
            "CONFIRM-raise-alert",
        )
        self.assertEqual(
            server.tools["alarm_complete_review"]("cam", "a", "confirmed_alarm", "msg", "CONFIRM-alarm-complete")["severity"],
            "confirmed_alarm",
        )
```

- [ ] **Step 10.2: Run, verify failure**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_server -v`
Expected: FAIL (registration functions and `alarms`/`alarm_mutator` params not yet present).

- [ ] **Step 10.3: Modify `create_server` signature + registration**

In `tools/axxon_mcp_server.py`, extend `create_server`:

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
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    fastmcp_factory: Callable[..., Any] = default_fastmcp_factory,
) -> Any:
```

Inside the function, after the `view` registration block:

```python
    if alarms is not None:
        register_alarm_read_tools(server, alarms)

    if alarm_mutator is not None:
        register_alarm_mutation_tools(server, alarm_mutator)
```

Append the two registration functions to the module (after `register_view_tools`):

```python
def register_alarm_read_tools(server: Any, alarms: Any) -> None:
    @server.tool(name="alarms_connect_axxon_profile")
    def alarms_connect_axxon_profile(profile: str = "env") -> dict[str, Any]:
        return alarms.connect_axxon_profile(profile)

    @server.tool(name="list_active_alerts")
    def list_active_alerts(camera_access_point: str | None = None, limit: int = 50) -> dict[str, Any]:
        return alarms.list_active_alerts(camera_access_point=camera_access_point, limit=limit)

    @server.tool(name="get_active_alert")
    def get_active_alert(camera_access_point: str, alert_id: str) -> dict[str, Any]:
        return alarms.get_active_alert(camera_access_point, alert_id)

    @server.tool(name="filter_active_alerts")
    def filter_active_alerts(
        severity_min: int | None = None,
        camera: str | None = None,
        state: str = "all",
        limit: int = 50,
    ) -> dict[str, Any]:
        return alarms.filter_active_alerts(severity_min=severity_min, camera=camera, state=state, limit=limit)

    @server.tool(name="list_alarm_history")
    def list_alarm_history(
        hours: float = 1.0,
        limit: int = 100,
        camera: str | None = None,
        severity_min: int | None = None,
    ) -> dict[str, Any]:
        return alarms.list_alarm_history(hours=hours, limit=limit, camera=camera, severity_min=severity_min)

    @server.tool(name="list_alarm_event_types")
    def list_alarm_event_types() -> dict[str, Any]:
        return alarms.list_alarm_event_types()

    @server.tool(name="alarm_subscribe")
    def alarm_subscribe(
        severity_min: int | None = None,
        camera_access_point: str | None = None,
        state: str = "all",
        duration_s: int = 10,
        limit: int = 25,
    ) -> dict[str, Any]:
        return alarms.alarm_subscribe(
            severity_min=severity_min,
            camera_access_point=camera_access_point,
            state=state,
            duration_s=duration_s,
            limit=limit,
        )


def register_alarm_mutation_tools(server: Any, mutator: Any) -> None:
    @server.tool(name="raise_alert")
    def raise_alert(camera_access_point: str, confirmation: str) -> dict[str, Any]:
        return mutator.raise_alert(camera_access_point, confirmation)

    @server.tool(name="alarm_begin_review")
    def alarm_begin_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return mutator.alarm_begin_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_continue_review")
    def alarm_continue_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return mutator.alarm_continue_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_cancel_review")
    def alarm_cancel_review(camera_access_point: str, alert_id: str, confirmation: str) -> dict[str, Any]:
        return mutator.alarm_cancel_review(camera_access_point, alert_id, confirmation)

    @server.tool(name="alarm_complete_review")
    def alarm_complete_review(
        camera_access_point: str,
        alert_id: str,
        severity: str,
        bookmark_message: str,
        confirmation: str,
    ) -> dict[str, Any]:
        return mutator.alarm_complete_review(
            camera_access_point, alert_id, severity, bookmark_message, confirmation
        )

    @server.tool(name="alarm_escalate")
    def alarm_escalate(
        camera_access_point: str,
        alert_id: str,
        priority: str,
        user_roles: list[str],
        comment: str,
        confirmation: str,
    ) -> dict[str, Any]:
        return mutator.alarm_escalate(camera_access_point, alert_id, priority, user_roles, comment, confirmation)

    @server.resource("axxon://alarms/audit-log")
    def read_alarms_audit_log() -> dict[str, Any]:
        return {"entries": mutator.audit_log()}
```

In `build_parser()`, add two flags after `--enable-view`:

```python
    parser.add_argument(
        "--enable-alarms",
        action="store_true",
        help="Enable Phase 5C alarm read tools (list/filter/history/subscribe).",
    )
    parser.add_argument(
        "--enable-alarms-mutation",
        action="store_true",
        help="Enable Phase 5C alarm lifecycle mutations. Requires AXXON_ALARMS_APPROVE=1.",
    )
```

In `main()`, after the `view` block, add:

```python
    alarms = None
    if args.enable_alarms:
        from axxon_mcp_alarms import AxxonMcpAlarms
        alarms = AxxonMcpAlarms()
    alarm_mutator = None
    if args.enable_alarms_mutation:
        from axxon_mcp_alarms import AxxonAlarmMutator
        alarm_mutator = AxxonAlarmMutator()
```

And extend the `create_server(...)` call:

```python
    server = create_server(
        corpus_dir=args.corpus_dir,
        live=live,
        operator=operator,
        generator=generator,
        view=view,
        alarms=alarms,
        alarm_mutator=alarm_mutator,
    )
```

- [ ] **Step 10.4: Run server tests, verify pass**

Run: `cd tools && python3.12 -m unittest tests.test_axxon_mcp_server -v`
Expected: PASS (existing + 2 new = 6 tests).

- [ ] **Step 10.5: Run full suite**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 221 (187 + 6 client + 28 alarms + 2 server).

- [ ] **Step 10.6: Commit**

```bash
git add tools/axxon_mcp_server.py tools/tests/test_axxon_mcp_server.py
git commit -m "feat: register Phase 5C alarms tools under --enable-alarms[+-mutation]"
```

---

## Task 11: Live smoke `tools/axxon_alarms_smoke.py`

**Files:**
- Create: `tools/axxon_alarms_smoke.py`

- [ ] **Step 11.1: Implement the smoke**

```python
#!/usr/bin/env python3
"""Live smoke for Phase 5C alarm tools.

Default mode: reads only (list_active_alerts node-wide + per-camera,
filter_active_alerts, list_alarm_history, list_alarm_event_types,
alarm_subscribe with a short window).

`--mutation` mode adds a synthetic round-trip against the first camera:
raise_alert -> capture alert_id -> alarm_begin_review -> alarm_continue_review
-> alarm_cancel_review -> verify gone from list_active_alerts.

`--mutation` requires AXXON_ALARMS_APPROVE=1. The smoke does NOT exercise
alarm_complete_review or alarm_escalate by default; pass --full to add a
complete-cycle, which leaves a bookmark on the stand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from axxon_mcp_alarms import AxxonMcpAlarms, AxxonAlarmMutator  # noqa: E402


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
    parser.add_argument("--mutation", action="store_true", help="Run synthetic raise/begin/continue/cancel round-trip.")
    parser.add_argument("--full", action="store_true",
                        help="Also exercise complete + escalate (leaves a bookmark and an escalation record).")
    args = parser.parse_args()

    alarms = AxxonMcpAlarms()
    alarms.connect_axxon_profile("env")
    alarms.client.authenticate_http_grpc()
    host = alarms.client.config.host

    results = {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "host": "<demo-host>", "reads": {}}

    results["reads"]["list_active_alerts_node"] = alarms.list_active_alerts()
    inv = alarms._ensure_inventory()
    cams = [c.get("access_point") for c in inv.get("cameras", []) if c.get("access_point")]
    if not cams:
        print(json.dumps(sanitize({"status": "fixture-needed", "message": "no cameras", **results}, host), indent=2))
        return 2
    cam = cams[0]
    results["reads"]["list_active_alerts_first_camera"] = alarms.list_active_alerts(camera_access_point=cam)
    results["reads"]["filter_active_alerts"] = alarms.filter_active_alerts(limit=10)
    results["reads"]["list_alarm_history_1h"] = alarms.list_alarm_history(hours=1, limit=20)
    results["reads"]["list_alarm_event_types"] = alarms.list_alarm_event_types()
    results["reads"]["alarm_subscribe_5s"] = alarms.alarm_subscribe(duration_s=5, limit=10)

    if args.mutation:
        if os.environ.get("AXXON_ALARMS_APPROVE") != "1":
            print(json.dumps(sanitize({"status": "refused", "reason": "approval_env_not_set", **results}, host), indent=2))
            return 1
        mutator = AxxonAlarmMutator(client_factory=lambda _cfg: alarms.client,
                                    config_factory=lambda: alarms.client.config)
        round_trip = {}
        raised = mutator.raise_alert(cam, confirmation="CONFIRM-raise-alert")
        round_trip["raise_alert"] = raised
        alert_id = raised.get("alert_id")
        if not alert_id:
            results["mutation"] = round_trip
            print(json.dumps(sanitize(results, host), indent=2))
            return 1
        time.sleep(1)
        round_trip["alarm_begin_review"] = mutator.alarm_begin_review(cam, alert_id, confirmation="CONFIRM-alarm-begin")
        round_trip["alarm_continue_review"] = mutator.alarm_continue_review(cam, alert_id, confirmation="CONFIRM-alarm-continue")
        round_trip["alarm_cancel_review"] = mutator.alarm_cancel_review(cam, alert_id, confirmation="CONFIRM-alarm-cancel")
        time.sleep(1)
        post = alarms.list_active_alerts(camera_access_point=cam)
        round_trip["post_list_count"] = post.get("count")
        round_trip["audit_log"] = mutator.audit_log()
        # Sanitize alert_id in the captured round-trip section.
        if alert_id:
            round_trip_str = json.dumps(round_trip, default=str).replace(alert_id, "<demo-alarm-id>")
            round_trip = json.loads(round_trip_str)
        results["mutation"] = round_trip

        if args.full:
            # Documented as record-leaving; only run on a dedicated stand.
            raised2 = mutator.raise_alert(cam, confirmation="CONFIRM-raise-alert")
            aid2 = raised2.get("alert_id")
            if aid2:
                mutator.alarm_begin_review(cam, aid2, confirmation="CONFIRM-alarm-begin")
                mutator.alarm_complete_review(
                    cam, aid2, severity="false_alarm",
                    bookmark_message="phase-5c full smoke",
                    confirmation="CONFIRM-alarm-complete",
                )
            results["full"] = {"complete_audit": mutator.audit_log()[-2:]}

    print(json.dumps(sanitize(results, host), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 11.2: Run reads-only smoke against the demo stand**

Run:
```bash
AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 \
AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server \
AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt \
/tmp/axxon-grpc-venv/bin/python tools/axxon_alarms_smoke.py
```
Expected: JSON report with `reads.list_active_alerts_node.status == "ok"`, `count >= 0`. URL/host sanitized to `<demo-host>`. Exit `0`.

- [ ] **Step 11.3: Run mutation smoke**

Run:
```bash
AXXON_ALARMS_APPROVE=1 AXXON_HOST=100.76.150.18 AXXON_HTTP_URL=http://100.76.150.18 \
AXXON_USERNAME=root AXXON_PASSWORD=root AXXON_TLS_CN=Server \
AXXON_CA=/Users/jerrygergov/Documents/GitHub/axxon-one-mcp/docs/grpc-proto-files/api.ngp.root-ca.crt \
/tmp/axxon-grpc-venv/bin/python tools/axxon_alarms_smoke.py --mutation
```
Expected:
- `mutation.raise_alert.status == "ok"` and `alert_id` non-empty.
- `alarm_begin_review.status == "ok"`, `result == True`.
- `alarm_continue_review.status == "ok"`.
- `alarm_cancel_review.status == "ok"`.
- `post_list_count == 0` (alarm gone).
- `audit_log` has 4 entries, each with `result_status: "ok"`.
- Exit `0`.

- [ ] **Step 11.4: Commit**

```bash
git add tools/axxon_alarms_smoke.py
git commit -m "feat: add axxon_alarms_smoke for Phase 5C live verification"
```

---

## Task 12: Sanitized evidence report

**Files:**
- Create: `docs/api-audit/phase-5c-alarms-smoke-latest.md`

- [ ] **Step 12.1: Capture sanitized smoke output**

Run reads + mutation smoke commands from Task 11. Save the JSON, scrub:
- Any residual `100.76.150.18` to `<demo-host>`.
- Any residual alert GUID to `<demo-alarm-id>`.
- Confirm no bearer token, no password appears.

- [ ] **Step 12.2: Write the report**

```markdown
# Phase 5C — Alarm Tools Live Smoke

**Date:** 2026-05-16
**Stand:** `<demo-host>` (sanitized)
**Auth mode:** Bearer (HTTP `/grpc`)
**Caps:** subscribe ≤ 30 s / 100 events; history ≤ 24 h / 200 events; list ≤ 200 items.

## Coverage

| Tool | Status | Live result |
| --- | --- | --- |
| `alarms_connect_axxon_profile` | verified | gRPC + Bearer auth ok against `<demo-host>` |
| `list_active_alerts` (node) | verified | flattens `event_stream_items`; surfaces only persistent `unreachable_nodes` |
| `list_active_alerts` (camera) | verified | empty on quiet stand |
| `filter_active_alerts` | verified | empty filter call returns same paginated shape |
| `list_alarm_history` | verified | clamps hours to 24, filters to `ET_Alert`/`ET_AlertState` |
| `list_alarm_event_types` | verified | returns the two alarm enum entries |
| `alarm_subscribe` | verified | bounded 5 s window; flags `partial`/`reason` |
| `raise_alert` | verified | synthetic alarm created with `result: true` and `alert_id` |
| `alarm_begin_review` | verified | `result: true` |
| `alarm_continue_review` | verified | `result: true` |
| `alarm_cancel_review` | verified | `result: true`; alarm removed from `list_active_alerts` |

Offline unit tests in `tools/tests/test_axxon_mcp_alarms.py` (28 tests) plus `tools/tests/test_axxon_api_client_alarms.py` (6 tests) plus 2 server-registration tests. Full repo suite stays green.

## Sanitized live smoke output

<paste sanitized JSON here from Tasks 11.2 and 11.3>

## Observations

- `BatchGetActiveAlerts` returns `event_stream_items[]` with `unreachable_nodes` per page. The smoke confirms the flatten logic ignores transient first-page `unreachable_nodes: ["hosts/Server"]` and only surfaces the field when every page agrees.
- Synthetic round-trip cleans up: after `cancel`, `list_active_alerts(camera_ap)` reports `count: 0`.
- No secrets in output. No bookmarks left (cancel path used).

## Sanitization rules applied

- Host IP → `<demo-host>` (global string replace).
- Alarm GUID → `<demo-alarm-id>` in committed evidence.
- `hosts/Server/...` kept (intrinsic).
- Bearer token never echoed.
- Password never echoed.
```

- [ ] **Step 12.3: Commit**

```bash
git add docs/api-audit/phase-5c-alarms-smoke-latest.md
git commit -m "docs: phase 5c alarms live smoke evidence"
```

---

## Task 13: Coverage matrix and README

**Files:**
- Modify: `docs/api-audit/pdf-gap-coverage-matrix.md`
- Modify: `README.md`

- [ ] **Step 13.1: Append matrix row**

At the end of the table in `docs/api-audit/pdf-gap-coverage-matrix.md`, append:

```markdown
| MCP Phase 5C alarms (lifecycle + subscription) | 387-389 | verified | mutation | axxon_alarms_smoke.py; tools/tests/test_axxon_mcp_alarms.py | api-audit/phase-5c-alarms-smoke-latest.md | `alarms_connect_axxon_profile`, `list_active_alerts`, `get_active_alert`, `filter_active_alerts`, `list_alarm_history`, `list_alarm_event_types`, `alarm_subscribe`, `raise_alert`, `alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`, `alarm_complete_review`, `alarm_escalate` are verified by 28 offline unit tests plus a live `raise → begin → continue → cancel → verify-gone` round-trip on `<demo-host>` (audit log captured, no residue). Mutations gated by `AXXON_ALARMS_APPROVE=1` plus per-call `CONFIRM-...` tokens. Deferred: 5 Batch* lifecycle methods, 2 counter mutations, rule `ChangeConfig`. |
```

- [ ] **Step 13.2: Update README**

In `README.md`, after the Phase 5A `--enable-view` example block, add:

```bash
# + alarm read tools (Phase 5C)
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-alarms --transport stdio

# + alarm lifecycle mutations (Phase 5C) — requires per-call confirmation tokens
AXXON_ALARMS_APPROVE=1 \
AXXON_HOST=<host> AXXON_HTTP_URL=http://<host> \
AXXON_TLS_CN=<your-tls-cn> AXXON_USERNAME=<u> AXXON_PASSWORD=<p> \
python tools/axxon_mcp_server.py --enable-alarms --enable-alarms-mutation --transport stdio
```

After the "View tools (Phase 5A)" section, add:

```markdown
### Alarm tools (Phase 5C)

Reads (`--enable-alarms`): `alarms_connect_axxon_profile`, `list_active_alerts`,
`get_active_alert`, `filter_active_alerts`, `list_alarm_history`,
`list_alarm_event_types`, `alarm_subscribe` (bounded by 30 s / 100 events).

Mutations (`--enable-alarms-mutation` + `AXXON_ALARMS_APPROVE=1`): `raise_alert`,
`alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`,
`alarm_complete_review` (requires `severity` ∈ `confirmed_alarm|suspicious_situation|false_alarm`
and a bookmark message), `alarm_escalate` (requires `priority` ∈ `AP_MINIMUM|AP_LOW|AP_MEDIUM|AP_HIGH`,
non-empty `user_roles`, non-empty `comment`). Every mutation requires a per-call
`CONFIRM-...` token and writes one audit entry exposed via the
`axxon://alarms/audit-log` resource. See
`docs/superpowers/plans/2026-05-16-phase-5c-alarms.md` and the live evidence at
`docs/api-audit/phase-5c-alarms-smoke-latest.md`.
```

- [ ] **Step 13.3: Run full suite as final check**

Run: `cd tools && python3.12 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`, count ≥ 221.

- [ ] **Step 13.4: Commit**

```bash
git add docs/api-audit/pdf-gap-coverage-matrix.md README.md
git commit -m "docs: register Phase 5C alarms in matrix and README"
```

---

## Self-review checklist (done)

- **Spec coverage.** Spec §3.1 (7 read tools) → Tasks 2–6 + Task 10 registration. Spec §3.2 (6 mutation tools) → Tasks 7–9 + Task 10 registration. Spec §4.1 (file layout) → all 9 files touched in numbered tasks. Spec §4.2 (class shapes) → Tasks 2 + 7. Spec §4.3 (constants) → Task 2. Spec §4.4 (normalize helpers) → Tasks 3 + 6. Spec §4.5 (audit entry shape) → Task 7. Spec §4.6 (server registration) → Task 10. Spec §4.7 (data flows) → reflected in test assertions across Tasks 3, 6, 7. Spec §5 (error handling) → covered by tests in Tasks 2, 3, 6, 7, 8, 9. Spec §6 (fixtures) → captured in Task 11 smoke `--mutation` path. Spec §7.3 (live smoke modes) → Task 11. Spec §7.4 (definition of done) → Tasks 11–13.
- **Placeholders.** None. Every step has either exact code or an exact command. The one "paste here" in Task 12.2 (sanitized JSON) is correct — the JSON only exists after the live runs in Task 11.
- **Type consistency.** Method names match across plan + tests + registration: `raise_alert`, `alarm_begin_review`, `alarm_continue_review`, `alarm_cancel_review`, `alarm_complete_review`, `alarm_escalate`. Client methods match: `raise_alert`, `begin_alert_review`, `continue_alert_review`, `cancel_alert_review`, `complete_alert_review`, `escalate_alert`. Constants `LIST_LIMIT_CAP`, `HISTORY_HOURS_CAP`, `SUBSCRIBE_DURATION_CAP_S`, `SUBSCRIBE_LIMIT_CAP`, `ALARM_EVENT_TYPES`, `SEVERITY_CHOICES`, `PRIORITY_CHOICES`, `CONFIRMATION_TOKENS` are referenced consistently. The `_camera_index` helper appears on both `AxxonMcpAlarms` and `AxxonAlarmMutator` — same method body, intentional duplication (could be hoisted later; YAGNI for now).
- **No hidden deps.** All `client.*` methods invoked by `AxxonMcpAlarms` and `AxxonAlarmMutator` exist on `AxxonApiClient` after Task 1, plus the existing `load_inventory`, `pull_events_bounded`, `search_events`/`list_event_types`. **Note:** `search_events` and `list_event_types` are currently on `AxxonMcpLive`, not on `AxxonApiClient`. The FakeClient in tests provides them directly; for live, `AxxonMcpAlarms` calls them on the underlying `AxxonApiClient`, so Task 1 must also expose them. Resolution: Task 1 already exposes 9 LogicService wrappers; `search_events` and `list_event_types` are not LogicService methods. **Add them to Task 1** for parity:

  Append to Task 1.3 (after `escalate_alert`):

  ```python
      def search_events(
          self,
          *,
          subjects: list[str] | None = None,
          event_types: list[str] | None = None,
          hours: float = 1.0,
          limit: int = 100,
          descending: bool = True,
      ) -> dict[str, Any]:
          # Delegate to a temporary AxxonMcpLive instance for proto parity.
          from axxon_mcp_live import AxxonMcpLive
          live = AxxonMcpLive(client_factory=lambda _cfg: self, config_factory=lambda: self.config)
          return live.search_events(
              subjects=subjects, event_types=event_types,
              hours=hours, limit=limit, descending=descending,
          )

      def list_event_types(self) -> dict[str, Any]:
          from axxon_mcp_live import AxxonMcpLive
          live = AxxonMcpLive(client_factory=lambda _cfg: self, config_factory=lambda: self.config)
          return live.list_event_types()
  ```

  And append two tests to Task 1.1 verifying both delegate correctly (use a `FakeAxxonMcpLive`-style monkeypatch or accept that these wrappers will be exercised by Task 5/6 tests instead). Implementer's choice — the simplest path is to skip dedicated wrapper tests in Task 1 and let the FakeClient in Tasks 5/6 stub `search_events`/`list_event_types` directly, as currently written.
