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

    def batch_filter_active_alerts(self, nodes: list[str], filter: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(("batch_filter_active_alerts", (tuple(nodes),), dict(filter or {})))
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


if __name__ == "__main__":
    unittest.main()
