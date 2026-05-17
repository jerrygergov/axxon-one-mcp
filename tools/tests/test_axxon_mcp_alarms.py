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
        events = getattr(self, "history_events", None)
        if events is None:
            events = [{
                "type": "ET_Alert",
                "guid": "hist-1",
                "timestamp": "20260516T170000.000000",
                "camera": {"access_point": "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"},
            }]
        return {
            "status": "ok",
            "subjects": list(subjects or []),
            "event_types": list(event_types or []),
            "hours": hours,
            "limit": limit,
            "count": len(events),
            "events": list(events),
        }

    def list_event_types(self) -> dict[str, Any]:
        self.calls.append(("list_event_types", (), {}))
        items = [
            {"name": "ET_DetectorEvent", "value": 1},
            {"name": "ET_Alert", "value": 15},
            {"name": "ET_AlertState", "value": 16},
        ]
        return {"status": "ok", "count": len(items), "items": items}

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

    def test_filter_active_alerts_bad_state_returns_gap_even_when_empty(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        fake.batch_alert_pages = []  # no items at all
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.filter_active_alerts(state="not_a_real_state")
        self.assertEqual(r["status"], "gap")
        self.assertIn("not_a_real_state", r["message"])

    def test_get_active_alert_unknown_camera_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: FakeClient(),
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.get_active_alert("hosts/Server/NotACamera", "any")
        self.assertEqual(r["status"], "gap")
        self.assertIn("NotACamera", r["message"])

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
        self.assertEqual(r["count"], 2)
        names = {it["name"] for it in r["items"]}
        self.assertEqual(names, set(module.ALARM_EVENT_TYPES))


    def test_list_alarm_history_severity_min_filters_in_process(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        fake.history_events = [
            {"type": "ET_Alert", "guid": "lo", "severity": 2},
            {"type": "ET_Alert", "guid": "hi", "severity": 6},
            {"type": "ET_AlertState", "guid": "none-sev"},  # missing severity, must be rejected
        ]
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.list_alarm_history(hours=1, limit=50, severity_min=5)
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["guid"], "hi")
        self.assertEqual(r["applied_filters"]["severity_min"], 5)

    def test_list_alarm_history_camera_substitutes_subjects(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        cam = "hosts/Server/DeviceIpint.1/SourceEndpoint.video:0:0"
        r = alarms.list_alarm_history(hours=1, limit=10, camera=cam)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["applied_filters"]["camera"], cam)
        kw = fake.calls[-1][2]
        self.assertEqual(kw["subjects"], (cam,))


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

    def test_alarm_subscribe_filters_by_state_keeps_only_matching_transition(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(state="active", duration_s=5, limit=10)
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["items"][0]["transition"], "raised")

    def test_alarm_subscribe_unknown_state_returns_gap(self) -> None:
        module = importlib.import_module("axxon_mcp_alarms")
        fake = FakeClient()
        alarms = module.AxxonMcpAlarms(
            client_factory=lambda _cfg: fake,
            config_factory=lambda: FakeConfig(),
        )
        r = alarms.alarm_subscribe(state="bogus", duration_s=5, limit=10)
        self.assertEqual(r["status"], "gap")
        self.assertIn("bogus", r["message"])

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


if __name__ == "__main__":
    unittest.main()
